# ---------------------------- PreviewWindow Class ------------------------
import tkinter as tk

class PreviewWindow:
    def __init__(self, master):
        self.master = master
        self.preview_window = tk.Toplevel(master)
        self.preview_window.title("Live Preview")
        self.preview_window.geometry("500x500")
        self.preview_window.resizable(True, True)
        self.preview_label = tk.Label(self.preview_window)
        self.preview_label.pack(fill="both", expand=True)
        self.preview_window.attributes('-topmost', True)
        self.image = None  # Store the current image reference
        self.canvas = tk.Canvas(self.preview_window)
        self.canvas.pack(fill="both", expand=True)

    def display_preview(self, img_tk):
        self.preview_label.configure(image=img_tk)
        self.preview_label.image = img_tk
        self.preview_window.geometry(f"{img_tk.width()}x{img_tk.height()}")

    def update_size(self, width, height):
        """Update window size while maintaining minimum dimensions"""
        min_width = 400
        min_height = 400
        new_width = max(width, min_width)
        new_height = max(height, min_height)
        self.preview_window.geometry(f"{new_width}x{new_height}")


