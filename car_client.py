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
import logging
from video_monitor import VideoMonitor
from car_control import CarControl

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

def main():
    # 创建并启动视频监控窗口
    video_monitor = VideoMonitor()
    video_thread = threading.Thread(target=video_monitor.run)
    video_thread.start()
    
    # 创建并启动车辆控制窗口
    car_control = CarControl()
    car_control.run()
    
    # 等待视频监控线程结束
    video_thread.join()

if __name__ == "__main__":
    main() 