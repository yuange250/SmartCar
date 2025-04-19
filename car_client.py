#!/usr/bin/env python3
import socket
import json
import keyboard
import time
import sys
import tkinter as tk
from tkinter import ttk
import struct
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
import tkinter.messagebox as messagebox

class CarClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.current_speed = 50

    def connect(self):
        """连接到服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"已连接到服务器 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def send_command(self, command):
        """发送命令到服务器"""
        if not self.connected:
            print("未连接到服务器")
            return False

        try:
            # 发送命令
            self.socket.send(json.dumps(command).encode('utf-8'))
            
            # 接收响应
            response = self.socket.recv(1024).decode('utf-8')
            response_data = json.loads(response)
            
            # 更新当前速度
            if 'current_speed' in response_data:
                self.current_speed = response_data['current_speed']
            
            # 打印响应消息
            print(response_data['message'])
            return True
            
        except Exception as e:
            print(f"发送命令失败: {e}")
            self.connected = False
            return False

    def close(self):
        """关闭连接"""
        if self.socket:
            self.socket.close()
        self.connected = False

class CarControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("智能小车控制系统")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # 设置样式
        self.style = ttk.Style()
        self.style.configure('TButton', padding=5, font=('Arial', 10))
        self.style.configure('TLabel', font=('Arial', 10))
        self.style.configure('TFrame', background='#f0f0f0')
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 创建左右分栏
        self.left_frame = ttk.Frame(self.main_frame)
        self.right_frame = ttk.Frame(self.main_frame)
        self.left_frame.grid(row=0, column=0, padx=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.right_frame.grid(row=0, column=1, padx=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 视频显示区域
        self.video_frame = ttk.LabelFrame(self.left_frame, text="视频预览", padding="5")
        self.video_frame.grid(row=0, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.video_label = ttk.Label(self.video_frame)
        self.video_label.grid(row=0, column=0, padx=5, pady=5)
        
        # 日志显示区域
        self.log_frame = ttk.LabelFrame(self.left_frame, text="运行日志", padding="5")
        self.log_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 创建日志文本框和滚动条
        self.log_text = tk.Text(self.log_frame, height=10, width=50, wrap=tk.WORD)
        self.log_scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scrollbar.set)
        
        # 放置日志文本框和滚动条
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 配置日志文本框只读
        self.log_text.configure(state='disabled')
        
        # 连接控制区域
        self.connection_frame = ttk.LabelFrame(self.left_frame, text="连接控制", padding="5")
        self.connection_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        # IP地址输入
        ttk.Label(self.connection_frame, text="IP地址:").grid(row=0, column=0, padx=5, pady=5)
        self.ip_entry = ttk.Entry(self.connection_frame, width=15)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)
        self.ip_entry.insert(0, "192.168.1.100")
        
        # 连接按钮
        self.connect_button = ttk.Button(self.connection_frame, text="连接", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)
        
        # 状态标签
        self.status_label = ttk.Label(self.connection_frame, text="未连接", foreground="red")
        self.status_label.grid(row=0, column=3, padx=5, pady=5)
        
        # 运动控制区域
        self.movement_frame = ttk.LabelFrame(self.right_frame, text="运动控制", padding="5")
        self.movement_frame.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 速度控制
        self.speed_frame = ttk.Frame(self.movement_frame)
        self.speed_frame.grid(row=0, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        ttk.Label(self.speed_frame, text="速度:").grid(row=0, column=0, padx=5)
        self.speed_scale = ttk.Scale(self.speed_frame, from_=0, to=100, orient=tk.HORIZONTAL, length=200)
        self.speed_scale.grid(row=0, column=1, padx=5)
        self.speed_scale.set(50)
        self.speed_label = ttk.Label(self.speed_frame, text="50%")
        self.speed_label.grid(row=0, column=2, padx=5)
        self.speed_scale.bind("<Motion>", self.update_speed_label)
        self.speed_scale.bind("<ButtonRelease-1>", self.on_speed_change)
        
        # 方向控制按钮
        button_frame = ttk.Frame(self.movement_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.forward_button = ttk.Button(button_frame, text="↑", width=5, command=self.forward)
        self.forward_button.grid(row=0, column=1, padx=5, pady=5)
        
        self.left_button = ttk.Button(button_frame, text="←", width=5, command=self.turn_left)
        self.left_button.grid(row=1, column=0, padx=5, pady=5)
        
        self.stop_button = ttk.Button(button_frame, text="■", width=5, command=self.stop)
        self.stop_button.grid(row=1, column=1, padx=5, pady=5)
        
        self.right_button = ttk.Button(button_frame, text="→", width=5, command=self.turn_right)
        self.right_button.grid(row=1, column=2, padx=5, pady=5)
        
        self.backward_button = ttk.Button(button_frame, text="↓", width=5, command=self.backward)
        self.backward_button.grid(row=2, column=1, padx=5, pady=5)
        
        # 舵机控制区域
        self.servo_frame = ttk.LabelFrame(self.right_frame, text="舵机控制", padding="5")
        self.servo_frame.grid(row=1, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # 水平舵机控制
        h_frame = ttk.Frame(self.servo_frame)
        h_frame.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E))
        ttk.Label(h_frame, text="水平:").grid(row=0, column=0, padx=5)
        self.h_scale = ttk.Scale(h_frame, from_=0, to=180, orient=tk.HORIZONTAL, length=200)
        self.h_scale.grid(row=0, column=1, padx=5)
        self.h_scale.set(90)
        self.h_label = ttk.Label(h_frame, text="90°")
        self.h_label.grid(row=0, column=2, padx=5)
        self.h_scale.bind("<Motion>", self.update_h_label)
        self.h_scale.bind("<ButtonRelease-1>", self.on_h_change)
        
        # 垂直舵机控制
        v_frame = ttk.Frame(self.servo_frame)
        v_frame.grid(row=1, column=0, pady=5, sticky=(tk.W, tk.E))
        ttk.Label(v_frame, text="垂直:").grid(row=0, column=0, padx=5)
        self.v_scale = ttk.Scale(v_frame, from_=0, to=180, orient=tk.HORIZONTAL, length=200)
        self.v_scale.grid(row=0, column=1, padx=5)
        self.v_scale.set(90)
        self.v_label = ttk.Label(v_frame, text="90°")
        self.v_label.grid(row=0, column=2, padx=5)
        self.v_scale.bind("<Motion>", self.update_v_label)
        self.v_scale.bind("<ButtonRelease-1>", self.on_v_change)
        
        # 摄像头控制区域
        self.camera_frame = ttk.LabelFrame(self.right_frame, text="摄像头控制", padding="5")
        self.camera_frame.grid(row=2, column=0, pady=5, sticky=(tk.W, tk.E))
        
        self.start_camera_button = ttk.Button(self.camera_frame, text="开启摄像头", command=self.start_camera)
        self.start_camera_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.stop_camera_button = ttk.Button(self.camera_frame, text="关闭摄像头", command=self.stop_camera)
        self.stop_camera_button.grid(row=0, column=1, padx=5, pady=5)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.left_frame.columnconfigure(0, weight=1)
        self.left_frame.rowconfigure(0, weight=3)  # 视频区域占更多空间
        self.left_frame.rowconfigure(1, weight=1)  # 日志区域
        self.right_frame.columnconfigure(0, weight=1)
        
        # 初始化变量
        self.client_socket = None
        self.is_connected = False
        self.video_thread = None
        self.video_running = False
        self.frame_counter = 0  # 添加帧计数器
        
        # 绑定键盘事件
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        
        # 设置定时器，每秒发送一次ping
        self.root.after(1000, self.send_ping)

    def log_message(self, message):
        """添加日志消息"""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)  # 滚动到最新消息
        self.log_text.configure(state='disabled')

    def receive_video_stream(self):
        """接收视频流"""
        try:
            while self.video_running:
                try:
                    # 设置接收超时
                    self.client_socket.settimeout(1.0)
                    
                    # 接收帧大小（4字节）
                    size_data = self.client_socket.recv(4)
                    if not size_data:
                        self.log_message("连接已断开")
                        break
                    
                    # 解析帧大小
                    size = struct.unpack('>L', size_data)[0]
                    
                    # 检查帧大小是否合理
                    if size <= 0 or size > 1000000:  # 设置最大帧大小为1MB
                        self.log_message(f"收到无效的帧大小: {size}")
                        continue
                    
                    # 接收帧数据
                    frame_data = b''
                    remaining = size
                    while remaining > 0:
                        chunk = self.client_socket.recv(min(remaining, 8192))
                        if not chunk:
                            self.log_message("连接已断开")
                            break
                        frame_data += chunk
                        remaining -= len(chunk)
                    
                    if len(frame_data) != size:
                        self.log_message(f"帧数据大小不匹配: 预期 {size}, 实际 {len(frame_data)}")
                        continue
                    
                    # 解码图像
                    try:
                        frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is None:
                            self.log_message("无法解码图像")
                            continue
                        
                        # 增加帧计数
                        self.frame_counter += 1
                        
                        # 每15帧打印一次日志
                        if self.frame_counter % 15 == 0:
                            self.log_message(f"已接收 {self.frame_counter} 帧视频")
                        
                        # 调整图像大小以适应显示区域
                        frame = cv2.resize(frame, (640, 480))
                        
                        # 转换为PIL图像
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame = Image.fromarray(frame)
                        
                        # 转换为PhotoImage并显示
                        photo = ImageTk.PhotoImage(image=frame)
                        self.video_label.configure(image=photo)
                        self.video_label.image = photo
                        
                        # 清理内存
                        del frame
                        del photo
                        
                    except Exception as e:
                        self.log_message(f"处理图像时出错: {e}")
                        continue
                    
                except socket.timeout:
                    # 超时不是错误，继续尝试
                    continue
                except struct.error as e:
                    self.log_message(f"解析帧大小时出错: {e}")
                    continue
                except Exception as e:
                    self.log_message(f"接收视频流时出错: {e}")
                    continue
                
        except Exception as e:
            self.log_message(f"视频流线程错误: {e}")
        finally:
            self.video_running = False
            self.frame_counter = 0  # 重置帧计数器
            self.log_message("视频流已停止")
            # 清理资源
            try:
                self.video_label.configure(image='')
            except:
                pass

    def start_camera(self):
        """开启摄像头"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先连接到服务器")
            return
        
        try:
            # 确保之前的视频流已停止
            self.stop_camera()
            
            # 发送开启摄像头命令
            response = self.client.send_command({'action': 'start_camera'})
            if response and response.get('message') == "摄像头已启动":
                self.video_running = True
                self.video_thread = threading.Thread(target=self.receive_video_stream)
                self.video_thread.daemon = True
                self.video_thread.start()
                self.start_camera_button.state(['disabled'])
                self.stop_camera_button.state(['!disabled'])
            else:
                messagebox.showerror("错误", "无法启动摄像头")
        except Exception as e:
            messagebox.showerror("错误", f"启动摄像头失败: {e}")

    def stop_camera(self):
        """关闭摄像头"""
        if not self.is_connected:
            return
        
        try:
            # 停止视频流
            self.video_running = False
            if self.video_thread:
                self.video_thread.join(timeout=1.0)
                self.video_thread = None
            
            # 发送关闭摄像头命令
            response = self.client.send_command({'action': 'stop_camera'})
            if response and response.get('message') == "摄像头已停止":
                self.start_camera_button.state(['!disabled'])
                self.stop_camera_button.state(['disabled'])
                # 清除视频显示
                self.video_label.configure(image='')
            else:
                messagebox.showerror("错误", "无法关闭摄像头")
        except Exception as e:
            messagebox.showerror("错误", f"关闭摄像头失败: {e}")
        finally:
            # 确保资源被清理
            self.video_running = False
            self.video_thread = None

def main():
    # 获取服务器IP地址
    if len(sys.argv) != 2:
        print("使用方法: python car_client.py <服务器IP>")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    client = CarClient(server_ip, 5000)
    
    if not client.connect():
        sys.exit(1)

    print("\n远程控制小车")
    print("控制命令:")
    print("w - 前进")
    print("s - 后退")
    print("a - 左转")
    print("d - 右转")
    print("q - 停止")
    print("1-9 - 设置速度（1最慢，9最快）")
    print("esc - 退出程序")
    print("\n当前速度:", client.current_speed, "%")

    try:
        while True:
            # 检查速度控制
            for i in range(1, 10):
                if keyboard.is_pressed(str(i)):
                    speed = int(i) * 11  # 将1-9转换为11-99
                    client.send_command({
                        'action': 'speed',
                        'value': speed
                    })
                    time.sleep(0.2)  # 防止重复触发

            # 检查方向控制
            if keyboard.is_pressed('w'):
                client.send_command({'action': 'forward'})
            elif keyboard.is_pressed('s'):
                client.send_command({'action': 'backward'})
            elif keyboard.is_pressed('a'):
                client.send_command({'action': 'left'})
            elif keyboard.is_pressed('d'):
                client.send_command({'action': 'right'})
            elif keyboard.is_pressed('q'):
                client.send_command({'action': 'stop'})
            elif keyboard.is_pressed('esc'):
                break

            time.sleep(0.1)  # 短暂延时，防止CPU占用过高

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        client.close()
        print("程序已退出")

if __name__ == "__main__":
    main() 