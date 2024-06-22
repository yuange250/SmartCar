import RPi.GPIO as GPIO
from time import sleep


def tonum(num):  # 用于处理角度转换的函数
    fm = 10.0 / 180.0
    num = num * fm + 2.5
    num = int(num * 10) / 10.0
    return num


servopin1 = 15  # 舵机1,方向为左右转
servopin2 = 18  # 舵机2,方向为上下转

GPIO.setmode(GPIO.BCM)
GPIO.setup(servopin1, GPIO.OUT, initial=False)
GPIO.setup(servopin2, GPIO.OUT, initial=False)
p1 = GPIO.PWM(servopin1, 50)  # 50HZ
p2 = GPIO.PWM(servopin2, 50)  # 50HZ

p1.start(tonum(85))  # 初始化角度
p2.start(tonum(40))  # 初始化角度
sleep(0.5)
p1.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
p2.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
sleep(0.1)

a = 0  # 云台舵机1的执行次数
c = 9  # 云台舵机1初始化角度：90度
b = 0  # 云台舵机2的执行次数
d = 4  # 云台舵机2初始化角度：40度

q = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90,
     100, 110, 120, 130, 140, 150, 160, 170, 180]  # 旋转角度列表


def left():
    global a, c  # 引入全局变量
    a += 1
    if c > 2:  # 判断角度是否大于20度
        c = c - 1
        g = q[c]  # 调用q列表中的第c位元素
        print('当前角度为', g)
        p1.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第c位元素的角度
        sleep(0.1)
        p1.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)
    else:
        print('\n**超出范围**\n')
        c = 9
        g = 85  # 调用q列表中的第c位元素
        p1.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第c位元素的角度
        sleep(0.1)
        p1.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)


def right():
    global a, c  # 引入全局变量
    if c < 16:
        c = c + 1
        g = q[c]  # 调用q列表中的第c位元素
        print('当前角度为', g)
        p1.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第c位元素的角度
        sleep(0.1)
        p1.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)
    else:
        print('\n****超出范围****\n')
        c = 9
        g = 85  # 调用q列表中的第c位元素
        p1.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第c位元素的角度
        sleep(0.1)
        p1.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)


def up():
    global b, d  # 引入全局变量
    b += 1
    if d > 2:
        d = d - 1
        g = q[d]  # 调用q列表中的第d位元素
        print('当前角度为', g)
        p2.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第d位元素的角度
        sleep(0.1)
        p2.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)
    else:
        print('\n**超出范围**\n')
        d = 4
        g = q[d]  # 调用q列表中的第d位元素
        p2.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第d位元素的角度
        sleep(0.1)
        p2.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)


def down():
    global b, d  # 引入全局变量
    if d < 11:
        d = d + 1
        g = q[d]  # 调用q列表中的第d位元素
        print('当前角度为', g)
        p2.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第d位元素的角度
        sleep(0.1)
        p2.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)
    else:
        print('\n****超出范围****\n')
        d = 4
        g = q[d]  # 调用q列表中的第d位元素
        p2.ChangeDutyCycle(tonum(g))  # 执行角度变化，跳转到q列表中对应第d位元素的角度
        sleep(0.1)
        p2.ChangeDutyCycle(0)  # 清除当前占空比，使舵机停止抖动
        sleep(0.01)


if __name__ == '__main__':
    while True:
        command = input('输入:')
        if command == 'a':
            left()
        elif command == 'd':
            right()
        elif command == 'w':
            up()
        elif command == 's':
            down()
