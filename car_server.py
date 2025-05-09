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
import pickle

# 设置GPIO模式为BCM
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# 定义GPIO引脚
IN1 = 9   # 控制端1
IN2 = 25  # 控制端2
IN3 = 11  # 控制端3
IN4 = 8   # 控制端4
ENA = 6  # 电机A使能端
ENB = 16  # 电机B使能端

# 定义舵机GPIO引脚
SERVO_H = 15  # 水平舵机
SERVO_V = 18  # 垂直舵机

# 全局变量
current_speed = 50
current_h_angle = 90
current_v_angle = 90
camera = None  # 添加全局camera变量
camera_lock = threading.Lock()  # 添加摄像头锁
camera_running = False  # 添加摄像头运行状态标志
camera_thread = None  # 添加摄像头线程变量

class CarServer:
    def __init__(self, control_port=5000, video_port=5001):
        # 舵机相关引脚和参数
        self.PIN_SERVO_HORIZONTAL = SERVO_H  # 水平舵机
        self.PIN_SERVO_VERTICAL = SERVO_V    # 垂直舵机
        self.servo_h_angle = 90         # 水平舵机初始角度
        self.servo_v_angle = 0         # 垂直舵机初始角度

        # 服务器配置
        self.control_port = control_port
        self.video_port = video_port
        self.control_socket = None
        self.video_socket = None
        self.clients = []
        self.video_clients = []
        self.running = False
        
        # 创建事件循环线程
        self.event_thread = None
        
        # 视频流配置
        self.frame_interval = 1/30  # 30 FPS
        self.video_running = False
        self.video_thread = None
        # 初始化GPIO和电机控制
        self.setup_gpio()

        # 初始化相机
        self.setup_camera()

    def setup_camera(self):
        """初始化相机"""
        try:
            self.camera = cv2.VideoCapture(0)  # 使用默认摄像头
            # 设置分辨率
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # 设置帧率
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            if not self.camera.isOpened():
                raise Exception("无法打开摄像头")
                
            print("相机初始化成功")
        except Exception as e:
            print(f"相机初始化失败: {e}")
            self.camera = None

    def start(self):
        """启动服务器"""
        try:
            # 启动控制服务器
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.control_socket.bind(('0.0.0.0', self.control_port))
            self.control_socket.listen(5)
            print(f"控制服务器启动在端口 {self.control_port}")
            
            # 启动视频服务器
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.video_socket.bind(('0.0.0.0', self.video_port))
            self.video_socket.listen(5)
            print(f"视频服务器启动在端口 {self.video_port}")
            
            self.running = True
            
            # 启动事件循环
            self.event_thread = threading.Thread(target=self.event_loop)
            self.event_thread.daemon = True
            self.event_thread.start()
            
            # 启动视频流线程
            self.video_running = True
            self.video_thread = threading.Thread(target=self.video_stream_loop)
            self.video_thread.daemon = True
            self.video_thread.start()
            
            # 接受控制连接
            self.accept_control_connections()
            
        except Exception as e:
            print(f"启动服务器失败: {e}")
            self.stop()

    def accept_control_connections(self):
        """接受控制连接"""
        while self.running:
            try:
                client_socket, address = self.control_socket.accept()
                print(f"新的控制连接来自 {address}")
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                self.clients.append(client_socket)
            except Exception as e:
                if self.running:
                    print(f"接受控制连接时出错: {e}")

    def accept_video_connections(self):
        """接受视频连接"""
        while self.running:
            try:
                client_socket, address = self.video_socket.accept()
                print(f"新的视频连接来自 {address}")
                self.video_clients.append(client_socket)
            except Exception as e:
                if self.running:
                    print(f"接受视频连接时出错: {e}")

    def video_stream_loop(self):
        """视频流循环"""
        if not self.camera:
            print("相机未初始化，无法启动视频流")
            return
            
        # 启动视频连接接收线程
        video_accept_thread = threading.Thread(target=self.accept_video_connections)
        video_accept_thread.daemon = True
        video_accept_thread.start()
        
        last_frame_time = 0
        
        while self.video_running:
            try:
                current_time = time.time()
                # 控制帧率
                if current_time - last_frame_time < self.frame_interval:
                    time.sleep(0.001)
                    continue
                
                # 捕获图像
                ret, frame = self.camera.read()
                if not ret:
                    print("读取视频帧失败")
                    continue
                
                # 压缩图像
                _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                frame_data = jpeg.tobytes()
                
                # 构建帧头
                frame_size = len(frame_data)
                header = struct.pack('>L', frame_size)  # 使用大端序打包
                
                # 发送给所有客户端
                disconnected_clients = []
                for client in self.video_clients:
                    try:
                        # 发送帧头
                        client.sendall(header)
                        # 发送帧数据
                        client.sendall(frame_data)
                    except Exception as e:
                        print(f"发送视频帧失败: {e}")
                        disconnected_clients.append(client)
                
                # 移除断开的客户端
                for client in disconnected_clients:
                    try:
                        client.close()
                    except:
                        pass
                    if client in self.video_clients:
                        self.video_clients.remove(client)
                
                last_frame_time = current_time
                
            except Exception as e:
                print(f"视频流循环错误: {e}")
                time.sleep(0.1)

    def stop(self):
        """停止服务器"""
        self.running = False
        self.video_running = False
        
        # 关闭所有客户端连接
        for client in self.clients + self.video_clients:
            try:
                client.close()
            except:
                pass
        
        # 清空客户端列表
        self.clients.clear()
        self.video_clients.clear()
        
        # 关闭服务器socket
        if self.control_socket:
            try:
                self.control_socket.close()
            except:
                pass
            
        if self.video_socket:
            try:
                self.video_socket.close()
            except:
                pass
        
        # 释放相机
        if self.camera:
            try:
                self.camera.release()
            except:
                pass
        
        # 清理GPIO
        self.cleanup_gpio()
        
        print("服务器已停止")

    def setup_gpio(self):
        """设置GPIO"""
        # 设置GPIO为输出模式
        GPIO.setup(IN1, GPIO.OUT)
        GPIO.setup(IN2, GPIO.OUT)
        GPIO.setup(IN3, GPIO.OUT)
        GPIO.setup(IN4, GPIO.OUT)
        GPIO.setup(ENA, GPIO.OUT)
        GPIO.setup(ENB, GPIO.OUT)

        # 创建PWM对象
        self.pwm_a = GPIO.PWM(ENA, 100)  # 频率100Hz
        self.pwm_b = GPIO.PWM(ENB, 100)  # 频率100Hz

        # 启动PWM
        self.pwm_a.start(0)
        self.pwm_b.start(0)

        # 设置舵机引脚
        GPIO.setup(self.PIN_SERVO_HORIZONTAL, GPIO.OUT)
        GPIO.setup(self.PIN_SERVO_VERTICAL, GPIO.OUT)
        
        # 初始化舵机PWM
        self.servo_h = GPIO.PWM(self.PIN_SERVO_HORIZONTAL, 50)  # 50Hz
        self.servo_v = GPIO.PWM(self.PIN_SERVO_VERTICAL, 50)    # 50Hz
        
        # 启动舵机PWM
        self.servo_h.start(0)
        self.servo_v.start(0)
        
        # 设置舵机初始位置
        self.set_servo_angle('h', self.servo_h_angle)
        self.set_servo_angle('v', self.servo_v_angle)
        
        print("舵机初始化完成")

    def cleanup_gpio(self):
        """清理GPIO"""
        # 停止小车
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(0)
        self.pwm_b.ChangeDutyCycle(0)
        
        # 停止PWM
        self.pwm_a.stop()
        self.pwm_b.stop()
        
        # 清理GPIO
        GPIO.cleanup()

    def init_camera(self):
        """初始化摄像头"""
        global camera
        try:
            with camera_lock:  # 使用锁保护摄像头初始化
                if camera is not None:
                    camera.release()
                camera = self.camera
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

    def release_camera(self):
        """释放摄像头"""
        global camera
        if camera:
            camera.release()
            camera = None

    def get_frame(self):
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

    def camera_stream_thread(self, client_socket):
        """摄像头流线程"""
        global camera_running
        try:
            while camera_running:
                frame_data = self.get_frame()
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

    def send_video_stream(self, client_socket):
        """发送视频流"""
        global camera, camera_running
        
        try:
            while camera_running:
                with camera_lock:
                    if camera is None or not camera.isOpened():
                        print("摄像头未打开或已关闭，尝试重新初始化...")
                        if not self.init_camera():
                            print("重新初始化摄像头失败")
                            break
                    
                    # 读取一帧
                    ret, frame = camera.read()
                    if not ret:
                        print("无法读取摄像头帧，尝试重新初始化...")
                        camera.release()
                        if not self.init_camera():
                            print("重新初始化摄像头失败")
                            break
                        continue
                    
                    # 减小分辨率
                    frame = cv2.resize(frame, (320, 240))  # 降低分辨率到320x240
                    
                    # 压缩图像
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 30])  # 降低质量到30%
                    frame_data = buffer.tobytes()
                    
                    # 发送帧大小
                    size = len(frame_data)
                    try:
                        # 使用struct打包大小信息
                        size_data = struct.pack('>L', size)
                        client_socket.sendall(size_data)
                        
                        # 发送帧数据
                        client_socket.sendall(frame_data)

                        # 控制帧率
                        time.sleep(1/15)  # 限制为15fps
                    except socket.error as e:
                        print(f"发送视频数据错误: {e}")
                        break
                    
        except Exception as e:
            print(f"视频流错误: {e}")
        finally:
            camera_running = False
            print("视频流已停止")

    def start_camera_stream(self, client_socket):
        """启动摄像头流"""
        global camera_running, camera_thread
        
        if camera_running:
            return "摄像头已经在运行"
        
        try:
            # 初始化摄像头
            if not self.init_camera():
                return "无法打开摄像头"
            
            camera_running = True
            camera_thread = threading.Thread(target=self.send_video_stream, args=(client_socket,))
            camera_thread.daemon = True
            camera_thread.start()
            return "摄像头已启动"
        except Exception as e:
            return f"启动摄像头失败: {e}"

    def stop_camera_stream(self):
        """停止摄像头流"""
        global camera_running, camera
        camera_running = False
        if camera_thread:
            camera_thread.join(timeout=1.0)
        with camera_lock:
            if camera is not None:
                camera.release()
                camera = None
        print("摄像头已停止")

    def set_speed(self, speed):
        """设置速度（0-100）"""
        global current_speed
        current_speed = max(0, min(100, speed))
        # 根据当前运动状态设置PWM占空比
        self.pwm_a.ChangeDutyCycle(current_speed)
        self.pwm_b.ChangeDutyCycle(current_speed)

        return f"速度已设置为: {current_speed}%"

    def angle_to_duty_cycle(self, angle):
        """将角度转换为占空比"""
        return 2.5 + (angle / 180.0) * 10.0

    def set_servo_h(self, angle):
        """设置水平舵机角度"""
        global current_h_angle
        current_h_angle = max(0, min(180, angle))
        duty_cycle = self.angle_to_duty_cycle(current_h_angle)
        self.servo_h.ChangeDutyCycle(duty_cycle)
        return f"水平角度已设置为: {current_h_angle}度"

    def set_servo_v(self, angle):
        """设置垂直舵机角度"""
        global current_v_angle
        current_v_angle = max(0, min(180, angle))
        duty_cycle = self.angle_to_duty_cycle(current_v_angle)
        self.servo_v.ChangeDutyCycle(duty_cycle)
        return f"垂直角度已设置为: {current_v_angle}度"

    def forward(self):
        """小车前进"""
        if current_speed > 0:
            GPIO.output(IN1, GPIO.HIGH)
            GPIO.output(IN2, GPIO.LOW)
            GPIO.output(IN3, GPIO.HIGH)
            GPIO.output(IN4, GPIO.LOW)
            # 设置PWM占空比
            self.pwm_a.ChangeDutyCycle(current_speed)
            self.pwm_b.ChangeDutyCycle(current_speed)
        else:
            self.stop()
        return "前进"

    def backward(self):
        """小车后退"""
        if current_speed > 0:
            GPIO.output(IN1, GPIO.LOW)
            GPIO.output(IN2, GPIO.HIGH)
            GPIO.output(IN3, GPIO.LOW)
            GPIO.output(IN4, GPIO.HIGH)
            # 设置PWM占空比
            self.pwm_a.ChangeDutyCycle(current_speed)
            self.pwm_b.ChangeDutyCycle(current_speed)
        else:
            self.stop()
        return "后退"

    def turn_right(self):
        """小车左转 - 通过降低左轮速度实现"""
        if current_speed > 0:
            GPIO.output(IN1, GPIO.HIGH)
            GPIO.output(IN2, GPIO.LOW)
            GPIO.output(IN3, GPIO.LOW)
            GPIO.output(IN4, GPIO.LOW)
            # 左轮速度降低到30%，右轮保持原速
            self.pwm_b.ChangeDutyCycle(current_speed)  # 左轮
            self.pwm_a.ChangeDutyCycle(current_speed)  # 右轮
        else:
            self.stop()
        return "左转"

    def turn_left(self):
        """小车右转 - 通过降低右轮速度实现"""
        if current_speed > 0:
            GPIO.output(IN1, GPIO.LOW)
            GPIO.output(IN2, GPIO.LOW)
            GPIO.output(IN3, GPIO.HIGH)
            GPIO.output(IN4, GPIO.LOW)
            self.pwm_b.ChangeDutyCycle(current_speed)  # 左轮
            self.pwm_a.ChangeDutyCycle(current_speed)  # 右轮
        else:
            self.stop()
        return "右转"

    def stop(self):
        """小车停止"""
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.LOW)
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(0)
        self.pwm_b.ChangeDutyCycle(0)
        return "停止"

    def send_frame(self, client_socket, frame):
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
            
            # 等待一小段时间确保大小数据被发送
            time.sleep(0.001)
            
            # 发送帧数据
            client_socket.sendall(frame_data)
            
        except Exception as e:
            print(f"发送视频帧错误: {e}")
            return False
        return True

    def handle_client(self, client_socket, address):
        """处理客户端连接"""
        print(f"新的控制连接：{address}")
        while self.running:
            try:
                # 接收数据
                data = client_socket.recv(1024)
                if not data:
                    break
                
                # 解析命令
                try:
                    command = json.loads(data.decode())
                    print(f"收到命令: {command}")
                    
                    # 提取命令和参数
                    cmd = command.get('command', '')
                    speed = command.get('speed', current_speed)
                    self.set_speed(speed)
                    
                    # 舵机控制命令
                    if cmd == 'servo':
                        servo_type = command.get('type', '')  # 'h' 或 'v'
                        angle = command.get('angle', 90)      # 角度值
                        print(f"舵机控制: 类型={servo_type}, 角度={angle}")
                        self.set_servo_angle(servo_type, angle)
                    
                    # 其他命令处理
                    elif cmd == 'forward':
                        print(f"执行前进命令，速度：{current_speed}")
                        self.forward()
                    elif cmd == 'backward':
                        print(f"执行后退命令，速度：{current_speed}")
                        self.backward()
                    elif cmd == 'left':
                        print(f"执行左转命令，速度：{current_speed}")
                        self.turn_left()
                    elif cmd == 'right':
                        print(f"执行右转命令，速度：{current_speed}")
                        self.turn_right()
                    elif cmd == 'stop':
                        print("执行停止命令")
                        self.stop_motors()
                    elif cmd == 'heartbeat':
                        pass  # 忽略心跳包
                    else:
                        print(f"未知命令: {cmd}")
                    
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}")
                except Exception as e:
                    print(f"处理命令时出错: {e}")
                    
            except Exception as e:
                print(f"接收数据时出错: {e}")
                break
        
        # 关闭连接
        try:
            client_socket.close()
        except:
            pass
        if client_socket in self.clients:
            self.clients.remove(client_socket)
        print(f"控制连接断开：{address}")

    def event_loop(self):
        """事件循环"""
        while self.running:
            try:
                # 接受控制连接
                client_socket, addr = self.control_socket.accept()
                # 为每个客户端创建新线程
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"接受控制连接时出错: {e}")

    def stop_motors(self):
        """停止电机"""
        try:
            print("执行电机停止")
            # 设置所有控制引脚为低电平
            GPIO.output(IN1, GPIO.LOW)
            GPIO.output(IN2, GPIO.LOW)
            GPIO.output(IN3, GPIO.LOW)
            GPIO.output(IN4, GPIO.LOW)
            
            # 设置PWM占空比为0
            self.pwm_a.ChangeDutyCycle(0)
            self.pwm_b.ChangeDutyCycle(0)
            
            print("电机已停止")
            
        except Exception as e:
            print(f"停止电机失败: {e}")

    def set_servo_angle(self, servo_type, angle):
        """设置舵机角度
        
        Args:
            servo_type: 'h' 水平舵机, 'v' 垂直舵机
            angle: 角度 (0-180)
        """
        try:
            # 确保角度在有效范围内
            angle = max(0, min(180, angle))
            
            # 将角度转换为占空比 (0.5ms-2.5ms)
            duty = 2.5 + angle * 10 / 180
            
            # 设置PWM占空比
            if servo_type == 'h':
                self.servo_h.ChangeDutyCycle(duty)
                self.servo_h_angle = angle
                print(f"设置水平舵机角度: {angle}°")
            elif servo_type == 'v':
                self.servo_v.ChangeDutyCycle(duty)
                self.servo_v_angle = angle
                print(f"设置垂直舵机角度: {angle}°")
            
            # 等待舵机转动
            time.sleep(0.1)
            
            # 停止PWM输出，防止抖动
            if servo_type == 'h':
                self.servo_h.ChangeDutyCycle(0)
            else:
                self.servo_v.ChangeDutyCycle(0)
                
        except Exception as e:
            print(f"设置舵机角度失败: {e}")

def main():
    server = CarServer()
    try:
        server.start()
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        server.stop()

if __name__ == "__main__":
    main() 