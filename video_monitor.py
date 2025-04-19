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

class VideoMonitor:
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
        
        # 创建界面元素
        self.create_widgets()
        
        # 设置日志
        self.setup_logging()
        
        # 设置关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def run(self):
        """运行视频监控窗口"""
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"运行错误: {e}")
        finally:
            self.cleanup()

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
        if hasattr(self.video_label, 'image'):
            del self.video_label.image
        self.fps_label.configure(text="FPS: 0")
        
        # 重置计数器
        self.frame_count = 0
        self.last_fps_update = time.time()
        
        # 强制垃圾回收
        import gc
        gc.collect()

    def process_frame(self, frame):
        """处理接收到的视频帧"""
        try:
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            
            self.frame_queue.put_nowait(frame)
            
            if not self.processing_frame:
                self.root.after_idle(self.process_next_frame)
            
        except Exception as e:
            self.logger.error(f"处理视频帧错误: {e}")

    def process_next_frame(self):
        """处理队列中的下一帧"""
        try:
            if self.processing_frame:
                return
            
            current_time = time.time()
            if current_time - self.last_frame_time < self.frame_interval:
                self.root.after(int((self.frame_interval - 
                                   (current_time - self.last_frame_time)) * 1000), 
                              self.process_next_frame)
                return
            
            self.processing_frame = True
            
            try:
                frame = self.frame_queue.get_nowait()
                
                # 转换颜色空间
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 转换为PIL图像
                image = Image.fromarray(frame_rgb)
                
                # 创建PhotoImage
                photo = ImageTk.PhotoImage(image=image)
                
                # 更新显示
                self.update_video_frame(photo)
                
                # 更新FPS计数
                self.frame_count += 1
                if current_time - self.last_fps_update >= self.fps_update_interval:
                    fps = self.frame_count / (current_time - self.last_fps_update)
                    self.fps_label.configure(text=f"FPS: {fps:.1f}")
                    self.frame_count = 0
                    self.last_fps_update = current_time
                
                del frame_rgb
                image.close()
                
            except Exception as e:
                self.logger.error(f"处理帧数据错误: {e}")
            
            self.last_frame_time = current_time
            self.processing_frame = False
            
            if not self.frame_queue.empty():
                self.root.after_idle(self.process_next_frame)
            
        except Exception as e:
            self.logger.error(f"处理视频帧错误: {e}")
            self.processing_frame = False

    def update_video_frame(self, photo):
        """更新视频显示"""
        try:
            old_photo = getattr(self.video_label, 'image', None)
            self.video_label.configure(image=photo)
            self.video_label.image = photo
            if old_photo is not None:
                del old_photo
        except Exception as e:
            self.logger.error(f"更新视频帧失败: {e}")

    def take_snapshot(self):
        """截图功能"""
        if hasattr(self.video_label, 'image'):
            # 创建screenshots目录（如果不存在）
            if not os.path.exists('screenshots'):
                os.makedirs('screenshots')
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join('screenshots', f"snapshot_{timestamp}.png")
            try:
                # 保存当前帧
                if hasattr(self.video_label, 'image'):
                    # 将PhotoImage转换回PIL Image
                    image = ImageTk.getimage(self.video_label.image)
                    image.save(filename)
                    self.logger.info(f"截图已保存: {filename}")
            except Exception as e:
                self.logger.error(f"保存截图失败: {e}")

    def on_closing(self):
        """窗口关闭处理"""
        self.cleanup()

    def setup_logging(self):
        """配置日志系统"""
        # 创建自定义的日志处理器，将日志输出到文本框
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.see(tk.END)
                    # 限制日志显示行数
                    if float(self.text_widget.index('end')) > 1000:  # 超过1000行
                        self.text_widget.delete('1.0', '100.0')  # 删除前100行
                # 在主线程中更新GUI
                self.text_widget.after(0, append)

        try:
            # 创建日志记录器
            self.logger = logging.getLogger('VideoMonitor')
            self.logger.setLevel(logging.INFO)
            
            # 清除可能存在的旧处理器
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
            # 创建文本处理器
            text_handler = TextHandler(self.log_text)
            
            # 设置日志格式
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            text_handler.setFormatter(formatter)
            
            # 添加处理器到日志记录器
            self.logger.addHandler(text_handler)
            
            # 添加文件处理器（可选）
            if not os.path.exists('logs'):
                os.makedirs('logs')
            file_handler = logging.FileHandler(
                os.path.join('logs', 'video_monitor.log'),
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            self.logger.info("日志系统初始化完成")
            
        except Exception as e:
            print(f"设置日志系统时出错: {e}")
            # 创建基本的日志记录器
            self.logger = logging.getLogger('VideoMonitor')
            self.logger.setLevel(logging.INFO)
            self.logger.addHandler(logging.StreamHandler())