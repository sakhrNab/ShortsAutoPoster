# image_processor.py

import os
import subprocess
import platform
import logging
from PIL import Image, ImageDraw, ImageFont
from functools import partial
from multiprocessing import Pool, cpu_count
import traceback
from utils import create_gradient

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

def process_image(image_path, config, parameters, logger, preview=False, max_preview_size=(800, 800)):
    try:
        # Load the image
        img = Image.open(image_path)
        original_size = img.size

        # Aspect Ratio Transformation
        aspect_ratio = parameters.get('aspect_ratio', (1, 1))  # Default to 1:1
        desired_ratio = aspect_ratio[0] / aspect_ratio[1]
        current_ratio = img.width / img.height

        if current_ratio > desired_ratio:
            # Image is wider than desired ratio
            new_width = int(desired_ratio * img.height)
            left = (img.width - new_width) / 2
            right = left + new_width
            img = img.crop((left, 0, right, img.height))
            logger.debug(f"Cropped image width from {img.width + (img.width - new_width)} to {new_width}")
        elif current_ratio < desired_ratio:
            # Image is taller than desired ratio
            new_height = int(img.width / desired_ratio)
            top = (img.height - new_height) / 2
            bottom = top + new_height
            img = img.crop((0, top, img.width, bottom))
            logger.debug(f"Cropped image height from {img.height + (img.height - new_height)} to {new_height}")
        else:
            logger.debug("Image aspect ratio matches the desired aspect ratio. No cropping needed.")

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
                        fill_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))  # Convert HEX to RGB
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
        return img if preview else None
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {str(e)}")
        logger.debug(traceback.format_exc())
        return None

def process_images_in_batch(image_paths, config, parameters, logger, chunk_size=10):
    try:
        total_images = len(image_paths)
        processed = 0

        with Pool(processes=cpu_count()) as pool:
            func = partial(process_image, config=config, parameters=parameters, logger=logger, preview=False)
            for i in range(0, total_images, chunk_size):
                chunk = image_paths[i:i + chunk_size]
                pool.map(func, chunk)
                processed += len(chunk)
                logger.info(f"Processed {processed}/{total_images} images...")
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        logger.debug(traceback.format_exc())
