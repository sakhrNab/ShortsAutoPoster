from tkinter import colorchooser

class ColorPickerDialog:
    def __init__(self, parent, initial_color="#FFFFFF"):
        self.result = initial_color
        # Convert the initial color to RGB for the color chooser
        rgb_color = self.convert_to_rgb(initial_color)
        
        # Show color chooser dialog
        color = colorchooser.askcolor(
            color=rgb_color,
            parent=parent,
            title="Choose Color"
        )
        
        if color and color[1]:  # color is ((r,g,b), hex_value)
            self.result = color[1]  # Use hex value for consistency

    def convert_to_rgb(self, color):
        """Convert any color format to RGB tuple"""
        color_map = {
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255),
            'purple': (128, 0, 128),
            'pink': (255, 192, 203)
        }
        
        try:
            # Handle named colors
            if isinstance(color, str):
                color = color.lower().strip()
                if color in color_map:
                    return color_map[color]
                
                # Handle hex colors
                if color.startswith('#'):
                    color = color.lstrip('#')
                    if len(color) == 6:
                        r = int(color[0:2], 16)
                        g = int(color[2:4], 16)
                        b = int(color[4:6], 16)
                        return (r, g, b)
                
            # Handle RGB tuple/list
            elif isinstance(color, (tuple, list)) and len(color) == 3:
                return tuple(map(int, color))
                
        except (ValueError, AttributeError):
            pass
            
        return (255, 255, 255)  # Default to white
