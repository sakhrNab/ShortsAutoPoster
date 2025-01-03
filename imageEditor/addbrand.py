import os
import json
import logging
from PIL import Image, ImageDraw, ImageFont, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
from multiprocessing import Pool, cpu_count
from functools import partial
import subprocess
import platform
import threading
import time

# ----------------------------- Logging Setup -----------------------------

def setup_logging(log_file):
    logger = logging.getLogger("ImageEditor")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

# ------------------------- Configuration Loading ------------------------

def load_config(config_path='config.json'):
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file '{config_path}' not found.")
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

# ---------------------------- Gradient Function --------------------------

def create_gradient(color_start, color_end, length):
    r1, g1, b1 = color_start
    r2, g2, b2 = color_end
    gradient = []
    for i in range(length):
        ratio = i / max(length - 1, 1)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        gradient.append((r, g, b))
    return gradient

# ---------------------------- Image Processing ---------------------------

def process_image(image_path, config, parameters, logger, preview=False, max_preview_size=(800, 800)):
    try:
        # Load the image
        img = Image.open(image_path)
        original_size = img.size
        if preview:
            # Calculate scaling factor to maintain aspect ratio
            ratio = min(max_preview_size[0] / img.width, max_preview_size[1] / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Load and resize the brand icon dynamically
        try:
            icon = Image.open(config['BRAND_ICON_PATH']).convert("RGBA")
        except FileNotFoundError:
            logger.error(f"Brand icon not found at {config['BRAND_ICON_PATH']}. Skipping image: {image_path}")
            return None

        icon_width = int(width * (parameters['icon_width_percentage'] / 100))
        icon_height = int(height * (parameters['icon_height_percentage'] / 100))
        
        # Compatibility fix for Pillow versions
        try:
            icon = icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)
        except AttributeError:
            # For older Pillow versions
            icon = icon.resize((icon_width, icon_height), Image.LANCZOS)

        # Load font
        try:
            font_size = int(parameters['description_font_size'])
            font_obj = ImageFont.truetype(config['FONT_PATH'], font_size)
        except IOError:
            logger.warning(f"Font file not found at {config['FONT_PATH']}. Using default font.")
            font_obj = ImageFont.load_default()

        # Add first semi-transparent black background at the bottom
        black_bg_height_1 = int(height * (parameters['black_bg_height_percentage'] / 100))
        black_bg_1 = Image.new("RGBA", (width, black_bg_height_1), color=(0, 0, 0, int(255 * (parameters['black_bg_transparency'] / 100))))
        img.paste(black_bg_1, (0, height - black_bg_height_1), black_bg_1)

        # Calculate vertical positions with full range
        def calculate_vertical_position(offset, height, element_height):
            # Convert slider value (-100 to 100) to actual position
            # -100 means top of image, 0 means middle, 100 means bottom
            relative_pos = offset / 100  # Convert to -1 to 1 range
            available_space = height - element_height
            middle_pos = available_space / 2
            return int(middle_pos + (relative_pos * middle_pos))

        # Position icon with offsets
        icon_x = (width - icon_width) // 2 + parameters['icon_offset_x']
        icon_y = calculate_vertical_position(parameters['icon_offset_y'], height, icon_height)
        img.paste(icon, (icon_x, icon_y), icon)

        # Add gradient line based on user selection
        line_length = int(width * 0.4)
        line_y = calculate_vertical_position(parameters['line_offset_y'], height, 5)  # Positioning below the icon
        line_thickness = 5
        line_type = parameters['line_type']
        line_transparency = int(255 * (parameters['line_transparency'] / 100))

        if line_type == "Solid":
            draw.line(
                [(icon_x - line_length, line_y), (icon_x, line_y)],
                fill=(*parameters['line_color'], line_transparency),
                width=line_thickness
            )
            draw.line(
                [(icon_x + icon_width, line_y), (icon_x + icon_width + line_length, line_y)],
                fill=(*parameters['line_color'], line_transparency),
                width=line_thickness
            )
        elif line_type == "Dashed":
            dash_length = 15
            gap_length = 10
            # Left side dashed line
            for i in range(0, line_length, dash_length + gap_length):
                start = (icon_x - line_length + i, line_y)
                end = (icon_x - line_length + i + dash_length, line_y)
                draw.line([start, end], fill=(*parameters['line_color'], line_transparency), width=line_thickness)
            # Right side dashed line
            for i in range(0, line_length, dash_length + gap_length):
                start = (icon_x + icon_width + i, line_y)
                end = (icon_x + icon_width + i + dash_length, line_y)
                draw.line([start, end], fill=(*parameters['line_color'], line_transparency), width=line_thickness)
        elif line_type == "Gradient":
            gradient_colors = create_gradient(parameters['line_gradient_start'], parameters['line_gradient_end'], line_length)
            for i, color in enumerate(gradient_colors):
                # Left side gradient line
                draw.line(
                    [(icon_x - line_length + i, line_y), (icon_x - line_length + i + 1, line_y)],
                    fill=(*color, line_transparency),
                    width=line_thickness
                )
                # Right side gradient line
                draw.line(
                    [(icon_x + icon_width + i, line_y), (icon_x + icon_width + i + 1, line_y)],
                    fill=(*color, line_transparency),
                    width=line_thickness
                )
        else:
            logger.warning(f"Unknown line type '{line_type}'. Skipping line drawing.")

        # Add description text with formatting
        description = parameters['description']
        if description.strip():
            # Retrieve all tags
            tags = parameters.get("tags", [])
            if not tags:
                # No tags, draw normally
                text_bbox = draw.textbbox((0, 0), description, font=font_obj)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                text_x = (width - text_width) // 2 + parameters['description_offset_x']
                text_y = calculate_vertical_position(parameters['description_offset_y'], height, text_height)
                draw.text((text_x, text_y), description, font=font_obj, fill=tuple(parameters['text_color']))
            else:
                # Draw each formatted segment
                current_x = 0
                text_y = calculate_vertical_position(parameters['description_offset_y'], height, font_obj.getsize("Text")[1])
                for tag, text in tags:
                    # Determine color
                    if tag.startswith("color_"):
                        color_hex = tag.split("_")[1]
                        fill_color = tuple(int(color_hex[i:i+2], 16) for i in (1, 3, 5))  # Convert HEX to RGB
                    else:
                        fill_color = tuple(parameters['text_color'])
                    draw.text((current_x, text_y), text, font=font_obj, fill=fill_color)
                    text_width, _ = draw.textsize(text, font=font_obj)
                    current_x += text_width

        # Add second semi-transparent black background if enabled
        if parameters['enable_second_bg']:
            black_bg_height_2 = int(height * (parameters['second_black_bg_height_percentage'] / 100))
            black_bg_2 = Image.new("RGBA", (width, black_bg_height_2), color=(0, 0, 0, int(255 * (parameters['second_black_bg_transparency'] / 100))))
            img.paste(black_bg_2, (parameters['second_bg_position_x'], parameters['second_bg_position_y']), black_bg_2)

        # Convert back to RGB if saving as JPEG
        if img.mode == 'RGBA':
            img = img.convert('RGB')

        # For preview, return the Image object without saving
        if preview:
            return img

        # Save the edited image
        output_path = os.path.join(config['OUTPUT_DIR'], os.path.basename(image_path))
        img.save(output_path)
        logger.info(f"Processed: {output_path}")

        # Open image if selected
        if parameters['open_image']:
            open_image(output_path, logger)
    except Exception as e:
        logger.error(f"Failed to process image {image_path}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# ---------------------------- Open Image Function ------------------------

def open_image(path, logger):
    try:
        if platform.system() == 'Darwin':       # macOS
            subprocess.call(['open', path])
        elif platform.system() == 'Windows':    # Windows
            os.startfile(path)
        else:                                   # Linux variants
            subprocess.call(['xdg-open', path])
        logger.info(f"Opened image: {path}")
    except Exception as e:
        logger.error(f"Failed to open image {path}: {e}")

# ---------------------------- Scrollable Frame Class ----------------------

class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, borderwidth=0, background="#f0f0f0")
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, background="#f0f0f0")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Bind mouse wheel to scrolling
        self.bind_mouse_wheel()
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def bind_mouse_wheel(self):
        def _on_mousewheel(event):
            if platform.system() == 'Windows':
                delta = int(-1*(event.delta/120))
                self.canvas.yview_scroll(delta, "units")
            elif platform.system() == 'Darwin':
                delta = int(-1*(event.delta))
                self.canvas.yview_scroll(delta, "units")
            else:
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")
        
        # Windows and MacOS
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux
        self.canvas.bind_all("<Button-4>", _on_mousewheel)
        self.canvas.bind_all("<Button-5>", _on_mousewheel)

# ---------------------------- GUI Interface ------------------------------

class ImageEditorGUI:
    def __init__(self, master, config, logger):
        self.master = master
        self.config = config
        self.logger = logger
        master.title("Automated Image Editor")
        master.geometry("1000x700")  # Adjusted size
        master.resizable(True, True)  # Allow window to be resizable

        # Apply a modern theme
        style = ttk.Style()
        if platform.system() == 'Windows':
            style.theme_use('vista')
        elif platform.system() == 'Darwin':
            style.theme_use('clam')
        else:
            style.theme_use('clam')  # Fallback theme

        # Create PanedWindow
        self.paned_window = ttk.Panedwindow(master, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Left pane: Scrollable controls
        self.controls_frame = ScrollableFrame(self.paned_window)
        self.paned_window.add(self.controls_frame, weight=3)

        # Initialize a separate preview window
        self.preview_window = tk.Toplevel(master)
        self.preview_window.title("Live Preview")
        self.preview_window.geometry("400x400")  # Initial size
        self.preview_window.resizable(True, True)
        self.preview_label = tk.Label(self.preview_window)
        self.preview_label.pack(fill="both", expand=True)
        self.preview_window.attributes('-topmost', True)

        # Bind the main window close event to also close the preview window
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Processing Mode
        self.mode = tk.StringVar(value="single")

        self.mode_frame = tk.LabelFrame(self.controls_frame.scrollable_frame, text="Processing Mode", padx=10, pady=10)
        self.mode_frame.pack(padx=10, pady=10, fill="x")

        self.single_rb = tk.Radiobutton(self.mode_frame, text="Process a Single Image", variable=self.mode, value="single")
        self.single_rb.pack(anchor="w", padx=10, pady=2)

        self.batch_rb = tk.Radiobutton(self.mode_frame, text="Process Multiple Images in a Folder", variable=self.mode, value="batch")
        self.batch_rb.pack(anchor="w", padx=10, pady=2)

        # File/Folder Selection
        self.selection_frame = tk.Frame(self.controls_frame.scrollable_frame)
        self.selection_frame.pack(padx=10, pady=5, fill="x")

        self.path_label = tk.Label(self.selection_frame, text="Image/Folder Path:")
        self.path_label.pack(side="left", padx=5)

        self.path_entry = tk.Entry(self.selection_frame, width=50)
        self.path_entry.pack(side="left", padx=5)

        self.browse_button = tk.Button(self.selection_frame, text="Browse", command=self.browse)
        self.browse_button.pack(side="left", padx=5)

        # Description Input
        self.description_frame = tk.Frame(self.controls_frame.scrollable_frame)
        self.description_frame.pack(padx=10, pady=5, fill="x")

        self.description_label = tk.Label(self.description_frame, text="Description:")
        self.description_label.pack(side="left", padx=5)

        self.description_text = tk.Text(self.description_frame, height=2, width=50)
        self.description_text.pack(side="left", padx=5)
        self.description_text.insert("1.0", self.config.get("DESCRIPTION", "Your Brand Description"))

        # Formatting Toolbar
        self.format_toolbar = tk.Frame(self.controls_frame.scrollable_frame)
        self.format_toolbar.pack(padx=10, pady=5, fill="x")

        self.color_button = tk.Button(self.format_toolbar, text="Change Color", command=self.change_text_color)
        self.color_button.pack(side="left", padx=5)

        self.bold_button = tk.Button(self.format_toolbar, text="Bold", command=self.toggle_bold)
        self.bold_button.pack(side="left", padx=5)

        self.italic_button = tk.Button(self.format_toolbar, text="Italic", command=self.toggle_italic)
        self.italic_button.pack(side="left", padx=5)

        # Parameters Group Frame
        self.param_group_frame = tk.Frame(self.controls_frame.scrollable_frame)
        self.param_group_frame.pack(padx=10, pady=10, fill="both", expand=True)

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

        # Background Settings Frame
        self.bg_settings_frame = tk.LabelFrame(self.param_group_frame, text="Background Settings", padx=10, pady=10)
        self.bg_settings_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

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

        # Line Settings Frame
        self.line_settings_frame = tk.LabelFrame(self.param_group_frame, text="Line Settings", padx=10, pady=10)
        self.line_settings_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

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

        # Text Settings Frame
        self.text_settings_frame = tk.LabelFrame(self.param_group_frame, text="Text Settings", padx=10, pady=10)
        self.text_settings_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        # Text Color with Button
        self.text_color_label = tk.Label(self.text_settings_frame, text="Text Color:")
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
        self.font_size_spinbox.insert(0, "24")  # Default font size

        # Enable Second Black Background
        self.second_bg_var = tk.BooleanVar(value=False)
        self.enable_second_bg_rb = tk.Checkbutton(self.param_group_frame, text="Enable Second Black Background", variable=self.second_bg_var, command=self.toggle_second_bg)
        self.enable_second_bg_rb.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        # Second Black Background Positioning
        self.second_bg_position_frame = tk.LabelFrame(self.param_group_frame, text="Second Background Position", padx=10, pady=10)
        self.second_bg_position_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="we")
        self.second_bg_position_frame.grid_remove()  # Hide initially

        tk.Label(self.second_bg_position_frame, text="X Position:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_pos_x_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_pos_x_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_pos_x_entry.insert(0, "0")  # Default X position

        tk.Label(self.second_bg_position_frame, text="Y Position:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_pos_y_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_pos_y_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_pos_y_entry.insert(0, "0")  # Default Y position

        tk.Label(self.second_bg_position_frame, text="Height (%):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_height_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_height_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_height_entry.insert(0, "10")  # Default height percentage

        tk.Label(self.second_bg_position_frame, text="Transparency (%):").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.second_bg_transparency_entry = tk.Entry(self.second_bg_position_frame, width=5)
        self.second_bg_transparency_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.second_bg_transparency_entry.insert(0, "50")  # Default transparency

        # Position Adjustments with grouped layout
        self.position_adjustments_frame = tk.LabelFrame(self.controls_frame.scrollable_frame, text="Position Adjustments", padx=10, pady=10)
        self.position_adjustments_frame.pack(padx=10, pady=10, fill="x")

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

        # Add Open Image Checkbox (near the start button)
        self.open_image_var = tk.BooleanVar(value=True)  # Default to True
        self.open_image_cb = tk.Checkbutton(
            self.controls_frame.scrollable_frame, 
            text="Open Image After Processing", 
            variable=self.open_image_var
        )
        self.open_image_cb.pack(padx=10, pady=5)  # Pack it before the start button

        # Start Button should be after this
        self.start_button = tk.Button(self.controls_frame.scrollable_frame, text="Start Processing", command=self.start_processing)
        self.start_button.pack(padx=10, pady=10)

        # Log Display
        self.log_frame = tk.LabelFrame(self.controls_frame.scrollable_frame, text="Log", padx=10, pady=10)
        self.log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_text = tk.Text(self.log_frame, height=10, state='disabled')
        self.log_text.pack(fill="both", expand=True)

        # Configure logging to also write to the log_text widget
        self.setup_gui_logging()

        # Initialize the preview image
        self.preview_image = None
        self.preview_thread = None
        self.preview_lock = threading.Lock()
        self.last_preview_time = time.time()

        # Initialize with default parameters
        self.initialize_preview()

    def setup_gui_logging(self):
        # Create a handler that writes log messages to the Text widget
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

        # Correct Formatter with 'levelname'
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

    # Text Formatting Methods
    def change_text_color(self):
        color_code = colorchooser.askcolor(title="Choose Text Color")
        if color_code and color_code[1]:
            selected_text = self.description_text.tag_ranges(tk.SEL)
            if selected_text:
                tag_name = f"color_{color_code[1][1:]}"  # e.g., color_ff0000
                self.description_text.tag_add(tag_name, "sel.first", "sel.last")
                self.description_text.tag_config(tag_name, foreground=color_code[1])
                self.logger.info(f"Changed color of selected text to {color_code[1]}")

    def toggle_bold(self):
        selected_text = self.description_text.tag_ranges(tk.SEL)
        if selected_text:
            tag_name = "bold"
            if "bold" in self.description_text.tag_names(tk.SEL_FIRST):
                self.description_text.tag_remove(tag_name, "sel.first", "sel.last")
            else:
                self.description_text.tag_add(tag_name, "sel.first", "sel.last")
                # Note: To implement bold, you may need a separate bold font file
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
                # Note: To implement italic, you may need a separate italic font file
                try:
                    italic_font = ImageFont.truetype(self.config['FONT_PATH'], int(self.font_size_spinbox.get()))
                    self.description_text.tag_config(tag_name, font=italic_font)
                except IOError:
                    self.logger.warning("Italic font not found. Using default font.")
            self.update_preview()

    def get_tags_from_description(self):
        # Extract tags and associated text
        tags = []
        index = "1.0"
        while True:
            if index == '':
                break
            # Get next tag
            current_tags = self.description_text.tag_names(index)
            if current_tags:
                for tag in current_tags:
                    if tag.startswith("color_") or tag in ["bold", "italic"]:
                        # Get the text for this tag
                        tag_ranges = self.description_text.tag_ranges(tag)
                        for i in range(0, len(tag_ranges), 2):
                            start = tag_ranges[i]
                            end = tag_ranges[i+1]
                            text = self.description_text.get(start, end)
                            tags.append((tag, text))
            index = self.description_text.index(f"{index} +1c")
            if index.startswith(str(float(index))):  # If index becomes invalid, break
                break
        return tags

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
        color_code = colorchooser.askcolor(title="Choose Description Text Color")
        if color_code and color_code[0]:
            self.text_color = color_code[0]
            self.logger.info(f"Selected Description Text Color: {self.text_color}")
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

    def bind_preview_events(self):
        # Bind events to update preview when parameters change
        # For Entry and Text widgets, use trace or bind events
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

    def initialize_preview(self):
        # Set default values if not already set
        self.line_color = self.config.get("LINE_COLOR", (255, 255, 255))
        self.line_gradient_start = self.config.get("LINE_GRADIENT_START", (255, 69, 0))
        self.line_gradient_end = self.config.get("LINE_GRADIENT_END", (30, 144, 255))
        self.text_color = self.config.get("TEXT_COLOR", (255, 255, 255))

        # Start the initial preview
        self.update_preview()

    def update_preview(self, event=None):
        # Debounce the preview updates to avoid excessive processing
        current_time = time.time()
        if current_time - self.last_preview_time < 0.3:
            return
        self.last_preview_time = current_time

        # Cancel previous preview thread if running
        if self.preview_thread and self.preview_thread.is_alive():
            return  # Let the existing thread finish

        # Start a new thread for preview
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
                # Collect all image paths
                image_paths = [os.path.join(path, f) for f in os.listdir(path)
                               if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                if not image_paths:
                    self.logger.warning("No image files found for preview.")
                    return

            # For preview, only process the first image
            image_path = image_paths[0]

            # Gather parameters
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
            # open_image = self.open_image_var.get()  # Not needed for preview

            # Gather position adjustments
            line_offset_x = self.line_offset_x_slider.get()
            line_offset_y = self.line_offset_y_slider.get()
            description_offset_x = self.desc_offset_x_slider.get()
            description_offset_y = self.desc_offset_y_slider.get()
            icon_offset_x = self.icon_offset_x_slider.get()
            icon_offset_y = self.icon_offset_y_slider.get()

            description = self.description_text.get("1.0", tk.END).strip()

            # Gather second background parameters if enabled
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

            parameters = {
                'icon_width_percentage': icon_width_percentage,
                'icon_height_percentage': icon_height_percentage,
                'black_bg_height_percentage': bg_height_percentage,
                'black_bg_transparency': bg_transparency,
                'line_transparency': line_transparency,
                'line_type': line_type,
                'open_image': False,  # No need to open image in preview
                'line_color': self.line_color,
                'line_gradient_start': self.line_gradient_start,
                'line_gradient_end': self.line_gradient_end,
                'text_color': self.text_color,
                'description_offset_x': description_offset_x,
                'description_offset_y': description_offset_y,
                'icon_offset_x': icon_offset_x,
                'icon_offset_y': icon_offset_y,
                'description': description,
                'line_offset_y': line_offset_y,  # Ensure this parameter is included
                'enable_second_bg': enable_second_bg,
                'second_bg_position_x': second_bg_pos_x,
                'second_bg_position_y': second_bg_pos_y,
                'second_black_bg_height_percentage': second_bg_height_percentage,
                'second_black_bg_transparency': second_bg_transparency,
                'description_font_size': description_font_size
            }

            # Generate preview image
            preview_img = process_image(image_path, self.config, parameters, self.logger, preview=True)
            if preview_img:
                # Convert PIL image to ImageTk for Tkinter
                preview_img_tk = ImageTk.PhotoImage(preview_img)
                # Update the preview_label in the main thread
                self.preview_label.after(0, self.display_preview, preview_img_tk)
            else:
                self.logger.warning("Failed to generate preview.")

    def display_preview(self, img_tk):
        self.preview_label.configure(image=img_tk)
        self.preview_label.image = img_tk  # Keep a reference to prevent garbage collection
        # Optionally adjust the preview window size based on image
        self.preview_window.geometry(f"{img_tk.width()}x{img_tk.height()}")

    def start_processing(self):
        path = self.path_entry.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select an image or folder path.")
            return

        # Collect and validate parameters
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
        open_image = self.open_image_var.get()

        # Gather position adjustments
        line_offset_x = self.line_offset_x_slider.get()
        line_offset_y = self.line_offset_y_slider.get()
        description_offset_x = self.desc_offset_x_slider.get()
        description_offset_y = self.desc_offset_y_slider.get()
        icon_offset_x = self.icon_offset_x_slider.get()
        icon_offset_y = self.icon_offset_y_slider.get()

        description = self.description_text.get("1.0", tk.END).strip()

        # Gather second background parameters if enabled
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

        parameters = {
            'icon_width_percentage': icon_width_percentage,
            'icon_height_percentage': icon_height_percentage,
            'black_bg_height_percentage': bg_height_percentage,
            'black_bg_transparency': bg_transparency,
            'line_transparency': line_transparency,
            'line_type': line_type,
            'open_image': open_image,
            'line_color': self.line_color,
            'line_gradient_start': self.line_gradient_start,
            'line_gradient_end': self.line_gradient_end,
            'text_color': self.text_color,
            'description_offset_x': description_offset_x,
            'description_offset_y': description_offset_y,
            'icon_offset_x': icon_offset_x,
            'icon_offset_y': icon_offset_y,
            'description': description,
            'line_offset_y': line_offset_y,  # Ensure this parameter is included
            'enable_second_bg': enable_second_bg,
            'second_bg_position_x': second_bg_pos_x,
            'second_bg_position_y': second_bg_pos_y,
            'second_black_bg_height_percentage': second_bg_height_percentage,
            'second_black_bg_transparency': second_bg_transparency,
            'description_font_size': description_font_size
        }

        # Update font path in config
        if hasattr(self, 'selected_font'):
            self.config['FONT_PATH'] = self.selected_font
        else:
            # If selected_font is not set, use the default from config
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
            # Collect all image paths
            image_files = [os.path.join(path, f) for f in os.listdir(path)
                           if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            if not image_files:
                messagebox.showwarning("Warning", "No image files found in the selected folder.")
                return

            # Process images in chunks to avoid memory issues
            chunk_size = 10  # Process 10 images at a time
            total_images = len(image_files)
            processed = 0

            with Pool(processes=cpu_count()) as pool:
                # Partial function with fixed arguments
                func = partial(process_image, config=self.config, 
                           parameters=parameters, logger=self.logger, preview=False)

                # Process images in chunks
                for i in range(0, total_images, chunk_size):
                    chunk = image_files[i:i + chunk_size]
                    pool.map(func, chunk)
                    processed += len(chunk)
                    self.logger.info(f"Processed {processed}/{total_images} images...")

            self.logger.info("Batch image processing completed.")
            messagebox.showinfo("Success", f"Batch processing completed. {total_images} images processed.")

    def sync_slider_entry(self, value, entry_widget):
        """Synchronize slider value with entry widget and trigger preview update"""
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, str(int(float(value))))
        self.update_preview()

    def sync_entry_slider(self, event, entry_widget, slider_widget):
        """Synchronize entry value with slider widget and trigger preview update"""
        try:
            value = int(float(entry_widget.get()))
            slider_widget.set(value)
            self.update_preview()
        except ValueError:
            pass

    def on_closing(self):
        self.preview_window.destroy()
        self.master.destroy()

    def get_tags_from_description(self):
        # Extract tags and associated text
        tags = []
        index = "1.0"
        while True:
            if index == '':
                break
            # Get next tag
            current_tags = self.description_text.tag_names(index)
            if current_tags:
                for tag in current_tags:
                    if tag.startswith("color_") or tag in ["bold", "italic"]:
                        # Get the text for this tag
                        tag_ranges = self.description_text.tag_ranges(tag)
                        for i in range(0, len(tag_ranges), 2):
                            start = tag_ranges[i]
                            end = tag_ranges[i+1]
                            text = self.description_text.get(start, end)
                            tags.append((tag, text))
            index = self.description_text.index(f"{index} +1c")
            if index.startswith(str(float(index))):  # If index becomes invalid, break
                break
        return tags

    # Text Formatting Methods are already defined above

# --------------------------- Main Functionality ---------------------------

def main():
    try:
        # Load configuration
        config = load_config()
        
        # Setup logging
        logger = setup_logging(config.get("LOG_FILE", "image_editor.log"))
        logger.info("Image Editor Started.")

        # Ensure output directory exists
        os.makedirs(config['OUTPUT_DIR'], exist_ok=True)

        # Initialize GUI
        root = tk.Tk()
        app = ImageEditorGUI(root, config, logger)
        root.mainloop()

        logger.info("Image Editor Finished.")
    except Exception as e:
        print(f"Error in main: {e}")
        return

if __name__ == "__main__":
    main()
