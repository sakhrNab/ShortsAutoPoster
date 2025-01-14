import tkinter as tk
from tkinter import ttk

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
