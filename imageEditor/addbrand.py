import os
import json
import logging
from PIL import Image, ImageDraw, ImageFont, ImageColor
import tkinter as tk
from tkinter import filedialog, messagebox
from multiprocessing import Pool, cpu_count
from functools import partial

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

def process_image(image_path, config, percentages, logger):
    try:
        # Load the image
        img = Image.open(image_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Load and resize the brand icon dynamically
        icon = Image.open(config['BRAND_ICON_PATH']).convert("RGBA")
        icon_width = int(width * (percentages['icon_width_percentage'] / 100))
        icon_height = int(height * (percentages['icon_height_percentage'] / 100))
        icon = icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)

        # Load font
        try:
            font_size = int(height * 0.03)
            font = ImageFont.truetype(config['FONT_PATH'], font_size)
        except IOError:
            logger.warning(f"Font file not found at {config['FONT_PATH']}. Using default font.")
            font = ImageFont.load_default()

        # Add semi-transparent black background at the bottom
        black_bg_height = int(height * (percentages['black_bg_height_percentage'] / 100))
        black_bg = Image.new("RGBA", (width, black_bg_height), color=(0, 0, 0, 128))  # 50% transparency
        img.paste(black_bg, (0, height - black_bg_height), black_bg)

        # Position icon
        icon_x = (width - icon_width) // 2
        icon_y = height - black_bg_height + (black_bg_height - icon_height) // 2
        img.paste(icon, (icon_x, icon_y), icon)

        # Add gradient line
        line_length = int(width * 0.4)
        line_y = height - black_bg_height // 2
        line_thickness = 5
        gradient_colors = create_gradient(config['LINE_COLOR'], config['LINE_COLOR'], line_length)  # Single color as placeholder

        # For a more appealing gradient, you might want to set different start and end colors
        # Example: gradient from orange to blue
        gradient_colors = create_gradient((255, 69, 0), (30, 144, 255), line_length)

        def add_gradient_line(draw, start_x, y, thickness, gradient_colors):
            for i, color in enumerate(gradient_colors):
                draw.line([(start_x + i, y), (start_x + i, y)], fill=color, width=thickness)

        # Left side gradient line
        add_gradient_line(draw, icon_x - line_length, line_y, line_thickness, gradient_colors)
        # Right side gradient line
        add_gradient_line(draw, icon_x + icon_width, line_y, line_thickness, gradient_colors)

        # Add description text
        description = config['DESCRIPTION']
        text_bbox = draw.textbbox((0, 0), description, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (width - text_width) // 2
        text_y = height - black_bg_height + (black_bg_height - text_height) // 2
        draw.text((text_x, text_y), description, font=font, fill=tuple(config['TEXT_COLOR']))

        # Convert back to RGB if saving as JPEG
        if img.mode == 'RGBA':
            img = img.convert('RGB')

        # Save the edited image
        output_path = os.path.join(config['OUTPUT_DIR'], os.path.basename(image_path))
        img.save(output_path)
        logger.info(f"Processed: {output_path}")

    except Exception as e:
        logger.error(f"Failed to process {image_path}: {e}")

# -------------------------- Parameter Collection -------------------------

def collect_parameters(logger):
    percentages = {}
    try:
        icon_width_percentage = float(input("Enter the icon width percentage (e.g., 40 for 40%): "))
        if not (0 < icon_width_percentage < 100):
            raise ValueError
        percentages['icon_width_percentage'] = icon_width_percentage
    except ValueError:
        logger.error("Invalid input for icon width percentage. Please enter a number between 0 and 100.")
        raise

    try:
        icon_height_percentage = float(input("Enter the icon height percentage (e.g., 10 for 10%): "))
        if not (0 < icon_height_percentage < 100):
            raise ValueError
        percentages['icon_height_percentage'] = icon_height_percentage
    except ValueError:
        logger.error("Invalid input for icon height percentage. Please enter a number between 0 and 100.")
        raise

    try:
        black_bg_height_percentage = float(input("Enter the size of black background in percentage (e.g., 15 for 15%): "))
        if not (0 < black_bg_height_percentage < 100):
            raise ValueError
        percentages['black_bg_height_percentage'] = black_bg_height_percentage
    except ValueError:
        logger.error("Invalid input for black background height percentage. Please enter a number between 0 and 100.")
        raise

    return percentages

# ---------------------------- GUI Interface ------------------------------

class ImageEditorGUI:
    def __init__(self, master, config, logger):
        self.master = master
        self.config = config
        self.logger = logger
        master.title("Automated Image Editor")

        # Single or Batch Processing
        self.mode = tk.StringVar(value="single")

        self.mode_frame = tk.LabelFrame(master, text="Processing Mode")
        self.mode_frame.pack(padx=10, pady=10, fill="x")

        self.single_rb = tk.Radiobutton(self.mode_frame, text="Process a Single Image", variable=self.mode, value="single")
        self.single_rb.pack(anchor="w", padx=10, pady=2)

        self.batch_rb = tk.Radiobutton(self.mode_frame, text="Process Multiple Images in a Folder", variable=self.mode, value="batch")
        self.batch_rb.pack(anchor="w", padx=10, pady=2)

        # File/Folder Selection
        self.selection_frame = tk.Frame(master)
        self.selection_frame.pack(padx=10, pady=5, fill="x")

        self.path_label = tk.Label(self.selection_frame, text="Image Path:")
        self.path_label.pack(side="left", padx=5)

        self.path_entry = tk.Entry(self.selection_frame, width=50)
        self.path_entry.pack(side="left", padx=5)

        self.browse_button = tk.Button(self.selection_frame, text="Browse", command=self.browse)
        self.browse_button.pack(side="left", padx=5)

        # Percentage Inputs
        self.percent_frame = tk.LabelFrame(master, text="Parameters")
        self.percent_frame.pack(padx=10, pady=10, fill="x")

        self.icon_width_label = tk.Label(self.percent_frame, text="Icon Width (%):")
        self.icon_width_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.icon_width_entry = tk.Entry(self.percent_frame)
        self.icon_width_entry.grid(row=0, column=1, padx=5, pady=5)

        self.icon_height_label = tk.Label(self.percent_frame, text="Icon Height (%):")
        self.icon_height_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.icon_height_entry = tk.Entry(self.percent_frame)
        self.icon_height_entry.grid(row=1, column=1, padx=5, pady=5)

        self.bg_height_label = tk.Label(self.percent_frame, text="Black Background Height (%):")
        self.bg_height_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.bg_height_entry = tk.Entry(self.percent_frame)
        self.bg_height_entry.grid(row=2, column=1, padx=5, pady=5)

        # Start Button
        self.start_button = tk.Button(master, text="Start Processing", command=self.start_processing)
        self.start_button.pack(padx=10, pady=10)

        # Log Display
        self.log_frame = tk.LabelFrame(master, text="Log")
        self.log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_text = tk.Text(self.log_frame, height=10, state='disabled')
        self.log_text.pack(fill="both", expand=True)

        # Configure logging to also write to the log_text widget
        self.setup_gui_logging()

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
        else:
            folder_path = filedialog.askdirectory(title="Select Folder")
            if folder_path:
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, folder_path)

    def start_processing(self):
        path = self.path_entry.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select an image or folder path.")
            return

        try:
            icon_width_percentage = float(self.icon_width_entry.get())
            icon_height_percentage = float(self.icon_height_entry.get())
            bg_height_percentage = float(self.bg_height_entry.get())

            if not (0 < icon_width_percentage < 100 and
                    0 < icon_height_percentage < 100 and
                    0 < bg_height_percentage < 100):
                raise ValueError

            percentages = {
                'icon_width_percentage': icon_width_percentage,
                'icon_height_percentage': icon_height_percentage,
                'black_bg_height_percentage': bg_height_percentage
            }
        except ValueError:
            messagebox.showerror("Error", "Please enter valid percentage values between 0 and 100.")
            return

        self.logger.info("Starting image processing...")

        if self.mode.get() == "single":
            if not os.path.isfile(path):
                messagebox.showerror("Error", "Selected path is not a valid file.")
                return
            process_image(path, self.config, percentages, self.logger)
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

            # Multiprocessing setup
            cpu_cores = cpu_count()
            pool = Pool(cpu_cores)

            # Partial function with fixed arguments
            func = partial(process_image, config=self.config, 
                           percentages=percentages, logger=self.logger)

            # Process images in parallel
            pool.map(func, image_files)
            pool.close()
            pool.join()

            self.logger.info("Batch image processing completed.")
            messagebox.showinfo("Success", "Batch image processing completed.")

# --------------------------- Main Functionality ---------------------------

def main():
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return

    # Setup logging
    logger = setup_logging(config.get("LOG_FILE", "image_editor.log"))
    logger.info("Image Editor Started.")

    # Ensure output directory exists
    try:
        os.makedirs(config['OUTPUT_DIR'], exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create output directory '{config['OUTPUT_DIR']}': {e}")
        return

    # Initialize GUI
    root = tk.Tk()
    app = ImageEditorGUI(root, config, logger)
    root.mainloop()

    logger.info("Image Editor Finished.")

if __name__ == "__main__":
    main()
