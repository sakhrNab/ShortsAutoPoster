# video_editor_gui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Y
import os
import yaml
import threading
import queue
import logging
from datetime import datetime
from video_automater import process_video, load_config, get_parameters_from_config, get_platform_defaults, generate_filter_complex
from typing import Dict, Any, Tuple
import subprocess
from gui.widgets.preview_panel import PreviewPanel
from gui.dialogs.custom_settings_dialog import CustomSettingsDialog
from gui.dialogs.text_overlay_dialog import TextOverlayDialog




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
        if (folder):
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
        dialog = TextOverlayDialog(self.root, 
                                 self.update_text_overlays,
                                 preview_callback=self.preview_text_overlays)
        dialog.overlays = self.text_overlays.copy()
        dialog.update_list()
        self.root.wait_window(dialog.dialog)
        self.text_overlays = dialog.overlays

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

    def preview_text_overlays(self, temp_overlays):
        """Preview temporary text overlay changes"""
        if hasattr(self, 'preview_panel'):
            # Create temporary settings with current overlays
            temp_settings = self.session_settings.copy()
            temp_settings['text_overlays'] = temp_overlays
            
            # Update preview with temporary settings
            self.preview_panel.update_preview(
                settings=temp_settings,
                dimensions=self.current_dimensions
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
            "4": self.current_dimensions  # Custom dimensions
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
