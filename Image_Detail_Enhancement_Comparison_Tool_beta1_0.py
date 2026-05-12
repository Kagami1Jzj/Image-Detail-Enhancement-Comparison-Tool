import sys
import os
import time
import re
import numpy as np
from PIL import Image, ImageDraw, ImageTk
from skimage.metrics import structural_similarity as ssim
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------- 尝试导入 tkinterdnd2 ----------
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = tk.Tk
    print("警告：未安装 tkinterdnd2，拖放功能不可用，请使用文件选择按钮。")
    print("安装命令：pip install tkinterdnd2")


def load_image_safe(path):
    return np.array(Image.open(path).convert("RGB"))


def process_images(clean_path, our_path, other_paths, h, step, k, corner, metric):
    """
    滑动窗口分析，返回:
        best_pos: (x, y)
        marked_images: 字典 {name: PIL.Image}，所有标记后的图
        patches: 字典 {name: PIL.Image}，对应放大后的局部 patch
    """
    clean = load_image_safe(clean_path)
    our = load_image_safe(our_path)
    others = {}
    for p in other_paths:
        others[p] = load_image_safe(p)

    H, W, _ = clean.shape
    assert our.shape == (H, W, 3)
    for img in others.values():
        assert img.shape == (H, W, 3)

    # 计算最佳窗口位置
    best_score = -float("inf")
    best_pos = (0, 0)

    for y in range(0, H - h + 1, step):
        for x in range(0, W - h + 1, step):
            clean_patch = clean[y:y+h, x:x+h]
            our_patch = our[y:y+h, x:x+h]
            ss_clean = ssim(clean_patch, our_patch, data_range=255, channel_axis=2)

            ss_others = []
            for other_img in others.values():
                other_patch = other_img[y:y+h, x:x+h]
                ss_others.append(ssim(other_patch, our_patch, data_range=255, channel_axis=2))

            if metric == "max_diff":
                score = ss_clean - max(ss_others) if ss_others else ss_clean
            else:
                score = ss_clean - np.mean(ss_others) if ss_others else ss_clean

            if score > best_score:
                best_score = score
                best_pos = (x, y)

    x, y = best_pos

    # 生成所有标记图像
    marked_images = {}
    patches = {}

    # 计算角标放置位置（四个角）
    paste_size = (h * k, h * k)
    if corner == "top_left":
        paste_pos = (0, 0)
    elif corner == "top_right":
        paste_pos = (W - paste_size[0], 0)
    elif corner == "bottom_left":
        paste_pos = (0, H - paste_size[1])
    else:  # bottom_right
        paste_pos = (W - paste_size[0], H - paste_size[1])

    # 辅助函数：生成单张标记图
    def mark_image(img_array, name, patch_array):
        pil_img = Image.fromarray(img_array)
        draw = ImageDraw.Draw(pil_img)
        draw.rectangle([x, y, x + h, y + h], outline="red", width=2)

        patch_img = Image.fromarray(patch_array).resize(paste_size, Image.NEAREST)
        pil_img.paste(patch_img, paste_pos)
        return pil_img, patch_img

    # 干净图
    clean_patch = clean[y:y+h, x:x+h]
    marked_clean, patch_clean = mark_image(clean, "clean", clean_patch)
    marked_images["clean"] = marked_clean
    patches["clean"] = patch_clean

    # 我们模型图
    our_patch = our[y:y+h, x:x+h]
    marked_our, patch_our = mark_image(our, "our", our_patch)
    marked_images["our"] = marked_our
    patches["our"] = patch_our

    # 其他模型图（使用路径作为键）
    for path, other_img in others.items():
        other_patch = other_img[y:y+h, x:x+h]
        marked_other, patch_other = mark_image(other_img, path, other_patch)
        marked_images[path] = marked_other
        patches[path] = patch_other

    return best_pos, marked_images, patches


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("图像细节增强对比工具")
        self.root.geometry("1200x850")

        # 文件路径
        self.clean_path = None
        self.our_path = None
        self.other_paths = []

        # 生成结果缓存
        self.marked_images = {}  # name -> PIL.Image
        self.patches = {}
        self.current_other_index = 0  # 当前显示的其他模型索引

        # 参数变量
        self.h = tk.IntVar(value=64)
        self.step = tk.IntVar(value=32)
        self.k = tk.IntVar(value=4)
        self.corner = tk.StringVar(value="bottom_right")
        self.metric = tk.StringVar(value="mean_diff")

        self.build_ui()

    def build_ui(self):
        # ----- 顶部拖放框区域 (高度约 200) -----
        top_frame = tk.Frame(self.root, height=200)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        top_frame.pack_propagate(False)

        self.create_drop_box(top_frame, "干净图像\n(真实图)", 0, self.set_clean)
        self.create_drop_box(top_frame, "我们模型恢复图\n(只能一张)", 1, self.set_our)
        self.create_drop_box(top_frame, "其他模型恢复图\n(可拖入多张)", 2, self.set_others, multi=True)

        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=1)

        # ----- 参数设置行 -----
        param_frame = tk.Frame(self.root)
        param_frame.pack(pady=5)

        row = 0
        tk.Label(param_frame, text="窗口边长 h:").grid(row=row, column=0, sticky="e")
        tk.Entry(param_frame, textvariable=self.h, width=6).grid(row=row, column=1, sticky="w")
        tk.Label(param_frame, text="步长 step:").grid(row=row, column=2, sticky="e", padx=(10,0))
        tk.Entry(param_frame, textvariable=self.step, width=6).grid(row=row, column=3, sticky="w")
        tk.Label(param_frame, text="放大倍数 k:").grid(row=row, column=4, sticky="e", padx=(10,0))
        tk.Entry(param_frame, textvariable=self.k, width=6).grid(row=row, column=5, sticky="w")
        tk.Label(param_frame, text="角标位置:").grid(row=row, column=6, sticky="e", padx=(10,0))
        corner_menu = ttk.Combobox(param_frame, textvariable=self.corner,
                                   values=["bottom_right", "bottom_left", "top_right", "top_left"],
                                   width=12, state="readonly")
        corner_menu.grid(row=row, column=7, sticky="w")
        tk.Label(param_frame, text="评分方式:").grid(row=row, column=8, sticky="e", padx=(10,0))
        metric_menu = ttk.Combobox(param_frame, textvariable=self.metric,
                                   values=["mean_diff", "max_diff"], width=10, state="readonly")
        metric_menu.grid(row=row, column=9, sticky="w")

        # ----- 生成按钮（1/2 高度位置的感觉）-----
        gen_frame = tk.Frame(self.root)
        gen_frame.pack(pady=10)
        self.btn_generate = tk.Button(gen_frame, text="▶ 开始生成比较图", command=self.on_generate,
                                      font=("微软雅黑", 12), bg="#4CAF50", fg="white", padx=20, pady=5)
        self.btn_generate.pack()

        # ----- 下方结果展示区（带切换控件）-----
        bottom_frame = tk.Frame(self.root, height=280, bg="#f0f0f0")
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        bottom_frame.pack_propagate(False)

        # 其他模型切换栏
        other_control = tk.Frame(bottom_frame, bg="#f0f0f0")
        other_control.pack(fill=tk.X, pady=(5,0))
        self.lbl_other_count = tk.Label(other_control, text="其他模型: 0 张", bg="#f0f0f0")
        self.lbl_other_count.pack(side=tk.LEFT, padx=5)
        self.btn_prev = tk.Button(other_control, text="◀ 上一张", command=self.prev_other, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, padx=2)
        self.btn_next = tk.Button(other_control, text="下一张 ▶", command=self.next_other, state=tk.DISABLED)
        self.btn_next.pack(side=tk.LEFT, padx=2)
        self.lbl_other_name = tk.Label(other_control, text="", bg="#f0f0f0", fg="blue")
        self.lbl_other_name.pack(side=tk.LEFT, padx=5)

        # 三个图片 Label
        result_frame = tk.Frame(bottom_frame, bg="#f0f0f0")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_labels = []
        titles = ["干净图 (带标记)", "我们模型 (带标记)", "其他模型 (带标记)"]
        for i, title in enumerate(titles):
            frame = tk.Frame(result_frame, bd=2, relief=tk.SUNKEN, bg="white")
            frame.grid(row=0, column=i, sticky="nsew", padx=3, pady=3)
            result_frame.grid_columnconfigure(i, weight=1)
            result_frame.grid_rowconfigure(0, weight=1)

            lbl_title = tk.Label(frame, text=title, bg="white", font=("微软雅黑", 9))
            lbl_title.pack(pady=2)
            lbl_img = tk.Label(frame, bg="gray90", text="等待生成...")
            lbl_img.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
            self.result_labels.append(lbl_img)

        # ----- 保存全部按钮 -----
        save_frame = tk.Frame(self.root)
        save_frame.pack(pady=5)
        self.btn_save = tk.Button(save_frame, text="💾 保存全部标记图及局部放大", command=self.on_save_all,
                                  font=("微软雅黑", 11), bg="#2196F3", fg="white", padx=20, pady=5,
                                  state=tk.DISABLED)
        self.btn_save.pack()

    def create_drop_box(self, parent, title, column, setter_func, multi=False):
        frame = tk.Frame(parent, bd=2, relief=tk.GROOVE, bg="white")
        frame.grid(row=0, column=column, sticky="nsew", padx=10, pady=5)

        lbl_title = tk.Label(frame, text=title, bg="white", font=("微软雅黑", 9))
        lbl_title.pack(pady=4)

        lbl_drop = tk.Label(frame, text="拖放图片到此处\n或点击选择文件",
                            bg="#E3F2FD", relief=tk.RIDGE, cursor="hand2")
        lbl_drop.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if DND_AVAILABLE:
            if multi:
                lbl_drop.drop_target_register(DND_FILES)
                lbl_drop.dnd_bind('<<Drop>>', lambda e: self.on_drop_multi(e, setter_func, lbl_drop))
            else:
                lbl_drop.drop_target_register(DND_FILES)
                lbl_drop.dnd_bind('<<Drop>>', lambda e: self.on_drop_single(e, setter_func, lbl_drop))

        if multi:
            lbl_drop.bind("<Button-1>", lambda e: self.on_click_multi(setter_func, lbl_drop))
        else:
            lbl_drop.bind("<Button-1>", lambda e: self.on_click_single(setter_func, lbl_drop))

        if column == 0:
            self.lbl_clean_status = lbl_drop
        elif column == 1:
            self.lbl_our_status = lbl_drop
        else:
            self.lbl_other_status = lbl_drop

    # ---------- 文件处理 ----------
    @staticmethod
    def parse_drop(data):
        paths = re.findall(r'\{([^}]+)\}', data)
        if not paths:
            paths = [p.strip() for p in data.split() if p.strip()]
        return paths

    def on_drop_single(self, event, setter_func, label_widget):
        files = self.parse_drop(event.data)
        if files:
            setter_func(files[0])
            label_widget.config(text=os.path.basename(files[0]))

    def on_drop_multi(self, event, setter_func, label_widget):
        files = self.parse_drop(event.data)
        if files:
            setter_func(files)
            label_widget.config(text=f"已选择 {len(files)} 张")

    def on_click_single(self, setter_func, label_widget):
        path = filedialog.askopenfilename(filetypes=[("图片文件", "*.png *.jpg *.bmp")])
        if path:
            setter_func(path)
            label_widget.config(text=os.path.basename(path))

    def on_click_multi(self, setter_func, label_widget):
        paths = filedialog.askopenfilenames(filetypes=[("图片文件", "*.png *.jpg *.bmp")])
        if paths:
            setter_func(list(paths))
            label_widget.config(text=f"已选择 {len(paths)} 张")

    def set_clean(self, path):
        self.clean_path = path

    def set_our(self, path):
        self.our_path = path

    def set_others(self, paths):
        self.other_paths = paths if isinstance(paths, list) else [paths]

    # ---------- 其他模型切换 ----------
    def update_other_controls(self):
        n = len(self.other_paths)
        self.lbl_other_count.config(text=f"其他模型: {n} 张")
        if n == 0:
            self.btn_prev.config(state=tk.DISABLED)
            self.btn_next.config(state=tk.DISABLED)
            self.lbl_other_name.config(text="")
        else:
            self.btn_prev.config(state=tk.NORMAL)
            self.btn_next.config(state=tk.NORMAL)
            self.current_other_index = 0
            self.show_other_name()

    def show_other_name(self):
        if self.other_paths:
            idx = self.current_other_index
            self.lbl_other_name.config(text=os.path.basename(self.other_paths[idx]))
        else:
            self.lbl_other_name.config(text="")

    def prev_other(self):
        if self.other_paths:
            self.current_other_index = (self.current_other_index - 1) % len(self.other_paths)
            self.show_other_name()
            self.refresh_other_display()

    def next_other(self):
        if self.other_paths:
            self.current_other_index = (self.current_other_index + 1) % len(self.other_paths)
            self.show_other_name()
            self.refresh_other_display()

    def refresh_other_display(self):
        if not self.marked_images or not self.other_paths:
            return
        path = self.other_paths[self.current_other_index]
        if path in self.marked_images:
            self.display_in_label(self.result_labels[2], self.marked_images[path])

    # ---------- 生成逻辑 ----------
    def on_generate(self):
        if not self.clean_path:
            messagebox.showerror("错误", "请先拖入干净图像")
            return
        if not self.our_path:
            messagebox.showerror("错误", "请先拖入我们模型恢复图")
            return

        try:
            h = self.h.get()
            step = self.step.get()
            k = self.k.get()
            corner = self.corner.get()
            metric = self.metric.get()
        except:
            messagebox.showerror("错误", "参数必须为整数")
            return

        self.btn_generate.config(state=tk.DISABLED)
        self.root.config(cursor="watch")
        self.root.update()

        try:
            best_pos, marked_images, patches = process_images(
                self.clean_path, self.our_path, self.other_paths,
                h, step, k, corner, metric
            )
            self.marked_images = marked_images
            self.patches = patches
            self.current_other_index = 0
            self.update_other_controls()

            # 显示固定两张
            self.display_in_label(self.result_labels[0], marked_images["clean"])
            self.display_in_label(self.result_labels[1], marked_images["our"])
            # 显示当前其他
            if self.other_paths:
                self.show_other_name()
                self.refresh_other_display()
            else:
                self.result_labels[2].config(image="", text="无其他模型图")
                self.result_labels[2].image = None

            self.btn_save.config(state=tk.NORMAL)
            messagebox.showinfo("完成", f"生成成功！最佳窗口位置: {best_pos}")
        except Exception as e:
            messagebox.showerror("处理失败", str(e))
        finally:
            self.btn_generate.config(state=tk.NORMAL)
            self.root.config(cursor="")

    def display_in_label(self, label_widget, pil_img):
        max_w = label_widget.winfo_width()
        max_h = label_widget.winfo_height()
        if max_w < 20: max_w = 300
        if max_h < 20: max_h = 250
        img_w, img_h = pil_img.size
        scale = min(max_w / img_w, max_h / img_h, 1.0)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        resized = pil_img.resize((new_w, new_h), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(resized)
        label_widget.config(image=tk_img, text="")
        label_widget.image = tk_img

    # ---------- 保存全部 ----------
    def on_save_all(self):
        if not self.marked_images:
            messagebox.showwarning("警告", "尚未生成结果")
            return
        dir_path = filedialog.askdirectory(title="选择保存目录")
        if not dir_path:
            return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        try:
            # 保存所有标记图
            for name, img in self.marked_images.items():
                if name == "clean":
                    fname = f"marked_clean_{timestamp}.png"
                elif name == "our":
                    fname = f"marked_our_{timestamp}.png"
                else:
                    base = os.path.splitext(os.path.basename(name))[0]
                    fname = f"marked_other_{base}_{timestamp}.png"
                img.save(os.path.join(dir_path, fname))

            # 保存局部放大图（可选）
            for name, patch in self.patches.items():
                if name == "clean":
                    fname = f"patch_clean_{timestamp}.png"
                elif name == "our":
                    fname = f"patch_our_{timestamp}.png"
                else:
                    base = os.path.splitext(os.path.basename(name))[0]
                    fname = f"patch_other_{base}_{timestamp}.png"
                patch.save(os.path.join(dir_path, fname))

            messagebox.showinfo("保存成功", f"全部图片已保存至:\n{dir_path}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


if __name__ == "__main__":
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = App(root)
    root.mainloop()