#!/usr/bin/env python3
"""
SO101 机械臂控制模块（基于 LeRobot + FeetechMotorsBus 的薄封装）

适用场景：
- 机械臂：SO101（follower arm）
- 控制板：微雪 SO-ARM100/101，通过 USB 连接到树莓派
- 下层驱动与标定：由 LeRobot 官方完成，本模块只做“薄封装”

前置条件（非常重要）：
1. 已在当前 Python 环境中安装 LeRobot 及 Feetech 支持：
   pip install "lerobot[feetech]"
2. 已使用官方命令完成电机配置与标定（只需做一次）：
   lerobot-find-port
   lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=my_follower_arm
   lerobot-calibrate   --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=my_follower_arm

本文件在此基础上，提供：
- ArmController：按“关节 ID / 简单动作”来控制机械臂，方便与你的小车逻辑对接。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

import draccus
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus


@dataclass
class JointLimit:
    """单个关节的角度或开合范围限制."""

    min_val: float
    max_val: float


class ArmController:
    """
    SO101 机械臂控制类（基于 LeRobot 的 FeetechMotorsBus）。

    约定：
    - 关节 ID 与官方示意保持一致：
        1: shoulder_pan   （底座）
        2: shoulder_lift  （大臂）
        3: elbow_flex     （小臂）
        4: wrist_flex     （手腕俯仰）
        5: wrist_roll     （手腕旋转）
        6: gripper        （夹爪）
    - 1~5 关节使用“角度（度）”控制，6 使用 [0, 100] 的开合百分比。

    参数:
        port:      USB 串口设备路径，例如 '/dev/ttyACM0'
        robot_id:  标定时使用的 --robot.id，例如 'my_follower_arm'
        joint_limits: 关节限制配置，key 为关节 ID（1~6）
    """

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        robot_id: str = "my_follower_arm",
        joint_limits: Optional[Dict[int, JointLimit]] = None,
    ) -> None:
        self._port = port
        self._robot_id = robot_id

        # 关节 ID -> 名称 映射
        self.id_to_name: Dict[int, str] = {
            1: "shoulder_pan",
            2: "shoulder_lift",
            3: "elbow_flex",
            4: "wrist_flex",
            5: "wrist_roll",
            6: "gripper",
        }

        # 关节限制（1~5：角度，单位度；6：夹爪开合百分比 0~100）
        self.joint_limits: Dict[int, JointLimit] = joint_limits or {
            1: JointLimit(-90.0, 90.0),
            2: JointLimit(-60.0, 90.0),
            3: JointLimit(-120.0, 120.0),
            4: JointLimit(-120.0, 120.0),
            5: JointLimit(-180.0, 180.0),
            6: JointLimit(0.0, 100.0),  # 夹爪开合 0~100%
        }

        # 加载标定文件
        calibration = self._load_calibration(robot_id)

        # 创建电机总线
        self._bus = FeetechMotorsBus(
            port=self._port,
            motors={
                "shoulder_pan": Motor(1, "sts3215", MotorNormMode.DEGREES),
                "shoulder_lift": Motor(2, "sts3215", MotorNormMode.DEGREES),
                "elbow_flex": Motor(3, "sts3215", MotorNormMode.DEGREES),
                "wrist_flex": Motor(4, "sts3215", MotorNormMode.DEGREES),
                "wrist_roll": Motor(5, "sts3215", MotorNormMode.DEGREES),
                # 夹爪用 0~100 范围控制，具体含义取决于标定和机械结构
                "gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
            },
            calibration=calibration,
        )

        # 连接电机总线（部分版本会在 connect 内部自动上扭矩）
        # 如果你的 LeRobot 版本需要手动 enable torque，可以在这里补充：
        #   self._bus.enable_torque(...)
        self._bus.connect()

    @staticmethod
    def _load_calibration(robot_id: str) -> Dict[str, MotorCalibration]:
        """
        从默认路径加载标定数据。

        标定文件默认位于：
        ~/.cache/huggingface/lerobot/calibration/robots/<robot_id>.json
        """
        calib_path = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "lerobot"
            / "calibration"
            / "robots"
            / "so_follower"
            / f"{robot_id}.json"
        )
        if not calib_path.exists():
            raise FileNotFoundError(
                f"找不到标定文件: {calib_path}\n"
                f"请先运行 lerobot-calibrate 完成机械臂标定。"
            )

        with calib_path.open("r", encoding="utf-8") as f, draccus.config_type("json"):
            calibration = draccus.load(Dict[str, MotorCalibration], f)
        return calibration

    # ===================== 对外高层接口 ===================== #
    def close(self) -> None:
        """断开总线连接，释放扭矩。"""
        if self._bus:
            self._bus.disconnect()

    def set_joint_angle(
        self,
        joint_id: int,
        angle_deg: float,
        duration_ms: int = 500,
    ) -> None:
        """
        设置单个关节角度。

        Args:
            joint_id: 关节 ID（1~6）
            angle_deg: 目标值：
                - 关节 1~5：角度（度）
                - 关节 6：夹爪开合百分比（0~100）
            duration_ms: 运动时间，毫秒（当前版本依赖 LeRobot 默认时间常数）
        """
        if joint_id not in self.id_to_name:
            raise ValueError(f"未知关节 ID: {joint_id}")

        name = self.id_to_name[joint_id]
        limit = self.joint_limits.get(joint_id)
        value = angle_deg
        if limit:
            value = max(limit.min_val, min(limit.max_val, value))

        # 这里直接写入目标位置，具体时间参数由 LeRobot/舵机内部控制
        # 使用归一化写入：1~5 关节为角度（度），6 号为开合百分比（0~100）
        self._bus.write("Goal_Position", name, float(value), normalize=True)

    def set_pose(
        self,
        joint_ids: Sequence[int],
        angles_deg: Sequence[float],
        duration_ms: int = 800,
    ) -> None:
        """
        同步设置多个关节角度（典型用于一个动作姿态）。

        Args:
            joint_ids: 关节 ID 列表（1~6）
            angles_deg: 对应的目标值列表
            duration_ms: 所有关节共同的运动时间（当前版本依赖 LeRobot 默认时间常数）
        """
        if len(joint_ids) != len(angles_deg):
            raise ValueError("joint_ids 和 angles_deg 长度必须一致")

        goals: Dict[str, float] = {}
        for jid, ang in zip(joint_ids, angles_deg):
            if jid not in self.id_to_name:
                raise ValueError(f"未知关节 ID: {jid}")
            name = self.id_to_name[jid]
            limit = self.joint_limits.get(jid)
            value = ang
            if limit:
                value = max(limit.min_val, min(limit.max_val, value))
            goals[name] = float(value)

        # 同步写入多个关节的目标位置
        self._bus.sync_write("Goal_Position", goals, normalize=True)

    def open_gripper(self, open_percent: float = 100.0) -> None:
        """打开夹爪，参数为 0~100 的开合百分比。"""
        self.set_joint_angle(6, open_percent)

    def close_gripper(self, close_percent: float = 0.0) -> None:
        """闭合夹爪，参数为 0~100 的开合百分比。"""
        self.set_joint_angle(6, close_percent)

    def go_home(self, duration_ms: int = 1000) -> None:
        """
        回到预设“初始姿态”，可以根据实际需要修改各关节角度。
        这里假设：
        - 底座关节 1：0°
        - 大臂 2：0°
        - 小臂 3：0°
        - 手腕俯仰 4：0°
        - 手腕旋转 5：0°
        - 末端 5：0°
        - 夹爪 6：50%（半开）
        """
        joint_ids = [1, 2, 3, 4, 5, 6]
        angles = [0.0, 0.0, 0.0, 0.0, 0.0, 50.0]
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


def _demo() -> None:
    """
    简单本地测试示例：
    在树莓派上直接运行本文件，先让机械臂回到初始姿态，然后轻微摆动关节 2。
    请根据实际串口号和 robot_id 调整参数。
    """
    arm = ArmController(port="/dev/ttyACM0", robot_id="my_follower_arm")
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

