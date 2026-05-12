# 🖼️ 图像细节增强对比工具 (Image Detail Enhancement Comparison Tool)

一个基于 Python 的图形界面程序，用于比较干净图像、自身模型恢复图像和其他模型恢复图像，**自动定位自身模型细节提升最明显的区域**，并在所有图像上绘制红框、粘贴放大角标，便于视觉对比和论文展示。

## ✨ 功能

- **拖放或点击选择图片**：在三个区域分别放入干净图、自身模型图、其他模型图（可多张）。
- **滑动窗口搜索最优区域**：以用户自定义的窗口边长和步长，在所有图像上同步滑动，计算 SSIM 指标找到自身模型与干净图最相似、且与其他模型差异最大的区域。
- **所有图像标注同一窗口**：在干净图、自身模型图和每一张其他模型图上画出红色矩形框，并在指定角粘贴该区域的 **k 倍放大图**（角标位置支持四个角）。
- **结果预览与切换**：下方三个预览框分别显示干净图（带标记）、自身模型图（带标记）和当前选择的其他模型图（带标记），可通过按钮切换其他模型图。
- **一键保存全部结果**：保存所有带标记的图像及对应的局部放大图，文件名带时间戳和来源标识，方便直接用于报告或论文。
- **可调节参数**：窗口边长、步长、放大倍数、角标位置、评分方式（与干净图的 SSIM 减去与其他模型的平均/最大 SSIM）。

## 🧠 算法原理

对于每一张恢复图像和干净图像，在整张图上以步长 `step` 滑动 `h × h` 的正方形窗口。对每个位置计算：

- `SSIM(自身模型窗口, 干净窗口)` → **ss_clean**
- `SSIM(自身模型窗口, 其他模型i窗口)` → **ss_others**

综合评分（越高越好）：
- `mean_diff`：`ss_clean - mean(ss_others)`
- `max_diff`：`ss_clean - max(ss_others)`

选择评分最高的窗口作为最优区域，确保该区域自身模型恢复得最接近干净图、同时与其他模型区别最大（即自身模型的独有细节改进最显著）。

## 📦 依赖

- Python 3.7+
- [NumPy](https://numpy.org/)
- [Pillow](https://python-pillow.org/)
- [scikit-image](https://scikit-image.org/)
- [tkinterdnd2](https://pypi.org/project/tkinterdnd2/)（用于拖放功能，可选但推荐）

安装依赖：

```bash
pip install numpy pillow scikit-image tkinterdnd2
```

❗️注意：如果没有安装 tkinterdnd2，程序仍可正常运行，但只能通过点击选择文件，无法拖放。

## 🚀 快速开始

1.克隆仓库或下载脚本 image_compare_gui.py。

2.安装依赖。

3.运行脚本：
```bash
python image_compare_gui.py
```
4.在打开的窗口中：

- 左边框：拖入或选择干净图像（ground truth）
- 中间框：拖入或选择自身模型恢复图像
- 右边框：拖入或选择其他模型恢复图像（可多张，支持多次拖放或点击追加）
- 调整参数（窗口大小、步长、放大倍数、角标位置等）
- 点击 “开始生成比较图”
- 下方三个预览框将显示：

- 干净图（带红框和放大角标）
- 自身模型图（带红框和放大角标）
- 当前其他模型图（带红框和放大角标），可通过按钮切换
- 点击 “保存全部标记图及局部放大”，选择目录即可保存所有结果。

## 📁 输出文件说明

保存时会生成两类文件，带时间戳命名。

## 📦 打包成独立 EXE

可以使用 PyInstaller 打包为 Windows 可执行文件，无需安装 Python 环境即可运行：

可以使用 PyInstaller 打包为 Windows 可执行文件，无需安装 Python 环境即可运行：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --hidden-import=skimage.metrics --hidden-import=tkinterdnd2 --name="ImageDetailCompare" image_compare_gui.py
```
生成的 dist/ImageDetailCompare.exe 可直接发送给用户使用。

🤝 贡献

欢迎提交 Issue 或 Pull Request。如有任何问题，欢迎提出讨论。

————————————————————————————————————————————————————————
如果觉得有用，请给个 ⭐ Star 支持一下！
