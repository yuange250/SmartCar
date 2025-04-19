import tkinter as tk
from tkinter import ttk
import logging
import json
import socket
import threading
import time

class CarControlGUI:
    def __init__(self, root, host="192.168.1.100", port=5000):
        # 使用传入的root窗口
        self.root = root
        self.host = host
        self.port = port
        
        # 设置窗口大小和位置
        window_width = 600
        window_height = 400
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 初始化变量
        self.connected = False
        self.current_speed = 50  # 默认速度50%
        self.socket = None
        self.last_command_time = 0
        self.command_interval = 0.1  # 命令发送间隔（秒）
        
        # 创建界面元素
        self.create_widgets()
        
        # 设置日志
        self.setup_logging()
        
        # 设置键盘事件
        self.setup_keyboard_control()
        
        # 设置关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """创建界面元素"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 连接控制区域
        connection_frame = ttk.LabelFrame(main_frame, text="连接控制")
        connection_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(connection_frame, text="IP地址:").pack(side=tk.LEFT, padx=5)
        self.ip_entry = ttk.Entry(connection_frame)
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.insert(0, self.host)
        
        ttk.Label(connection_frame, text="端口:").pack(side=tk.LEFT, padx=5)
        self.port_entry = ttk.Entry(connection_frame, width=8)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        self.port_entry.insert(0, str(self.port))
        
        self.connect_button = ttk.Button(connection_frame, text="连接", 
                                       command=self.toggle_connection)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        # 速度控制区域
        speed_frame = ttk.LabelFrame(main_frame, text="速度控制")
        speed_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 添加速度显示标签
        self.speed_label = ttk.Label(speed_frame, text=f"当前速度: {self.current_speed}%")
        self.speed_label.pack(pady=(5, 0))
        
        # 速度滑块
        self.speed_scale = ttk.Scale(speed_frame, from_=0, to=100, 
                                    orient=tk.HORIZONTAL,
                                    command=self.on_speed_change)
        self.speed_scale.set(self.current_speed)
        self.speed_scale.pack(fill=tk.X, padx=5, pady=5)
        
        # 方向控制区域
        control_frame = ttk.LabelFrame(main_frame, text="方向控制")
        control_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 使用网格布局创建方向控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(expand=True)
        
        # 创建控制按钮
        self.create_control_buttons(button_frame)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="运行日志")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=6, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, 
                                command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def create_control_buttons(self, frame):
        """创建方向控制按钮"""
        # 按钮配置：(名称, 文本, 行, 列, 命令)
        button_config = [
            ('up_button', '前进', 0, 1, self.move_forward),
            ('left_button', '左转', 1, 0, self.turn_left),
            ('stop_button', '停止', 1, 1, self.stop),
            ('right_button', '右转', 1, 2, self.turn_right),
            ('down_button', '后退', 2, 1, self.move_backward)
        ]
        
        # 创建按钮
        for name, text, row, col, command in button_config:
            btn = ttk.Button(frame, text=text, command=command, width=10)
            btn.grid(row=row, column=col, padx=5, pady=5)
            setattr(self, name, btn)

    def setup_logging(self):
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.see(tk.END)
                self.text_widget.after(0, append)

        formatter = logging.Formatter('%(asctime)s - %(message)s', 
                                   datefmt='%H:%M:%S')
        
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(formatter)
        
        self.logger = logging.getLogger('CarControl')
        self.logger.addHandler(text_handler)
        self.logger.setLevel(logging.INFO)

    def setup_keyboard_control(self):
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)

    def on_key_press(self, event):
        if not self.connected:
            return
            
        key = event.keysym.lower()
        if key == 'w':
            self.move_forward()
        elif key == 's':
            self.move_backward()
        elif key == 'a':
            self.turn_left()
        elif key == 'd':
            self.turn_right()
        elif key == 'space':
            self.stop()

    def on_key_release(self, event):
        if not self.connected:
            return
            
        key = event.keysym.lower()
        if key in ['w', 's', 'a', 'd']:
            self.stop()

    def on_speed_change(self, value):
        """处理速度变化"""
        try:
            self.current_speed = int(float(value))
            self.speed_label.configure(text=f"当前速度: {self.current_speed}%")
        except Exception as e:
            self.logger.error(f"更新速度显示失败: {e}")

    def toggle_connection(self):
        if not self.connected:
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        try:
            ip = self.ip_entry.get()
            port = int(self.port_entry.get())
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, port))
            
            self.connected = True
            self.connect_button.configure(text="断开")
            self.logger.info(f"已连接到 {ip}:{port}")
            
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None

    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        self.connect_button.configure(text="连接")
        self.logger.info("已断开连接")

    def send_command(self, command):
        if not self.connected or not self.socket:
            return
        
        current_time = time.time()
        if current_time - self.last_command_time < self.command_interval:
            return
        
        try:
            # 构建命令数据
            data = {
                'command': command,
                'speed': self.current_speed
            }
            
            # 发送命令
            self.socket.send(json.dumps(data).encode())
            self.last_command_time = current_time
            
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            self.disconnect()

    def move_forward(self):
        if self.connected:
            self.send_command('forward')
            self.logger.info("前进")

    def move_backward(self):
        if self.connected:
            self.send_command('backward')
            self.logger.info("后退")

    def turn_left(self):
        if self.connected:
            self.send_command('left')
            self.logger.info("左转")

    def turn_right(self):
        if self.connected:
            self.send_command('right')
            self.logger.info("右转")

    def stop(self):
        if self.connected:
            self.send_command('stop')
            self.logger.info("停止")

    def on_closing(self):
        if self.connected:
            self.disconnect()
        self.root.destroy()

    def run(self):
        self.root.mainloop() 