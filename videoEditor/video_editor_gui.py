import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import yaml
import threading
import queue
import logging
from datetime import datetime
from video_automater11 import process_video, load_config, get_parameters_from_config, get_platform_defaults
from typing import Dict, Any, Tuple
import cv2
from PIL import Image, ImageTk
import random
import numpy as np

class CustomSettingsDialog:
    def __init__(self, parent, preview_callback):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Custom Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        
        # Initialize variables
        self.video_position = tk.BooleanVar(value=False)
        self.video_position_height = tk.StringVar(value="10")
        self.video_position_opacity = tk.StringVar(value="0.7")
        
        self.top_bg = tk.BooleanVar(value=False)
        self.top_bg_height = tk.StringVar(value="10")
        self.top_bg_opacity = tk.StringVar(value="0.7")
        
        self.bottom_bg = tk.BooleanVar(value=False)
        self.bottom_bg_height = tk.StringVar(value="10")
        self.bottom_bg_opacity = tk.StringVar(value="0.7")
        
        self.icon_width = tk.StringVar(value="500")
        self.icon_x_pos = tk.StringVar(value="c")
        self.icon_y_pos = tk.StringVar(value="12.5")
        
        self.create_widgets()
        self.result = None
        self.preview_callback = preview_callback

    def create_widgets(self):
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Video Position Frame
        vp_frame = ttk.Frame(notebook, padding="10")
        notebook.add(vp_frame, text='Video Position')
        ttk.Checkbutton(vp_frame, text="Enable Video Position", variable=self.video_position).pack()
        ttk.Label(vp_frame, text="Height %:").pack()
        ttk.Entry(vp_frame, textvariable=self.video_position_height).pack()
        ttk.Label(vp_frame, text="Opacity (0-1):").pack()
        ttk.Entry(vp_frame, textvariable=self.video_position_opacity).pack()
        
        # Top Background Frame
        top_frame = ttk.Frame(notebook, padding="10")
        notebook.add(top_frame, text='Top Background')
        ttk.Checkbutton(top_frame, text="Enable Top Background", variable=self.top_bg).pack()
        ttk.Label(top_frame, text="Height %:").pack()
        ttk.Entry(top_frame, textvariable=self.top_bg_height).pack()
        ttk.Label(top_frame, text="Opacity (0-1):").pack()
        ttk.Entry(top_frame, textvariable=self.top_bg_opacity).pack()
        
        # Bottom Background Frame
        bottom_frame = ttk.Frame(notebook, padding="10")
        notebook.add(bottom_frame, text='Bottom Background')
        ttk.Checkbutton(bottom_frame, text="Enable Bottom Background", variable=self.bottom_bg).pack()
        ttk.Label(bottom_frame, text="Height %:").pack()
        ttk.Entry(bottom_frame, textvariable=self.bottom_bg_height).pack()
        ttk.Label(bottom_frame, text="Opacity (0-1):").pack()
        ttk.Entry(bottom_frame, textvariable=self.bottom_bg_opacity).pack()
        
        # Icon Settings Frame
        icon_frame = ttk.Frame(notebook, padding="10")
        notebook.add(icon_frame, text='Icon Settings')
        ttk.Label(icon_frame, text="Width:").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_width).pack()
        ttk.Label(icon_frame, text="X Position (c/l/r or 0-100):").pack()
        ttk.Entry(icon_frame, textvariable=self.icon_x_pos).pack()
        ttk.Label(icon_frame, text="Y Position %:").pack()
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
                    'opacity': float(self.video_position_opacity.get())
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
                'opacity': float(self.video_position_opacity.get())
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
            
        # Resize frame to target dimensions
        target_width, target_height = dimensions
        current_height, current_width = frame.shape[:2]
        
        # Calculate scaling to maintain aspect ratio
        scale = min(target_width/current_width, target_height/current_height)
        new_width = int(current_width * scale)
        new_height = int(current_height * scale)
        
        # Resize frame
        resized = cv2.resize(frame, (new_width, new_height))
        
        # Create canvas with target dimensions
        canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        
        # Center the video
        y_offset = (target_height - new_height) // 2
        x_offset = (target_width - new_width) // 2
        canvas[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
        
        if settings:
            # Apply video position
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
                            x = int(target_width * (float(x_pos) / 100))
                            
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
        
        return canvas

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
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

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
        
        # Video selection combobox
        ttk.Label(controls_frame, text="Select Video:").grid(row=1, column=0, sticky=tk.W, pady=10)
        self.video_combo = ttk.Combobox(controls_frame, textvariable=self.selected_video, state="readonly")
        self.video_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=10)
        self.video_combo.bind('<<ComboboxSelected>>', self.on_video_selected)

        # Settings button next to video selection
        ttk.Button(controls_frame, text="Settings", 
                  command=self.show_settings).grid(row=1, column=2, padx=5)
        
        # Platform selection
        ttk.Label(controls_frame, text="Platform:").grid(row=2, column=0, sticky=tk.W, pady=10)
        platform_frame = ttk.Frame(controls_frame)
        platform_frame.grid(row=2, column=1, sticky=tk.W)
        
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
        ttk.Label(controls_frame, text="Aspect Ratio:").grid(row=3, column=0, sticky=tk.W, pady=10)
        ratio_frame = ttk.Frame(controls_frame)
        ratio_frame.grid(row=3, column=1, sticky=tk.W)
        
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
                          variable=self.use_defaults).grid(row=4, column=0, 
                          columnspan=2, sticky=tk.W, pady=10)
        
        # Advanced settings button
        ttk.Button(controls_frame, text="Advanced Settings", 
                  command=self.show_advanced_settings).grid(row=5, column=0, 
                  columnspan=2, pady=10)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(controls_frame, length=400, 
                                          mode='determinate', variable=self.progress)
        self.progress_bar.grid(row=6, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # Status label
        self.status_label = ttk.Label(controls_frame, text="Ready")
        self.status_label.grid(row=7, column=0, columnspan=3)
        
        # Process button
        self.process_button = ttk.Button(controls_frame, text="Process Videos", 
                                       command=self.start_processing)
        self.process_button.grid(row=8, column=0, columnspan=3, pady=10)
        
        # Add log display
        log_frame = ttk.LabelFrame(controls_frame, text="Logs", padding="5")
        log_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_display = scrolledtext.ScrolledText(log_frame, height=10, width=60)
        self.log_display.pack(expand=True, fill='both')

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder.set(folder)
            # Update video list
            video_files = [f for f in os.listdir(folder) 
                          if f.lower().endswith((".mp4", ".mov"))]
            self.video_combo['values'] = video_files
            if video_files:
                self.video_combo.set(video_files[0])
                self.on_video_selected(None)

    def on_video_selected(self, event):
        if self.selected_video.get():
            video_path = os.path.join(self.source_folder.get(), self.selected_video.get())
            self.preview_panel.update_preview(video_path)

    def show_settings(self):
        dialog = CustomSettingsDialog(self.root, 
                                    lambda s: self.preview_panel.update_preview(settings=s))
        self.root.wait_window(dialog.dialog)
        return dialog.result

    def show_advanced_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Advanced Settings")
        settings_window.geometry("400x500")
        
        # Add advanced settings controls here
        # (black background, icon settings, etc.)
        # This is a placeholder for the actual implementation
        ttk.Label(settings_window, text="Advanced settings coming soon...").pack(pady=20)
        
    def update_progress(self, value):
        self.progress.set(value)
        self.root.update_idletasks()
        
    def process_complete(self):
        self.processing = False
        self.process_button.config(state=tk.NORMAL)
        self.status_label.config(text="Processing complete!")
        messagebox.showinfo("Complete", "Video processing has finished!")
        
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
                    self.log_display.insert(tk.END, f"{value}\n")
                    self.log_display.see(tk.END)
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
            "4": (1080, 1920)
        }
        dimensions = ratio_dimensions[self.aspect_ratio.get()]
        self.preview_panel.update_preview(dimensions=dimensions)

    def process_videos(self):
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
                    return
                
                # Convert settings to the correct parameter format
                if settings['video_position']['enabled']:
                    video_position_params = {
                        'bottom_height_percent': settings['video_position']['height'],
                        'opacity': settings['video_position']['opacity']
                    }
                else:
                    video_position_params = None

                if settings['top_bg']['enabled']:
                    top_bg_params = {
                        'height_percent': settings['top_bg']['height'],
                        'opacity': settings['top_bg']['opacity']
                    }
                else:
                    top_bg_params = None

                if settings['bottom_bg']['enabled']:
                    black_bg_params = {
                        'height_percent': settings['bottom_bg']['height'],
                        'opacity': settings['bottom_bg']['opacity']
                    }
                else:
                    black_bg_params = None

                # Icon params don't need restructuring
                icon_params = settings['icon']

            # Set target dimensions based on aspect ratio
            ratio_dimensions = {
                "1": (1080, 1080),
                "2": (1080, 1920),
                "3": (1920, 1080),
                "4": (1080, 1920)  # Custom - using default portrait for now
            }
            target_dimensions = ratio_dimensions[self.aspect_ratio.get()]
            
            # Process videos
            source_folder = self.source_folder.get()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_folder = os.path.join(script_dir, "ai.waverider", self.platform.get())
            os.makedirs(output_folder, exist_ok=True)
            
            brand_icon = "assets/fullicon.png"
            if not os.path.isfile(brand_icon):
                raise FileNotFoundError(f"Brand icon not found at '{brand_icon}'")
            
            video_files = [f for f in os.listdir(source_folder) 
                         if f.lower().endswith((".mp4", ".mov"))]
            
            for i, video_file in enumerate(video_files):
                input_path = os.path.join(source_folder, video_file)
                output_path = os.path.join(output_folder, f"processed_{video_file}")
                
                # Process single video
                process_video((input_path, brand_icon, output_path, target_dimensions,
                             black_bg_params, video_position_params, top_bg_params, 
                             icon_params))
                
                # Update progress through queue
                progress = (i + 1) / len(video_files) * 100
                self.update_queue.put(("progress", progress))
                self.update_queue.put(("log", f"Processed: {video_file}"))
                
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