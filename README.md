# AVM-SurroundView — 360° 全景环视系统

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)](https://python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv)](https://opencv.org/)
[![NumPy](https://img.shields.io/badge/NumPy-科学计算-013243?logo=numpy)](https://numpy.org/)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

> 软件杯竞赛参赛作品

## 项目背景

车辆在泊车和低速行驶时，驾驶员对周围环境的感知存在大面积盲区，倒车镜和倒车影像只能覆盖有限角度。商用 360° 全景环视系统（AVM）价格高昂，且通常与特定硬件深度绑定，不便于学习研究和二次开发。

本项目实现了一套完整的 AVM 全景环视处理流程：从四路摄像头（前/后/左/右）的标定、畸变校正、透视投影，到多视角图像拼接融合，最终生成实时的 360° 鸟瞰全景图。整个流程基于 Python + OpenCV 实现，并提供 PyQt5 图形界面，方便操作和调试。

## 处理流程

```
相机标定 → 畸变校正 → 透视投影 → 图像拼接 → 实时环视
```

1. **相机标定**（`run_calibrate_camera.py`）：棋盘格标定法获取相机内参，支持鱼眼/广角镜头
2. **图像采集**（`save_camera_images.py`）：从四路摄像头采集标定用图像
3. **透视投影**（`run_get_projection_maps.py`）：手动标注关键点，计算鸟瞰视角投影矩阵
4. **权重生成**（`run_get_weight_matrices.py`）：生成多视角图像融合权重矩阵
5. **实时环视**（`run_live_demo.py`）：实时接入摄像头，生成 360° 鸟瞰全景

## 项目结构

```
AVM-SurroundView/
├── run_calibrate_camera.py     # 相机内参标定
├── save_camera_images.py       # 摄像头图像采集
├── run_get_projection_maps.py  # 透视投影矩阵标定
├── run_get_weight_matrices.py  # 融合权重矩阵生成
├── run_live_demo.py            # 实时全景环视
├── main_gui.py                 # PyQt5 GUI 主程序
├── stitcher.py                 # 图像拼接算法
├── camera_direct.py            # 摄像头直连测试
├── test_cameras.py             # 摄像头检测
├── surround_view/              # 核心算法模块
├── yaml/                       # 标定参数文件
├── images/                     # 标定图像
├── doc/                        # 技术文档
├── masks.png                   # 拼接掩码
└── weights.png                 # 融合权重
```

## 快速开始

**环境要求：** Python 3.8+、OpenCV 4.x、NumPy、PyQt5、4 个 USB 广角摄像头

```bash
pip install opencv-python numpy PyQt5

# 步骤 1：相机内参标定（各摄像头分别执行）
python run_calibrate_camera.py -i 0 -grid 8x6 --no_gst -r 1280x720 -o yaml/front.yaml

# 步骤 2：采集标定图像
python save_camera_images.py -i 0 -n front -r 1280x720

# 步骤 3：标定投影矩阵
python run_get_projection_maps.py -camera front

# 步骤 4：生成融合权重
python run_get_weight_matrices.py

# 步骤 5：运行实时全景环视
python run_live_demo.py

# 或者使用 GUI 模式
python main_gui.py
```

详细技术文档见 `doc/` 目录。

## 开源协议

MIT License
