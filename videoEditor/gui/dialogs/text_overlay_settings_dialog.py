import tkinter as tk
from tkinter import ttk, messagebox
from gui.dialogs.color_picker_dialog import ColorPickerDialog

class TextOverlaySettingsDialog:
    def __init__(self, parent, settings=None, preview_callback=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Text Overlay Settings")
        self.dialog.geometry("400x500")
        self.result = None
        self.preview_callback = preview_callback
        self.available_fonts = self.get_system_fonts()
        self.widgets_ready = False  # Add this flag
        self.create_widgets(settings)
        self.widgets_ready = True  # Set flag after widgets are created
        self.update_color_previews()  # Move this here

    def get_system_fonts(self):
        """Get list of available system fonts using cv2"""
        try:
            import matplotlib.font_manager
            fonts = [f.name for f in matplotlib.font_manager.fontManager.ttflist]
            # Add some common fonts that might not be detected
            common_fonts = ['Arial', 'Helvetica', 'Times New Roman', 'Courier New', 'Verdana']
            fonts.extend([f for f in common_fonts if f not in fonts])
            return sorted(set(fonts))  # Remove duplicates and sort
        except ImportError:
            # Fallback to basic fonts if matplotlib is not available
            return ['Arial', 'Helvetica', 'Times New Roman', 'Courier New', 'Verdana']

    def create_widgets(self, settings):
        settings = settings or {}
        
        # Text content
        ttk.Label(self.dialog, text="Text:").pack(pady=2)
        self.text = tk.Text(self.dialog, height=3)
        self.text.pack(fill='x', padx=5)
        if settings.get('text'):
            self.text.insert('1.0', settings['text'])
        # Add binding for text changes
        self.text.bind('<KeyRelease>', self.on_setting_changed)

        # Font settings frame
        font_frame = ttk.LabelFrame(self.dialog, text="Font Settings", padding="5")
        font_frame.pack(fill='x', padx=5, pady=5)

        # Font family dropdown
        ttk.Label(font_frame, text="Font:").pack(pady=2)
        self.font = ttk.Combobox(font_frame, values=self.available_fonts)
        self.font.pack(fill='x', padx=5)
        self.font.set(settings.get('font', 'Arial'))

        # Font size with real-time updates
        ttk.Label(font_frame, text="Font Size:").pack(pady=2)
        size_frame = ttk.Frame(font_frame)
        size_frame.pack(fill='x', padx=5)
        
        self.font_size = ttk.Entry(size_frame)
        self.font_size.pack(side='left', fill='x', expand=True)
        self.font_size.insert(0, str(settings.get('font_size', 24)))
        
        # Size adjustment buttons with immediate preview updates
        ttk.Button(size_frame, text="-", width=3, 
                  command=lambda: self.adjust_font_size(-2, update_preview=True)).pack(side='left', padx=2)
        ttk.Button(size_frame, text="+", width=3,
                  command=lambda: self.adjust_font_size(2, update_preview=True)).pack(side='left')

        # Style options
        style_frame = ttk.Frame(font_frame)
        style_frame.pack(fill='x', padx=5, pady=5)
        
        self.bold = tk.BooleanVar(value=settings.get('bold', False))
        self.italic = tk.BooleanVar(value=settings.get('italic', False))
        
        ttk.Checkbutton(style_frame, text="Bold", 
                       variable=self.bold).pack(side='left', padx=5)
        ttk.Checkbutton(style_frame, text="Italic", 
                       variable=self.italic).pack(side='left', padx=5)

        # Colors section with color pickers
        colors_frame = ttk.LabelFrame(self.dialog, text="Colors", padding="5")
        colors_frame.pack(fill='x', padx=5, pady=5)

        # Text color row with immediate preview
        text_color_frame = ttk.Frame(colors_frame)
        text_color_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(text_color_frame, text="Text Color:").pack(side='left')
        
        self.color = ttk.Entry(text_color_frame, width=10)
        self.color.pack(side='left', padx=5)
        self.color.insert(0, settings.get('color', 'white'))
        
        self.text_color_preview = tk.Label(text_color_frame, width=3, relief="sunken")
        self.text_color_preview.pack(side='left', padx=2)
        
        ttk.Button(text_color_frame, text="Pick", 
                  command=self.pick_text_color).pack(side='left', padx=5)

        # Background color row with immediate preview
        bg_color_frame = ttk.Frame(colors_frame)
        bg_color_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(bg_color_frame, text="Background Color:").pack(side='left')
        
        self.bg_color = ttk.Entry(bg_color_frame, width=10)
        self.bg_color.pack(side='left', padx=5)
        self.bg_color.insert(0, settings.get('bg_color', 'black'))
        
        self.bg_color_preview = tk.Label(bg_color_frame, width=3, relief="sunken")
        self.bg_color_preview.pack(side='left', padx=2)
        
        ttk.Button(bg_color_frame, text="Pick", 
                  command=self.pick_bg_color).pack(side='left', padx=5)

        # Background opacity
        opacity_frame = ttk.Frame(colors_frame)
        opacity_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(opacity_frame, text="Background Opacity (0-1):").pack(side='left')
        self.bg_opacity = ttk.Entry(opacity_frame, width=10)
        self.bg_opacity.pack(side='left', padx=5)
        self.bg_opacity.insert(0, str(settings.get('bg_opacity', 0.5)))

        # Update color previews
        self.update_color_previews()

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

        # Add change event bindings to all inputs
        self.font.bind('<<ComboboxSelected>>', self.on_setting_changed)
        self.font_size.bind('<KeyRelease>', self.on_setting_changed)
        self.color.bind('<KeyRelease>', self.on_setting_changed)
        self.bg_color.bind('<KeyRelease>', self.on_setting_changed)
        self.bg_opacity.bind('<KeyRelease>', self.on_setting_changed)
        self.position.bind('<<ComboboxSelected>>', self.on_setting_changed)
        self.margin.bind('<KeyRelease>', self.on_setting_changed)
        
        # Add trace to boolean variables
        self.bold.trace_add("write", self.on_bool_changed)
        self.italic.trace_add("write", self.on_bool_changed)

    def update_color_previews(self):
        """Update the color preview swatches"""
        if not self.widgets_ready:
            return
        try:
            # Update preview swatches with current colors
            text_color = self.color.get()
            bg_color = self.bg_color.get()
            
            # Handle hex colors properly
            if not text_color.startswith('#'):
                text_color = f"#{text_color}" if text_color else "#FFFFFF"
            if not bg_color.startswith('#'):
                bg_color = f"#{bg_color}" if bg_color else "#000000"
                
            self.text_color_preview.configure(bg=text_color)
            self.bg_color_preview.configure(bg=bg_color)
            self.on_setting_changed(None)
        except tk.TclError:
            pass  # Invalid color format

    def pick_text_color(self):
        """Open color picker for text color"""
        dialog = ColorPickerDialog(self.dialog, self.color.get())
        if dialog.result:
            self.color.delete(0, tk.END)
            self.color.insert(0, dialog.result)
            self.text_color_preview.configure(bg=dialog.result)
            self.on_setting_changed(None)

    def pick_bg_color(self):
        """Open color picker for background color"""
        dialog = ColorPickerDialog(self.dialog, self.bg_color.get())
        if dialog.result:
            self.bg_color.delete(0, tk.END)
            self.bg_color.insert(0, dialog.result)
            self.bg_color_preview.configure(bg=dialog.result)
            self.on_setting_changed(None)

    def adjust_font_size(self, delta, update_preview=False):
        """Adjust font size by delta amount"""
        try:
            current = int(self.font_size.get())
            new_size = max(8, min(72, current + delta))  # Limit size between 8 and 72
            self.font_size.delete(0, tk.END)
            self.font_size.insert(0, str(new_size))
            if update_preview:
                self.on_setting_changed(None)
        except ValueError:
            pass

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
                'margin': int(self.margin.get()),
                'bold': self.bold.get(),
                'italic': self.italic.get()
            }
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Error", "Please enter valid numbers for font size, opacity, and margin.")

    def cancel(self):
        self.dialog.destroy()

    def on_bool_changed(self, *args):
        """Handle changes in boolean variables"""
        self.on_setting_changed(None)

    def on_setting_changed(self, event):
        """Update preview when any setting changes"""
        if not self.widgets_ready:  # Check if widgets are ready
            return
        try:
            current_settings = self.get_current_settings()
            if current_settings and self.preview_callback:
                self.preview_callback(current_settings)
        except ValueError:
            pass  # Ignore invalid values during typing

    def get_current_settings(self):
        """Get current settings without validation"""
        try:
            return {
                'text': self.text.get('1.0', 'end-1c'),
                'font': self.font.get(),
                'font_size': int(self.font_size.get()),
                'color': self.color.get(),
                'bg_color': self.bg_color.get(),
                'bg_opacity': float(self.bg_opacity.get()),
                'position': self.position.get(),
                'margin': int(self.margin.get()),
                'bold': self.bold.get(),
                'italic': self.italic.get()
            }
        except (ValueError, tk.TclError):
            return None
