import cv2
import numpy as np
import time
import threading


class DirectCameraManager:
    """直接管理摄像头连接，无缓存机制，实时获取画面"""

    def __init__(self):
        """初始化摄像头管理器"""
        self.camera_streams = {}  # 存储所有打开的摄像头对象
        self.available_cameras = self._detect_cameras()
        print(f"检测到 {len(self.available_cameras)} 个可用摄像头")
        for idx, info in self.available_cameras.items():
            print(f"摄像头 {idx}: {info['name']} ({info['width']}x{info['height']})")

    def _detect_cameras(self):
        """检测可用的摄像头并返回它们的信息"""
        cameras = {}
        # 尝试前10个索引查找摄像头
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # 在Windows上使用DirectShow
            if cap.isOpened():
                # 获取摄像头名称和分辨率
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                name = f"Camera {i}"

                cameras[i] = {
                    "name": name,
                    "width": width,
                    "height": height,
                    "fps": fps,
                }
                cap.release()
        return cameras

    def open_cameras(self, camera_indices):
        """打开指定索引的摄像头"""
        for idx in camera_indices:
            if idx is not None and idx in self.available_cameras:
                # 使用DirectShow以获取更好的性能
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if cap.isOpened():
                    # 设置摄像头参数以获得最佳性能

                    # 设置分辨率
                    cam_info = self.available_cameras[idx]
                    original_width = cam_info["width"]
                    original_height = cam_info["height"]

                    # 如果摄像头支持720p或更高分辨率，则使用1280x720
                    if original_height >= 720:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    else:
                        # 否则使用原始分辨率
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)

                    # 获取实际设置的分辨率并输出
                    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    print(
                        f"摄像头(索引: {idx})实际设置分辨率: {actual_width}x{actual_height}"
                    )

                    # 性能优化设置
                    # 设置帧率到最大值，通常为30fps
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    # 直接读取最新帧，跳过缓冲区
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    # 减少解码时间
                    cap.set(
                        cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G")
                    )

                    self.camera_streams[idx] = cap
                    print(f"成功打开摄像头 {idx}")
                else:
                    print(f"无法打开摄像头 {idx}")

    def get_frame(self, index):
        """直接从摄像头获取最新帧"""
        if index not in self.camera_streams:
            return None

        cap = self.camera_streams[index]
        if not cap.isOpened():
            return None

        # 丢弃缓冲区中的旧帧（如果有）
        for _ in range(1):  # 尝试丢弃1帧以确保获取最新的帧
            cap.grab()

        # 读取最新的一帧
        ret, frame = cap.read()
        if ret:
            return frame
        return None

    def release(self):
        """释放所有摄像头资源"""
        for idx, cap in self.camera_streams.items():
            if cap:
                cap.release()
        self.camera_streams.clear()
