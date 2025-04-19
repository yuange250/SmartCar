from video_monitor import VideoMonitor
from car_control_gui import CarControlGUI
import tkinter as tk
from tkinter import ttk
import json
import os

class SmartCarApp:
    def __init__(self):
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("智能小车控制系统")
        
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
        
        # 存储窗口实例
        self.video_window = None
        self.control_window = None

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
        except Exception as e:
            print(f"加载配置文件失败: {e}")

    def save_config(self):
        """保存配置文件"""
        if self.save_config_var.get():
            config = {
                'host': self.ip_entry.get()
            }
            try:
                with open('config.json', 'w') as f:
                    json.dump(config, f)
            except Exception as e:
                print(f"保存配置文件失败: {e}")

    def create_video_window(self):
        """创建视频监控窗口"""
        video_root = tk.Toplevel(self.root)
        video_root.title("视频监控")
        return VideoMonitor(video_root, host=self.ip_entry.get(), port=5001)

    def create_control_window(self):
        """创建控制面板窗口"""
        control_root = tk.Toplevel(self.root)
        control_root.title("控制面板")
        return CarControlGUI(control_root, host=self.ip_entry.get(), port=5000)

    def start_program(self):
        """启动主程序"""
        # 保存配置
        self.save_config()
        
        # 创建视频监控窗口
        self.video_window = self.create_video_window()
        
        # 创建控制面板窗口
        self.control_window = self.create_control_window()
        
        # 隐藏配置窗口
        self.root.withdraw()
        
        # 设置窗口关闭处理
        self.video_window.root.protocol("WM_DELETE_WINDOW", self.on_video_window_close)
        self.control_window.root.protocol("WM_DELETE_WINDOW", self.on_control_window_close)

    def on_video_window_close(self):
        """处理视频窗口关闭"""
        if self.video_window:
            self.video_window.cleanup()
            self.video_window.root.destroy()
            self.video_window = None
        self.check_windows_status()

    def on_control_window_close(self):
        """处理控制窗口关闭"""
        if self.control_window:
            self.control_window.cleanup()
            self.control_window.root.destroy()
            self.control_window = None
        self.check_windows_status()

    def check_windows_status(self):
        """检查窗口状态"""
        if not self.video_window and not self.control_window:
            # 所有窗口都关闭时，显示配置窗口
            self.root.deiconify()

    def run(self):
        """运行应用程序"""
        self.root.mainloop()

def main():
    app = SmartCarApp()
    app.run()

if __name__ == "__main__":
    main() 