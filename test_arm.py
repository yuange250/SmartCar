#!/usr/bin/env python3
"""
SO101 机械臂基础测试脚本

用途：
1. 检查树莓派能否通过 USB 串口识别微雪控制板
2. 验证简单动作是否能正常执行（回零、摆动、夹爪）

使用方法（在树莓派上）：
1. 确认串口号，例如：
   ls /dev/ttyACM*
   sudo chmod 666 /dev/ttyACM*
2. 安装依赖：
   pip install pyserial
3. 运行测试：
   python3 test_arm.py
4. 按提示输入串口号（默认 /dev/ttyACM0），然后根据菜单选择动作
"""

import sys
import time

from arm import ArmController


def select_port(default: str = "/dev/ttyACM0") -> str:
    """简单交互式选择串口。"""
    print("请输入机械臂控制板对应的串口设备路径：")
    print(f"直接回车使用默认值 [{default}]")
    port = input("> ").strip()
    if not port:
        port = default
    return port


def main() -> None:
    print("==== SO101 机械臂测试程序 ====")
    port = select_port()

    try:
        arm = ArmController(port=port, baud=115200)
    except Exception as e:
        print(f"打开串口失败，请检查 USB 连接和权限: {e}")
        sys.exit(1)

    print(f"已连接串口: {port}")
    print("注意：如果机械臂没有反应，请先确认：")
    print("  - 微雪控制板电源已接好")
    print("  - 舵机 ID 与协议配置正确")
    print("  - 串口号、波特率与控制板文档一致\n")

    try:
        while True:
            print("\n=== 功能菜单 ===")
            print("1. 回到初始姿态 (go_home)")
            print("2. 关节2 上下摆动一次")
            print("3. 打开夹爪")
            print("4. 闭合夹爪")
            print("5. 自定义单关节角度")
            print("0. 退出")
            choice = input("请选择功能编号: ").strip()

            if choice == "1":
                print("执行：回到初始姿态...")
                arm.go_home(duration_ms=1500)
                time.sleep(2.0)
                print("完成")

            elif choice == "2":
                print("执行：关节2 上下摆动一次...")
                arm.set_joint_angle(2, 30, duration_ms=600)
                time.sleep(0.8)
                arm.set_joint_angle(2, -10, duration_ms=600)
                time.sleep(0.8)
                print("完成")

            elif choice == "3":
                print("执行：打开夹爪...")
                arm.open_gripper()
                time.sleep(1.0)
                print("完成")

            elif choice == "4":
                print("执行：闭合夹爪...")
                arm.close_gripper()
                time.sleep(1.0)
                print("完成")

            elif choice == "5":
                try:
                    jid = int(input("请输入关节 ID (整数，例如 1~7): ").strip())
                    ang = float(input("请输入目标角度（度，例如 0 / 30 / -30）: ").strip())
                    dur = int(input("请输入运动时间 ms（例如 500）: ").strip() or "500")
                except ValueError:
                    print("输入格式错误，请重试。")
                    continue

                print(f"执行：关节 {jid} -> {ang} 度，用时 {dur} ms ...")
                arm.set_joint_angle(jid, ang, duration_ms=dur)
                time.sleep(dur / 1000.0 + 0.3)
                print("完成")

            elif choice == "0":
                print("退出测试程序。")
                break

            else:
                print("无效选择，请重新输入。")

    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，准备退出...")
    finally:
        arm.close()
        print("串口已关闭。")


if __name__ == "__main__":
    main()

