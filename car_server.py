#!/usr/bin/env python3
import RPi.GPIO as GPIO
import socket
import json
import threading
import time

# 设置GPIO模式为BCM
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# 定义GPIO引脚
IN1 = 9  # 控制端1
IN2 = 25  # 控制端2
IN3 = 11  # 控制端3
IN4 = 8  # 控制端4

# 设置GPIO为输出模式
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# 当前速度（0-100）
current_speed = 50

def set_speed(speed):
    """设置速度（0-100）"""
    global current_speed
    current_speed = max(0, min(100, speed))
    return f"速度已设置为: {current_speed}%"

def forward():
    """小车前进"""
    # 使用速度值调整输出
    if current_speed > 0:
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
    else:
        stop()
    return "前进"

def backward():
    """小车后退"""
    # 使用速度值调整输出
    if current_speed > 0:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.HIGH)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.HIGH)
    else:
        stop()
    return "后退"

def turn_left():
    """小车左转"""
    # 使用速度值调整输出
    if current_speed > 0:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.HIGH)
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
    else:
        stop()
    return "左转"

def turn_right():
    """小车右转"""
    # 使用速度值调整输出
    if current_speed > 0:
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.HIGH)
    else:
        stop()
    return "右转"

def stop():
    """小车停止"""
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    return "停止"

def cleanup():
    """清理GPIO设置"""
    GPIO.cleanup()

def handle_client(client_socket, addr):
    """处理客户端连接"""
    print(f"客户端 {addr} 已连接")
    try:
        while True:
            # 接收客户端命令
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break

            # 解析命令
            try:
                command = json.loads(data)
                cmd = command.get('command', '').lower()
                response = ""

                # 处理命令
                if cmd == 'forward':
                    response = forward()
                elif cmd == 'backward':
                    response = backward()
                elif cmd == 'left':
                    response = turn_left()
                elif cmd == 'right':
                    response = turn_right()
                elif cmd == 'stop':
                    response = stop()
                elif cmd == 'speed':
                    speed = command.get('speed', 50)
                    response = set_speed(speed)
                elif cmd == 'ping':
                    response = "pong"
                else:
                    response = "未知命令"

                # 发送响应
                client_socket.send(json.dumps({
                    'status': 'success',
                    'response': response,
                    'speed': current_speed
                }).encode('utf-8'))

            except json.JSONDecodeError:
                client_socket.send(json.dumps({
                    'status': 'error',
                    'response': '无效的命令格式'
                }).encode('utf-8'))

    except Exception as e:
        print(f"处理客户端 {addr} 时发生错误: {e}")
    finally:
        client_socket.close()
        print(f"客户端 {addr} 已断开连接")

def main():
    # 创建服务器套接字
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # 绑定地址和端口
    host = '0.0.0.0'  # 监听所有网络接口
    port = 5000
    server.bind((host, port))
    
    # 开始监听
    server.listen(5)
    print(f"服务器已启动，监听地址: {host}:{port}")

    try:
        while True:
            # 接受客户端连接
            client_socket, addr = server.accept()
            # 为每个客户端创建新线程
            client_thread = threading.Thread(target=handle_client, args=(client_socket, addr))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\n服务器正在关闭...")
    finally:
        cleanup()
        server.close()
        print("服务器已关闭")

if __name__ == "__main__":
    main() 