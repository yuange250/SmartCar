#!/usr/bin/env python3
import socket
import json
import keyboard
import time
import sys

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