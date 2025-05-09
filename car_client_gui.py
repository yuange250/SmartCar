#!/usr/bin/env python3
import socket
import json
import tkinter as tk
from tkinter import ttk
import threading
import time
import sys
import struct
import io
from PIL import Image, ImageTk
import cv2
import numpy as np

class CarClientGUI:
    def __init__(self, root, host, port):
        self.root = root
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.current_speed = 50
        self.camera_running = False
        self.camera_thread = None
        self.frame_counter = 0  # 添加帧计数器
        
        # 设置窗口
        self.root.title("小车远程控制系统")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 创建左侧控制面板
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 连接状态
        self.status_var = tk.StringVar(value="未连接")
        self.status_label = ttk.Label(self.control_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # 连接按钮
        self.connect_button = ttk.Button(self.control_frame, text="连接", command=self.toggle_connection)
        self.connect_button.grid(row=1, column=0, columnspan=3, pady=5)
        
        # 方向控制框架
        self.direction_frame = ttk.LabelFrame(self.control_frame, text="方向控制", padding="10")
        self.direction_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # 方向按钮
        self.forward_button = ttk.Button(self.direction_frame, text="↑", command=lambda: self.send_command('forward'))
        self.forward_button.grid(row=0, column=1, padx=5, pady=5)
        
        self.backward_button = ttk.Button(self.direction_frame, text="↓", command=lambda: self.send_command('backward'))
        self.backward_button.grid(row=2, column=1, padx=5, pady=5)
        
        self.left_button = ttk.Button(self.direction_frame, text="←", command=lambda: self.send_command('left'))
        self.left_button.grid(row=1, column=0, padx=5, pady=5)
        
        self.right_button = ttk.Button(self.direction_frame, text="→", command=lambda: self.send_command('right'))
        self.right_button.grid(row=1, column=2, padx=5, pady=5)
        
        self.stop_button = ttk.Button(self.direction_frame, text="停止", command=lambda: self.send_command('stop'))
        self.stop_button.grid(row=1, column=1, padx=5, pady=5)
        
        # 速度控制框架
        self.speed_frame = ttk.LabelFrame(self.control_frame, text="速度控制", padding="10")
        self.speed_frame.grid(row=3, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # 速度滑块
        self.speed_var = tk.IntVar(value=50)
        self.speed_scale = ttk.Scale(self.speed_frame, from_=0, to=100, 
                                   orient=tk.HORIZONTAL, variable=self.speed_var,
                                   command=self.on_speed_change)
        self.speed_scale.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=5)
        
        # 速度显示
        self.speed_label = ttk.Label(self.speed_frame, text="50%")
        self.speed_label.grid(row=1, column=0, columnspan=3, pady=5)
        
        # 舵机控制框架
        self.servo_frame = ttk.LabelFrame(self.control_frame, text="摄像头控制", padding="10")
        self.servo_frame.grid(row=4, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # 水平舵机控制
        ttk.Label(self.servo_frame, text="左右旋转:").grid(row=0, column=0, padx=5)
        self.servo_h_var = tk.IntVar(value=90)
        self.servo_h_scale = ttk.Scale(self.servo_frame, from_=0, to=180, 
                                      orient=tk.HORIZONTAL, variable=self.servo_h_var,
                                      command=self.on_servo_h_change)
        self.servo_h_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.servo_h_label = ttk.Label(self.servo_frame, text="90°")
        self.servo_h_label.grid(row=0, column=2, padx=5)
        
        # 垂直舵机控制
        ttk.Label(self.servo_frame, text="上下抬头:").grid(row=1, column=0, padx=5)
        self.servo_v_var = tk.IntVar(value=90)
        self.servo_v_scale = ttk.Scale(self.servo_frame, from_=0, to=180, 
                                      orient=tk.HORIZONTAL, variable=self.servo_v_var,
                                      command=self.on_servo_v_change)
        self.servo_v_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.servo_v_label = ttk.Label(self.servo_frame, text="90°")
        self.servo_v_label.grid(row=1, column=2, padx=5)
        
        # 摄像头控制按钮
        self.camera_button = ttk.Button(self.servo_frame, text="开启摄像头", command=self.toggle_camera)
        self.camera_button.grid(row=2, column=0, columnspan=3, pady=5)
        
        # 日志框架
        self.log_frame = ttk.LabelFrame(self.control_frame, text="控制日志", padding="10")
        self.log_frame.grid(row=5, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 日志文本框
        self.log_text = tk.Text(self.log_frame, height=10, width=40)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 滚动条
        self.scrollbar = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = self.scrollbar.set
        
        # 创建右侧视频显示面板
        self.video_frame = ttk.LabelFrame(self.main_frame, text="摄像头画面", padding="10")
        self.video_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 视频显示标签
        self.video_label = ttk.Label(self.video_frame)
        self.video_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 键盘控制
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        
        # 设置网格权重
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.rowconfigure(0, weight=1)
        self.control_frame.columnconfigure(0, weight=1)
        self.control_frame.columnconfigure(1, weight=1)
        self.control_frame.columnconfigure(2, weight=1)
        self.direction_frame.columnconfigure(0, weight=1)
        self.direction_frame.columnconfigure(1, weight=1)
        self.direction_frame.columnconfigure(2, weight=1)
        self.speed_frame.columnconfigure(0, weight=1)
        self.speed_frame.columnconfigure(1, weight=1)
        self.speed_frame.columnconfigure(2, weight=1)
        self.servo_frame.columnconfigure(0, weight=1)
        self.servo_frame.columnconfigure(1, weight=1)
        self.servo_frame.columnconfigure(2, weight=1)
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        self.video_frame.columnconfigure(0, weight=1)
        self.video_frame.rowconfigure(0, weight=1)
        
        # 禁用所有控制
        self.set_controls_state(False)
        
        # 启动状态更新线程
        self.running = True
        self.status_thread = threading.Thread(target=self.update_status)
        self.status_thread.daemon = True
        self.status_thread.start()

    def set_controls_state(self, state):
        """设置控制按钮状态"""
        self.forward_button['state'] = 'normal' if state else 'disabled'
        self.backward_button['state'] = 'normal' if state else 'disabled'
        self.left_button['state'] = 'normal' if state else 'disabled'
        self.right_button['state'] = 'normal' if state else 'disabled'
        self.stop_button['state'] = 'normal' if state else 'disabled'
        self.speed_scale['state'] = 'normal' if state else 'disabled'
        self.servo_h_scale['state'] = 'normal' if state else 'disabled'
        self.servo_v_scale['state'] = 'normal' if state else 'disabled'
        self.camera_button['state'] = 'normal' if state else 'disabled'

    def toggle_connection(self):
        """切换连接状态"""
        if not self.connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        """连接到服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.status_var.set(f"已连接到 {self.host}:{self.port}")
            self.connect_button['text'] = "断开"
            self.set_controls_state(True)
            self.log("已连接到服务器")
        except Exception as e:
            self.status_var.set("连接失败")
            self.log(f"连接失败: {e}")

    def disconnect(self):
        """断开连接"""
        self.stop_camera()
        if self.socket:
            self.socket.close()
        self.connected = False
        self.status_var.set("未连接")
        self.connect_button['text'] = "连接"
        self.set_controls_state(False)
        self.log("已断开连接")

    def send_command(self, action, value=None):
        """发送命令到服务器"""
        if not self.connected:
            self.log("未连接到服务器")
            return False

        try:
            command = {'action': action}
            if value is not None:
                command['value'] = value
            
            # 发送命令
            self.socket.send(json.dumps(command).encode('utf-8'))
            
            # 接收响应
            try:
                response = self.socket.recv(1024)
                if not response:
                    self.log("服务器断开连接")
                    self.disconnect()
                    return False
                
                # 尝试解码响应
                try:
                    response_text = response.decode('utf-8')
                    self.log(f"收到响应: {response_text}")  # 添加调试日志
                    response_data = json.loads(response_text)
                except UnicodeDecodeError as e:
                    self.log(f"接收到的数据不是有效的UTF-8编码: {e}")
                    self.log(f"原始数据: {response}")
                    return False
                except json.JSONDecodeError as e:
                    self.log(f"接收到的数据不是有效的JSON格式: {e}")
                    self.log(f"原始数据: {response_text}")
                    return False
                
                # 处理响应
                if 'current_speed' in response_data:
                    self.current_speed = response_data['current_speed']
                    self.speed_var.set(self.current_speed)
                    self.speed_label['text'] = f"{self.current_speed}%"
                
                if 'message' in response_data:
                    self.log(response_data['message'])
                return True
                
            except socket.error as e:
                self.log(f"接收响应错误: {e}")
                self.disconnect()
                return False
            
        except Exception as e:
            self.log(f"发送命令失败: {e}")
            self.disconnect()
            return False

    def on_speed_change(self, value):
        """速度改变时的回调"""
        try:
            speed = int(float(value))
            # 确保速度在有效范围内
            speed = max(0, min(100, speed))
            
            # 更新UI
            self.speed_label['text'] = f"{speed}%"
            
            # 只有在连接状态且速度真正改变时才发送命令
            if self.connected and speed != self.current_speed:
                self.current_speed = speed
                self.send_command('speed', speed)
                self.log(f"设置速度: {speed}%")
        except Exception as e:
            self.log(f"设置速度失败: {e}")
            # 恢复之前的速度值
            self.speed_var.set(self.current_speed)
            self.speed_label['text'] = f"{self.current_speed}%"

    def on_key_press(self, event):
        """键盘按下事件"""
        if not self.connected:
            return
            
        key = event.keysym.lower()
        if key == 'w':
            self.send_command('forward')
        elif key == 's':
            self.send_command('backward')
        elif key == 'a':
            self.send_command('left')
        elif key == 'd':
            self.send_command('right')
        elif key == 'q':
            self.send_command('stop')

    def on_key_release(self, event):
        """键盘释放事件"""
        if not self.connected:
            return
            
        key = event.keysym.lower()
        if key in ['w', 's', 'a', 'd']:
            self.send_command('stop')

    def on_servo_h_change(self, value):
        """水平舵机角度改变时的回调"""
        angle = int(float(value))
        self.servo_h_label['text'] = f"{angle}°"
        if self.connected:
            self.send_command('servo_h', angle)

    def on_servo_v_change(self, value):
        """垂直舵机角度改变时的回调"""
        angle = int(float(value))
        self.servo_v_label['text'] = f"{angle}°"
        if self.connected:
            self.send_command('servo_v', angle)

    def toggle_camera(self):
        """切换摄像头状态"""
        if not self.camera_running:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        """启动摄像头"""
        if self.connected and not self.camera_running:
            try:
                self.send_command('start_camera')
                self.camera_running = True
                self.camera_button['text'] = "关闭摄像头"
                self.camera_thread = threading.Thread(target=self.receive_video)
                self.camera_thread.daemon = True
                self.camera_thread.start()
                self.log("摄像头已启动")
            except Exception as e:
                self.log(f"启动摄像头失败: {e}")
                self.camera_running = False
                self.camera_button['text'] = "开启摄像头"

    def stop_camera(self):
        """停止摄像头"""
        if self.connected and self.camera_running:
            try:
                self.send_command('stop_camera')
                self.camera_running = False
                self.camera_button['text'] = "开启摄像头"
                if self.camera_thread:
                    self.camera_thread.join(timeout=1.0)
                self.video_label.configure(image='')
                self.log("摄像头已停止")
            except Exception as e:
                self.log(f"停止摄像头失败: {e}")

    def receive_video(self):
        """接收视频流"""
        while self.camera_running:
            self.log(f"接受到图像")
            try:
                if not self.connected or self.socket is None:
                    print("连接已断开")
                    continue
                    
                # 设置接收超时
                self.socket.settimeout(1.0)
                
                # 接收帧大小
                try:
                    size_data = b''
                    while len(size_data) < 4:
                        chunk = self.socket.recv(4 - len(size_data))
                        if not chunk:
                            print("连接已断开")
                            continue
                        size_data += chunk
                    
                    if len(size_data) != 4:
                        print("接收帧大小数据不完整")
                        continue
                        
                    size = struct.unpack('>L', size_data)[0]
                    if size > 1e8:  # 限制最大帧大小为1e8字节
                        print(f"帧大小异常: {size}")
                        continue
                    
                except socket.error as e:
                    print(f"接收数据错误: {e}")
                    continue
                
                # 接收帧数据
                frame_data = b''
                remaining = size
                while remaining > 0:
                    try:
                        packet = self.socket.recv(min(remaining, 8192))
                        if not packet:
                            print("连接已断开")
                            break
                        frame_data += packet
                        remaining -= len(packet)
                    except socket.error as e:
                        print(f"接收数据错误: {e}")
                        continue
                
                if len(frame_data) == size:
                    # 解码图像
                    frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is None:
                        print("图像解码失败")
                        continue
                        
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 增加帧计数
                    self.frame_counter += 1
                    
                    # 每15帧打印一次日志
                    if self.frame_counter % 15 == 0:
                        self.log(f"已接收 {self.frame_counter} 帧视频")
                    
                    # 调整大小以适应显示
                    height, width = frame.shape[:2]
                    max_size = 400
                    if width > height:
                        new_width = max_size
                        new_height = int(height * (max_size / width))
                    else:
                        new_height = max_size
                        new_width = int(width * (max_size / height))
                    
                    frame = cv2.resize(frame, (new_width, new_height))
                    
                    # 转换为PhotoImage
                    image = Image.fromarray(frame)
                    photo = ImageTk.PhotoImage(image=image)
                                        
                    # 使用after方法在主线程中更新UI
                    self.root.after(0, lambda p=photo: self.update_video_frame(p))
                    
                    # 添加短暂延迟，与服务器端帧率同步
                    time.sleep(0.05)
                else:
                    self.log(f"解析图像失败，已接收 {self.frame_counter} 帧视频")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收视频错误: {e}")
                continue
        self.log(f"跳出不接受了")

        self.camera_running = False
        self.frame_counter = 0  # 重置帧计数器
        self.root.after(0, lambda: self.camera_button.configure(text="开启摄像头"))
        self.root.after(0, lambda: self.log("视频流已停止"))

    def update_video_frame(self, photo):
        """在主线程中更新视频帧"""
        if self.camera_running:
            self.video_label.configure(image=photo)
            self.video_label.image = photo  # 保持引用
            self.log(f"完成显示")

    def log(self, message):
        """添加日志"""
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)

    def update_status(self):
        """更新状态线程"""
        while self.running:
            if self.connected:
                try:
                    # 发送心跳包
                    self.socket.send(json.dumps({'action': 'ping'}).encode('utf-8'))
                    self.socket.recv(1024)
                except:
                    self.root.after(0, self.disconnect)
            time.sleep(1)

    def on_closing(self):
        """窗口关闭时的处理"""
        self.camera_running = False
        if self.camera_thread:
            self.camera_thread.join(timeout=1.0)
        if self.connected:
            self.disconnect()
        self.root.destroy()

def main():
    if len(sys.argv) != 2:
        print("使用方法: python car_client_gui.py <服务器IP>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    
    root = tk.Tk()
    app = CarClientGUI(root, server_ip, 5000)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main() 