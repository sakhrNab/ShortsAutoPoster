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

class CustomSettingsDialog:
    def __init__(self, parent):
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

class VideoEditorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Editor")
        self.root.geometry("800x600")
        
        # Variables
        self.source_folder = tk.StringVar()
        self.platform = tk.StringVar(value="youtube_shorts")
        self.use_defaults = tk.BooleanVar(value=True)
        self.aspect_ratio = tk.StringVar(value="2")  # Default to portrait
        self.progress = tk.DoubleVar(value=0)
        self.processing = False
        
        # Load config
        self.config = load_config()
        
        self.create_gui()
        
        # Add queue for thread-safe updates
        self.update_queue = queue.Queue()
        
        # Set up logging
        self.setup_logging()
        
        # Setup periodic queue check
        self.check_queue()

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
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Source folder selection
        ttk.Label(main_frame, text="Source Folder:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.source_folder, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_source).grid(row=0, column=2)
        
        # Platform selection
        ttk.Label(main_frame, text="Platform:").grid(row=1, column=0, sticky=tk.W, pady=10)
        platform_frame = ttk.Frame(main_frame)
        platform_frame.grid(row=1, column=1, sticky=tk.W)
        
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
        ttk.Label(main_frame, text="Aspect Ratio:").grid(row=2, column=0, sticky=tk.W, pady=10)
        ratio_frame = ttk.Frame(main_frame)
        ratio_frame.grid(row=2, column=1, sticky=tk.W)
        
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
            ttk.Checkbutton(main_frame, text="Use defaults from config.yaml", 
                          variable=self.use_defaults).grid(row=3, column=0, 
                          columnspan=2, sticky=tk.W, pady=10)
        
        # Advanced settings button
        ttk.Button(main_frame, text="Advanced Settings", 
                  command=self.show_advanced_settings).grid(row=4, column=0, 
                  columnspan=2, pady=10)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, length=400, 
                                          mode='determinate', variable=self.progress)
        self.progress_bar.grid(row=5, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=6, column=0, columnspan=3)
        
        # Process button
        self.process_button = ttk.Button(main_frame, text="Process Videos", 
                                       command=self.start_processing)
        self.process_button.grid(row=7, column=0, columnspan=3, pady=10)
        
        # Add log display
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding="5")
        log_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_display = scrolledtext.ScrolledText(log_frame, height=10, width=60)
        self.log_display.pack(expand=True, fill='both')

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder.set(folder)
            
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
        dialog = CustomSettingsDialog(self.root)
        self.root.wait_window(dialog.dialog)
        return dialog.result

    def process_videos(self):
        try:
            platform_defaults = get_platform_defaults(self.config, self.platform.get())
            
            if self.use_defaults.get() and self.config:
                video_position_params, top_bg_params, black_bg_params, icon_params = \
                    get_parameters_from_config(self.config, platform_defaults)
            else:
                # Get custom settings
                settings = self.get_custom_settings()
                if not settings:
                    self.update_queue.put(("complete", None))
                    return
                
                # Convert settings to parameter format
                video_position_params = settings['video_position'] if settings['video_position']['enabled'] else None
                top_bg_params = settings['top_bg'] if settings['top_bg']['enabled'] else None
                black_bg_params = settings['bottom_bg'] if settings['bottom_bg']['enabled'] else None
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
