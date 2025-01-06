import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, colorchooser
import os
import yaml
import threading
import queue
import logging
from datetime import datetime
from video_automater11 import (
    process_video, load_config, get_parameters_from_config,
    get_platform_defaults
)
from typing import Dict, Any, Tuple, List
import cv2
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import numpy as np
import subprocess

# A small list of fonts for demonstration.
COMMON_FONTS = ["Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana"]

def safe_color_for_chooser(hex_str: str) -> str:
    """
    If the hex has 8 digits (like #00000000),
    strip alpha so colorchooser doesn't crash.
    """
    hex_str = hex_str.strip()
    if hex_str.startswith("#"):
        hex_str = hex_str[1:]
    if len(hex_str) == 8:  # remove alpha for colorchooser
        hex_str = hex_str[:6]
    return f"#{hex_str}"

def ImageColor_getrgba(hex_str):
    """
    Converts a hex color (#RRGGBB or #RRGGBBAA) to an RGBA tuple (R, G, B, A).
    If alpha not provided, defaults to 255.
    """
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return (r, g, b, 255)
    elif len(hex_str) == 8:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        a = int(hex_str[6:8], 16)
        return (r, g, b, a)
    return (255, 255, 255, 255)

class OverlayEditorDialog:
    """
    A dialog for editing/creating a single text overlay in real time.
    Changes are pushed immediately via on_change_callback.
    """
    def __init__(self, parent, overlay_data, on_change_callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Text Overlay")
        self.dialog.geometry("380x480")
        self.dialog.transient(parent)

        self.overlay_data = overlay_data
        self.on_change_callback = on_change_callback

        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(expand=True, fill='both')

        row_idx = 0
        # Text
        ttk.Label(main_frame, text="Text:").grid(row=row_idx, column=0, sticky=tk.W)
        self.text_var = tk.StringVar(value=self.overlay_data.get("text", ""))
        text_entry = ttk.Entry(main_frame, textvariable=self.text_var)
        text_entry.grid(row=row_idx, column=1, pady=2, sticky=tk.EW)
        text_entry.bind("<KeyRelease>", self.update_overlay)
        row_idx += 1

        # Font
        ttk.Label(main_frame, text="Font:").grid(row=row_idx, column=0, sticky=tk.W)
        self.font_var = tk.StringVar(value=self.overlay_data.get("font", "Arial"))
        self.font_combo = ttk.Combobox(
            main_frame,
            textvariable=self.font_var,
            values=COMMON_FONTS,
            state="readonly"
        )
        self.font_combo.grid(row=row_idx, column=1, pady=2, sticky=tk.EW)
        self.font_combo.bind("<<ComboboxSelected>>", self.update_overlay)
        row_idx += 1

        # Size
        ttk.Label(main_frame, text="Size:").grid(row=row_idx, column=0, sticky=tk.W)
        self.size_var = tk.IntVar(value=self.overlay_data.get("size", 24))
        size_spin = ttk.Spinbox(
            main_frame,
            from_=8, to=300, increment=2, textvariable=self.size_var,
            command=self.update_overlay
        )
        size_spin.grid(row=row_idx, column=1, pady=2, sticky=tk.EW)
        size_spin.bind("<KeyRelease>", self.update_overlay)
        row_idx += 1

        # Color
        ttk.Label(main_frame, text="Color:").grid(row=row_idx, column=0, sticky=tk.W)
        color_frame = ttk.Frame(main_frame)
        color_frame.grid(row=row_idx, column=1, pady=2, sticky=tk.EW)
        self.color_var = tk.StringVar(value=self.overlay_data.get("color", "#FFFFFF"))
        color_entry = ttk.Entry(color_frame, textvariable=self.color_var, width=10)
        color_entry.pack(side=tk.LEFT)
        ttk.Button(color_frame, text="Pick", command=self.pick_text_color).pack(side=tk.LEFT, padx=5)
        row_idx += 1

        # BG Color + Opacity
        ttk.Label(main_frame, text="BG Color:").grid(row=row_idx, column=0, sticky=tk.W)
        bg_frame = ttk.Frame(main_frame)
        bg_frame.grid(row=row_idx, column=1, pady=2, sticky=tk.EW)
        self.bg_color_var = tk.StringVar(value=self.overlay_data.get("bg_color", "#00000000"))
        bg_entry = ttk.Entry(bg_frame, textvariable=self.bg_color_var, width=10)
        bg_entry.pack(side=tk.LEFT)
        ttk.Button(bg_frame, text="Pick", command=self.pick_bg_color).pack(side=tk.LEFT, padx=5)
        row_idx += 1

        ttk.Label(main_frame, text="BG Opacity:").grid(row=row_idx, column=0, sticky=tk.W)
        self.bg_opacity_var = tk.DoubleVar(value=self.overlay_data.get("bg_opacity", 0.0))
        bg_opacity_spin = ttk.Spinbox(
            main_frame,
            from_=0.0, to=1.0, increment=0.1, textvariable=self.bg_opacity_var,
            command=self.update_overlay
        )
        bg_opacity_spin.grid(row=row_idx, column=1, pady=2, sticky=tk.EW)
        bg_opacity_spin.bind("<KeyRelease>", self.update_overlay)
        row_idx += 1

        # Position
        pos_frame = ttk.LabelFrame(main_frame, text="Position (%)")
        pos_frame.grid(row=row_idx, column=0, columnspan=2, pady=5, sticky=tk.EW)
        pos_frame.columnconfigure(1, weight=1)

        ttk.Label(pos_frame, text="X%:").grid(row=0, column=0, sticky=tk.W)
        self.x_var = tk.DoubleVar(value=self.overlay_data.get("x", 50.0))
        x_spin = ttk.Spinbox(pos_frame, from_=0, to=100, increment=1,
                             textvariable=self.x_var,
                             command=self.update_overlay)
        x_spin.grid(row=0, column=1, padx=2, pady=2, sticky=tk.EW)
        x_spin.bind("<KeyRelease>", self.update_overlay)

        ttk.Label(pos_frame, text="Y%:").grid(row=0, column=2, sticky=tk.W)
        self.y_var = tk.DoubleVar(value=self.overlay_data.get("y", 50.0))
        y_spin = ttk.Spinbox(pos_frame, from_=0, to=100, increment=1,
                             textvariable=self.y_var,
                             command=self.update_overlay)
        y_spin.grid(row=0, column=3, padx=2, pady=2, sticky=tk.EW)
        y_spin.bind("<KeyRelease>", self.update_overlay)
        row_idx += 1

        # Outline & Shadow
        style_frame = ttk.Frame(main_frame)
        style_frame.grid(row=row_idx, column=0, columnspan=2, sticky=tk.EW, pady=5)
        self.outline_var = tk.BooleanVar(value=self.overlay_data.get("outline", False))
        ttk.Checkbutton(style_frame, text="Outline", variable=self.outline_var,
                        command=self.update_overlay).pack(side=tk.LEFT, padx=5)
        self.shadow_var = tk.BooleanVar(value=self.overlay_data.get("shadow", False))
        ttk.Checkbutton(style_frame, text="Shadow", variable=self.shadow_var,
                        command=self.update_overlay).pack(side=tk.LEFT, padx=5)
        row_idx += 1

        # Close button
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row_idx, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(side=tk.RIGHT, padx=5)

        for col in range(2):
            main_frame.columnconfigure(col, weight=1)

    def pick_text_color(self):
        initial = safe_color_for_chooser(self.color_var.get())
        c = colorchooser.askcolor(initialcolor=initial)
        if c and c[1]:
            self.color_var.set(c[1])
            self.update_overlay()

    def pick_bg_color(self):
        initial = safe_color_for_chooser(self.bg_color_var.get())
        c = colorchooser.askcolor(initialcolor=initial)
        if c and c[1]:
            self.bg_color_var.set(c[1])
            self.update_overlay()

    def update_overlay(self, *args):
        self.overlay_data["text"] = self.text_var.get()
        self.overlay_data["font"] = self.font_var.get()
        self.overlay_data["size"] = self.size_var.get()
        self.overlay_data["color"] = self.color_var.get()
        self.overlay_data["bg_color"] = self.bg_color_var.get()
        self.overlay_data["bg_opacity"] = self.bg_opacity_var.get()
        self.overlay_data["x"] = self.x_var.get()
        self.overlay_data["y"] = self.y_var.get()
        self.overlay_data["outline"] = self.outline_var.get()
        self.overlay_data["shadow"] = self.shadow_var.get()

        # Notify parent for real-time preview update
        self.on_change_callback()

    def close_dialog(self):
        self.dialog.destroy()


class TextOverlaysDialog:
    """
    Manages multiple text overlays in a list (add, edit, remove, reorder).
    """
    def __init__(self, parent, text_overlays, on_change_callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Text Overlays")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)

        self.text_overlays = text_overlays
        self.on_change_callback = on_change_callback

        main_frame = ttk.Frame(self.dialog, padding=5)
        main_frame.pack(expand=True, fill='both')

        list_frame = ttk.LabelFrame(main_frame, text="Overlays")
        list_frame.pack(side=tk.LEFT, fill='both', expand=True)

        self.overlay_listbox = tk.Listbox(list_frame, height=15)
        self.overlay_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        scroll = ttk.Scrollbar(list_frame, command=self.overlay_listbox.yview)
        scroll.pack(side=tk.RIGHT, fill='y')
        self.overlay_listbox.config(yscrollcommand=scroll.set)

        self.refresh_listbox()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.RIGHT, fill='y', padx=5)
        ttk.Button(btn_frame, text="Add", command=self.add_overlay).pack(pady=2, fill='x')
        ttk.Button(btn_frame, text="Edit", command=self.edit_overlay).pack(pady=2, fill='x')
        ttk.Button(btn_frame, text="Remove", command=self.remove_overlay).pack(pady=2, fill='x')
        ttk.Button(btn_frame, text="Up", command=self.move_up).pack(pady=2, fill='x')
        ttk.Button(btn_frame, text="Down", command=self.move_down).pack(pady=2, fill='x')
        ttk.Button(btn_frame, text="Close", command=self.close_dialog).pack(pady=20, fill='x')

        self.overlay_listbox.bind("<Double-Button-1>", lambda e: self.edit_overlay())

    def refresh_listbox(self):
        self.overlay_listbox.delete(0, tk.END)
        for i, ov in enumerate(self.text_overlays):
            text_str = ov.get("text", "(no text)")
            self.overlay_listbox.insert(tk.END, f"{i+1}. {text_str}")

    def add_overlay(self):
        new_overlay = {
            "text": "New Overlay",
            "font": "Arial",
            "size": 40,
            "color": "#FFFFFF",
            "bg_color": "#00000000",
            "bg_opacity": 0.0,
            "x": 50.0,
            "y": 50.0,
            "outline": False,
            "shadow": False
        }
        self.text_overlays.append(new_overlay)
        self.refresh_listbox()
        self.on_change_callback()
        idx = len(self.text_overlays) - 1
        self.overlay_listbox.select_set(idx)
        self.edit_overlay()

    def edit_overlay(self):
        sel = self.overlay_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        overlay_data = self.text_overlays[idx]

        def refresh_callback():
            self.on_change_callback()
            self.refresh_listbox()

        OverlayEditorDialog(self.dialog, overlay_data, refresh_callback)

    def remove_overlay(self):
        sel = self.overlay_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.text_overlays[idx]
        self.refresh_listbox()
        self.on_change_callback()

    def move_up(self):
        sel = self.overlay_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self.text_overlays[idx-1], self.text_overlays[idx] = self.text_overlays[idx], self.text_overlays[idx-1]
        self.refresh_listbox()
        self.overlay_listbox.select_set(idx-1)
        self.on_change_callback()

    def move_down(self):
        sel = self.overlay_listbox.curselection()
        if not sel or sel[0] == len(self.text_overlays)-1:
            return
        idx = sel[0]
        self.text_overlays[idx+1], self.text_overlays[idx] = self.text_overlays[idx], self.text_overlays[idx+1]
        self.refresh_listbox()
        self.overlay_listbox.select_set(idx+1)
        self.on_change_callback()

    def close_dialog(self):
        self.dialog.destroy()


class CustomSettingsDialog:
    def __init__(self, parent, preview_callback, session_settings=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Custom Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        
        if session_settings is None:
            session_settings = {}

        self.video_position = tk.BooleanVar(
            value=session_settings.get('video_position', {}).get('enabled', False)
        )
        self.video_position_height = tk.StringVar(
            value=str(session_settings.get('video_position', {}).get('height', 20))
        )
        self.video_position_opacity = tk.StringVar(
            value=str(session_settings.get('video_position', {}).get('opacity', 0.5))
        )
        self.video_position_type = tk.StringVar(
            value=session_settings.get('video_position', {}).get('position', 'center')
        )
        self.video_scale = tk.StringVar(
            value=str(int(session_settings.get('video_position', {}).get('scale', 1.0) * 100))
        )
        
        self.top_bg = tk.BooleanVar(
            value=session_settings.get('top_bg', {}).get('enabled', False)
        )
        self.top_bg_height = tk.StringVar(
            value=str(session_settings.get('top_bg', {}).get('height', 15))
        )
        self.top_bg_opacity = tk.StringVar(
            value=str(session_settings.get('top_bg', {}).get('opacity', 0.5))
        )
        
        self.bottom_bg = tk.BooleanVar(
            value=session_settings.get('bottom_bg', {}).get('enabled', False)
        )
        self.bottom_bg_height = tk.StringVar(
            value=str(session_settings.get('bottom_bg', {}).get('height', 15))
        )
        self.bottom_bg_opacity = tk.StringVar(
            value=str(session_settings.get('bottom_bg', {}).get('opacity', 0.5))
        )
        
        self.icon_width = tk.StringVar(
            value=str(session_settings.get('icon', {}).get('width', 400))
        )
        self.icon_x_pos = tk.StringVar(
            value=session_settings.get('icon', {}).get('x_position', 'c')
        )
        self.icon_y_pos = tk.StringVar(
            value=str(session_settings.get('icon', {}).get('y_position', 90))
        )

        self.text_overlays = session_settings.get('text_overlays', [])

        self.preview_callback = preview_callback
        self.result = None

        self.create_widgets()

    def create_widgets(self):
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Video Position
        vp_frame = ttk.Frame(notebook, padding="10")
        notebook.add(vp_frame, text='Video Position')
        
        ttk.Label(vp_frame, text="Video Position:").pack()
        ttk.Radiobutton(vp_frame, text="Center", value="center", variable=self.video_position_type).pack()
        ttk.Radiobutton(vp_frame, text="Top", value="top", variable=self.video_position_type).pack()
        ttk.Radiobutton(vp_frame, text="Bottom", value="bottom", variable=self.video_position_type).pack()
        
        ttk.Label(vp_frame, text="Video Scale (50-100%):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_scale).pack()
        
        ttk.Separator(vp_frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(vp_frame, text="Black Background:").pack()
        ttk.Checkbutton(vp_frame, text="Enable Background", variable=self.video_position).pack()
        ttk.Label(vp_frame, text="Background Height (10-50%):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_position_height).pack()
        ttk.Label(vp_frame, text="Background Opacity (0.0-1.0):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_position_opacity).pack()
        
        # Top Background
        top_frame = ttk.Frame(notebook, padding="10")
        notebook.add(top_frame, text='Top Background')
        ttk.Checkbutton(top_frame, text="Enable Top Background", variable=self.top_bg).pack()
        ttk.Label(top_frame, text="Background Height (5-30%):").pack()
        ttk.Entry(top_frame, textvariable=self.top_bg_height).pack()
        ttk.Label(top_frame, text="Background Opacity (0.0-1.0):").pack()
        ttk.Entry(top_frame, textvariable=self.top_bg_opacity).pack()
        
        # Bottom Background
        bottom_frame = ttk.Frame(notebook, padding="10")
        notebook.add(bottom_frame, text='Bottom Background')
        ttk.Checkbutton(bottom_frame, text="Enable Bottom Background", variable=self.bottom_bg).pack()
        ttk.Label(bottom_frame, text="Background Height (5-30%):").pack()
        ttk.Entry(bottom_frame, textvariable=self.bottom_bg_height).pack()
        ttk.Label(bottom_frame, text="Background Opacity (0.0-1.0):").pack()
        ttk.Entry(bottom_frame, textvariable=self.bottom_bg_opacity).pack()
        
        # Icon
        icon_frame = ttk.Frame(notebook, padding="10")
        notebook.add(icon_frame, text='Icon Settings')
        ttk.Label(icon_frame, text="Icon Width (100-1000px):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_width).pack()
        ttk.Label(icon_frame, text="X Pos (c= center, l= left, r= right, or 0-100):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_x_pos).pack()
        ttk.Label(icon_frame, text="Y Pos (0-100%):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_y_pos).pack()

        # Text Overlays
        text_frame = ttk.Frame(notebook, padding="10")
        notebook.add(text_frame, text="Text Overlays")
        ttk.Label(text_frame, text="Manage multiple text overlays:").pack(anchor="w", pady=5)
        ttk.Button(text_frame, text="Open Overlays Manager", command=self.open_overlays_dialog).pack(pady=5, anchor="w")
        ttk.Label(text_frame, text="Changes appear immediately in preview.").pack(anchor="w")

        # OK/Cancel
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="OK", command=self.ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side='right')

        # Traces
        self.video_position.trace_add("write", self.on_setting_changed)
        self.video_position_height.trace_add("write", self.on_setting_changed)
        self.video_position_opacity.trace_add("write", self.on_setting_changed)
        self.video_position_type.trace_add("write", self.on_setting_changed)
        self.video_scale.trace_add("write", self.on_setting_changed)
        self.top_bg.trace_add("write", self.on_setting_changed)
        self.top_bg_height.trace_add("write", self.on_setting_changed)
        self.top_bg_opacity.trace_add("write", self.on_setting_changed)
        self.bottom_bg.trace_add("write", self.on_setting_changed)
        self.bottom_bg_height.trace_add("write", self.on_setting_changed)
        self.bottom_bg_opacity.trace_add("write", self.on_setting_changed)
        self.icon_width.trace_add("write", self.on_setting_changed)
        self.icon_x_pos.trace_add("write", self.on_setting_changed)
        self.icon_y_pos.trace_add("write", self.on_setting_changed)

    def open_overlays_dialog(self):
        def overlays_changed():
            self.on_setting_changed()
        TextOverlaysDialog(self.dialog, self.text_overlays, overlays_changed)

    def on_setting_changed(self, *args):
        try:
            settings = {
                'video_position': {
                    'enabled': self.video_position.get(),
                    'height': float(self.video_position_height.get()),
                    'opacity': float(self.video_position_opacity.get()),
                    'position': self.video_position_type.get(),
                    'scale': float(self.video_scale.get()) / 100.0
                },
                'top_bg': {
                    'enabled': self.top_bg.get(),
                    'height': float(self.top_bg_height.get()),
                    'opacity': float(self.top_bg_opacity.get())
                },
                'bottom_bg': {
                    'enabled': self.bottom_bg.get(),
                    'height': float(self.bottom_bg_height.get()),
                    'opacity': float(self.bottom_bg_opacity.get())
                },
                'icon': {
                    'width': int(self.icon_width.get()),
                    'x_position': self.icon_x_pos.get(),
                    'y_position': float(self.icon_y_pos.get())
                },
                'text_overlays': self.text_overlays
            }
            self.preview_callback(settings)
        except Exception:
            pass

    def ok(self):
        self.result = {
            'video_position': {
                'enabled': self.video_position.get(),
                'height': float(self.video_position_height.get()),
                'opacity': float(self.video_position_opacity.get()),
                'position': self.video_position_type.get(),
                'scale': float(self.video_scale.get()) / 100.0
            },
            'top_bg': {
                'enabled': self.top_bg.get(),
                'height': float(self.top_bg_height.get()),
                'opacity': float(self.top_bg_opacity.get())
            },
            'bottom_bg': {
                'enabled': self.bottom_bg.get(),
                'height': float(self.bottom_bg_height.get()),
                'opacity': float(self.bottom_bg_opacity.get())
            },
            'icon': {
                'width': int(self.icon_width.get()),
                'x_position': self.icon_x_pos.get(),
                'y_position': float(self.icon_y_pos.get())
            },
            'text_overlays': self.text_overlays
        }
        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()

class PreviewPanel:
    def __init__(self, parent, settings_callback):
        self.frame = ttk.LabelFrame(parent, text="Preview", padding="5")
        self.canvas = tk.Canvas(self.frame, width=400, height=600)
        self.canvas.pack(expand=True, fill='both')
        self.current_preview = None
        self.current_video = None
        self.settings_callback = settings_callback
        self.preview_image = None
        self.original_frame = None
        self.current_settings = {}
        self.current_dimensions = (1080, 1920)

    def extract_random_frame(self, video_path):
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return None
        random_frame = random.randint(0, max(0, total_frames - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            self.original_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return self.original_frame
        return None

    def update_preview(self, video_path=None, settings=None, dimensions=None):
        if settings is None:
            settings = {}
        self.current_settings.update(settings)

        if video_path and video_path != self.current_video:
            self.current_video = video_path
            self.extract_random_frame(video_path)

        if dimensions:
            self.current_dimensions = dimensions

        if self.original_frame is not None:
            frame = self.apply_settings_to_frame(
                self.original_frame.copy(),
                self.current_settings,
                self.current_dimensions
            )
            if frame is not None:
                disp_w, disp_h = 400, 600
                scale = min(disp_w / frame.shape[1], disp_h / frame.shape[0])
                display_size = (int(frame.shape[1] * scale), int(frame.shape[0] * scale))
                frame = cv2.resize(frame, display_size)

                image = Image.fromarray(frame)
                self.preview_image = ImageTk.PhotoImage(image)
                self.canvas.delete("all")
                self.canvas.create_image(
                    disp_w // 2,
                    disp_h // 2,
                    anchor='center',
                    image=self.preview_image
                )

    def apply_settings_to_frame(self, frame, settings, dimensions):
        if frame is None:
            return None

        target_w, target_h = dimensions
        h, w = frame.shape[:2]
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))

        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2

        video_pos = settings.get("video_position", {})
        if video_pos.get("enabled", False):
            pos_type = video_pos.get("position", "center")
            scale_factor = video_pos.get("scale", 1.0)

            if scale_factor != 1.0:
                new_w = int(new_w * scale_factor)
                new_h = int(new_h * scale_factor)
                resized = cv2.resize(frame, (new_w, new_h))

            if pos_type == "top":
                x_offset = (target_w - new_w) // 2
                y_offset = 0
            elif pos_type == "bottom":
                x_offset = (target_w - new_w) // 2
                bg_h = int(target_h * (video_pos.get("height", 0) / 100.0))
                y_offset = target_h - new_h - bg_h
            else:
                x_offset = (target_w - new_w) // 2
                y_offset = (target_h - new_h) // 2

        canvas[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = resized

        if video_pos.get("enabled", False):
            height_percent = video_pos.get("height", 20)
            opacity = video_pos.get("opacity", 0.5)
            hpix = int(target_h * (height_percent / 100))
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, target_h - hpix), (target_w, target_h), (0,0,0), -1)
            canvas = cv2.addWeighted(overlay, opacity, canvas, 1 - opacity, 0)

        top_bg = settings.get("top_bg", {})
        if top_bg.get("enabled", False):
            hp = top_bg.get("height", 15)
            op = top_bg.get("opacity", 0.5)
            top_pix = int(target_h * (hp / 100))
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, 0), (target_w, top_pix), (0,0,0), -1)
            canvas = cv2.addWeighted(overlay, op, canvas, 1 - op, 0)

        bottom_bg = settings.get("bottom_bg", {})
        if bottom_bg.get("enabled", False):
            hp = bottom_bg.get("height", 15)
            op = bottom_bg.get("opacity", 0.5)
            bot_pix = int(target_h * (hp / 100))
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, target_h - bot_pix), (target_w, target_h), (0,0,0), -1)
            canvas = cv2.addWeighted(overlay, op, canvas, 1 - op, 0)

        icon_params = settings.get("icon", {})
        if os.path.exists("assets/fullicon.png"):
            try:
                icon_img = cv2.imread("assets/fullicon.png", cv2.IMREAD_UNCHANGED)
                if icon_img is not None and icon_img.shape[2] == 4:
                    iw = icon_params.get("width", 400)
                    iw = min(iw, target_w)
                    oh, ow = icon_img.shape[:2]
                    ratio = oh / ow
                    ih = int(iw * ratio)
                    if ih > target_h:
                        ih = target_h
                        iw = int(ih / ratio)
                    icon_img = cv2.resize(icon_img, (iw, ih))
                    x_pos = icon_params.get("x_position", "c")
                    y_pos = float(icon_params.get("y_position", 90.0))

                    if x_pos == 'c':
                        x = (target_w - iw) // 2
                    elif x_pos == 'l':
                        x = 10
                    elif x_pos == 'r':
                        x = target_w - iw - 10
                    else:
                        x = int(target_w * (float(x_pos) / 100.0))

                    y = int(target_h * (y_pos / 100.0))
                    x = max(0, min(x, target_w - iw))
                    y = max(0, min(y, target_h - ih))

                    alpha = icon_img[:, :, 3] / 255.0
                    alpha = np.dstack([alpha, alpha, alpha])
                    bgr = icon_img[:, :, :3]

                    roi = canvas[y:y+ih, x:x+iw]
                    if roi.shape[:2] == bgr.shape[:2]:
                        blended = roi * (1 - alpha) + bgr * alpha
                        canvas[y:y+ih, x:x+iw] = blended
            except Exception as e:
                print(f"Error applying icon: {str(e)}")

        # Now apply text overlays
        pil_image = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)

        for overlay in settings.get("text_overlays", []):
            self.draw_text_overlay(draw, overlay, target_w, target_h)

        final_canvas = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        return final_canvas

    def draw_text_overlay(self, draw, overlay, img_w, img_h):
        text = overlay.get("text", "Text")
        font_name = overlay.get("font", "Arial")
        font_size = overlay.get("size", 40)
        color_hex = overlay.get("color", "#FFFFFF")
        bg_hex = overlay.get("bg_color", "#00000000")
        bg_opacity = overlay.get("bg_opacity", 0.0)
        x_pct = overlay.get("x", 50.0)
        y_pct = overlay.get("y", 50.0)
        outline = overlay.get("outline", False)
        shadow = overlay.get("shadow", False)

        try:
            font = ImageFont.truetype(font_name, font_size)
        except:
            font = ImageFont.load_default()

        text_color = ImageColor_getrgba(color_hex)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = int(img_w * (x_pct / 100.0))
        y = int(img_h * (y_pct / 100.0))
        x -= text_w // 2
        y -= text_h // 2

        if bg_opacity > 0.0:
            bg_rgba = ImageColor_getrgba(bg_hex)
            overlay_img = Image.new("RGBA", (text_w, text_h), (0,0,0,0))
            bg_layer = Image.new("RGBA", (text_w, text_h), bg_rgba)
            bg_layer.putalpha(int(bg_opacity * 255))
            overlay_img.alpha_composite(bg_layer, (0,0))
            draw.im.paste(overlay_img, (x, y), overlay_img)

        if shadow:
            shadow_offset = 2
            shadow_color = (0, 0, 0, 128)
            draw.text((x+shadow_offset, y+shadow_offset), text, font=font, fill=shadow_color)

        if outline:
            for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((x+ox, y+oy), text, font=font, fill=(0,0,0,255))

        draw.text((x, y), text, font=font, fill=text_color)

    def get_current_settings(self):
        return self.current_settings


class VideoEditorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Editor")
        self.root.geometry("1200x800")
        
        self.source_folder = tk.StringVar()
        self.platform = tk.StringVar(value="youtube_shorts")
        self.use_defaults = tk.BooleanVar(value=True)
        self.aspect_ratio = tk.StringVar(value="2")
        self.progress = tk.DoubleVar(value=0)
        self.processing = False
        self.selected_video = tk.StringVar()
        self.session_settings = None
        self.output_folder = tk.StringVar()
        self.selected_videos = set()
        self.current_preview_video = None
        
        self.config = load_config()
        
        self.create_gui()
        
        self.update_queue = queue.Queue()
        self.setup_logging()
        self.check_queue()
        
        self.aspect_ratio.trace_add("write", self.on_aspect_ratio_changed)

    def setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        log_file = os.path.join("logs", f"video_editor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', errors='replace'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        self.preview_panel = PreviewPanel(main_frame, self.get_custom_settings)
        self.preview_panel.frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        ttk.Label(controls_frame, text="Source Folder:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(controls_frame, textvariable=self.source_folder, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.browse_source).grid(row=0, column=2)

        ttk.Label(controls_frame, text="Output Folder (optional):").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(controls_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)

        video_selection_frame = ttk.LabelFrame(controls_frame, text="Video Selection", padding="5")
        video_selection_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        list_frame = ttk.Frame(video_selection_frame)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, height=6, yscrollcommand=scrollbar.set)
        self.video_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.config(command=self.video_listbox.yview)
        
        self.video_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)

        video_controls = ttk.Frame(video_selection_frame)
        video_controls.pack(fill='x', pady=5)

        left_buttons = ttk.Frame(video_controls)
        left_buttons.pack(side=tk.LEFT, fill='x', expand=True)
        
        ttk.Button(left_buttons, text="Select All", command=self.select_all_videos).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_buttons, text="Deselect All", command=self.deselect_all_videos).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_buttons, text="Remove Selected", command=self.remove_selected_videos).pack(side=tk.LEFT, padx=2)
        
        right_buttons = ttk.Frame(video_controls)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="Settings", command=self.show_settings).pack(side=tk.RIGHT, padx=2)
        ttk.Button(right_buttons, text="Preview Selected", command=self.preview_selected).pack(side=tk.RIGHT, padx=2)

        ttk.Label(controls_frame, text="Platform:").grid(row=4, column=0, sticky=tk.W, pady=10)
        platform_frame = ttk.Frame(controls_frame)
        platform_frame.grid(row=4, column=1, sticky=tk.W)
        
        platforms = [
            ("YouTube Shorts", "youtube_shorts"),
            ("Instagram", "instagram"),
            ("TikTok", "tiktok"),
            ("YouTube Long", "youtube_long")
        ]
        for i, (txt, val) in enumerate(platforms):
            ttk.Radiobutton(platform_frame, text=txt, value=val, variable=self.platform).grid(row=0, column=i, padx=5)

        ttk.Label(controls_frame, text="Aspect Ratio:").grid(row=5, column=0, sticky=tk.W, pady=10)
        ratio_frame = ttk.Frame(controls_frame)
        ratio_frame.grid(row=5, column=1, sticky=tk.W)
        
        ratios = [
            ("Square (1:1)", "1"),
            ("Portrait (9:16)", "2"),
            ("Landscape (16:9)", "3"),
            ("Custom", "4")
        ]
        for i, (txt, val) in enumerate(ratios):
            ttk.Radiobutton(ratio_frame, text=txt, value=val, variable=self.aspect_ratio).grid(row=0, column=i, padx=5)

        if self.config:
            ttk.Checkbutton(controls_frame, text="Use defaults from config.yaml", variable=self.use_defaults).grid(
                row=6, column=0, columnspan=2, sticky=tk.W, pady=10
            )

        ttk.Button(controls_frame, text="Advanced Settings", command=self.show_advanced_settings).grid(
            row=7, column=0, columnspan=2, pady=10
        )

        self.progress_bar = ttk.Progressbar(controls_frame, length=400, mode='determinate', variable=self.progress)
        self.progress_bar.grid(row=8, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(controls_frame, text="Ready")
        self.status_label.grid(row=9, column=0, columnspan=3)

        self.process_button = ttk.Button(controls_frame, text="Process Videos", command=self.start_processing)
        self.process_button.grid(row=10, column=0, columnspan=3, pady=10)
        
        ttk.Button(controls_frame, text="Process Selected Video", command=self.process_selected_video).grid(
            row=11, column=1, pady=10
        )

        log_frame = ttk.LabelFrame(controls_frame, text="Logs", padding=5)
        log_frame.grid(row=12, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_display = scrolledtext.ScrolledText(log_frame, height=10, width=60)
        self.log_display.pack(expand=True, fill='both')

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder.set(folder)
            self.update_video_list()

    def update_video_list(self):
        self.video_listbox.delete(0, tk.END)
        folder = self.source_folder.get()
        if folder:
            video_files = sorted(
                f for f in os.listdir(folder) if f.lower().endswith((".mp4", ".mov"))
            )
            for vf in video_files:
                self.video_listbox.insert(tk.END, vf)
            if video_files:
                self.video_listbox.select_set(0)
                self.preview_selected()

    def select_all_videos(self):
        self.video_listbox.select_set(0, tk.END)

    def deselect_all_videos(self):
        self.video_listbox.selection_clear(0, tk.END)

    def remove_selected_videos(self):
        sel = self.video_listbox.curselection()
        for idx in reversed(sel):
            self.video_listbox.delete(idx)

    def on_listbox_select(self, event):
        selection = self.video_listbox.curselection()
        if selection:
            selected_video = self.video_listbox.get(selection[-1])
            video_path = os.path.join(self.source_folder.get(), selected_video)
            if video_path != self.current_preview_video:
                self.current_preview_video = video_path
                self.preview_panel.update_preview(video_path=video_path)

    def preview_selected(self):
        sel = self.video_listbox.curselection()
        if sel:
            selected_video = self.video_listbox.get(sel[-1])
            video_path = os.path.join(self.source_folder.get(), selected_video)
            if video_path != self.current_preview_video:
                self.current_preview_video = video_path
                self.preview_panel.update_preview(video_path=video_path)

    def show_settings(self):
        dialog = CustomSettingsDialog(
            self.root,
            lambda s: self.preview_panel.update_preview(settings=s),
            self.session_settings if self.session_settings else {}
        )
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            self.session_settings = dialog.result
            return dialog.result
        return None

    def show_advanced_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Advanced Settings")
        win.geometry("400x500")
        ttk.Label(
            win,
            text=(
                "Here you could add advanced FFmpeg flags,\n"
                "GPU usage settings, or other advanced features.\n"
                "This is just a placeholder."
            )
        ).pack(pady=20)

    def process_selected_video(self):
        sel = self.video_listbox.curselection()
        if not sel:
            messagebox.showerror("Error", "No video selected!")
            return
        if self.processing:
            return

        self.processing = True
        self.process_button.config(state=tk.DISABLED)
        self.status_label.config(text="Processing video...")
        thread = threading.Thread(target=lambda: self.process_videos(single_video=True))
        thread.daemon = True
        thread.start()

    def start_processing(self):
        if not self.source_folder.get():
            messagebox.showerror("Error", "Select a source folder first.")
            return
        if self.processing:
            return

        self.processing = True
        self.process_button.config(state=tk.DISABLED)
        self.status_label.config(text="Processing videos...")
        thread = threading.Thread(target=self.process_videos)
        thread.daemon = True
        thread.start()

    def check_queue(self):
        try:
            while True:
                update_type, value = self.update_queue.get_nowait()
                if update_type == "progress":
                    self.progress.set(value)
                elif update_type == "log":
                    self.log_display.insert(tk.END, f"{value}\n")
                    self.log_display.see(tk.END)
                elif update_type == "complete":
                    self.process_complete()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def process_complete(self):
        self.processing = False
        self.process_button.config(state=tk.NORMAL)
        self.status_label.config(text="Processing complete!")
        messagebox.showinfo("Complete", "Video processing is finished.")

    def get_custom_settings(self):
        dialog = CustomSettingsDialog(self.root, lambda s: self.preview_panel.update_preview(settings=s))
        self.root.wait_window(dialog.dialog)
        return dialog.result

    def on_aspect_ratio_changed(self, *args):
        ratio_dims = {
            "1": (1080, 1080),
            "2": (1080, 1920),
            "3": (1920, 1080),
            "4": (1080, 1920)
        }
        dims = ratio_dims[self.aspect_ratio.get()]
        self.preview_panel.update_preview(dimensions=dims)

    def process_videos(self, single_video=False):
        try:
            platform_defaults = get_platform_defaults(self.config, self.platform.get())
            if self.use_defaults.get() and self.config:
                video_position_params, top_bg_params, black_bg_params, icon_params = \
                    get_parameters_from_config(self.config, platform_defaults)
                text_overlays = []
                if self.session_settings and 'text_overlays' in self.session_settings:
                    text_overlays = self.session_settings['text_overlays']
            else:
                settings = self.preview_panel.get_current_settings()
                if not settings:
                    messagebox.showerror("Error", "Please configure settings first.")
                    self.update_queue.put(("complete", None))
                    return

                text_overlays = settings.get("text_overlays", [])

                if settings['video_position']['enabled']:
                    video_position_params = {
                        'bottom_height_percent': float(settings['video_position']['height']),
                        'opacity': min(1.0, max(0.0, float(settings['video_position']['opacity'])))
                    }
                else:
                    video_position_params = None

                if settings['top_bg']['enabled']:
                    top_bg_params = {
                        'height_percent': float(settings['top_bg']['height']),
                        'opacity': min(1.0, max(0.0, float(settings['top_bg']['opacity'])))
                    }
                else:
                    top_bg_params = None

                if settings['bottom_bg']['enabled']:
                    black_bg_params = {
                        'height_percent': float(settings['bottom_bg']['height']),
                        'opacity': min(1.0, max(0.0, float(settings['bottom_bg']['opacity'])))
                    }
                else:
                    black_bg_params = None

                icon_params = {
                    'width': int(settings['icon']['width']),
                    'x_position': settings['icon']['x_position'],
                    'y_position': min(100.0, max(0.0, float(settings['icon']['y_position'])))
                }

            self.logger.info("Processing with parameters:")
            self.logger.info(f"video_position={video_position_params}, top_bg={top_bg_params}, bottom_bg={black_bg_params}, icon={icon_params}, text_overlays={text_overlays}")

            ratio_dims = {
                "1": (1080, 1080),
                "2": (1080, 1920),
                "3": (1920, 1080),
                "4": (1080, 1920)
            }
            target_dimensions = ratio_dims[self.aspect_ratio.get()]

            source_folder = self.source_folder.get()
            if self.output_folder.get():
                output_folder = self.output_folder.get()
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_folder = os.path.join(script_dir, "ai.waverider", self.platform.get())
            os.makedirs(output_folder, exist_ok=True)

            brand_icon = "assets/fullicon.png"
            if not os.path.isfile(brand_icon):
                raise FileNotFoundError(f"Brand icon not found at '{brand_icon}'")

            if single_video:
                sel = self.video_listbox.curselection()
                if not sel:
                    raise ValueError("No video selected")
                video_files = [self.video_listbox.get(sel[-1])]
            else:
                sel = self.video_listbox.curselection()
                if not sel:
                    video_files = [self.video_listbox.get(idx) for idx in range(self.video_listbox.size())]
                else:
                    video_files = [self.video_listbox.get(idx) for idx in sel]

            for i, vf in enumerate(video_files):
                input_path = os.path.join(source_folder, vf)
                output_path = os.path.join(output_folder, f"processed_{vf}")

                # Pass text_overlays to process_video for drawtext
                process_video((
                    input_path,
                    brand_icon,
                    output_path,
                    target_dimensions,
                    black_bg_params,
                    video_position_params,
                    top_bg_params,
                    icon_params,
                    text_overlays
                ))

                progress = (i + 1) / len(video_files) * 100
                self.update_queue.put(("progress", progress))
                self.update_queue.put(("log", f"Processed: {vf}"))

            self.update_queue.put(("complete", None))

        except Exception as e:
            self.logger.error(f"Error during processing: {str(e)}")
            self.update_queue.put(("log", f"Error: {str(e)}"))
            self.update_queue.put(("complete", None))

def main():
    root = tk.Tk()
    app = VideoEditorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
