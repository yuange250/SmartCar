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
    def __init__(self, host="192.168.1.100", port=5001):  # 视频使用5001端口
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("智能小车 - 视频监控")
        
        # 设置窗口大小和位置
        window_width = 800
        window_height = 600
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 初始化变量
        self.host = host
        self.port = port
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
        # ... 现有的代码 ...
        
        # 在控制按钮区域添加IP配置
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

    def connect_to_video_stream(self):
        """连接到视频流"""
        try:
            self.host = self.ip_entry.get()
            self.port = int(self.port_entry.get())
            
            # 创建视频接收线程
            self.video_thread = threading.Thread(target=self.receive_video)
            self.video_thread.daemon = True
            self.video_thread.start()
            
            self.logger.info(f"正在连接视频流 {self.host}:{self.port}")
            
        except Exception as e:
            self.logger.error(f"连接视频流失败: {e}")
            self.stop_camera()

    def receive_video(self):
        """接收视频流"""
        try:
            # 创建socket连接
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.connect((self.host, self.port))
            
            # 接收视频数据
            data = b""
            payload_size = struct.calcsize("L")
            
            while self.camera_running:
                try:
                    # 接收帧大小
                    while len(data) < payload_size:
                        data += self.video_socket.recv(4096)
                    
                    packed_size = data[:payload_size]
                    data = data[payload_size:]
                    frame_size = struct.unpack("L", packed_size)[0]
                    
                    # 接收帧数据
                    while len(data) < frame_size:
                        data += self.video_socket.recv(4096)
                    
                    frame_data = data[:frame_size]
                    data = data[frame_size:]
                    
                    # 解码帧
                    frame = pickle.loads(frame_data)
                    
                    # 处理帧
                    self.process_frame(frame)
                    
                except Exception as e:
                    self.logger.error(f"接收视频数据错误: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"视频流连接错误: {e}")
        finally:
            if self.video_socket:
                self.video_socket.close()
            self.camera_running = False
            self.root.after(0, self.update_camera_button)

    def update_camera_button(self):
        """更新摄像头按钮状态"""
        self.camera_button.configure(text="开启摄像头")

    def cleanup(self):
        """清理资源"""
        self.stop_camera()
        if hasattr(self, 'root'):
            self.root.destroy()

    def stop_camera(self):
        """停止摄像头"""
        if self.camera_running:
            self.camera_running = False
            
            # 关闭视频socket
            if self.video_socket:
                try:
                    self.video_socket.close()
                except:
                    pass
                self.video_socket = None
            
            # 等待视频线程结束
            if self.video_thread and self.video_thread.is_alive():
                self.video_thread.join(timeout=1.0)
            
            # 清理资源
            self.cleanup_video()
            self.camera_button.configure(text="开启摄像头")
            self.logger.info("已断开视频流连接")

    def on_closing(self):
        """窗口关闭处理"""
        self.cleanup()