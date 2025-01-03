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
        if platform.system() == 'Darwin':
            subprocess.call(['open', path])
        elif platform.system() == 'Windows':
            os.startfile(path)
        else:
            subprocess.call(['xdg-open', path])
        logger.info(f"Opened image: {path}")
    except Exception as e:
        logger.error(f"Failed to open image {path}: {e}")

def process_image(image_path, config, parameters, logger, preview=False, max_preview_size=(800, 800)):
    try:
        img = Image.open(image_path)
        original_size = img.size

        aspect_ratio = parameters.get('aspect_ratio', (1, 1))
        desired_ratio = aspect_ratio[0] / aspect_ratio[1]
        current_ratio = img.width / img.height

        if current_ratio > desired_ratio:
            new_width = int(desired_ratio * img.height)
            left = (img.width - new_width) / 2
            right = left + new_width
            img = img.crop((left, 0, right, img.height))
        elif current_ratio < desired_ratio:
            new_height = int(img.width / desired_ratio)
            top = (img.height - new_height) / 2
            bottom = top + new_height
            img = img.crop((0, top, img.width, bottom))

        if preview:
            ratio = min(max_preview_size[0] / img.width, max_preview_size[1] / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        draw = ImageDraw.Draw(img)
        width, height = img.size

        try:
            icon = Image.open(config['BRAND_ICON_PATH']).convert("RGBA")
        except FileNotFoundError:
            logger.error(f"Brand icon not found at {config['BRAND_ICON_PATH']}. Skipping image: {image_path}")
            return None

        icon_width = int(width * (parameters['icon_width_percentage'] / 100))
        icon_height = int(height * (parameters['icon_height_percentage'] / 100))
        try:
            icon = icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)
        except AttributeError:
            icon = icon.resize((icon_width, icon_height), Image.LANCZOS)

        try:
            font_size = int(parameters['description_font_size'])
            font_obj = ImageFont.truetype(config['FONT_PATH'], font_size)
        except IOError:
            logger.warning(f"Font file not found at {config['FONT_PATH']}. Using default font.")
            font_obj = ImageFont.load_default()

        black_bg_height_1 = int(height * (parameters['black_bg_height_percentage'] / 100))
        black_bg_1 = Image.new("RGBA", (width, black_bg_height_1), color=(0, 0, 0, int(255 * (parameters['black_bg_transparency'] / 100))))
        img.paste(black_bg_1, (0, height - black_bg_height_1), black_bg_1)

        def calculate_vertical_position(offset, height, element_height):
            relative_pos = offset / 100
            available_space = height - element_height
            middle_pos = available_space / 2
            return int(middle_pos + (relative_pos * middle_pos))

        icon_x = (width - icon_width) // 2 + parameters['icon_offset_x']
        icon_y = calculate_vertical_position(parameters['icon_offset_y'], height, icon_height)
        img.paste(icon, (icon_x, icon_y), icon)

        line_length = int(width * 0.4)
        line_y = calculate_vertical_position(parameters['line_offset_y'], height, 5)
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
            for i in range(0, line_length, dash_length + gap_length):
                start = (icon_x - line_length + i, line_y)
                end = (icon_x - line_length + i + dash_length, line_y)
                draw.line([start, end], fill=(*parameters['line_color'], line_transparency), width=line_thickness)
            for i in range(0, line_length, dash_length + gap_length):
                start = (icon_x + icon_width + i, line_y)
                end = (icon_x + icon_width + i + dash_length, line_y)
                draw.line([start, end], fill=(*parameters['line_color'], line_transparency), width=line_thickness)
        elif line_type == "Gradient":
            gradient_colors = create_gradient(parameters['line_gradient_start'], parameters['line_gradient_end'], line_length)
            for i, color in enumerate(gradient_colors):
                draw.line(
                    [(icon_x - line_length + i, line_y), (icon_x - line_length + i + 1, line_y)],
                    fill=(*color, line_transparency),
                    width=line_thickness
                )
                draw.line(
                    [(icon_x + icon_width + i, line_y), (icon_x + icon_width + i + 1, line_y)],
                    fill=(*color, line_transparency),
                    width=line_thickness
                )
        else:
            logger.warning(f"Unknown line type '{line_type}'. Skipping line drawing.")

        descriptions = parameters.get('descriptions', [])
        if descriptions:
            bbox = font_obj.getbbox("Text")
            text_height = bbox[3] - bbox[1]
            text_y = calculate_vertical_position(parameters['description_offset_y'], height, text_height)
            for desc in descriptions:
                bbox_desc = font_obj.getbbox(desc)
                text_width = bbox_desc[2] - bbox_desc[0]
                text_height_desc = bbox_desc[3] - bbox_desc[1]
                text_x = (width - text_width) // 2 + parameters['description_offset_x']
                draw.text((text_x, text_y), desc, font=font_obj, fill=tuple(parameters['text_color']))
                text_y += text_height_desc + 5

        if parameters['enable_second_bg']:
            black_bg_height_2 = int(height * (parameters['second_black_bg_height_percentage'] / 100))
            black_bg_2 = Image.new("RGBA", (width, black_bg_height_2), color=(0, 0, 0, int(255 * (parameters['second_black_bg_transparency'] / 100))))
            img.paste(black_bg_2, (parameters['second_bg_position_x'], parameters['second_bg_position_y']), black_bg_2)

        if img.mode == 'RGBA':
            img = img.convert('RGB')

        if preview:
            return img

        output_path = os.path.join(config['OUTPUT_DIR'], os.path.basename(image_path))
        img.save(output_path)
        logger.info(f"Processed: {output_path}")

        if parameters['open_image']:
            open_image(output_path, logger)
            
        return output_path
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
                try:
                    chunk = image_paths[i:i + chunk_size]
                    results = pool.map(func, chunk)
                    successful = len([r for r in results if r is not None])
                    processed += successful
                    logger.info(f"Processed {processed}/{total_images} images...")
                except Exception as e:
                    logger.error(f"Error processing chunk {i}-{i+chunk_size}: {str(e)}")
                    continue
        
        return processed
    except Exception as e:
        logger.error(f"Fatal error in batch processing: {str(e)}")
        logger.debug(traceback.format_exc())
        return 0
