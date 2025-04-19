from video_monitor import VideoMonitor
from car_control_gui import CarControlGUI
import threading
import tkinter as tk
from tkinter import ttk
import json
import os

class SmartCarGUI:
    def __init__(self):
        # 创建配置窗口
        self.root = tk.Tk()
        self.root.title("智能小车 - 配置")
        
        # 设置窗口大小和位置
        window_width = 300
        window_height = 150
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 加载配置
        self.load_config()
        
        # 创建配置界面
        self.create_widgets()

    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # IP配置
        ttk.Label(main_frame, text="小车IP地址:").pack(pady=(0, 5))
        self.ip_entry = ttk.Entry(main_frame)
        self.ip_entry.pack(fill=tk.X, pady=(0, 10))
        self.ip_entry.insert(0, self.config.get('host', '192.168.1.100'))
        
        # 启动按钮
        ttk.Button(main_frame, text="启动程序", 
                  command=self.start_program).pack(pady=10)
        
        # 保存配置复选框
        self.save_config_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="记住配置", 
                       variable=self.save_config_var).pack()

    def load_config(self):
        """加载配置文件"""
        self.config = {}
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    self.config = json.load(f)
        except Exception:
            pass

    def save_config(self):
        """保存配置文件"""
        if self.save_config_var.get():
            config = {
                'host': self.ip_entry.get()
            }
            try:
                with open('config.json', 'w') as f:
                    json.dump(config, f)
            except Exception:
                pass

    def start_program(self):
        """启动主程序"""
        # 获取配置
        host = self.ip_entry.get()
        
        # 保存配置
        self.save_config()
        
        # 关闭配置窗口
        self.root.destroy()
        
        # 创建并启动视频监控窗口
        video_monitor = VideoMonitor(host=host, port=5001)  # 视频使用5001端口
        video_thread = threading.Thread(target=video_monitor.run)
        video_thread.daemon = True
        video_thread.start()
        
        # 创建并启动车辆控制窗口
        car_control = CarControlGUI(host=host, port=5000)  # 控制使用5000端口
        car_control.run()

def main():
    app = SmartCarGUI()
    app.root.mainloop()

if __name__ == "__main__":
    main() 