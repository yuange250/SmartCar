#!/usr/bin/env python3
import RPi.GPIO as GPIO
import socket
import json
import threading
import time
import cv2
import numpy as np
import struct
import io
import base64
from PIL import Image

# 设置GPIO模式为BCM
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# 定义GPIO引脚
IN1 = 9   # 控制端1
IN2 = 25  # 控制端2
IN3 = 11  # 控制端3
IN4 = 8   # 控制端4
ENA = 27  # 电机A使能端（从4改为27）
ENB = 17  # 电机B使能端

# 定义舵机GPIO引脚
SERVO_H = 15  # 水平舵机
SERVO_V = 18  # 垂直舵机

# 设置GPIO为输出模式
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)
GPIO.setup(ENA, GPIO.OUT)
GPIO.setup(ENB, GPIO.OUT)

# 设置舵机GPIO为输出模式
GPIO.setup(SERVO_H, GPIO.OUT)
GPIO.setup(SERVO_V, GPIO.OUT)

# 创建PWM对象
pwm_a = GPIO.PWM(ENA, 100)  # 频率100Hz
pwm_b = GPIO.PWM(ENB, 100)  # 频率100Hz
pwm_h = GPIO.PWM(SERVO_H, 50)
pwm_v = GPIO.PWM(SERVO_V, 50)

# 启动PWM
pwm_a.start(0)
pwm_b.start(0)
pwm_h.start(0)
pwm_v.start(0)

# 全局变量
current_speed = 50
current_h_angle = 90
current_v_angle = 90
camera = None  # 添加全局camera变量
camera_lock = threading.Lock()  # 添加摄像头锁
camera_running = False  # 添加摄像头运行状态标志
camera_thread = None  # 添加摄像头线程变量

def init_camera():
    """初始化摄像头"""
    global camera
    try:
        with camera_lock:  # 使用锁保护摄像头初始化
            if camera is not None:
                camera.release()
            camera = cv2.VideoCapture(0)  # 使用默认摄像头
            if not camera.isOpened():
                print("无法打开摄像头")
                return False
            # 设置分辨率
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            return True
    except Exception as e:
        print(f"初始化摄像头失败: {e}")
        return False

def release_camera():
    """释放摄像头"""
    global camera
    if camera:
        camera.release()
        camera = None

def get_frame():
    """获取一帧图像并压缩"""
    global camera
    if not camera:
        return None
    
    with camera_lock:
        ret, frame = camera.read()
        if not ret:
            return None
        
        # 压缩图像
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        return buffer.tobytes()

def camera_stream_thread(client_socket):
    """摄像头流线程"""
    global camera_running
    try:
        while camera_running:
            frame_data = get_frame()
            if frame_data:
                # 发送帧大小和帧数据
                size = len(frame_data)
                client_socket.send(struct.pack('>L', size))
                client_socket.send(frame_data)
            time.sleep(0.05)  # 约20fps
    except Exception as e:
        print(f"摄像头流错误: {e}")
    finally:
        camera_running = False

def start_camera_stream(client_socket):
    """启动摄像头流"""
    global camera_running, camera_thread
    if not camera_running:
        camera_running = True
        camera_thread = threading.Thread(target=camera_stream_thread, args=(client_socket,))
        camera_thread.daemon = True
        camera_thread.start()

def stop_camera_stream():
    """停止摄像头流"""
    global camera_running
    camera_running = False
    if camera_thread:
        camera_thread.join(timeout=1.0)

def set_speed(speed):
    """设置速度（0-100）"""
    global current_speed
    current_speed = max(0, min(100, speed))
    # 设置PWM占空比
    pwm_a.ChangeDutyCycle(current_speed)
    pwm_b.ChangeDutyCycle(current_speed)
    return f"速度已设置为: {current_speed}%"

def angle_to_duty_cycle(angle):
    """将角度转换为占空比"""
    return 2.5 + (angle / 180.0) * 10.0

def set_servo_h(angle):
    """设置水平舵机角度"""
    global current_h_angle
    current_h_angle = max(0, min(180, angle))
    duty_cycle = angle_to_duty_cycle(current_h_angle)
    pwm_h.ChangeDutyCycle(duty_cycle)
    return f"水平角度已设置为: {current_h_angle}度"

def set_servo_v(angle):
    """设置垂直舵机角度"""
    global current_v_angle
    current_v_angle = max(0, min(180, angle))
    duty_cycle = angle_to_duty_cycle(current_v_angle)
    pwm_v.ChangeDutyCycle(duty_cycle)
    return f"垂直角度已设置为: {current_v_angle}度"

def forward():
    """小车前进"""
    if current_speed > 0:
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
        pwm_a.ChangeDutyCycle(current_speed)
        pwm_b.ChangeDutyCycle(current_speed)
    else:
        stop()
    return "前进"

def backward():
    """小车后退"""
    if current_speed > 0:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.HIGH)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.HIGH)
        pwm_a.ChangeDutyCycle(current_speed)
        pwm_b.ChangeDutyCycle(current_speed)
    else:
        stop()
    return "后退"

def turn_left():
    """小车左转"""
    if current_speed > 0:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.HIGH)
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
        pwm_a.ChangeDutyCycle(current_speed)
        pwm_b.ChangeDutyCycle(current_speed)
    else:
        stop()
    return "左转"

def turn_right():
    """小车右转"""
    if current_speed > 0:
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.HIGH)
        pwm_a.ChangeDutyCycle(current_speed)
        pwm_b.ChangeDutyCycle(current_speed)
    else:
        stop()
    return "右转"

def stop():
    """小车停止"""
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(0)
    pwm_b.ChangeDutyCycle(0)
    return "停止"

def send_frame(client_socket, frame):
    """发送视频帧"""
    try:
        # 调整图像大小以减少数据量
        frame = cv2.resize(frame, (320, 240))
        
        # 压缩图像
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]  # 降低质量以减少数据量
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        frame_data = buffer.tobytes()
        
        # 检查帧大小
        size = len(frame_data)
        if size > 100000:  # 如果帧太大，进一步压缩
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 30]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            frame_data = buffer.tobytes()
            size = len(frame_data)
        
        # 发送帧大小（4字节）
        size_bytes = struct.pack('>L', size)
        client_socket.sendall(size_bytes)
        
        # 发送帧数据
        client_socket.sendall(frame_data)
        
    except Exception as e:
        print(f"发送视频帧错误: {e}")
        return False
    return True

def handle_client(client_socket, addr):
    """处理客户端连接"""
    global current_speed, current_h_angle, current_v_angle, camera, camera_running
    
    print(f"客户端 {addr} 已连接")
    
    try:
        while True:
            # 接收命令
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break
                
            command = json.loads(data)
            action = command.get('action', '')
            value = command.get('value', 50)
            
            response = {'message': '', 'current_speed': current_speed, 
                       'current_h_angle': current_h_angle, 'current_v_angle': current_v_angle}
            
            # 处理命令
            if action == 'forward':
                response['message'] = forward()
            elif action == 'backward':
                response['message'] = backward()
            elif action == 'left':
                response['message'] = turn_left()
            elif action == 'right':
                response['message'] = turn_right()
            elif action == 'stop':
                response['message'] = stop()
            elif action == 'speed':
                current_speed = value
                response['message'] = set_speed(value)
            elif action == 'servo_h':
                current_h_angle = value
                response['message'] = set_servo_h(value)
            elif action == 'servo_v':
                current_v_angle = value
                response['message'] = set_servo_v(value)
            elif action == 'start_camera':
                if init_camera():
                    response['message'] = "摄像头已启动"
                    camera_running = True
                    # 开始发送视频流
                    while camera_running:
                        with camera_lock:  # 使用锁保护摄像头访问
                            if camera is None or not camera.isOpened():
                                print("摄像头未就绪")
                                break
                            ret, frame = camera.read()
                            if not ret:
                                print("无法读取摄像头画面")
                                break
                            if not send_frame(client_socket, frame):
                                break
                        time.sleep(0.05)  # 控制帧率
                else:
                    response['message'] = "摄像头启动失败"
            elif action == 'stop_camera':
                response['message'] = "摄像头已停止"
                camera_running = False
                with camera_lock:  # 使用锁保护摄像头释放
                    if camera is not None:
                        camera.release()
                        camera = None
                break
            elif action == 'ping':
                response['message'] = "pong"
            
            # 发送响应
            client_socket.send(json.dumps(response).encode('utf-8'))
            
    except Exception as e:
        print(f"处理客户端 {addr} 错误: {e}")
    finally:
        camera_running = False
        with camera_lock:  # 使用锁保护摄像头释放
            if camera is not None:
                camera.release()
                camera = None
        client_socket.close()
        print(f"客户端 {addr} 已断开")

def cleanup():
    """清理资源"""
    global camera, camera_running
    
    # 停止摄像头
    camera_running = False
    with camera_lock:
        if camera is not None:
            camera.release()
            camera = None
    
    # 停止小车
    stop()
    
    # 停止PWM
    pwm_a.stop()
    pwm_b.stop()
    
    # 清理GPIO
    GPIO.cleanup()
    
    print("资源已清理")

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