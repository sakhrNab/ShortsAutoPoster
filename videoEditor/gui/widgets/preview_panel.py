import os
import random
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

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

                    # Apply bold if enabled
                    if overlay.get('bold', False):
                        thickness = 3

                    # Apply italic by adjusting the font face
                    if overlay.get('italic', False):
                        font_face = cv2.FONT_HERSHEY_COMPLEX_SMALL

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
        """Convert any color format to BGR for OpenCV"""
        if not color:
            return (255, 255, 255)  # Default to white

        try:
            # Handle hex colors
            if color.startswith('#'):
                c = color.lstrip('#')
                if len(c) == 6:
                    r = int(c[0:2], 16)
                    g = int(c[2:4], 16)
                    b = int(c[4:6], 16)
                    return (b, g, r)  # Convert to BGR

            # Handle color names
            color_map = {
                'white': (255, 255, 255),
                'black': (0, 0, 0),
                'red': (0, 0, 255),      # BGR values
                'green': (0, 255, 0),
                'blue': (255, 0, 0),
                'yellow': (0, 255, 255),
                'cyan': (255, 255, 0),
                'magenta': (255, 0, 255),
                'purple': (128, 0, 128),
                'pink': (147, 192, 255)   # BGR for pink
            }
            
            color_lower = color.lower().strip()
            if color_lower in color_map:
                return color_map[color_lower]

            # Handle rgb() format
            if color.startswith('rgb'):
                rgb = tuple(map(int, color.strip('rgb()').split(',')))
                return (rgb[2], rgb[1], rgb[0])  # Convert to BGR
                
        except (ValueError, AttributeError):
            pass
            
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
