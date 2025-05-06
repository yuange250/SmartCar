import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import time
from queue import Queue
import logging
import os
import socket
import numpy as np
import threading
import struct
import pickle
from ultralytics import YOLO
import torch

class VideoMonitorAI:
    def __init__(self, root, host="192.168.1.100", port=5001):
        self.root = root
        self.host = host
        self.port = port
        
        # 设置窗口大小和位置
        window_width = 800
        window_height = 600
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 初始化其他变量
        self.camera_running = False
        self.frame_queue = Queue(maxsize=2)
        self.processing_frame = False
        self.frame_interval = 1/30
        self.last_frame_time = 0
        self.frame_count = 0
        self.fps = 0
        self.fps_update_interval = 1.0
        self.last_fps_update = time.time()
        self.video_socket = None
        self.video_thread = None
        
        # 初始化YOLO模型
        try:
            self.model = YOLO('yolov8n.pt')
            self.class_names = self.model.model.names
        except Exception as e:
            print(f"YOLO模型初始化失败: {e}")
            self.model = None
            self.class_names = {}
        
        # 创建界面元素
        self.create_widgets()
        
        # 设置日志
        self.setup_logging()
        
        # 设置关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """创建界面元素"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 视频显示区域
        self.video_frame = ttk.Frame(main_frame)
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        
        self.video_label = ttk.Label(self.video_frame, background='black')
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # 控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # IP配置区域
        ip_frame = ttk.Frame(control_frame)
        ip_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(ip_frame, text="IP:").pack(side=tk.LEFT, padx=5)
        self.ip_entry = ttk.Entry(ip_frame)
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.insert(0, self.host)
        
        ttk.Label(ip_frame, text="端口:").pack(side=tk.LEFT, padx=5)
        self.port_entry = ttk.Entry(ip_frame, width=8)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        self.port_entry.insert(0, str(self.port))
        
        # 控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.RIGHT)
        
        self.camera_button = ttk.Button(button_frame, text="开启摄像头", 
                                      command=self.toggle_camera)
        self.camera_button.pack(side=tk.LEFT, padx=5)
        
        self.snapshot_button = ttk.Button(button_frame, text="截图", 
                                        command=self.take_snapshot)
        self.snapshot_button.pack(side=tk.LEFT, padx=5)
        
        # FPS显示
        self.fps_label = ttk.Label(button_frame, text="FPS: 0")
        self.fps_label.pack(side=tk.LEFT, padx=5)
        
        # 日志区域
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, pady=(10, 0))
        
        self.log_text = tk.Text(log_frame, height=5, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, 
                                command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def start_monitor(self, camera_index=0):
        try:
            # 连接到视频流服务器
            self.host = self.ip_entry.get()
            self.port = int(self.port_entry.get())
            
            # 创建socket连接
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.connect((self.host, self.port))
            
            self.camera_running = True
            self.camera_button.configure(text="关闭摄像头")
            
            # 启动视频接收线程
            self.video_thread = threading.Thread(target=self.receive_video)
            self.video_thread.daemon = True
            self.video_thread.start()
            
            self.logger.info(f"已连接到视频流 {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"连接视频流失败: {e}")
            return False
    
    def stop_monitor(self):
        self.camera_running = False
        if self.video_socket is not None:
            try:
                self.video_socket.close()
            except:
                pass
            self.video_socket = None
        
        if self.video_thread is not None and self.video_thread.is_alive():
            self.video_thread.join(timeout=1.0)
        
        self.camera_button.configure(text="开启摄像头")
    
    def receive_video(self):
        """接收视频流"""
        try:
            while self.camera_running:
                try:
                    # 接收帧大小
                    header = self.receive_all(4)
                    if not header:
                        break
                    frame_size = struct.unpack('>L', header)[0]
                    
                    # 接收帧数据
                    frame_data = self.receive_all(frame_size)
                    if not frame_data:
                        break
                    
                    # 解码图像
                    frame = cv2.imdecode(
                        np.frombuffer(frame_data, dtype=np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    
                    if frame is not None:
                        # 保存最后一帧用于截图
                        self.last_frame = frame.copy()
                        
                        # 处理帧
                        processed_frame, detections = self.process_frame(frame)
                        
                        # 更新FPS
                        self.update_fps()
                        
                        # 转换为tkinter图像
                        image = Image.fromarray(processed_frame)
                        photo = ImageTk.PhotoImage(image=image)
                        
                        # 更新显示
                        self.video_label.configure(image=photo)
                        self.video_label.image = photo
                    
                except Exception as e:
                    self.logger.error(f"接收视频数据错误: {e}")
                    break
                
        except Exception as e:
            self.logger.error(f"视频接收线程错误: {e}")
        finally:
            if self.video_socket:
                self.video_socket.close()
            self.camera_running = False
            self.root.after(0, self.update_camera_button)
    
    def receive_all(self, size):
        """接收指定大小的数据"""
        data = bytearray()
        while len(data) < size:
            packet = self.video_socket.recv(size - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data
    
    def update_camera_button(self):
        """更新摄像头按钮状态"""
        self.camera_button.configure(text="开启摄像头")
    
    def toggle_camera(self):
        """切换摄像头状态"""
        if not self.camera_running:
            self.start_monitor()
        else:
            self.stop_monitor()
    
    def take_snapshot(self):
        """截图功能"""
        if self.camera_running:
            try:
                # 创建截图目录
                if not os.path.exists('snapshots'):
                    os.makedirs('snapshots')
                
                # 生成文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"snapshots/snapshot_{timestamp}.jpg"
                
                # 获取当前帧
                if hasattr(self, 'last_frame') and self.last_frame is not None:
                    # 保存图像
                    cv2.imwrite(filename, self.last_frame)
                    self.logger.info(f"截图已保存: {filename}")
            except Exception as e:
                self.logger.error(f"截图失败: {e}")
    
    def on_closing(self):
        """处理窗口关闭"""
        self.stop_monitor()
        self.root.destroy()

    def setup_logging(self):
        """设置日志系统"""
        self.logger = logging.getLogger('VideoMonitorAI')
        self.logger.setLevel(logging.INFO)
        
        # 创建文本处理器
        text_handler = TextHandler(self.log_text)
        text_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(text_handler)

    def process_frame(self, frame):
        """处理视频帧，添加目标检测和跟踪"""
        detections = []
        try:
            if not isinstance(frame, np.ndarray):
                frame = np.array(frame)
            
            # 运行YOLO检测
            if self.model is not None:
                results = self.model(frame, verbose=False)
                print("得到结果：", len(results))
                
                for result in results:
                    # 获取检测框
                    boxes = result.boxes.xyxy.cpu().numpy()
                    confs = result.boxes.conf.cpu().numpy()
                    cls = result.boxes.cls.cpu().numpy()
                    
                    # 处理每个检测结果
                    for box, conf, cl in zip(boxes, confs, cls):
                        x1, y1, x2, y2 = box.astype(int)
                        class_id = int(cl)
                        class_name = self.class_names.get(class_id, f"class_{class_id}")
                        confidence = float(conf)
                        
                        # 添加到检测结果列表
                        detections.append({
                            'class': class_name,
                            'confidence': confidence,
                            'bbox': [x1, y1, x2, y2]
                        })
                        
                        # 只绘制边界框，不显示类别
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 显示FPS
            cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # 转换颜色空间
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
        except Exception as e:
            print(f"处理帧时出错: {e}")
            # 如果出错，返回原始帧
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        return frame, detections
    
    def update_fps(self):
        """更新FPS计数"""
        self.frame_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_fps_update
        
        if elapsed >= self.fps_update_interval:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.last_fps_update = current_time
            # 更新FPS显示
            self.fps_label.config(text=f"FPS: {self.fps:.1f}")

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        def append():
            msg = self.format(record)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
        self.text_widget.after(0, append) 