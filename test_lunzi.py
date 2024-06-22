import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)

class CarMoving:
    def __init__(self):
        # self.IN1 = 9
        # self.IN2 = 25
        # self.IN3 = 22
        # self.IN4 = 8
        self.IN1 = 9
        self.IN2 = 25
        self.IN3 = 11
        self.IN4 = 8
        GPIO.setup(self.IN1, GPIO.OUT)
        GPIO.setup(self.IN2, GPIO.OUT)
        GPIO.setup(self.IN3, GPIO.OUT)
        GPIO.setup(self.IN4, GPIO.OUT)

    def up(self):
        GPIO.output(self.IN1, GPIO.HIGH) # 右前
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.HIGH) # 左前
        GPIO.output(self.IN4, GPIO.LOW)

    def down(self):
        GPIO.output(self.IN1, GPIO.LOW)
        GPIO.output(self.IN2, GPIO.HIGH)
        GPIO.output(self.IN3, GPIO.LOW)
        GPIO.output(self.IN4, GPIO.HIGH)

    def turn_left(self):
        GPIO.output(self.IN1, GPIO.HIGH)
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.LOW)
        GPIO.output(self.IN4, GPIO.LOW)

    def turn_right(self):
        GPIO.output(self.IN1, GPIO.LOW)
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.HIGH)
        GPIO.output(self.IN4, GPIO.LOW)

    def stop(self):
        GPIO.output(self.IN1, GPIO.LOW)
        GPIO.output(self.IN2, GPIO.LOW)
        GPIO.output(self.IN3, GPIO.LOW)
        GPIO.output(self.IN4, GPIO.LOW)

test = CarMoving()
test.up()
time.sleep(0.6)
test.down()
time.sleep(1.0)
# test.turn_left()
# time.sleep(0.3)
# test.turn_right()
# time.sleep(0.3)
test.stop()