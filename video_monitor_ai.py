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
        # 使用传入的root窗口
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
        self.fps_update_interval = 1.0
        self.last_fps_update = time.time()
        self.video_socket = None
        self.video_thread = None
        
        # 初始化YOLO模型
        self.model = YOLO('yolov8n.pt')  # 使用轻量级模型
        self.tracking_history = {}  # 用于存储跟踪历史
        self.max_history = 30  # 最大历史记录数
        
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

    def process_frame(self, frame):
        """处理视频帧，添加目标检测和跟踪"""
        if not self.processing_frame:
            self.processing_frame = True
            try:
                # 运行YOLO检测
                results = self.model(frame, verbose=False)
                
                # 获取检测结果
                if len(results) > 0:
                    result = results[0]
                    if hasattr(result, 'boxes') and len(result.boxes) > 0:
                        boxes = result.boxes.xyxy.cpu().numpy()
                        confs = result.boxes.conf.cpu().numpy()
                        cls = result.boxes.cls.cpu().numpy()
                        
                        # 为每个检测到的对象分配ID
                        for i, (box, conf, cl) in enumerate(zip(boxes, confs, cls)):
                            try:
                                # 确保box是有效的坐标
                                if not np.all(np.isfinite(box)):
                                    continue
                                    
                                x1, y1, x2, y2 = box.astype(int)
                                center = ((x1 + x2) // 2, (y1 + y2) // 2)
                                
                                # 使用索引作为临时ID
                                obj_id = i
                                
                                if obj_id not in self.tracking_history:
                                    self.tracking_history[obj_id] = []
                                self.tracking_history[obj_id].append(center)
                                
                                # 保持历史记录在限制范围内
                                if len(self.tracking_history[obj_id]) > self.max_history:
                                    self.tracking_history[obj_id].pop(0)
                                
                                # 绘制边界框和ID
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(frame, f'ID:{obj_id}', (x1, y1 - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                
                                # 绘制跟踪轨迹
                                if len(self.tracking_history[obj_id]) > 1:
                                    points = np.array(self.tracking_history[obj_id], np.int32)
                                    cv2.polylines(frame, [points], False, (0, 255, 255), 2)
                            except Exception as e:
                                self.logger.error(f"处理单个检测框时出错: {e}")
                                continue
                
                # 更新FPS计数
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.last_fps_update >= self.fps_update_interval:
                    fps = self.frame_count / (current_time - self.last_fps_update)
                    self.fps_label.config(text=f"FPS: {fps:.1f}")
                    self.frame_count = 0
                    self.last_fps_update = current_time
                
                # 转换图像格式并显示
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image=image)
                self.video_label.configure(image=photo)
                self.video_label.image = photo
                
            except Exception as e:
                self.logger.error(f"处理帧时出错: {e}")
            finally:
                self.processing_frame = False

    # 保留原有的其他方法...
    def connect_to_video_stream(self):
        """连接到视频流"""
        try:
            self.host = self.ip_entry.get()
            self.port = int(self.port_entry.get())
            
            # 创建socket连接
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.connect((self.host, self.port))
            
            # 启动视频接收线程
            self.video_thread = threading.Thread(target=self.receive_video)
            self.video_thread.daemon = True
            self.video_thread.start()
            
            self.logger.info(f"已连接到视频流 {self.host}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"连接视频流失败: {e}")
            self.stop_camera()

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
                        # 处理帧
                        self.process_frame(frame)
                    
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

    def cleanup(self):
        """清理资源"""
        self.stop_camera()
        if hasattr(self, 'root'):
            self.root.destroy()

    def toggle_camera(self):
        """切换摄像头状态"""
        if not self.camera_running:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        """启动摄像头"""
        if not self.camera_running:
            try:
                self.camera_running = True
                self.camera_button.configure(text="关闭摄像头")
                self.logger.info("正在连接视频流...")
                self.connect_to_video_stream()
            except Exception as e:
                self.logger.error(f"启动摄像头失败: {e}")
                self.stop_camera()

    def stop_camera(self):
        """停止摄像头"""
        if self.camera_running:
            self.camera_running = False
            
            # 关闭视频socket
            if hasattr(self, 'video_socket') and self.video_socket:
                try:
                    self.video_socket.close()
                except:
                    pass
                self.video_socket = None
            
            # 等待视频线程结束
            if hasattr(self, 'video_thread') and self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=1.0)
            
            # 清理资源
            self.cleanup_video()
            self.camera_button.configure(text="开启摄像头")
            self.logger.info("已断开视频流连接")

    def cleanup_video(self):
        """清理视频相关资源"""
        # 清空帧队列
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                pass
        
        # 清理显示
        self.video_label.configure(image='')

    def take_snapshot(self):
        """截图功能"""
        if self.processing_frame:
            try:
                # 获取当前帧
                frame = self.frame_queue.get_nowait()
                if frame is not None:
                    # 创建截图目录
                    if not os.path.exists('snapshots'):
                        os.makedirs('snapshots')
                    
                    # 生成文件名
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"snapshots/snapshot_{timestamp}.jpg"
                    
                    # 保存图像
                    cv2.imwrite(filename, frame)
                    self.logger.info(f"截图已保存: {filename}")
            except Exception as e:
                self.logger.error(f"截图失败: {e}")

    def on_closing(self):
        """处理窗口关闭"""
        self.cleanup()

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