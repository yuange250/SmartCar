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
        window_width = 800  # 增加宽度
        window_height = 600  # 增加高度
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
        
        # 添加键盘状态跟踪
        self.pressed_keys = set()
        self.key_command_active = False  # 当前是否有按键命令在执行
        self.current_command = None      # 当前执行的命令
        
        # 添加舵机角度状态
        self.horizontal_angle = 90  # 水平舵机初始角度90度
        self.vertical_angle = 0     # 垂直舵机初始角度0度
        self.angle_step = 5         # 每次调整的角度步长
        
        # 创建界面元素
        self.create_widgets()
        
        # 设置日志
        self.setup_logging()
        
        # 设置键盘事件
        self.setup_keyboard_control()
        
        # 初始化相机位置
        self.init_camera_position()
        
        # 设置关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """创建界面元素"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧控制面板
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 连接控制区域
        connection_frame = ttk.LabelFrame(left_frame, text="连接控制")
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
        
        # 摄像头控制区域 - 移到速度控制之前
        camera_control_frame = ttk.LabelFrame(left_frame, text="摄像头控制")
        camera_control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 水平控制
        h_frame = ttk.Frame(camera_control_frame)
        h_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(h_frame, text="水平角度:").pack(side=tk.LEFT)
        self.h_scale = ttk.Scale(h_frame, from_=0, to=180, orient=tk.HORIZONTAL,
                                command=lambda v: self.on_servo_change('h', v))
        self.h_scale.set(90)
        self.h_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 垂直控制
        v_frame = ttk.Frame(camera_control_frame)
        v_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(v_frame, text="垂直角度:").pack(side=tk.LEFT)
        self.v_scale = ttk.Scale(v_frame, from_=1, to=90, orient=tk.HORIZONTAL,
                                command=lambda v: self.on_servo_change('v', v))
        self.v_scale.set(1)
        self.v_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 添加复位按钮
        ttk.Button(camera_control_frame, text="复位摄像头",
                   command=self.reset_camera).pack(pady=5)
        
        # 速度控制区域
        speed_frame = ttk.LabelFrame(left_frame, text="速度控制")
        speed_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.speed_label = ttk.Label(speed_frame, 
                                   text=f"当前速度: {self.current_speed}%")
        self.speed_label.pack(pady=(5, 0))
        
        self.speed_scale = ttk.Scale(speed_frame, from_=0, to=100, 
                                   orient=tk.HORIZONTAL,
                                   command=self.on_speed_change)
        self.speed_scale.set(self.current_speed)
        self.speed_scale.pack(fill=tk.X, padx=5, pady=5)
        
        # 方向控制区域
        control_frame = ttk.LabelFrame(left_frame, text="方向控制")
        control_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 使用网格布局创建方向控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(expand=True)
        self.create_control_buttons(button_frame)
        
        # 右侧日志区域
        log_frame = ttk.LabelFrame(main_frame, text="运行日志")
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.log_text = tk.Text(log_frame, height=6, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, 
                                command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def create_control_buttons(self, frame):
        """创建方向控制按钮"""
        # 按钮配置：(名称, 文本, 行, 列, 命令, 提示文本)
        button_config = [
            ('up_button', '前进 (W)', 0, 1, self.move_forward, '按住 W 持续前进'),
            ('left_button', '左转 (A)', 1, 0, self.turn_left, '按住 A 持续左转'),
            ('stop_button', '停止 (空格)', 1, 1, self.stop, '按空格停止'),
            ('right_button', '右转 (D)', 1, 2, self.turn_right, '按住 D 持续右转'),
            ('down_button', '后退 (S)', 2, 1, self.move_backward, '按住 S 持续后退')
        ]
        
        # 创建按钮
        for name, text, row, col, command, tooltip in button_config:
            btn = ttk.Button(frame, text=text, command=command, width=15)
            btn.grid(row=row, column=col, padx=10, pady=10)
            
            # 创建工具提示
            self.create_tooltip(btn, tooltip)
            
            setattr(self, name, btn)

    def create_tooltip(self, widget, text):
        """为控件创建悬停提示"""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 20
            
            # 创建提示窗口
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(self.tooltip, text=text, justify=tk.LEFT,
                            background="#ffffe0", relief=tk.SOLID, borderwidth=1)
            label.pack()
            
        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

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
        """设置键盘控制"""
        # 原有的WASD控制
        self.key_commands = {
            'w': ('forward', self.move_forward, self.up_button),
            's': ('backward', self.move_backward, self.down_button),
            'a': ('left', self.turn_left, self.left_button),
            'd': ('right', self.turn_right, self.right_button),
            'space': ('stop', self.stop, self.stop_button)
        }
        
        # 方向键控制相机
        self.camera_keys = {
            'Up': self.camera_up,
            'Down': self.camera_down,
            'Left': self.camera_left,
            'Right': self.camera_right
        }
        
        # 绑定按键事件
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)

    def init_camera_position(self):
        """初始化相机位置"""
        if self.connected:
            self.send_command(f'set_horizontal_servo {self.horizontal_angle}')
            self.send_command(f'set_vertical_servo {self.vertical_angle}')
            self.update_servo_labels()

    def on_key_press(self, event):
        """处理按键按下事件"""
        if not self.connected:
            return
            
        key = event.keysym
        
        # 处理WASD控制
        if key.lower() in self.key_commands:
            if key.lower() not in self.pressed_keys:
                self.pressed_keys.add(key.lower())
                self.execute_key_command(key.lower())
                if self.key_commands[key.lower()][2]:
                    self.key_commands[key.lower()][2].state(['pressed'])
        
        # 处理方向键控制相机
        elif key in self.camera_keys:
            self.camera_keys[key]()

    def camera_up(self):
        """相机向上转"""
        if self.vertical_angle + self.angle_step <= 90:  # 限制最大角度
            self.vertical_angle += self.angle_step
            self.send_command(f'set_vertical_servo {self.vertical_angle}')
            self.update_servo_labels()
            self.logger.info(f"相机向上调整: {self.vertical_angle}度")

    def camera_down(self):
        """相机向下转"""
        if self.vertical_angle - self.angle_step >= -90:  # 限制最小角度
            self.vertical_angle -= self.angle_step
            self.send_command(f'set_vertical_servo {self.vertical_angle}')
            self.update_servo_labels()
            self.logger.info(f"相机向下调整: {self.vertical_angle}度")

    def camera_left(self):
        """相机向左转"""
        if self.horizontal_angle + self.angle_step <= 180:  # 限制最大角度
            self.horizontal_angle += self.angle_step
            self.send_command(f'set_horizontal_servo {self.horizontal_angle}')
            self.update_servo_labels()
            self.logger.info(f"相机向左调整: {self.horizontal_angle}度")

    def camera_right(self):
        """相机向右转"""
        if self.horizontal_angle - self.angle_step >= 0:  # 限制最小角度
            self.horizontal_angle -= self.angle_step
            self.send_command(f'set_horizontal_servo {self.horizontal_angle}')
            self.update_servo_labels()
            self.logger.info(f"相机向右调整: {self.horizontal_angle}度")

    def update_servo_labels(self):
        """更新舵机角度显示"""
        if hasattr(self, 'horizontal_label'):
            self.horizontal_label.config(text=f"水平角度: {self.horizontal_angle}°")
        if hasattr(self, 'vertical_label'):
            self.vertical_label.config(text=f"垂直角度: {self.vertical_angle}°")

    def create_camera_control(self, frame):
        """创建相机控制界面"""
        camera_frame = ttk.LabelFrame(frame, text="相机控制")
        camera_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        # 添加角度显示标签
        self.horizontal_label = ttk.Label(camera_frame, text=f"水平角度: {self.horizontal_angle}°")
        self.horizontal_label.grid(row=0, column=0, padx=5, pady=5)
        
        self.vertical_label = ttk.Label(camera_frame, text=f"垂直角度: {self.vertical_angle}°")
        self.vertical_label.grid(row=1, column=0, padx=5, pady=5)
        
        # 添加控制说明
        control_info = ttk.Label(camera_frame, 
                               text="使用方向键控制相机:\n↑: 向上\n↓: 向下\n←: 向左\n→: 向右",
                               justify=tk.LEFT)
        control_info.grid(row=2, column=0, padx=5, pady=5)

    def on_key_release(self, event):
        """处理按键释放事件"""
        if not self.connected:
            return
            
        key = event.keysym.lower()
        
        # 检查是否是支持的按键
        if key in self.key_commands:
            # 移除按键记录
            self.pressed_keys.discard(key)
            
            # 恢复按钮状态
            if self.key_commands[key][2]:  # 如果有对应的按钮
                self.key_commands[key][2].state(['!pressed'])
            
            # 如果没有其他方向键被按下，则停止
            if not any(k in self.pressed_keys for k in 'wasd'):
                self.stop()
                self.current_command = None
            else:
                # 执行最后一个按下的方向键的命令
                for k in 'wasd':
                    if k in self.pressed_keys:
                        self.execute_key_command(k)
                        break

    def execute_key_command(self, key):
        """执行按键对应的命令"""
        if key in self.key_commands:
            command_name, command_func, _ = self.key_commands[key]
            
            # 如果是新的命令
            if self.current_command != command_name:
                self.current_command = command_name
                command_func()
                self.logger.info(f"执行键盘命令: {command_name}")

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
        """连接到小车"""
        try:
            # 获取IP和端口
            host = self.ip_entry.get()
            port = int(self.port_entry.get())
            
            # 创建socket连接
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # 设置超时时间
            
            self.logger.info(f"正在连接到 {host}:{port}")
            self.socket.connect((host, port))
            
            # 连接成功
            self.connected = True
            self.connect_button.configure(text="断开")
            self.logger.info(f"已连接到 {host}:{port}")
            
            # 启动心跳检测
            self.start_heartbeat()
            
            # 初始化相机位置
            self.init_camera_position()
            
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None
            self.connected = False

    def start_heartbeat(self):
        """启动心跳检测"""
        def heartbeat():
            if self.connected and hasattr(self, 'socket') and self.socket:
                try:
                    # 发送心跳包
                    self.send_command('heartbeat')
                    # 每2秒发送一次心跳
                    self.root.after(2000, heartbeat)
                except:
                    self.disconnect()
        
        # 启动第一次心跳
        self.root.after(2000, heartbeat)

    def send_command(self, command):
        """发送控制命令"""
        if not self.connected or not self.socket:
            self.logger.error("未连接到服务器")
            return
            
        try:
            # 构建命令数据
            data = {
                'command': command,
                'speed': self.current_speed
            }
            
            # 转换为JSON并发送
            json_data = json.dumps(data)
            self.logger.info(f"发送命令: {json_data}")
            
            # 确保发送完整的数据
            self.socket.sendall(json_data.encode('utf-8'))
            
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            self.disconnect()

    def move_forward(self):
        """前进"""
        if self.connected:
            self.logger.info("前进")
            self.send_command('forward')

    def move_backward(self):
        """后退"""
        if self.connected:
            self.logger.info("后退")
            self.send_command('backward')

    def turn_left(self):
        """左转"""
        if self.connected:
            self.logger.info("左转")
            self.send_command('left')

    def turn_right(self):
        """右转"""
        if self.connected:
            self.logger.info("右转")
            self.send_command('right')

    def stop(self):
        """停止"""
        if self.connected:
            self.logger.info("停止")
            self.send_command('stop')

    def disconnect(self):
        """断开连接"""
        if self.connected:
            try:
                # 发送停止命令
                if self.socket:
                    try:
                        self.send_command('stop')
                    except:
                        pass
                
                # 关闭socket
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None
                
                self.connected = False
                self.connect_button.configure(text="连接")
                self.logger.info("已断开连接")
                
            except Exception as e:
                self.logger.error(f"断开连接时出错: {e}")
                self.connected = False
                self.connect_button.configure(text="连接")

    def on_closing(self):
        """窗口关闭处理"""
        try:
            # 清理资源
            self.cleanup()
            
            # 销毁窗口
            if hasattr(self, 'root'):
                self.root.destroy()
                
        except Exception as e:
            print(f"关闭窗口时出错: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            # 停止所有运动
            if self.connected:
                try:
                    self.stop()
                except:
                    pass
            
            # 断开连接
            self.disconnect()
            
            # 停止所有定时任务
            if hasattr(self, 'root'):
                try:
                    # 取消所有after任务
                    for after_id in self.root.tk.eval('after info').split():
                        try:
                            self.root.after_cancel(int(after_id))
                        except:
                            pass
                except:
                    pass
            
            # 清理日志处理器
            if hasattr(self, 'logger'):
                try:
                    # 记录清理操作
                    self.logger.info("正在清理资源...")
                    
                    # 清理所有日志处理器
                    for handler in self.logger.handlers[:]:
                        try:
                            handler.close()
                            self.logger.removeHandler(handler)
                        except:
                            pass
                except:
                    pass
            
            # 关闭socket连接
            if hasattr(self, 'socket') and self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            
            print("资源清理完成")
            
        except Exception as e:
            print(f"清理资源时出错: {e}")

    def on_servo_change(self, servo_type, value):
        """处理舵机角度变化"""
        try:
            angle = int(float(value))
            self.send_servo_command(servo_type, angle)
        except Exception as e:
            self.logger.error(f"设置舵机角度失败: {e}")

    def send_servo_command(self, servo_type, angle):
        """发送舵机控制命令"""
        if not self.connected:
            return
        
        try:
            data = {
                'command': 'servo',
                'type': servo_type,
                'angle': angle
            }
            self.logger.info(f"发送舵机命令: {data}")
            self.send_command_raw(data)
        except Exception as e:
            self.logger.error(f"发送舵机命令失败: {e}")

    def reset_camera(self):
        """复位摄像头位置"""
        try:
            # 设置水平和垂直舵机到90度
            self.h_scale.set(90)
            self.v_scale.set(0)
            self.send_servo_command('h', 90)
            self.send_servo_command('v', 1)
            self.logger.info("摄像头已复位")
        except Exception as e:
            self.logger.error(f"复位摄像头失败: {e}")

    def send_command_raw(self, data):
        """发送原始命令数据"""
        if not self.connected or not self.socket:
            return
            
        try:
            # 转换为JSON并发送
            json_data = json.dumps(data)
            self.socket.sendall(json_data.encode('utf-8'))
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            self.disconnect()

    def run(self):
        self.root.mainloop() 