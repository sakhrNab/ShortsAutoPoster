# gui/editor_gui.py

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
from PIL import ImageTk, ImageFont
import threading
import time
import platform
from multiprocessing import Pool, cpu_count
from functools import partial
import logging

from .scrollable_frame import ScrollableFrame
from image_processor import process_image, process_images_in_batch
from utils import create_gradient

class ImageEditorGUI:
    def __init__(self, master, config, logger):
        self.master = master
        self.config = config
        self.logger = logger
        master.title("Automated Image Editor")
        master.geometry("1400x800")
        master.resizable(True, True)

        style = ttk.Style()
        if platform.system() == 'Windows':
            style.theme_use('vista')
        elif platform.system() == 'Darwin':
            style.theme_use('clam')
        else:
            style.theme_use('clam')

        self.paned_window = ttk.Panedwindow(master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        self.controls_frame = ScrollableFrame(self.paned_window)
        self.paned_window.add(self.controls_frame, weight=3)

        self.preview_window = tk.Toplevel(master)
        self.preview_window.title("Live Preview")
        self.preview_window.geometry("600x600")
        self.preview_window.resizable(True, True)
        self.preview_label = tk.Label(self.preview_window)
        self.preview_label.pack(fill="both", expand=True)
        self.preview_window.attributes('-topmost', True)

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Processing Mode
        self.mode = tk.StringVar(value="single")

        self.mode_frame = tk.LabelFrame(self.controls_frame.scrollable_frame, text="Processing Mode", padx=10, pady=10)
        self.mode_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.single_rb = tk.Radiobutton(self.mode_frame, text="Process a Single Image", variable=self.mode, value="single")
        self.single_rb.pack(anchor="w", padx=10, pady=2)

        self.batch_rb = tk.Radiobutton(self.mode_frame, text="Process Multiple Images in a Folder", variable=self.mode, value="batch")
        self.batch_rb.pack(anchor="w", padx=10, pady=2)

        # File/Folder Selection
        self.selection_frame = tk.Frame(self.controls_frame.scrollable_frame)
        self.selection_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.path_label = tk.Label(self.selection_frame, text="Image/Folder Path:")
        self.path_label.pack(side="left", padx=5)

        self.path_entry = tk.Entry(self.selection_frame, width=60)
        self.path_entry.pack(side="left", padx=5)

        self.browse_button = tk.Button(self.selection_frame, text="Browse", command=self.browse)
        self.browse_button.pack(side="left", padx=5)

        # Description Input
        self.description_frame = tk.LabelFrame(self.controls_frame.scrollable_frame, text="Descriptions", padx=10, pady=10)
        self.description_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        self.descriptions_listbox = tk.Listbox(self.description_frame, selectmode=tk.SINGLE, width=50, height=5)
        self.descriptions_listbox.pack(side="left", padx=5, pady=5)

        self.desc_buttons_frame = tk.Frame(self.description_frame)
        self.desc_buttons_frame.pack(side="left", padx=5, pady=5)

        self.add_desc_button = tk.Button(self.desc_buttons_frame, text="Add Description", command=self.add_description)
        self.add_desc_button.pack(fill="x", pady=2)

        self.delete_desc_button = tk.Button(self.desc_buttons_frame, text="Delete Description", command=self.delete_description)
        self.delete_desc_button.pack(fill="x", pady=2)

        self.description_text = tk.Text(self.description_frame, height=5, width=50)
        self.description_text.pack(side="left", padx=5, pady=5)

        # Formatting Toolbar
        self.format_toolbar = tk.Frame(self.controls_frame.scrollable_frame)
        self.format_toolbar.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        self.color_button = tk.Button(self.format_toolbar, text="Change Description Color", command=self.change_description_color)
        self.color_button.pack(side="left", padx=5)

        # Parameters Group Frame
        self.param_group_frame = tk.Frame(self.controls_frame.scrollable_frame)
        self.param_group_frame.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")

        self.param_group_frame.grid_rowconfigure(0, weight=1)
        self.param_group_frame.grid_rowconfigure(1, weight=1)
        self.param_group_frame.grid_rowconfigure(2, weight=1)
        self.param_group_frame.grid_columnconfigure(0, weight=1)
        self.param_group_frame.grid_columnconfigure(1, weight=1)
        self.param_group_frame.grid_columnconfigure(2, weight=1)

        # Icon Settings Frame
        self.icon_settings_frame = tk.LabelFrame(self.param_group_frame, text="Icon Settings", padx=10, pady=10)
        self.icon_settings_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Icon Width Percentage with Slider and Entry
        self.icon_width_label = tk.Label(self.icon_settings_frame, text="Icon Width (%):")
        self.icon_width_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.icon_width_slider = tk.Scale(self.icon_settings_frame, from_=1, to=100, orient="horizontal", 
                                        command=lambda v: self.sync_slider_entry(v, self.icon_width_entry))
        self.icon_width_slider.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.icon_width_entry = tk.Entry(self.icon_settings_frame, width=5)
        self.icon_width_entry.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.icon_width_slider.set(40)
        self.icon_width_entry.insert(0, "40")

        # Icon Height Percentage with Slider and Entry
        self.icon_height_label = tk.Label(self.icon_settings_frame, text="Icon Height (%):")
        self.icon_height_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.icon_height_slider = tk.Scale(self.icon_settings_frame, from_=1, to=100, orient="horizontal",
                                         command=lambda v: self.sync_slider_entry(v, self.icon_height_entry))
        self.icon_height_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.icon_height_entry = tk.Entry(self.icon_settings_frame, width=5)
        self.icon_height_entry.grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.icon_height_slider.set(15)
        self.icon_height_entry.insert(0, "15")

        # Text Settings Frame
        self.text_settings_frame = tk.LabelFrame(self.param_group_frame, text="Text Settings", padx=10, pady=10)
        self.text_settings_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # Text Color with Button
        self.text_color_label = tk.Label(self.text_settings_frame, text="Default Text Color:")
        self.text_color_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.text_color_button = tk.Button(self.text_settings_frame, text="Choose Color", command=self.choose_text_color)
        self.text_color_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Font Selection with Button
        self.font_label = tk.Label(self.text_settings_frame, text="Font Type:")
        self.font_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.font_button = tk.Button(self.text_settings_frame, text="Choose Font", command=self.choose_font)
        self.font_button.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Font Size with Spinbox
        self.font_size_label = tk.Label(self.text_settings_frame, text="Font Size:")
        self.font_size_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.font_size_spinbox = tk.Spinbox(self.text_settings_frame, from_=10, to=100, width=5, command=self.update_preview)
        self.font_size_spinbox.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.font_size_spinbox.delete(0, tk.END)
        self.font_size_spinbox.insert(0, "24")

        # Aspect Ratio Settings Frame
        self.aspect_ratio_frame = tk.LabelFrame(self.param_group_frame, text="Aspect Ratio Settings", padx=10, pady=10)
        self.aspect_ratio_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")

        # Aspect Ratio Selection
        self.aspect_ratio_label = tk.Label(self.aspect_ratio_frame, text="Select Aspect Ratio:")
        self.aspect_ratio_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.aspect_ratio_var = tk.StringVar(value="1:1")
        self.aspect_ratio_combo = ttk.Combobox(self.aspect_ratio_frame, textvariable=self.aspect_ratio_var, state="readonly")
        self.aspect_ratio_combo['values'] = ("1:1", "9:16", "16:9", "Custom")
        self.aspect_ratio_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.aspect_ratio_combo.bind("<<ComboboxSelected>>", self.aspect_ratio_selection_changed)

        # Custom Aspect Ratio Inputs (Hidden by Default)
        self.custom_aspect_frame = tk.Frame(self.aspect_ratio_frame)
        self.custom_aspect_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="we")
        self.custom_aspect_frame.grid_remove()

        self.custom_width_label = tk.Label(self.custom_aspect_frame, text="Width:")
        self.custom_width_label.pack(side="left", padx=2)
        self.custom_width_entry = tk.Entry(self.custom_aspect_frame, width=5)
        self.custom_width_entry.pack(side="left", padx=2)
        self.custom_width_entry.insert(0, "1")

        self.custom_height_label = tk.Label(self.custom_aspect_frame, text="Height:")
        self.custom_height_label.pack(side="left", padx=2)
        self.custom_height_entry = tk.Entry(self.custom_aspect_frame, width=5)
        self.custom_height_entry.pack(side="left", padx=2)
        self.custom_height_entry.insert(0, "1")

        # Position Adjustments Frame
        self.position_adjustments_frame = tk.LabelFrame(self.param_group_frame, text="Position Adjustments", padx=10, pady=10)
        self.position_adjustments_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

        # Line Offset Frame
        self.line_offset_frame = tk.Frame(self.position_adjustments_frame)
        self.line_offset_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(self.line_offset_frame, text="Line Offset X:").pack(side="left", padx=5, pady=5)
        self.line_offset_x_slider = tk.Scale(self.line_offset_frame, from_=-100, to=100, orient="horizontal", command=lambda v: self.sync_slider_entry(v, self.line_offset_x_entry))
        self.line_offset_x_slider.pack(side="left", padx=5, pady=5)
        self.line_offset_x_entry = tk.Entry(self.line_offset_frame, width=5)
        self.line_offset_x_entry.pack(side="left", padx=5, pady=5)
        self.line_offset_x_slider.set(0)
        self.line_offset_x_entry.insert(0, "0")
        self.line_offset_x_entry.bind("<Return>", lambda event: self.sync_entry_slider(event, self.line_offset_x_entry, self.line_offset_x_slider))

        tk.Label(self.line_offset_frame, text="Line Offset Y:").pack(side="left", padx=5, pady=5)
        self.line_offset_y_slider = tk.Scale(self.line_offset_frame, from_=-100, to=100, orient="horizontal", command=lambda v: self.sync_slider_entry(v, self.line_offset_y_entry))
        self.line_offset_y_slider.pack(side="left", padx=5, pady=5)
        self.line_offset_y_entry = tk.Entry(self.line_offset_frame, width=5)
        self.line_offset_y_entry.pack(side="left", padx=5, pady=5)
        self.line_offset_y_slider.set(0)
        self.line_offset_y_entry.insert(0, "0")
        self.line_offset_y_entry.bind("<Return>", lambda event: self.sync_entry_slider(event, self.line_offset_y_entry, self.line_offset_y_slider))

        # Description Offset Frame
        self.desc_offset_frame = tk.Frame(self.position_adjustments_frame)
        self.desc_offset_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(self.desc_offset_frame, text="Description Offset X:").pack(side="left", padx=5, pady=5)
        self.desc_offset_x_slider = tk.Scale(self.desc_offset_frame, from_=-100, to=100, orient="horizontal", command=lambda v: self.sync_slider_entry(v, self.desc_offset_x_entry))
        self.desc_offset_x_slider.pack(side="left", padx=5, pady=5)
        self.desc_offset_x_entry = tk.Entry(self.desc_offset_frame, width=5)
        self.desc_offset_x_entry.pack(side="left", padx=5, pady=5)
        self.desc_offset_x_slider.set(0)
        self.desc_offset_x_entry.insert(0, "0")
        self.desc_offset_x_entry.bind("<Return>", lambda event: self.sync_entry_slider(event, self.desc_offset_x_entry, self.desc_offset_x_slider))

        tk.Label(self.desc_offset_frame, text="Description Offset Y:").pack(side="left", padx=5, pady=5)
        self.desc_offset_y_slider = tk.Scale(self.desc_offset_frame, from_=-100, to=100, orient="horizontal", command=lambda v: self.sync_slider_entry(v, self.desc_offset_y_entry))
        self.desc_offset_y_slider.pack(side="left", padx=5, pady=5)
        self.desc_offset_y_entry = tk.Entry(self.desc_offset_frame, width=5)
        self.desc_offset_y_entry.pack(side="left", padx=5, pady=5)
        self.desc_offset_y_slider.set(0)
        self.desc_offset_y_entry.insert(0, "0")
        self.desc_offset_y_entry.bind("<Return>", lambda event: self.sync_entry_slider(event, self.desc_offset_y_entry, self.desc_offset_y_slider))

        # Icon Offset Frame
        self.icon_offset_frame = tk.Frame(self.position_adjustments_frame)
        self.icon_offset_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(self.icon_offset_frame, text="Icon Offset X:").pack(side="left", padx=5, pady=5)
        self.icon_offset_x_slider = tk.Scale(self.icon_offset_frame, from_=-100, to=100, orient="horizontal", command=lambda v: self.sync_slider_entry(v, self.icon_offset_x_entry))
        self.icon_offset_x_slider.pack(side="left", padx=5, pady=5)
        self.icon_offset_x_entry = tk.Entry(self.icon_offset_frame, width=5)
        self.icon_offset_x_entry.pack(side="left", padx=5, pady=5)
        self.icon_offset_x_slider.set(0)
        self.icon_offset_x_entry.insert(0, "0")
        self.icon_offset_x_entry.bind("<Return>", lambda event: self.sync_entry_slider(event, self.icon_offset_x_entry, self.icon_offset_x_slider))

        tk.Label(self.icon_offset_frame, text="Icon Offset Y:").pack(side="left", padx=5, pady=5)
        self.icon_offset_y_slider = tk.Scale(self.icon_offset_frame, from_=-100, to=100, orient="horizontal", command=lambda v: self.sync_slider_entry(v, self.icon_offset_y_entry))
        self.icon_offset_y_slider.pack(side="left", padx=5, pady=5)
        self.icon_offset_y_entry = tk.Entry(self.icon_offset_frame, width=5)
        self.icon_offset_y_entry.pack(side="left", padx=5, pady=5)
        self.icon_offset_y_slider.set(0)
        self.icon_offset_y_entry.insert(0, "0")
        self.icon_offset_y_entry.bind("<Return>", lambda event: self.sync_entry_slider(event, self.icon_offset_y_entry, self.icon_offset_y_slider))

        # Line Settings Frame
        self.line_settings_frame = tk.LabelFrame(self.param_group_frame, text="Line Settings", padx=10, pady=10)
        self.line_settings_frame.grid(row=2, column=0, padx=5, pady=5, sticky="nsew")

        # Line Transparency with Slider and Entry
        self.line_transparency_label = tk.Label(self.line_settings_frame, text="Line Transparency (%):")
        self.line_transparency_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.line_transparency_slider = tk.Scale(self.line_settings_frame, from_=0, to=100, orient="horizontal",
                                               command=lambda v: self.sync_slider_entry(v, self.line_transparency_entry))
        self.line_transparency_slider.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.line_transparency_entry = tk.Entry(self.line_settings_frame, width=5)
        self.line_transparency_entry.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.line_transparency_slider.set(100)
        self.line_transparency_entry.insert(0, "100")

        # Line Type Selection
        self.line_type_label = tk.Label(self.line_settings_frame, text="Line Type:")
        self.line_type_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.line_type_var = tk.StringVar(value="Solid")
        self.line_type_combo = ttk.Combobox(self.line_settings_frame, textvariable=self.line_type_var, state="readonly")
        self.line_type_combo['values'] = ("Solid", "Dashed", "Gradient")
        self.line_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Background Settings Frame
        self.bg_settings_frame = tk.LabelFrame(self.param_group_frame, text="Background Settings", padx=10, pady=10)
        self.bg_settings_frame.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")

        # Black Background Height Percentage with Slider and Entry
        self.bg_height_label = tk.Label(self.bg_settings_frame, text="Bg Height (%):")
        self.bg_height_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.bg_height_slider = tk.Scale(self.bg_settings_frame, from_=1, to=100, orient="horizontal",
                                       command=lambda v: self.sync_slider_entry(v, self.bg_height_entry))
        self.bg_height_slider.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.bg_height_entry = tk.Entry(self.bg_settings_frame, width=5)
        self.bg_height_entry.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.bg_height_slider.set(15)
        self.bg_height_entry.insert(0, "15")

        # Black Background Transparency with Slider and Entry
        self.bg_transparency_label = tk.Label(self.bg_settings_frame, text="Bg Transparency (%):")
        self.bg_transparency_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.bg_transparency_slider = tk.Scale(self.bg_settings_frame, from_=0, to=100, orient="horizontal",
                                             command=lambda v: self.sync_slider_entry(v, self.bg_transparency_entry))
        self.bg_transparency_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.bg_transparency_entry = tk.Entry(self.bg_settings_frame, width=5)
        self.bg_transparency_entry.grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.bg_transparency_slider.set(50)
        self.bg_transparency_entry.insert(0, "50")

        # Enable Second Black Background
        self.second_bg_var = tk.BooleanVar(value=False)
        self.enable_second_bg_rb = tk.Checkbutton(self.param_group_frame, text="Enable Second Black Background", variable=self.second_bg_var, command=self.toggle_second_bg)
        self.enable_second_bg_rb.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="w")

        # Second Black Background Positioning
        self.second_bg_position_frame = tk.LabelFrame(self.param_group_frame, text="Second Background Position", padx=10, pady=10)
        self.second_bg_position_frame.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="we")
        self.second_bg_position_frame.grid_remove()

        tk.Label(self.second_bg_position_frame, text="X Position:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_pos_x_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_pos_x_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_pos_x_entry.insert(0, "0")

        tk.Label(self.second_bg_position_frame, text="Y Position:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_pos_y_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_pos_y_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_pos_y_entry.insert(0, "0")

        tk.Label(self.second_bg_position_frame, text="Height (%):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_height_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_height_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_height_entry.insert(0, "10")

        tk.Label(self.second_bg_position_frame, text="Transparency (%):").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_transparency_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_transparency_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_transparency_entry.insert(0, "50")

        # Add Open Image Checkbox
        self.open_image_var = tk.BooleanVar(value=True)
        self.open_image_cb = tk.Checkbutton(
            self.controls_frame.scrollable_frame, 
            text="Open Image After Processing", 
            variable=self.open_image_var
        )
        self.open_image_cb.grid(row=5, column=0, padx=10, pady=5, sticky="w")

        # Start Button
        self.start_button = tk.Button(self.controls_frame.scrollable_frame, text="Start Processing", command=self.start_processing)
        self.start_button.grid(row=6, column=0, padx=10, pady=10, sticky="ew")

        # Log Display
        self.log_frame = tk.LabelFrame(self.controls_frame.scrollable_frame, text="Log", padx=10, pady=10)
        self.log_frame.grid(row=7, column=0, padx=10, pady=10, sticky="nsew")

        self.log_text = tk.Text(self.log_frame, height=10, state='disabled')
        self.log_text.pack(fill="both", expand=True)

        self.setup_gui_logging()

        self.preview_image = None
        self.preview_thread = None
        self.preview_lock = threading.Lock()
        self.last_preview_time = time.time()

        self.descriptions = []
        self.initialize_preview()

        self.bind_preview_events()

    def setup_gui_logging(self):
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                self.text_widget.configure(state='normal')
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.configure(state='disabled')
                self.text_widget.see(tk.END)

        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(text_handler)

    def browse(self):
        if self.mode.get() == "single":
            file_path = filedialog.askopenfilename(title="Select Image", 
                                                   filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
            if file_path:
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, file_path)
                self.logger.info(f"Selected file: {file_path}")
        else:
            folder_path = filedialog.askdirectory(title="Select Folder")
            if folder_path:
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, folder_path)
                self.logger.info(f"Selected folder: {folder_path}")
        self.update_preview()

    def add_description(self):
        desc = self.description_text.get("1.0", tk.END).strip()
        if desc:
            self.descriptions.append(desc)
            self.descriptions_listbox.insert(tk.END, desc)
            self.description_text.delete("1.0", tk.END)
            self.logger.info("Added new description.")
            self.update_preview()

    def delete_description(self):
        selected = self.descriptions_listbox.curselection()
        if selected:
            index = selected[0]
            desc = self.descriptions.pop(index)
            self.descriptions_listbox.delete(index)
            self.logger.info(f"Deleted description: {desc}")
            self.update_preview()

    def change_description_color(self):
        selected = self.descriptions_listbox.curselection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a description to change its color.")
            return
        
        color_code = colorchooser.askcolor(title="Choose Description Color")
        if color_code and color_code[0]:  # color_code[0] is RGB tuple, color_code[1] is hex
            index = selected[0]
            desc = self.descriptions[index]
            rgb_color = tuple(map(int, color_code[0]))  # Convert to RGB tuple
            
            # Store the description with its color in a dictionary format
            self.descriptions[index] = {
                'text': desc if isinstance(desc, str) else desc.get('text', ''),
                'color': rgb_color
            }
            
            # Update the listbox display
            self.descriptions_listbox.delete(index)
            display_text = f"{self.descriptions[index]['text']} (RGB{rgb_color})"
            self.descriptions_listbox.insert(index, display_text)
            
            self.logger.info(f"Changed color of description to RGB{rgb_color}")
            self.update_preview()

    def toggle_bold(self):
        selected_text = self.description_text.tag_ranges(tk.SEL)
        if selected_text:
            tag_name = "bold"
            if "bold" in self.description_text.tag_names(tk.SEL_FIRST):
                self.description_text.tag_remove(tag_name, "sel.first", "sel.last")
            else:
                self.description_text.tag_add(tag_name, "sel.first", "sel.last")
                try:
                    bold_font = ImageFont.truetype(self.config['FONT_PATH'], int(self.font_size_spinbox.get()))
                    self.description_text.tag_config(tag_name, font=bold_font)
                except IOError:
                    self.logger.warning("Bold font not found. Using default font.")
            self.update_preview()

    def toggle_italic(self):
        selected_text = self.description_text.tag_ranges(tk.SEL)
        if selected_text:
            tag_name = "italic"
            if "italic" in self.description_text.tag_names(tk.SEL_FIRST):
                self.description_text.tag_remove(tag_name, "sel.first", "sel.last")
            else:
                self.description_text.tag_add(tag_name, "sel.first", "sel.last")
                try:
                    italic_font = ImageFont.truetype(self.config['FONT_PATH'], int(self.font_size_spinbox.get()))
                    self.description_text.tag_config(tag_name, font=italic_font)
                except IOError:
                    self.logger.warning("Italic font not found. Using default font.")
            self.update_preview()

    def choose_line_color(self):
        color_code = colorchooser.askcolor(title="Choose Line Color")
        if color_code and color_code[0]:
            self.line_color = color_code[0]
            self.logger.info(f"Selected Line Color: {self.line_color}")
            self.update_preview()

    def choose_line_gradient_start(self):
        color_code = colorchooser.askcolor(title="Choose Line Gradient Start Color")
        if color_code and color_code[0]:
            self.line_gradient_start = color_code[0]
            self.logger.info(f"Selected Line Gradient Start Color: {self.line_gradient_start}")
            self.update_preview()

    def choose_line_gradient_end(self):
        color_code = colorchooser.askcolor(title="Choose Line Gradient End Color")
        if color_code and color_code[0]:
            self.line_gradient_end = color_code[0]
            self.logger.info(f"Selected Line Gradient End Color: {self.line_gradient_end}")
            self.update_preview()

    def choose_text_color(self):
        color_code = colorchooser.askcolor(title="Choose Default Description Text Color")
        if color_code and color_code[0]:
            self.text_color = color_code[0]
            self.logger.info(f"Selected Default Description Text Color: {self.text_color}")
            self.update_preview()

    def choose_font(self):
        font_path = filedialog.askopenfilename(title="Select Font File", 
                                               filetypes=[("Font Files", "*.ttf *.otf")])
        if font_path:
            self.selected_font = font_path
            self.logger.info(f"Selected Font: {self.selected_font}")
            self.update_preview()

    def toggle_second_bg(self):
        if self.second_bg_var.get():
            self.second_bg_position_frame.grid()
        else:
            self.second_bg_position_frame.grid_remove()
        self.update_preview()

    def aspect_ratio_selection_changed(self, event):
        selection = self.aspect_ratio_var.get()
        if selection == "Custom":
            self.custom_aspect_frame.grid()
        else:
            self.custom_aspect_frame.grid_remove()
        self.update_preview()

    def bind_preview_events(self):
        self.descriptions_listbox.bind('<<ListboxSelect>>', self.update_description_text)
        self.description_text.bind("<KeyRelease>", lambda event: self.update_preview())
        self.icon_width_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.icon_height_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.bg_height_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.bg_transparency_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.line_transparency_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.second_bg_pos_x_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.second_bg_pos_y_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.second_bg_height_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.second_bg_transparency_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.font_size_spinbox.bind("<KeyRelease>", lambda event: self.update_preview())
        self.font_size_spinbox.bind("<ButtonRelease-1>", lambda event: self.update_preview())
        self.custom_width_entry.bind("<KeyRelease>", lambda event: self.update_preview())
        self.custom_height_entry.bind("<KeyRelease>", lambda event: self.update_preview())

    def update_description_text(self, event):
        selected = self.descriptions_listbox.curselection()
        if selected:
            index = selected[0]
            desc = self.descriptions[index]
            # Remove color tags for editing
            desc_clean = re.sub(r'</?\w+?>', '', desc)
            self.description_text.delete("1.0", tk.END)
            self.description_text.insert("1.0", desc_clean)

    def initialize_preview(self):
        self.line_color = self.config.get("LINE_COLOR", (255, 255, 255))
        self.line_gradient_start = self.config.get("LINE_GRADIENT_START", (255, 69, 0))
        self.line_gradient_end = self.config.get("LINE_GRADIENT_END", (30, 144, 255))
        self.text_color = self.config.get("TEXT_COLOR", (255, 255, 255))

        self.update_preview()

    def update_preview(self, event=None):
        current_time = time.time()
        if current_time - self.last_preview_time < 0.3:
            return
        self.last_preview_time = current_time

        if self.preview_thread and self.preview_thread.is_alive():
            return

        self.preview_thread = threading.Thread(target=self.generate_preview)
        self.preview_thread.daemon = True
        self.preview_thread.start()

    def generate_preview(self):
        with self.preview_lock:
            path = self.path_entry.get().strip()
            if not path or (self.mode.get() == "single" and not os.path.isfile(path)) or (self.mode.get() == "batch" and not os.path.isdir(path)):
                self.logger.warning("Invalid path for preview.")
                return

            if self.mode.get() == "single":
                image_paths = [path]
            else:
                image_paths = [os.path.join(path, f) for f in os.listdir(path)
                               if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                if not image_paths:
                    self.logger.warning("No image files found for preview.")
                    return

            image_path = image_paths[0]

            try:
                icon_width_percentage = float(self.icon_width_entry.get())
                if not (0 < icon_width_percentage < 100):
                    raise ValueError
            except ValueError:
                self.logger.warning("Invalid Icon Width percentage for preview.")
                return

            try:
                icon_height_percentage = float(self.icon_height_entry.get())
                if not (0 < icon_height_percentage < 100):
                    raise ValueError
            except ValueError:
                self.logger.warning("Invalid Icon Height percentage for preview.")
                return

            try:
                bg_height_percentage = float(self.bg_height_entry.get())
                if not (0 < bg_height_percentage < 100):
                    raise ValueError
            except ValueError:
                self.logger.warning("Invalid Black Background Height percentage for preview.")
                return

            try:
                bg_transparency = float(self.bg_transparency_entry.get())
                if not (0 <= bg_transparency <= 100):
                    raise ValueError
            except ValueError:
                self.logger.warning("Invalid Black Background Transparency percentage for preview.")
                return

            try:
                line_transparency = float(self.line_transparency_entry.get())
                if not (0 <= line_transparency <= 100):
                    raise ValueError
            except ValueError:
                self.logger.warning("Invalid Line Transparency percentage for preview.")
                return

            line_type = self.line_type_var.get()

            line_offset_x = self.line_offset_x_slider.get()
            line_offset_y = self.line_offset_y_slider.get()
            description_offset_x = self.desc_offset_x_slider.get()
            description_offset_y = self.desc_offset_y_slider.get()
            icon_offset_x = self.icon_offset_x_slider.get()
            icon_offset_y = self.icon_offset_y_slider.get()

            descriptions = self.descriptions

            enable_second_bg = self.second_bg_var.get()
            if enable_second_bg:
                try:
                    second_bg_pos_x = int(self.second_bg_pos_x_entry.get())
                    second_bg_pos_y = int(self.second_bg_pos_y_entry.get())
                    second_bg_height_percentage = float(self.second_bg_height_entry.get())
                    second_bg_transparency = float(self.second_bg_transparency_entry.get())
                    if not (0 <= second_bg_transparency <= 100 and 0 < second_bg_height_percentage < 100):
                        raise ValueError
                except ValueError:
                    self.logger.warning("Invalid Second Black Background parameters for preview.")
                    return
            else:
                second_bg_pos_x = 0
                second_bg_pos_y = 0
                second_bg_height_percentage = 10
                second_bg_transparency = 50

            try:
                description_font_size = int(self.font_size_spinbox.get())
                if not (10 <= description_font_size <= 100):
                    raise ValueError
            except ValueError:
                self.logger.warning("Invalid Description Font Size for preview.")
                return

            aspect_ratio_selection = self.aspect_ratio_var.get()
            if aspect_ratio_selection == "Custom":
                try:
                    custom_width = float(self.custom_width_entry.get())
                    custom_height = float(self.custom_height_entry.get())
                    if custom_width <= 0 or custom_height <= 0:
                        raise ValueError
                    aspect_ratio = (custom_width, custom_height)
                except ValueError:
                    self.logger.warning("Invalid Custom Aspect Ratio for preview.")
                    return
            else:
                ratios = {
                    "1:1": (1, 1),
                    "9:16": (9, 16),
                    "16:9": (16, 9)
                }
                aspect_ratio = ratios.get(aspect_ratio_selection, (1, 1))

            parameters = {
                'icon_width_percentage': icon_width_percentage,
                'icon_height_percentage': icon_height_percentage,
                'black_bg_height_percentage': bg_height_percentage,
                'black_bg_transparency': bg_transparency,
                'line_transparency': line_transparency,
                'line_type': line_type,
                'open_image': False,
                'line_color': self.line_color,
                'line_gradient_start': self.line_gradient_start,
                'line_gradient_end': self.line_gradient_end,
                'text_color': self.text_color,
                'description_offset_x': description_offset_x,
                'description_offset_y': description_offset_y,
                'icon_offset_x': icon_offset_x,
                'icon_offset_y': icon_offset_y,
                'descriptions': descriptions,
                'line_offset_y': line_offset_y,
                'enable_second_bg': enable_second_bg,
                'second_bg_position_x': second_bg_pos_x,
                'second_bg_position_y': second_bg_pos_y,
                'second_black_bg_height_percentage': second_bg_height_percentage,
                'second_black_bg_transparency': second_bg_transparency,
                'description_font_size': description_font_size,
                'aspect_ratio': aspect_ratio
            }

            preview_img = process_image(image_path, self.config, parameters, self.logger, preview=True)
            if preview_img:
                preview_img_tk = ImageTk.PhotoImage(preview_img)
                self.preview_label.after(0, self.display_preview, preview_img_tk)
            else:
                self.logger.warning("Failed to generate preview.")

    def display_preview(self, img_tk):
        self.preview_label.configure(image=img_tk)
        self.preview_label.image = img_tk
        self.preview_window.geometry(f"{img_tk.width()}x{img_tk.height()}")

    def start_processing(self):
        path = self.path_entry.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select an image or folder path.")
            return

        try:
            icon_width_percentage = float(self.icon_width_entry.get())
            if not (0 < icon_width_percentage < 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Icon Width percentage between 0 and 100.")
            return

        try:
            icon_height_percentage = float(self.icon_height_entry.get())
            if not (0 < icon_height_percentage < 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Icon Height percentage between 0 and 100.")
            return

        try:
            bg_height_percentage = float(self.bg_height_entry.get())
            if not (0 < bg_height_percentage < 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Black Background Height percentage between 0 and 100.")
            return

        try:
            bg_transparency = float(self.bg_transparency_entry.get())
            if not (0 <= bg_transparency <= 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Black Background Transparency percentage between 0 and 100.")
            return

        try:
            line_transparency = float(self.line_transparency_entry.get())
            if not (0 <= line_transparency <= 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Line Transparency percentage between 0 and 100.")
            return

        line_type = self.line_type_var.get()

        line_offset_x = self.line_offset_x_slider.get()
        line_offset_y = self.line_offset_y_slider.get()
        description_offset_x = self.desc_offset_x_slider.get()
        description_offset_y = self.desc_offset_y_slider.get()
        icon_offset_x = self.icon_offset_x_slider.get()
        icon_offset_y = self.icon_offset_y_slider.get()

        descriptions = self.descriptions

        enable_second_bg = self.second_bg_var.get()
        if enable_second_bg:
            try:
                second_bg_pos_x = int(self.second_bg_pos_x_entry.get())
                second_bg_pos_y = int(self.second_bg_pos_y_entry.get())
                second_bg_height_percentage = float(self.second_bg_height_entry.get())
                second_bg_transparency = float(self.second_bg_transparency_entry.get())
                if not (0 <= second_bg_transparency <= 100 and 0 < second_bg_height_percentage < 100):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Please enter valid Second Black Background parameters.")
                return
        else:
            second_bg_pos_x = 0
            second_bg_pos_y = 0
            second_bg_height_percentage = 10
            second_bg_transparency = 50

        try:
            description_font_size = int(self.font_size_spinbox.get())
            if not (10 <= description_font_size <= 100):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Description Font Size between 10 and 100.")
            return

        aspect_ratio_selection = self.aspect_ratio_var.get()
        if aspect_ratio_selection == "Custom":
            try:
                custom_width = float(self.custom_width_entry.get())
                custom_height = float(self.custom_height_entry.get())
                if custom_width <= 0 or custom_height <= 0:
                    raise ValueError
                aspect_ratio = (custom_width, custom_height)
            except ValueError:
                messagebox.showerror("Error", "Please enter valid Custom Aspect Ratio values.")
                return
        else:
            ratios = {
                "1:1": (1, 1),
                "9:16": (9, 16),
                "16:9": (16, 9)
            }
            aspect_ratio = ratios.get(aspect_ratio_selection, (1, 1))

        parameters = {
            'icon_width_percentage': icon_width_percentage,
            'icon_height_percentage': icon_height_percentage,
            'black_bg_height_percentage': bg_height_percentage,
            'black_bg_transparency': bg_transparency,
            'line_transparency': line_transparency,
            'line_type': line_type,
            'open_image': self.open_image_var.get(),
            'line_color': self.line_color,
            'line_gradient_start': self.line_gradient_start,
            'line_gradient_end': self.line_gradient_end,
            'text_color': self.text_color,
            'description_offset_x': description_offset_x,
            'description_offset_y': description_offset_y,
            'icon_offset_x': icon_offset_x,
            'icon_offset_y': icon_offset_y,
            'descriptions': descriptions,
            'line_offset_y': line_offset_y,
            'enable_second_bg': enable_second_bg,
            'second_bg_position_x': second_bg_pos_x,
            'second_bg_position_y': second_bg_pos_y,
            'second_black_bg_height_percentage': second_bg_height_percentage,
            'second_black_bg_transparency': second_bg_transparency,
            'description_font_size': description_font_size,
            'aspect_ratio': aspect_ratio
        }

        if hasattr(self, 'selected_font'):
            self.config['FONT_PATH'] = self.selected_font
        else:
            self.config['FONT_PATH'] = self.config.get("FONT_PATH", "C:/Windows/Fonts/arial.ttf")
            self.logger.warning("selected_font not found. Using default font path.")

        self.logger.info("Starting image processing...")

        if self.mode.get() == "single":
            if not os.path.isfile(path):
                messagebox.showerror("Error", "Selected path is not a valid file.")
                return
            process_image(path, self.config, parameters, self.logger)
            messagebox.showinfo("Success", "Image processing completed.")
        else:
            if not os.path.isdir(path):
                messagebox.showerror("Error", "Selected path is not a valid folder.")
                return
            image_files = [os.path.join(path, f) for f in os.listdir(path)
                           if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            if not image_files:
                messagebox.showwarning("Warning", "No image files found in the selected folder.")
                return

            self.logger.info(f"Starting batch processing of {len(image_files)} images...")
            process_images_in_batch(image_files, self.config, parameters, self.logger)
            self.logger.info("Batch image processing completed.")
            messagebox.showinfo("Success", f"Batch processing completed. {len(image_files)} images processed.")

    def sync_slider_entry(self, value, entry_widget):
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, str(int(float(value))))
        self.update_preview()

    def sync_entry_slider(self, event, entry_widget, slider_widget):
        try:
            value = int(float(entry_widget.get()))
            slider_widget.set(value)
            self.update_preview()
        except ValueError:
            pass

    def on_closing(self):
        self.preview_window.destroy()
        self.master.destroy()
