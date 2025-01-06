# video_editor_gui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Y
import os
import yaml
import threading
import queue
import logging
from datetime import datetime
from video_automater11 import process_video, load_config, get_parameters_from_config, get_platform_defaults, generate_filter_complex
from typing import Dict, Any, Tuple
import cv2
from PIL import Image, ImageTk
import random
import numpy as np
import subprocess

class CustomSettingsDialog:
    def __init__(self, parent, preview_callback, session_settings=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Custom Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        
        # Initialize variables with session settings if available, otherwise use defaults
        self.video_position = tk.BooleanVar(value=session_settings.get('video_position', {}).get('enabled', False) if session_settings else False)
        self.video_position_height = tk.StringVar(value=str(session_settings.get('video_position', {}).get('height', 20)) if session_settings else "20")
        self.video_position_opacity = tk.StringVar(value=str(session_settings.get('video_position', {}).get('opacity', 0.5)) if session_settings else "0.5")
        self.video_position_type = tk.StringVar(value=session_settings.get('video_position', {}).get('position', 'center') if session_settings else "center")
        self.video_scale = tk.StringVar(value=str(int(session_settings.get('video_position', {}).get('scale', 1.0) * 100)) if session_settings else "100")
        
        self.top_bg = tk.BooleanVar(value=session_settings.get('top_bg', {}).get('enabled', False) if session_settings else False)
        self.top_bg_height = tk.StringVar(value=str(session_settings.get('top_bg', {}).get('height', 15)) if session_settings else "15")
        self.top_bg_opacity = tk.StringVar(value=str(session_settings.get('top_bg', {}).get('opacity', 0.5)) if session_settings else "0.5")
        
        self.bottom_bg = tk.BooleanVar(value=session_settings.get('bottom_bg', {}).get('enabled', False) if session_settings else False)
        self.bottom_bg_height = tk.StringVar(value=str(session_settings.get('bottom_bg', {}).get('height', 15)) if session_settings else "15")
        self.bottom_bg_opacity = tk.StringVar(value=str(session_settings.get('bottom_bg', {}).get('opacity', 0.5)) if session_settings else "0.5")
        
        self.icon_width = tk.StringVar(value=str(session_settings.get('icon', {}).get('width', 400)) if session_settings else "400")
        self.icon_x_pos = tk.StringVar(value=session_settings.get('icon', {}).get('x_position', 'c') if session_settings else "c")
        self.icon_y_pos = tk.StringVar(value=str(session_settings.get('icon', {}).get('y_position', 90)) if session_settings else "90")
        
        self.create_widgets()
        self.result = None
        self.preview_callback = preview_callback

    def create_widgets(self):
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Video Position Frame with updated controls
        vp_frame = ttk.Frame(notebook, padding="10")
        notebook.add(vp_frame, text='Video Position')
        
        # Video positioning options
        ttk.Label(vp_frame, text="Video Position:").pack()
        ttk.Radiobutton(vp_frame, text="Center", value="center", 
                       variable=self.video_position_type).pack()
        ttk.Radiobutton(vp_frame, text="Top", value="top", 
                       variable=self.video_position_type).pack()
        ttk.Radiobutton(vp_frame, text="Bottom", value="bottom", 
                       variable=self.video_position_type).pack()
        
        ttk.Label(vp_frame, text="Video Scale (50-100%):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_scale).pack()
        
        # Black background options
        ttk.Separator(vp_frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(vp_frame, text="Black Background:").pack()
        ttk.Checkbutton(vp_frame, text="Enable Background", 
                       variable=self.video_position).pack()
        ttk.Label(vp_frame, text="Background Height (10-50%):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_position_height).pack()
        ttk.Label(vp_frame, text="Background Opacity (0.0-1.0):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_position_opacity).pack()
        
        # Top Background Frame with updated labels
        top_frame = ttk.Frame(notebook, padding="10")
        notebook.add(top_frame, text='Top Background')
        ttk.Checkbutton(top_frame, text="Enable Top Background", variable=self.top_bg).pack()
        ttk.Label(top_frame, text="Background Height (5-30%):").pack()
        ttk.Entry(top_frame, textvariable=self.top_bg_height).pack()
        ttk.Label(top_frame, text="Background Opacity (0.0-1.0):").pack()
        ttk.Entry(top_frame, textvariable=self.top_bg_opacity).pack()
        
        # Bottom Background Frame with updated labels
        bottom_frame = ttk.Frame(notebook, padding="10")
        notebook.add(bottom_frame, text='Bottom Background')
        ttk.Checkbutton(bottom_frame, text="Enable Bottom Background", variable=self.bottom_bg).pack()
        ttk.Label(bottom_frame, text="Background Height (5-30%):").pack()
        ttk.Entry(bottom_frame, textvariable=self.bottom_bg_height).pack()
        ttk.Label(bottom_frame, text="Background Opacity (0.0-1.0):").pack()
        ttk.Entry(bottom_frame, textvariable=self.bottom_bg_opacity).pack()
        
        # Icon Settings Frame with updated labels
        icon_frame = ttk.Frame(notebook, padding="10")
        notebook.add(icon_frame, text='Icon Settings')
        ttk.Label(icon_frame, text="Icon Width (100-1000px):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_width).pack()
        ttk.Label(icon_frame, text="X Position (c=center, l=left, r=right, 0-100):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_x_pos).pack()
        ttk.Label(icon_frame, text="Y Position (0-100%):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_y_pos).pack()
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(button_frame, text="OK", command=self.ok).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='right')
        
        # Add change callbacks to all settings
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
                }
            }
            self.preview_callback(settings)
        except (ValueError, TypeError):
            pass  # Ignore invalid values during typing

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
            }
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
        self.current_settings = None
        self.current_dimensions = (1080, 1920)  # Default dimensions

    def extract_random_frame(self, video_path):
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return None
        random_frame = random.randint(0, total_frames-1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame)
        ret, frame = cap.read()
        cap.release()
        if ret:
            self.original_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return self.original_frame
        return None

    def apply_settings_to_frame(self, frame, settings, dimensions):
        if frame is None:
            return None
            
        # Initialize default settings if none provided
        if settings is None:
            settings = {}
        
        # Ensure required settings structures exist
        if 'video_position' not in settings:
            settings['video_position'] = {'enabled': False}
        if 'top_bg' not in settings:
            settings['top_bg'] = {'enabled': False}
        if 'bottom_bg' not in settings:
            settings['bottom_bg'] = {'enabled': False}
        if 'icon' not in settings:
            settings['icon'] = {
                'width': 400,
                'x_position': 'c',
                'y_position': 90
            }
        if 'text_overlays' not in settings:
            settings['text_overlays'] = []
            
        target_width, target_height = dimensions
        current_height, current_width = frame.shape[:2]
        
        # Default scaling without any position adjustments
        scale = min(target_width/current_width, target_height/current_height)
        new_width = int(current_width * scale)
        new_height = int(current_height * scale)
        
        # Resize frame
        resized = cv2.resize(frame, (new_width, new_height))
        
        # Create canvas
        canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        
        # Always center by default unless explicitly positioned
        x_offset = (target_width - new_width) // 2
        y_offset = (target_height - new_height) // 2
        
        # Only adjust position if video position is enabled and settings exist
        if settings and 'video_position' in settings and settings['video_position'].get('enabled', False):
            position = settings['video_position'].get('position', 'center')
            scale_factor = settings['video_position'].get('scale', 1.0)
            
            # Recalculate size if scale is changed
            if scale_factor != 1.0:
                new_width = int(new_width * scale_factor)
                new_height = int(new_height * scale_factor)
                resized = cv2.resize(frame, (new_width, new_height))
                x_offset = (target_width - new_width) // 2
            
            # Adjust vertical position
            if position == 'top':
                y_offset = 0
            elif position == 'bottom':
                y_offset = target_height - new_height
                # Adjust for black background if enabled
                if settings['video_position']['enabled']:
                    bg_height = int(target_height * (settings['video_position']['height'] / 100))
                    y_offset = target_height - new_height - bg_height
        
        # Place video on canvas
        canvas[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
        
        # Apply effects only if explicitly enabled
        if settings:
            # Apply video position background
            if settings['video_position']['enabled']:
                height_percent = settings['video_position']['height']
                opacity = settings['video_position']['opacity']
                height_pixels = int(target_height * (height_percent / 100))
                overlay = canvas.copy()
                cv2.rectangle(overlay, (0, target_height-height_pixels), 
                            (target_width, target_height), (0,0,0), -1)
                canvas = cv2.addWeighted(overlay, opacity, canvas, 1-opacity, 0)
            
            # Apply top background
            if settings['top_bg']['enabled']:
                height_percent = settings['top_bg']['height']
                opacity = settings['top_bg']['opacity']
                height_pixels = int(target_height * (height_percent / 100))
                overlay = canvas.copy()
                cv2.rectangle(overlay, (0, 0), (target_width, height_pixels), 
                            (0,0,0), -1)
                canvas = cv2.addWeighted(overlay, opacity, canvas, 1-opacity, 0)
            
            # Apply bottom background
            if settings['bottom_bg']['enabled']:
                height_percent = settings['bottom_bg']['height']
                opacity = settings['bottom_bg']['opacity']
                height_pixels = int(target_height * (height_percent / 100))
                overlay = canvas.copy()
                cv2.rectangle(overlay, (0, target_height-height_pixels), 
                            (target_width, target_height), (0,0,0), -1)
                canvas = cv2.addWeighted(overlay, opacity, canvas, 1-opacity, 0)
                
            # Apply icon if available
            if os.path.exists("assets/fullicon.png"):
                try:
                    # Read icon with alpha channel
                    icon = cv2.imread("assets/fullicon.png", cv2.IMREAD_UNCHANGED)
                    if icon is not None and icon.shape[2] == 4:  # Ensure alpha channel exists
                        # Calculate icon dimensions
                        icon_width = min(settings['icon']['width'], target_width)
                        aspect_ratio = icon.shape[0] / icon.shape[1]
                        icon_height = int(icon_width * aspect_ratio)
                        
                        # Ensure icon fits within frame
                        if icon_height > target_height:
                            icon_height = target_height
                            icon_width = int(icon_height / aspect_ratio)
                            
                        # Resize icon
                        icon = cv2.resize(icon, (icon_width, icon_height))
                        
                        # Calculate position
                        x_pos = settings['icon']['x_position']
                        if x_pos == 'c':
                            x = (target_width - icon_width) // 2
                        elif x_pos == 'l':
                            x = 10
                        elif x_pos == 'r':
                            x = target_width - icon_width - 10
                        else:
                            try:
                                x_percentage = float(x_pos)
                                x = int(target_width * (x_percentage / 100))
                            except ValueError:
                                x = (target_width - icon_width) // 2  # Default to center if invalid
                                
                        y = int(target_height * (settings['icon']['y_position'] / 100))
                        
                        # Ensure coordinates are within bounds
                        x = max(0, min(x, target_width - icon_width))
                        y = max(0, min(y, target_height - icon_height))
                        
                        # Create mask from alpha channel
                        alpha = icon[:, :, 3] / 255.0
                        alpha = np.expand_dims(alpha, axis=-1)
                        
                        # Extract BGR channels
                        icon_bgr = icon[:, :, :3]
                        
                        # Get region of interest
                        roi = canvas[y:y+icon_height, x:x+icon_width]
                        
                        # Ensure shapes match
                        if roi.shape[:2] == icon_bgr.shape[:2]:
                            # Blend using alpha mask
                            blended = (1 - alpha) * roi + alpha * icon_bgr
                            canvas[y:y+icon_height, x:x+icon_width] = blended
                        
                except Exception as e:
                    print(f"Error applying icon: {str(e)}")
        
            # Add text overlays if present
            if 'text_overlays' in settings and settings['text_overlays']:
                for overlay in settings['text_overlays']:
                    font_face = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = overlay['font_size'] / 24.0  # Scale based on default size 24
                    color = self._parse_color(overlay['color'])
                    bg_color = self._parse_color(overlay['bg_color'])
                    thickness = 2
                    margin = overlay['margin']

                    # Get text size
                    text_size = cv2.getTextSize(overlay['text'], font_face, font_scale, thickness)[0]

                    # Calculate position
                    if overlay['position'] == 'top':
                        y_pos = margin + text_size[1]
                    elif overlay['position'] == 'middle':
                        y_pos = (target_height + text_size[1]) // 2
                    else:  # bottom
                        y_pos = target_height - margin

                    x_pos = (target_width - text_size[0]) // 2  # Center horizontally

                    # Draw background if opacity > 0
                    if overlay.get('bg_opacity', 0) > 0:
                        bg_overlay = canvas.copy()
                        padding = 10
                        cv2.rectangle(
                            bg_overlay,
                            (x_pos - padding, y_pos - text_size[1] - padding),
                            (x_pos + text_size[0] + padding, y_pos + padding),
                            bg_color,
                            -1
                        )
                        canvas = cv2.addWeighted(bg_overlay, overlay['bg_opacity'], canvas, 1 - overlay['bg_opacity'], 0)

                    # Draw text
                    cv2.putText(canvas, overlay['text'], (x_pos, y_pos),
                              font_face, font_scale, color, thickness, cv2.LINE_AA)

        return canvas

    def _parse_color(self, color):
        """Convert color name or hex to BGR tuple"""
        color_map = {
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'red': (0, 0, 255),
            'green': (0, 255, 0),
            'blue': (255, 0, 0),
        }
        if color.lower() in color_map:
            return color_map[color.lower()]
        # Handle hex colors
        if color.startswith('#'):
            c = color.lstrip('#')
            if len(c) == 6:
                rgb = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
                return (rgb[2], rgb[1], rgb[0])  # Convert to BGR
        return (255, 255, 255)  # Default to white

    def update_preview(self, video_path=None, settings=None, dimensions=None):
        if video_path and video_path != self.current_video:
            self.current_video = video_path
            self.extract_random_frame(video_path)
            
        if settings:
            self.current_settings = settings
            
        if dimensions:
            self.current_dimensions = dimensions
            
        if self.original_frame is not None:
            frame = self.apply_settings_to_frame(
                self.original_frame.copy(),
                self.current_settings,
                self.current_dimensions
            )
            
            if frame is not None:
                # Resize for display
                display_height = 600
                display_width = 400
                scale = min(display_width/frame.shape[1], display_height/frame.shape[0])
                display_size = (int(frame.shape[1]*scale), int(frame.shape[0]*scale))
                frame = cv2.resize(frame, display_size)
                
                # Convert to PhotoImage
                image = Image.fromarray(frame)
                self.preview_image = ImageTk.PhotoImage(image)
                
                # Update canvas
                self.canvas.delete("all")
                self.canvas.create_image(
                    display_width//2, 
                    display_height//2, 
                    anchor='center', 
                    image=self.preview_image
                )

    def get_current_settings(self):
        """Return the current settings being used in the preview"""
        return self.current_settings

class TextOverlayDialog:
    def __init__(self, parent, callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Text Overlays")
        self.dialog.geometry("600x400")
        self.callback = callback
        self.overlays = []
        self.dragging = False
        self.drag_source_index = None
        self.create_widgets()
        self.drag_line = None
        self.current_index = None  # Add this line
        self.drag_line_index = None  # Add this line to track the arrow position
        self.parent = parent  # Add this line to store parent reference

    def create_widgets(self):
        # Text overlays list
        list_frame = ttk.LabelFrame(self.dialog, text="Text Overlays", padding="5")
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.overlay_list = tk.Listbox(list_frame, height=6, selectmode=tk.SINGLE)
        self.overlay_list.pack(side=tk.LEFT, fill='both', expand=True)

        # Add drag and drop bindings
        self.overlay_list.bind('<Button-1>', self.on_press)
        self.overlay_list.bind('<B1-Motion>', self.on_motion)
        self.overlay_list.bind('<ButtonRelease-1>', self.on_release)

        # Add visual feedback
        self.drag_line = None

        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.overlay_list.yview)
        scroll.pack(side=tk.RIGHT, fill='y')
        self.overlay_list.configure(yscrollcommand=scroll.set)

        # Control buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill='x', padx=5, pady=5)

        # Add Delete All button
        ttk.Button(btn_frame, text="Delete All", 
                  command=self.delete_all_overlays,
                  style='Danger.TButton').pack(side=tk.LEFT, padx=2)
        
        # Existing buttons
        ttk.Button(btn_frame, text="Add", 
                  command=self.add_overlay).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit", 
                  command=self.edit_overlay).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", 
                  command=self.remove_overlay).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="OK", 
                  command=self.ok).pack(side=tk.RIGHT, padx=2)

    def delete_all_overlays(self):
        """Delete all text overlays after confirmation"""
        if messagebox.askyesno("Confirm Delete All", 
                             "Are you sure you want to delete all text overlays?"):
            self.overlays.clear()
            self.update_list()
            self.callback(self.overlays)

    def on_press(self, event):
        """Handle mouse press to start drag operation"""
        index = self.overlay_list.nearest(event.y)
        if index >= 0 and index < self.overlay_list.size():  # Add bounds check
            self.drag_source_index = index
            self.overlay_list.selection_clear(0, tk.END)
            self.overlay_list.selection_set(index)

    def on_motion(self, event):
        """Handle mouse motion during drag"""
        if self.drag_source_index is not None:
            try:
                current_index = self.overlay_list.nearest(event.y)
                if current_index >= self.overlay_list.size():
                    current_index = self.overlay_list.size() - 1
                
                # Remove previous arrow if it exists
                if self.drag_line_index is not None:
                    self.overlay_list.delete(self.drag_line_index)
                
                # Don't show arrow at source position
                if current_index != self.drag_source_index:
                    self.drag_line_index = current_index
                    self.overlay_list.insert(current_index, "▼")
                    self.current_index = current_index
                else:
                    self.drag_line_index = None
                    self.current_index = self.drag_source_index
                
            except tk.TclError:
                pass

    def on_release(self, event):
        """Handle mouse release to complete drag operation"""
        try:
            if self.drag_source_index is not None and len(self.overlays) > 0:
                # Remove the arrow indicator
                if self.drag_line_index is not None:
                    self.overlay_list.delete(self.drag_line_index)
                    
                drop_index = self.current_index if self.current_index is not None else self.drag_source_index
                
                # Only move if dropping at a different position
                if drop_index != self.drag_source_index:
                    # Get the overlay being moved
                    overlay = self.overlays[self.drag_source_index]
                    
                    # Remove from original position
                    self.overlays.pop(self.drag_source_index)
                    
                    # Adjust drop index if needed
                    if drop_index > self.drag_source_index:
                        drop_index -= 1
                    
                    # Insert at new position
                    if drop_index >= len(self.overlays):
                        self.overlays.append(overlay)
                    else:
                        self.overlays.insert(drop_index, overlay)
                    
                    # Update the display
                    self.update_list()
                    
                    # Force immediate callback for preview update
                    self.callback(self.overlays.copy())  # Send a copy to prevent reference issues
                
        except (IndexError, tk.TclError) as e:
            print(f"Error during drag-and-drop: {str(e)}")
        finally:
            self.drag_source_index = None
            self.current_index = None
            self.drag_line_index = None

    def update_list(self):
        """Update the listbox display"""
        self.overlay_list.delete(0, tk.END)
        for idx, overlay in enumerate(self.overlays):
            # Add numbering to make order clear
            self.overlay_list.insert(tk.END, f"{idx + 1}. {overlay['text']} ({overlay['position']})")

    def add_overlay(self):
        dialog = TextOverlaySettingsDialog(self.dialog)
        self.dialog.wait_window(dialog.dialog)
        if dialog.result:
            self.overlays.append(dialog.result)
            self.update_list()
            self.callback(self.overlays)

    def edit_overlay(self):
        sel = self.overlay_list.curselection()
        if sel and sel[0] < len(self.overlays):  # Add bounds check
            idx = sel[0]
            dialog = TextOverlaySettingsDialog(self.dialog, self.overlays[idx])
            self.dialog.wait_window(dialog.dialog)
            if dialog.result:
                self.overlays[idx] = dialog.result
                self.update_list()
                self.callback(self.overlays)

    def remove_overlay(self):
        sel = self.overlay_list.curselection()
        if sel:
            idx = sel[0]
            del self.overlays[idx]
            self.update_list()
            self.callback(self.overlays)

    def update_list(self):
        self.overlay_list.delete(0, tk.END)
        for overlay in self.overlays:
            self.overlay_list.insert(tk.END, f"{overlay['text']} ({overlay['position']})")

    def ok(self):
        self.dialog.destroy()

class TextOverlaySettingsDialog:
    def __init__(self, parent, settings=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Text Overlay Settings")
        self.dialog.geometry("400x500")
        self.result = None
        self.create_widgets(settings)

    def create_widgets(self, settings):
        settings = settings or {}
        
        # Text content
        ttk.Label(self.dialog, text="Text:").pack(pady=2)
        self.text = tk.Text(self.dialog, height=3)
        self.text.pack(fill='x', padx=5)
        if settings.get('text'):
            self.text.insert('1.0', settings['text'])

        # Font settings
        ttk.Label(self.dialog, text="Font:").pack(pady=2)
        self.font = ttk.Entry(self.dialog)
        self.font.pack(fill='x', padx=5)
        self.font.insert(0, settings.get('font', 'Arial'))

        ttk.Label(self.dialog, text="Font Size:").pack(pady=2)
        self.font_size = ttk.Entry(self.dialog)
        self.font_size.pack(fill='x', padx=5)
        self.font_size.insert(0, str(settings.get('font_size', 24)))

        # Colors
        ttk.Label(self.dialog, text="Text Color:").pack(pady=2)
        self.color = ttk.Entry(self.dialog)
        self.color.pack(fill='x', padx=5)
        self.color.insert(0, settings.get('color', 'white'))

        ttk.Label(self.dialog, text="Background Color:").pack(pady=2)
        self.bg_color = ttk.Entry(self.dialog)
        self.bg_color.pack(fill='x', padx=5)
        self.bg_color.insert(0, settings.get('bg_color', 'black'))

        ttk.Label(self.dialog, text="Background Opacity (0-1):").pack(pady=2)
        self.bg_opacity = ttk.Entry(self.dialog)
        self.bg_opacity.pack(fill='x', padx=5)
        self.bg_opacity.insert(0, str(settings.get('bg_opacity', 0.5)))

        # Position
        ttk.Label(self.dialog, text="Position:").pack(pady=2)
        self.position = ttk.Combobox(self.dialog, values=['top', 'middle', 'bottom'])
        self.position.pack(fill='x', padx=5)
        self.position.set(settings.get('position', 'bottom'))

        ttk.Label(self.dialog, text="Margin (pixels):").pack(pady=2)
        self.margin = ttk.Entry(self.dialog)
        self.margin.pack(fill='x', padx=5)
        self.margin.insert(0, str(settings.get('margin', 20)))

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="OK", command=self.ok).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side='right')

    def ok(self):
        try:
            self.result = {
                'text': self.text.get('1.0', 'end-1c'),
                'font': self.font.get(),
                'font_size': int(self.font_size.get()),
                'color': self.color.get(),
                'bg_color': self.bg_color.get(),
                'bg_opacity': float(self.bg_opacity.get()),
                'position': self.position.get(),
                'margin': int(self.margin.get())
            }
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", "Please enter valid numbers for font size, opacity, and margin.")

    def cancel(self):
        self.dialog.destroy()

class VideoEditorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Editor")
        self.root.geometry("1200x800")  # Increased window size
        
        # Variables
        self.source_folder = tk.StringVar()
        self.platform = tk.StringVar(value="youtube_shorts")
        self.use_defaults = tk.BooleanVar(value=True)
        self.aspect_ratio = tk.StringVar(value="2")  # Default to portrait
        self.progress = tk.DoubleVar(value=0)
        self.processing = False
        self.selected_video = tk.StringVar()
        self.session_settings = {
            'text_overlays': []  # Initialize text_overlays in session settings
        }  # Initialize as dictionary instead of None
        self.output_folder = tk.StringVar()
        self.selected_videos = set()  # Track selected videos
        self.current_preview_video = None  # Add this line
        self.text_overlays = []  # Add this line
        
        # Initialize current dimensions based on default aspect ratio
        ratio_dimensions = {
            "1": (1080, 1080),
            "2": (1080, 1920),
            "3": (1920, 1080),
            "4": (1080, 1920)
        }
        self.current_dimensions = ratio_dimensions[self.aspect_ratio.get()]
        
        # Load config
        self.config = load_config()
        
        self.create_gui()
        
        # Add queue for thread-safe updates
        self.update_queue = queue.Queue()
        
        # Set up logging
        self.setup_logging()
        
        # Setup periodic queue check
        self.check_queue()
        
        self.aspect_ratio.trace_add("write", self.on_aspect_ratio_changed)

    def setup_logging(self):
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"video_editor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # Configure logging
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Stream handler with UTF-8 encoding
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
        self.logger = logger

    def create_gui(self):
        # Main container with two columns
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Left column for controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Right column for preview
        self.preview_panel = PreviewPanel(main_frame, self.get_custom_settings)
        self.preview_panel.frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Source folder selection
        ttk.Label(controls_frame, text="Source Folder:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(controls_frame, textvariable=self.source_folder, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.browse_source).grid(row=0, column=2)
        
        # Add output folder selection
        ttk.Label(controls_frame, text="Output Folder (optional):").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(controls_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(controls_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)

        # Replace video selection area with improved version
        video_selection_frame = ttk.LabelFrame(controls_frame, text="Video Selection", padding="5")
        video_selection_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # Add scrollbar to listbox
        list_frame = ttk.Frame(video_selection_frame)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=Y)
        
        self.video_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, height=6, 
                                       yscrollcommand=scrollbar.set)
        self.video_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.config(command=self.video_listbox.yview)
        
        # Bind listbox selection event
        self.video_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)
        
        # Video controls in a separate frame
        video_controls = ttk.Frame(video_selection_frame)
        video_controls.pack(fill='x', pady=5)
        
        # Left side buttons
        left_buttons = ttk.Frame(video_controls)
        left_buttons.pack(side=tk.LEFT, fill='x', expand=True)
        
        ttk.Button(left_buttons, text="Select All", 
                  command=self.select_all_videos).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_buttons, text="Deselect All", 
                  command=self.deselect_all_videos).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_buttons, text="Remove Selected", 
                  command=self.remove_selected_videos).pack(side=tk.LEFT, padx=2)
        
        # Right side buttons
        right_buttons = ttk.Frame(video_controls)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="Settings", 
                  command=self.show_settings).pack(side=tk.RIGHT, padx=2)
        ttk.Button(right_buttons, text="Preview Selected", 
                  command=self.preview_selected).pack(side=tk.RIGHT, padx=2)

        # Platform selection
        ttk.Label(controls_frame, text="Platform:").grid(row=4, column=0, sticky=tk.W, pady=10)
        platform_frame = ttk.Frame(controls_frame)
        platform_frame.grid(row=4, column=1, sticky=tk.W)
        
        platforms = [
            ("YouTube Shorts", "youtube_shorts"),
            ("Instagram", "instagram"),
            ("TikTok", "tiktok"),
            ("YouTube Long", "youtube_long")
        ]
        
        for i, (text, value) in enumerate(platforms):
            ttk.Radiobutton(platform_frame, text=text, value=value, 
                          variable=self.platform).grid(row=0, column=i, padx=5)
        
        # Aspect ratio selection
        ttk.Label(controls_frame, text="Aspect Ratio:").grid(row=5, column=0, sticky=tk.W, pady=10)
        ratio_frame = ttk.Frame(controls_frame)
        ratio_frame.grid(row=5, column=1, sticky=tk.W)
        
        ratios = [
            ("Square (1:1)", "1"),
            ("Portrait (9:16)", "2"),
            ("Landscape (16:9)", "3"),
            ("Custom", "4")
        ]
        
        for i, (text, value) in enumerate(ratios):
            ttk.Radiobutton(ratio_frame, text=text, value=value, 
                          variable=self.aspect_ratio).grid(row=0, column=i, padx=5)
        
        # Use defaults checkbox
        if self.config:
            ttk.Checkbutton(controls_frame, text="Use defaults from config.yaml", 
                          variable=self.use_defaults).grid(row=6, column=0, 
                          columnspan=2, sticky=tk.W, pady=10)
        
        # Advanced settings button
        ttk.Button(controls_frame, text="Advanced Settings", 
                  command=self.show_advanced_settings).grid(row=7, column=0, 
                  columnspan=2, pady=10)
        
        # Add text overlay button after the Advanced Settings button
        ttk.Button(controls_frame, text="Text Overlays", 
                  command=self.show_text_overlays).grid(row=8, column=0, 
                  columnspan=2, pady=10)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(controls_frame, length=400, 
                                          mode='determinate', variable=self.progress)
        self.progress_bar.grid(row=9, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # Status label
        self.status_label = ttk.Label(controls_frame, text="Ready")
        self.status_label.grid(row=10, column=0, columnspan=3)
        
        # Process button
        self.process_button = ttk.Button(controls_frame, text="Process Videos", 
                                       command=self.start_processing)
        self.process_button.grid(row=11, column=0, columnspan=3, pady=10)
        
        # Process selected video button
        ttk.Button(controls_frame, text="Process Selected Video", 
                  command=self.process_selected_video).grid(row=12, column=1, pady=10)

        # Add log display
        log_frame = ttk.LabelFrame(controls_frame, text="Logs", padding="5")
        log_frame.grid(row=13, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_display = scrolledtext.ScrolledText(log_frame, height=10, width=60, state='disabled')
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
        """Update the video listbox with available videos"""
        self.video_listbox.delete(0, tk.END)
        folder = self.source_folder.get()
        if folder:
            video_files = [f for f in os.listdir(folder) 
                          if f.lower().endswith((".mp4", ".mov"))]
            for video in sorted(video_files):  # Sort the files alphabetically
                self.video_listbox.insert(tk.END, video)
            
            # Select and preview the first video if available
            if video_files:
                self.video_listbox.select_set(0)
                self.preview_selected()

    def select_all_videos(self):
        """Select all videos in the listbox"""
        self.video_listbox.select_set(0, tk.END)

    def deselect_all_videos(self):
        """Deselect all videos in the listbox"""
        self.video_listbox.selection_clear(0, tk.END)

    def remove_selected_videos(self):
        """Remove selected videos from the listbox"""
        selected = self.video_listbox.curselection()
        for index in reversed(selected):
            self.video_listbox.delete(index)

    def process_selected_video(self):
        """Process only the currently selected video"""
        selected = self.video_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a video to process")
            return
            
        if self.processing:
            return
            
        self.processing = True
        self.process_button.config(state=tk.DISABLED)
        self.status_label.config(text="Processing video...")
        
        # Start processing in a separate thread
        thread = threading.Thread(target=lambda: self.process_videos(single_video=True))
        thread.daemon = True
        thread.start()

    def on_listbox_select(self, event):
        """Handle listbox selection event"""
        selection = self.video_listbox.curselection()
        if selection:
            # Update preview with the last selected video
            selected_video = self.video_listbox.get(selection[-1])
            video_path = os.path.join(self.source_folder.get(), selected_video)
            if video_path != self.current_preview_video:
                self.current_preview_video = video_path
                self.preview_panel.update_preview(video_path=video_path, settings=self.session_settings, dimensions=self.current_dimensions)

    def preview_selected(self):
        """Preview the currently selected video"""
        selection = self.video_listbox.curselection()
        if selection:
            selected_video = self.video_listbox.get(selection[-1])
            video_path = os.path.join(self.source_folder.get(), selected_video)
            if video_path != self.current_preview_video:
                self.current_preview_video = video_path
                self.preview_panel.update_preview(video_path=video_path, settings=self.session_settings, dimensions=self.current_dimensions)

    def show_settings(self):
        dialog = CustomSettingsDialog(self.root, 
                                    lambda s: self.preview_panel.update_preview(settings=s),
                                    self.session_settings)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            # Preserve text overlays when updating settings
            self.session_settings.update(dialog.result)
            self.session_settings['text_overlays'] = self.text_overlays
            
            # Update preview with complete settings including text overlays
            self.preview_panel.update_preview(
                settings=self.session_settings,
                dimensions=self.current_dimensions
            )
            return self.session_settings
        return None

    def show_advanced_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Advanced Settings")
        settings_window.geometry("400x500")
        
        # Add advanced settings controls here
        # (black background, icon settings, etc.)
        # This is a placeholder for the actual implementation
        ttk.Label(settings_window, text="Advanced settings coming soon...").pack(pady=20)
        
    def show_text_overlays(self):
        dialog = TextOverlayDialog(self.root, self.update_text_overlays)
        dialog.overlays = self.text_overlays.copy()
        dialog.update_list()
        self.root.wait_window(dialog.dialog)

    def update_text_overlays(self, overlays):
        """Update text overlays and refresh preview"""
        self.text_overlays = overlays.copy()
        if hasattr(self, 'preview_panel'):
            # Update session settings with new overlays
            self.session_settings['text_overlays'] = self.text_overlays
            
            # Update preview with complete settings
            self.preview_panel.update_preview(
                settings=self.session_settings,
                dimensions=self.current_dimensions,
                video_path=self.current_preview_video
            )

    def update_progress(self, value):
        self.progress.set(value)
        self.root.update_idletasks()
        
    def process_complete(self):
        """Handle completion of video processing"""
        try:
            self.processing = False
            self.process_button.config(state=tk.NORMAL)
            self.status_label.config(text="Processing complete!")
            # Use after() to avoid blocking
            self.root.after(100, lambda: messagebox.showinfo("Complete", "Video processing has finished!"))
        except Exception as e:
            print(f"Error in process_complete: {str(e)}")
        
    def start_processing(self):
        if not self.source_folder.get():
            messagebox.showerror("Error", "Please select a source folder")
            return
            
        if self.processing:
            return
            
        self.processing = True
        self.process_button.config(state=tk.DISABLED)
        self.status_label.config(text="Processing videos...")
        
        # Start processing in a separate thread
        thread = threading.Thread(target=self.process_videos)
        thread.daemon = True
        thread.start()
        
    def check_queue(self):
        """Check for updates from the processing thread"""
        try:
            while True:
                update_type, value = self.update_queue.get_nowait()
                if update_type == "progress":
                    self.progress.set(value)
                elif update_type == "log":
                    self.log_display.config(state='normal')
                    self.log_display.insert(tk.END, f"{value}\n")
                    self.log_display.see(tk.END)
                    self.log_display.config(state='disabled')
                elif update_type == "complete":
                    self.process_complete()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def get_custom_settings(self):
        dialog = CustomSettingsDialog(self.root, 
                                    lambda s: self.preview_panel.update_preview(settings=s))
        self.root.wait_window(dialog.dialog)
        return dialog.result

    def on_aspect_ratio_changed(self, *args):
        ratio_dimensions = {
            "1": (1080, 1080),
            "2": (1080, 1920),
            "3": (1920, 1080),
            "4": (1080, 1920)  # Custom - using default portrait for now
        }
        self.current_dimensions = ratio_dimensions[self.aspect_ratio.get()]
        self.preview_panel.update_preview(dimensions=dimensions, settings=self.session_settings, video_path=self.current_preview_video)

    def process_videos(self, single_video=False):
        try:
            platform_defaults = get_platform_defaults(self.config, self.platform.get())
            
            if self.use_defaults.get() and self.config:
                video_position_params, top_bg_params, black_bg_params, icon_params = \
                    get_parameters_from_config(self.config, platform_defaults)
            else:
                # Use the current settings from preview panel
                settings = self.preview_panel.get_current_settings()
                if not settings:
                    messagebox.showerror("Error", "Please configure settings first")
                    self.update_queue.put(("complete", None))
                    self.processing = False
                    self.process_button.config(state=tk.NORMAL)
                    return
                
                # Convert settings to the correct parameter format with proper opacity values
                if settings['video_position']['enabled']:
                    video_position_params = {
                        'bottom_height_percent': float(settings['video_position']['height']),
                        'opacity': min(1.0, max(0.0, float(settings['video_position']['opacity'])))  # Ensure 0-1 range
                    }
                else:
                    video_position_params = None

                if settings['top_bg']['enabled']:
                    top_bg_params = {
                        'height_percent': float(settings['top_bg']['height']),
                        'opacity': min(1.0, max(0.0, float(settings['top_bg']['opacity'])))  # Ensure 0-1 range
                    }
                else:
                    top_bg_params = None

                if settings['bottom_bg']['enabled']:
                    black_bg_params = {
                        'height_percent': float(settings['bottom_bg']['height']),
                        'opacity': min(1.0, max(0.0, float(settings['bottom_bg']['opacity'])))  # Ensure 0-1 range
                    }
                else:
                    black_bg_params = None

                # Icon params
                icon_params = {
                    'width': int(settings['icon']['width']),
                    'x_position': settings['icon']['x_position'],
                    'y_position': min(100.0, max(0.0, float(settings['icon']['y_position'])))  # Ensure 0-100 range
                }

            # Log the parameters for debugging
            self.logger.info(f"Processing with parameters:")
            self.logger.info(f"Video position: {video_position_params}")
            self.logger.info(f"Top background: {top_bg_params}")
            self.logger.info(f"Bottom background: {black_bg_params}")
            self.logger.info(f"Icon: {icon_params}")
            self.logger.info(f"Text overlays: {self.text_overlays}")

            # Set target dimensions based on aspect ratio
            ratio_dimensions = {
                "1": (1080, 1080),
                "2": (1080, 1920),
                "3": (1920, 1080),
                "4": self.current_dimensions  # Custom dimensions
            }
            target_dimensions = ratio_dimensions[self.aspect_ratio.get()]
            
            # Process videos
            source_folder = self.source_folder.get()
            
            # Use custom output folder if specified
            if self.output_folder.get():
                output_folder = self.output_folder.get()
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_folder = os.path.join(script_dir, "ai.waverider", self.platform.get())
            
            os.makedirs(output_folder, exist_ok=True)
            
            brand_icon = "assets/fullicon.png"
            if not os.path.isfile(brand_icon):
                raise FileNotFoundError(f"Brand icon not found at '{brand_icon}'")
            
            # Get list of videos to process
            if single_video:
                selected = self.video_listbox.curselection()
                if not selected:
                    raise ValueError("No video selected")
                video_files = [self.video_listbox.get(selected[-1])]
            else:
                selected = self.video_listbox.curselection()
                if not selected:
                    video_files = [self.video_listbox.get(idx) for idx in range(self.video_listbox.size())]
                else:
                    video_files = [self.video_listbox.get(idx) for idx in selected]
            
            for i, video_file in enumerate(video_files):
                input_path = os.path.join(source_folder, video_file)
                output_path = os.path.join(output_folder, f"processed_{video_file}")
                
                # Process single video with text overlays
                process_video((
                    input_path, brand_icon, output_path, target_dimensions,
                    black_bg_params, video_position_params, top_bg_params, 
                    icon_params, self.text_overlays
                ))
                
                # Update progress through queue
                progress = (i + 1) / len(video_files) * 100
                self.update_queue.put(("progress", progress))
                self.update_queue.put(("log", f"Processed: {video_file}"))
                
            self.update_queue.put(("complete", None))
            
        except subprocess.CalledProcessError as e:
            error_message = f"FFmpeg error: {e.stderr}"
            self.logger.error(f"Error during processing: {error_message}")
            self.update_queue.put(("log", f"Error: {error_message}"))
            self.update_queue.put(("complete", None))
        except Exception as e:
            self.logger.error(f"Error during processing: {str(e)}")
            self.update_queue.put(("log", f"Error: {str(e)}"))
            self.update_queue.put(("complete", None))
        finally:
            self.processing = False
            self.process_button.config(state=tk.NORMAL)

def process_video(video_args):
    """
    Process a single video with proper UTF-8 encoding handling.
    """
    input_path, brand_icon, output_path, target_dimensions, black_bg_params, \
    video_position_params, top_bg_params, icon_params, text_overlays = video_args  # Add text_overlays
    
    filter_complex = generate_filter_complex(
        input_path, brand_icon, target_dimensions, black_bg_params,
        video_position_params, top_bg_params, icon_params, text_overlays  # Add text_overlays
    )

    command = [
        "ffmpeg",
        "-i", input_path,
        "-i", brand_icon,
        "-filter_complex", filter_complex,
        "-map", "[out]",      # Explicitly map the final output
        "-map", "0:a?",       # Map audio if present
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "20",
        "-c:a", "copy",
        "-y",
        output_path
    ]

    try:
        # Run FFmpeg and capture output for debugging
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # Enables text mode with universal newlines
            encoding='utf-8',         # Specify UTF-8 encoding
            errors='replace'          # Replace invalid characters instead of failing
        )
        
        # Wait for the process to complete and get output
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, 
                command, 
                output=stdout, 
                stderr=stderr
            )
            
        return output_path
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg failed for {input_path}:\n{e.stderr}")
        raise e
    except Exception as e:
        print(f"[ERROR] Unexpected error processing {input_path}: {str(e)}")
        raise e

def main():
    root = tk.Tk()
    app = VideoEditorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

