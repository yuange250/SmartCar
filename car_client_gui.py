#!/usr/bin/env python3
import socket
import json
import tkinter as tk
from tkinter import ttk
import threading
import time
import sys

class CarClientGUI:
    def __init__(self, root, host, port):
        self.root = root
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.current_speed = 50
        
        # 设置窗口
        self.root.title("小车远程控制系统")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 连接状态
        self.status_var = tk.StringVar(value="未连接")
        self.status_label = ttk.Label(self.main_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # 连接按钮
        self.connect_button = ttk.Button(self.main_frame, text="连接", command=self.toggle_connection)
        self.connect_button.grid(row=1, column=0, columnspan=3, pady=5)
        
        # 方向控制框架
        self.direction_frame = ttk.LabelFrame(self.main_frame, text="方向控制", padding="10")
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
        self.speed_frame = ttk.LabelFrame(self.main_frame, text="速度控制", padding="10")
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
        
        # 日志框架
        self.log_frame = ttk.LabelFrame(self.main_frame, text="控制日志", padding="10")
        self.log_frame.grid(row=4, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 日志文本框
        self.log_text = tk.Text(self.log_frame, height=10, width=40)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 滚动条
        self.scrollbar = ttk.Scrollbar(self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = self.scrollbar.set
        
        # 键盘控制
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        
        # 设置网格权重
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.columnconfigure(2, weight=1)
        self.direction_frame.columnconfigure(0, weight=1)
        self.direction_frame.columnconfigure(1, weight=1)
        self.direction_frame.columnconfigure(2, weight=1)
        self.speed_frame.columnconfigure(0, weight=1)
        self.speed_frame.columnconfigure(1, weight=1)
        self.speed_frame.columnconfigure(2, weight=1)
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        
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
            
            self.socket.send(json.dumps(command).encode('utf-8'))
            response = self.socket.recv(1024).decode('utf-8')
            response_data = json.loads(response)
            
            if 'current_speed' in response_data:
                self.current_speed = response_data['current_speed']
                self.speed_var.set(self.current_speed)
                self.speed_label['text'] = f"{self.current_speed}%"
            
            self.log(response_data['message'])
            return True
            
        except Exception as e:
            self.log(f"发送命令失败: {e}")
            self.disconnect()
            return False

    def on_speed_change(self, value):
        """速度改变时的回调"""
        speed = int(float(value))
        self.speed_label['text'] = f"{speed}%"
        if self.connected:
            self.send_command('speed', speed)

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
        self.running = False
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