<![CDATA[# 🚙 AVM-SurroundView — 360° 全景环视系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv" alt="OpenCV">
  <img src="https://img.shields.io/badge/NumPy-科学计算-013243?logo=numpy" alt="NumPy">
  <img src="https://img.shields.io/badge/🏆-软件杯竞赛作品-gold" alt="Competition">
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License">
</p>

> 🏆 **软件杯竞赛作品** — 基于多摄像头（前/后/左/右）的 **AVM 360° 全景环视系统**。实现了完整的 **相机标定 → 畸变校正 → 透视投影 → 图像拼接 → 实时环视** 流程，支持 GUI 交互界面和实时视频流处理。

---

## ✨ 功能特性

- 📷 **四路摄像头** — 支持前/后/左/右四路广角摄像头同步采集
- 🔧 **相机标定** — 基于棋盘格的内参标定（支持鱼眼/广角）
- 🗺️ **透视投影** — 手动标注关键点，生成鸟瞰视角投影矩阵
- 🧩 **图像拼接** — 基于权重矩阵的多视角图像无缝融合
- 🖥️ **GUI 界面** — PyQt5 图形化操作界面 (`main_gui.py`)
- 🎬 **实时环视** — 实时接入摄像头，生成 360° 鸟瞰全景图

---

## 🏗️ 项目结构

```
AVM-SurroundView/
├── run_calibrate_camera.py     # 📷 相机内参标定（棋盘格检测）
├── save_camera_images.py       # 💾 摄像头图像采集保存
├── run_get_projection_maps.py  # 🗺️ 透视投影矩阵标定
├── run_get_weight_matrices.py  # ⚖️ 融合权重矩阵生成
├── run_live_demo.py            # 🎬 实时全景环视演示
├── main_gui.py                 # 🖥️ PyQt5 GUI 主程序
├── camera_direct.py            # 📹 摄像头直连测试
├── stitcher.py                 # 🧩 图像拼接核心算法
├── test_cameras.py             # 🔍 摄像头检测工具
├── surround_view/              # 📦 核心模块包
├── yaml/                       # ⚙️ 相机标定参数文件
├── images/                     # 🖼️ 标定用图像
├── doc/                        # 📖 详细技术文档
├── masks.png                   # 🎭 拼接掩码
└── weights.png                 # ⚖️ 融合权重图
```

---

## 🚀 快速开始

### 环境要求
- Python 3.8+
- OpenCV 4.x
- NumPy
- PyQt5（GUI 模式）
- 4 个 USB 广角摄像头

### 安装依赖

```bash
pip install opencv-python numpy PyQt5
```

### 标定流程

```bash
# 1️⃣ 相机内参标定（对每个摄像头重复）
python run_calibrate_camera.py -i 0 -grid 8x6 --no_gst -r 1280x720 -o yaml/front.yaml

# 2️⃣ 采集标定图像
python save_camera_images.py -i 0 -n front -r 1280x720

# 3️⃣ 标定投影矩阵（手动选择关键点）
python run_get_projection_maps.py -camera front

# 4️⃣ 生成融合权重
python run_get_weight_matrices.py

# 5️⃣ 运行实时全景环视
python run_live_demo.py
```

### GUI 模式

```bash
python main_gui.py
```

---

## 📖 技术文档

详细技术文档位于 `doc/` 目录，涵盖：
- 相机标定原理与操作
- 透视投影矩阵计算
- 图像拼接与融合算法
- 系统部署指南

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
]]>
