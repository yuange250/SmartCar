# 智能小车控制系统

这是一个基于树莓派的智能小车控制系统，支持远程控制、摄像头云台控制和实时视频传输功能。

## 功能特点

- 远程控制小车移动（前进、后退、左转、右转、停止）
- 实时速度调节（0-100%）
- 摄像头云台控制（水平和垂直方向）
- 实时视频传输
- 图形用户界面（GUI）控制
- 键盘快捷键支持
- 实时状态显示和日志记录

## 硬件要求

- 树莓派（推荐树莓派 4B）
- L298N 电机驱动模块
- 2个直流电机
- 2个舵机（用于摄像头云台）
- USB摄像头
- 电源供应（建议使用5V/3A以上电源）

## 接线说明

### 电机驱动模块（L298N）接线
- IN1 -> GPIO 9
- IN2 -> GPIO 25
- IN3 -> GPIO 11
- IN4 -> GPIO 8
- ENA -> GPIO 6
- ENB -> GPIO 12

### 舵机接线
- 水平舵机 -> GPIO 15
- 垂直舵机 -> GPIO 18

## 软件要求

- Python 3.7+
- OpenCV
- RPi.GPIO
- tkinter
- numpy
- PIL (Pillow)

## 安装步骤

1. 安装系统依赖：
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-dev
sudo apt-get install libopencv-dev python3-opencv
```

2. 安装Python包：
```bash
pip3 install RPi.GPIO
pip3 install numpy
pip3 install pillow
```

3. 克隆代码库：
```bash
git clone https://github.com/yourusername/smart-car.git
cd smart-car
```

## 使用说明

### 服务器端（树莓派）

1. 启动服务器：
```bash
python3 car_server.py
```

### 客户端（控制端）

1. 启动GUI客户端：
```bash
python3 car_client_gui.py <树莓派IP地址>
```

### 控制方式

1. GUI控制：
   - 使用方向按钮控制小车移动
   - 使用滑块调节速度
   - 使用滑块控制摄像头云台
   - 点击"开启摄像头"按钮查看实时视频

2. 键盘控制：
   - W - 前进
   - S - 后退
   - A - 左转
   - D - 右转
   - Q - 停止
   - 1-9 - 设置速度（1最慢，9最快）

### 注意事项

1. 确保树莓派和客户端在同一网络下
2. 检查所有硬件连接是否正确
3. 确保电源供应充足
4. 首次使用时，建议先测试基本移动功能
5. 调整速度时建议从小速度开始测试
6. 如果视频传输卡顿，可以：
   - 降低视频分辨率
   - 检查网络连接
   - 减少其他网络占用

## 故障排除

1. 小车不移动：
   - 检查电机接线
   - 确认电源供应正常
   - 检查GPIO连接

2. 舵机不响应：
   - 检查舵机接线
   - 确认舵机供电正常
   - 检查PWM设置

3. 视频无法显示：
   - 确认USB摄像头连接正常
   - 检查网络连接
   - 查看服务器日志

4. 控制延迟：
   - 检查网络连接质量
   - 减少视频分辨率
   - 关闭不必要的后台程序

## 维护和更新

- 定期检查硬件连接
- 保持系统更新
- 备份重要配置
- 记录任何硬件改动

## 许可证

MIT License 