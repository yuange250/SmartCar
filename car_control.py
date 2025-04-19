#!/usr/bin/env python3
import RPi.GPIO as GPIO
import keyboard
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
    print(f"当前速度: {current_speed}%")

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

def stop():
    """小车停止"""
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)

def cleanup():
    """清理GPIO设置"""
    GPIO.cleanup()

def main():
    print("小车控制程序已启动")
    print("使用以下按键控制小车：")
    print("w - 前进")
    print("s - 后退")
    print("a - 左转")
    print("d - 右转")
    print("q - 停止")
    print("1-9 - 设置速度（1最慢，9最快）")
    print("esc - 退出程序")

    # 设置初始速度
    set_speed(50)

    try:
        while True:
            # 检查速度控制
            for i in range(1, 10):
                if keyboard.is_pressed(str(i)):
                    speed = int(i) * 11  # 将1-9转换为11-99
                    set_speed(speed)
                    time.sleep(0.2)  # 防止重复触发

            # 检查方向控制
            if keyboard.is_pressed('w'):
                forward()
            elif keyboard.is_pressed('s'):
                backward()
            elif keyboard.is_pressed('a'):
                turn_left()
            elif keyboard.is_pressed('d'):
                turn_right()
            elif keyboard.is_pressed('q'):
                stop()
            elif keyboard.is_pressed('esc'):
                break
            time.sleep(0.1)  # 短暂延时，防止CPU占用过高

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        stop()
        cleanup()
        print("程序已退出")

if __name__ == "__main__":
    main() 