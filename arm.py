#!/usr/bin/env python3
"""
SO101 机械臂控制模块（通过微雪控制板 + USB 串口）

注意：
1. 不同固件/控制板的总线舵机协议可能略有差异，请对照微雪/舵机官方文档确认帧格式。
2. 这里按照常见总线舵机协议（0x55 0x55 头 + ID + 长度 + 指令 + 参数 + 校验）给出参考实现，
   如果你的控制板文档使用不同协议，请只保留串口部分，替换打包指令的函数。
3. 建议在树莓派上安装 pyserial：
   pip install pyserial
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import serial


@dataclass
class JointLimit:
    """单个关节的角度限制（单位：度）"""

    min_deg: float
    max_deg: float


class ArmController:
    """
    SO101 机械臂控制类。

    典型接线：微雪 SO-ARM100/101 控制板通过 USB 连接到树莓派，
    在树莓派上会出现类似 /dev/ttyACM0 的串口设备。

    参数:
        port:   串口设备路径，树莓派上通常为 '/dev/ttyACM0' 或 '/dev/ttyACM1'
        baud:   波特率，参考控制板文档，常见为 115200 或 1000000
        timeout: 读超时时间（秒）
        joint_limits: 关节角度限制配置，key 为关节 ID（1~N）
    """

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baud: int = 115200,
        timeout: float = 0.1,
        joint_limits: Optional[Dict[int, JointLimit]] = None,
    ) -> None:
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._lock = threading.Lock()

        # 默认假设 6 自由度 + 夹爪，ID 1~6 为关节，ID 7 为夹爪
        self.joint_limits: Dict[int, JointLimit] = joint_limits or {
            1: JointLimit(-90, 90),   # 底座
            2: JointLimit(-45, 90),   # 大臂
            3: JointLimit(-90, 90),   # 小臂
            4: JointLimit(-90, 90),   # 手腕俯仰
            5: JointLimit(-180, 180), # 手腕旋转
            6: JointLimit(-180, 180), # 末端
            7: JointLimit(0, 90),     # 夹爪张合
        }

        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baud,
            timeout=self._timeout,
        )

    # ===================== 对外高层接口 ===================== #
    def close(self) -> None:
        """关闭串口连接。"""
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()

    def set_joint_angle(
        self,
        joint_id: int,
        angle_deg: float,
        duration_ms: int = 500,
    ) -> None:
        """
        设置单个关节角度。

        Args:
            joint_id: 关节 ID（1~N，对应舵机 ID）
            angle_deg: 目标角度（度），会根据 joint_limits 自动裁剪
            duration_ms: 运动时间，毫秒
        """
        limit = self.joint_limits.get(joint_id)
        if limit:
            angle_deg = max(limit.min_deg, min(limit.max_deg, angle_deg))

        packet = self._build_servo_move_packet(joint_id, angle_deg, duration_ms)
        self._send_packet(packet)

    def set_pose(
        self,
        joint_ids: Sequence[int],
        angles_deg: Sequence[float],
        duration_ms: int = 800,
    ) -> None:
        """
        同步设置多个关节角度（典型用于一个动作姿态）。

        Args:
            joint_ids: 关节 ID 列表
            angles_deg: 对应的角度列表
            duration_ms: 所有关节共同的运动时间
        """
        if len(joint_ids) != len(angles_deg):
            raise ValueError("joint_ids 和 angles_deg 长度必须一致")

        clipped_angles: List[float] = []
        for jid, ang in zip(joint_ids, angles_deg):
            limit = self.joint_limits.get(jid)
            if limit:
                ang = max(limit.min_deg, min(limit.max_deg, ang))
            clipped_angles.append(ang)

        packet = self._build_multi_servo_move_packet(joint_ids, clipped_angles, duration_ms)
        self._send_packet(packet)

    def open_gripper(self, angle_deg: float = 0, duration_ms: int = 400) -> None:
        """打开夹爪，角度和限制可根据实际机械结构调整。"""
        self.set_joint_angle(7, angle_deg, duration_ms=duration_ms)

    def close_gripper(self, angle_deg: float = 60, duration_ms: int = 400) -> None:
        """闭合夹爪。"""
        self.set_joint_angle(7, angle_deg, duration_ms=duration_ms)

    def go_home(self, duration_ms: int = 1000) -> None:
        """
        回到预设“初始姿态”，可以根据实际需要修改各关节角度。
        这里假设：
        - 底座关节 1：0°
        - 大臂 2：0°
        - 小臂 3：0°
        - 手腕俯仰 4：0°
        - 手腕旋转 5：0°
        - 末端 6：0°
        - 夹爪 7：30°
        """
        joint_ids = [1, 2, 3, 4, 5, 6, 7]
        angles = [0, 0, 0, 0, 0, 0, 30]
        self.set_pose(joint_ids, angles, duration_ms=duration_ms)

    def execute_trajectory(
        self,
        waypoints: Iterable[Dict[int, float]],
        duration_ms: int = 800,
        pause_ms_between: int = 200,
    ) -> None:
        """
        按顺序执行一系列关节空间路径点（适合简单抓取/放置动作）。

        Args:
            waypoints: 每个元素是 {joint_id: angle_deg} 的字典
            duration_ms: 每个路径点的移动时间
            pause_ms_between: 相邻路径点之间的停顿时间
        """
        for wp in waypoints:
            if not wp:
                continue
            joint_ids = list(wp.keys())
            angles = list(wp.values())
            self.set_pose(joint_ids, angles, duration_ms=duration_ms)
            time.sleep(pause_ms_between / 1000.0)

    # ===================== 串口与协议封装 ===================== #
    def _send_packet(self, packet: bytes) -> None:
        """线程安全地发送一帧数据到串口。"""
        with self._lock:
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("串口未打开")
            self._ser.write(packet)

    @staticmethod
    def _angle_deg_to_raw(angle_deg: float) -> int:
        """
        将角度转换为舵机内部位置值。

        这里默认假设：
            0~240 度 → 0~1000（仅作为示例）
        请根据实际舵机协议和量程修改。
        """
        angle_deg = max(0.0, min(240.0, angle_deg))
        return int(angle_deg / 240.0 * 1000)

    @staticmethod
    def _u16_to_bytes_le(value: int) -> bytes:
        """16bit 小端字节序。"""
        value = max(0, min(0xFFFF, int(value)))
        return bytes((value & 0xFF, (value >> 8) & 0xFF))

    def _build_servo_move_packet(
        self,
        servo_id: int,
        angle_deg: float,
        duration_ms: int,
    ) -> bytes:
        """
        构建单舵机移动指令帧。

        协议示例（常见总线舵机）：
        0    : 0x55
        1    : 0x55
        2    : ID
        3    : 长度（从指令到最后一个参数，包括校验前的所有字节数）
        4    : 指令码（示例使用 0x03：写位置）
        5..n : 参数（示例：位置、时间等）
        最后 : 校验和（从 ID 到最后一个参数取反）
        """
        # 示例：指令 0x03，参数：位置(2B) + 时间(2B)
        cmd = 0x03
        pos_raw = self._angle_deg_to_raw(angle_deg)
        pos_bytes = self._u16_to_bytes_le(pos_raw)
        time_bytes = self._u16_to_bytes_le(duration_ms)

        params = list(pos_bytes + time_bytes)

        length = 1 + len(params)  # 指令 + 参数
        frame = [0x55, 0x55, servo_id & 0xFF, length & 0xFF, cmd] + params

        checksum = (~sum(frame[2:]) + 1) & 0xFF
        frame.append(checksum)

        return bytes(frame)

    def _build_multi_servo_move_packet(
        self,
        servo_ids: Sequence[int],
        angles_deg: Sequence[float],
        duration_ms: int,
    ) -> bytes:
        """
        构建多舵机同步移动指令帧。

        常见格式示例：
        0    : 0x55
        1    : 0x55
        2    : 0xFE（广播 ID）
        3    : 长度
        4    : 指令码（自定义为 0x08 之类的“同步写”）
        5    : 舵机数量 N
        6..  : [ID, 位置低8位, 位置高8位] * N
        ...  : 共用时间（2B）
        最后 : 校验和
        """
        if not servo_ids:
            raise ValueError("servo_ids 不能为空")

        cmd = 0x08  # 示例：多舵机同步移动

        params: List[int] = [len(servo_ids) & 0xFF]

        for sid, ang in zip(servo_ids, angles_deg):
            pos_raw = self._angle_deg_to_raw(ang)
            pos_bytes = self._u16_to_bytes_le(pos_raw)
            params.append(sid & 0xFF)
            params.extend(pos_bytes)

        time_bytes = self._u16_to_bytes_le(duration_ms)
        params.extend(time_bytes)

        length = 1 + len(params)  # 指令 + 参数
        frame = [0x55, 0x55, 0xFE, length & 0xFF, cmd] + params

        checksum = (~sum(frame[2:]) + 1) & 0xFF
        frame.append(checksum)

        return bytes(frame)


def _demo() -> None:
    """
    简单本地测试示例：
    在树莓派上直接运行本文件，先让机械臂回到初始姿态，然后轻微摆动关节 2。
    请根据实际串口号调整 port 参数。
    """
    arm = ArmController(port="/dev/ttyACM0", baud=115200)
    try:
        arm.go_home(duration_ms=1500)
        time.sleep(2.0)

        # 让第二关节小幅度上下摆动三次
        for _ in range(3):
            arm.set_joint_angle(2, 30, duration_ms=600)
            time.sleep(0.8)
            arm.set_joint_angle(2, -10, duration_ms=600)
            time.sleep(0.8)

        # 打开/闭合夹爪
        arm.open_gripper()
        time.sleep(1.0)
        arm.close_gripper()
        time.sleep(1.0)
    finally:
        arm.close()


if __name__ == "__main__":
    _demo()

