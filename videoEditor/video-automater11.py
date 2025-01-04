import os
import subprocess
import signal
import sys
from multiprocessing import Pool
import json
import yaml  # Add this import at the top

def init_worker():
    """
    Ignore SIGINT in worker processes to allow the main process to handle it.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def calculate_aspect_ratio(input_path):
    """
    Calculate the aspect ratio of the input video.

    Parameters:
        input_path (str): Path to the input video file.

    Returns:
        tuple: (width, height) of the video.
    """
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        input_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    width, height = map(int, result.stdout.strip().split('x'))
    return width, height

def get_custom_ratio():
    """Get custom aspect ratio dimensions from user."""
    print("\nEnter custom dimensions:")
    while True:
        try:
            width = int(input("Width in pixels (e.g., 1080): ").strip())
            height = int(input("Height in pixels (e.g., 1920): ").strip())
            
            if width <= 0 or height <= 0:
                print("Dimensions must be positive numbers")
                continue
                
            if width > 3840 or height > 3840:
                print("Warning: Large dimensions might impact performance")
                confirm = input("Continue? (y/n): ").lower()
                if confirm != 'y':
                    continue
            
            return (width, height)
        except ValueError:
            print("Please enter valid numbers")

def get_ratio_choice():
    """Get user's preferred aspect ratio choice."""
    print("\nSelect output aspect ratio:")
    print("1. Square (1:1)")
    print("2. Portrait (9:16)")
    print("3. Landscape (16:9)")
    print("4. Custom ratio")
    
    while True:
        choice = input("Enter your choice (1-4): ").strip()
        if choice == '4':
            return get_custom_ratio()
        elif choice in ['1', '2', '3']:
            return {'1': (1080, 1080), '2': (1080, 1920), '3': (1920, 1080)}[choice]

def get_black_background_preferences():
    """Get user preferences for bottom black background."""
    while True:
        add_bg = input("\nAdd black background at bottom? (y/n): ").lower()
        if add_bg not in ['y', 'n']:
            continue
        
        if add_bg == 'n':
            return None
        
        height = input("Enter height percentage (1-50): ").strip()
        try:
            height = float(height)
            if not 1 <= height <= 50:
                print("Height must be between 1 and 50")
                continue
        except ValueError:
            print("Please enter a valid number")
            continue
            
        opacity = input("Enter opacity (0-1, e.g., 0.7): ").strip()
        try:
            opacity = float(opacity)
            if not 0 <= opacity <= 1:
                print("Opacity must be between 0 and 1")
                continue
        except ValueError:
            print("Please enter a valid number")
            continue
            
        return {"height_percent": height, "opacity": opacity}

def get_video_positioning_preferences():
    """Get user preferences for video positioning within the frame."""
    while True:
        position = input("\nDo you want to position the video with black bars? (y/n): ").lower()
        if position not in ['y', 'n']:
            continue
            
        if position == 'n':
            return None
            
        bottom_height = input("Enter bottom black bar height percentage (1-50): ").strip()
        try:
            bottom_height = float(bottom_height)
            if not 1 <= bottom_height <= 50:
                print("Height must be between 1 and 50")
                continue
        except ValueError:
            print("Please enter a valid number")
            continue
            
        video_opacity = input("Enter opacity for black bars (0-1, e.g., 0.7): ").strip()
        try:
            video_opacity = float(video_opacity)
            if not 0 <= video_opacity <= 1:
                print("Opacity must be between 0 and 1")
                continue
        except ValueError:
            print("Please enter a valid number")
            continue
            
        return {
            "bottom_height_percent": bottom_height,
            "opacity": video_opacity
        }

def get_top_background_preferences():
    """Get user preferences for top black background."""
    while True:
        add_bg = input("\nAdd black background at top? (y/n): ").lower()
        if add_bg not in ['y', 'n']:
            continue
        
        if add_bg == 'n':
            return None
        
        height = input("Enter top bar height percentage (1-30): ").strip()
        try:
            height = float(height)
            if not 1 <= height <= 30:
                print("Height must be between 1 and 30")
                continue
        except ValueError:
            print("Please enter a valid number")
            continue
            
        opacity = input("Enter opacity (0-1, e.g., 0.7): ").strip()
        try:
            opacity = float(opacity)
            if not 0 <= opacity <= 1:
                print("Opacity must be between 0 and 1")
                continue
        except ValueError:
            print("Please enter a valid number")
            continue
            
        return {"height_percent": height, "opacity": opacity}

def get_icon_preferences():
    """Get user preferences for icon positioning and size."""
    print("\nIcon positioning and size (press Enter for defaults):")
    
    # Get width
    while True:
        width = input("Enter icon width (default 500, range 100-1000): ").strip()
        if not width:
            width = 500
            break
        try:
            width = int(width)
            if 100 <= width <= 1000:
                break
            print("Width must be between 100 and 1000")
        except ValueError:
            print("Please enter a valid number")
    
    # Get X position
    while True:
        x_pos = input("Enter X position (c=center, l=left, r=right, or 0-100%): ").strip()
        if not x_pos:
            x_pos = 'c'
        if x_pos in ['c', 'l', 'r'] or (x_pos.replace('.', '').isdigit() and 0 <= float(x_pos) <= 100):
            break
        print("Invalid position. Use 'c', 'l', 'r', or 0-100")
    
    # Get Y position
    while True:
        y_pos = input("Enter Y position (0-100%, default 12.5%): ").strip()
        if not y_pos:
            y_pos = "12.5"
            break
        try:
            y_pos = float(y_pos)
            if 0 <= y_pos <= 100:
                break
            print("Y position must be between 0 and 100")
        except ValueError:
            print("Please enter a valid number")
    
    return {
        "width": width,
        "x_position": x_pos,
        "y_position": float(y_pos)
    }

def generate_filter_complex(input_path, brand_icon, target_dimensions, black_bg_params=None, 
                          video_position_params=None, top_bg_params=None, icon_params=None):
    """Generate the filter_complex string with properly chained filters."""
    target_width, target_height = target_dimensions
    current_stage = "scaled"
    
    # Initial scaling and positioning
    if video_position_params:
        # Calculate video and black bar heights
        bottom_height = int(target_height * (video_position_params["bottom_height_percent"] / 100))
        video_height = target_height - bottom_height
        opacity = video_position_params["opacity"]
        
        filter_complex = (
            # Scale video to fit within the allocated space
            f"[0:v]scale={target_width}:{video_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:0:black[scaled];"
            
            # Add black background at the bottom
            f"[scaled]drawbox=x=0:y={video_height}:w={target_width}:h={bottom_height}:"
            f"color=black@{opacity}:t=fill[withbg]"
        )
        
        current_stage = "withbg"
    else:
        filter_complex = (
            f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black[{current_stage}]"
        )

    # Add top black background if requested
    if top_bg_params:
        height_pixels = int(target_height * (top_bg_params["height_percent"] / 100))
        filter_complex += (
            f";[{current_stage}]drawbox=x=0:y=0:w={target_width}:h={height_pixels}:"
            f"color=black@{top_bg_params['opacity']}:t=fill[top]"
        )
        current_stage = "top"

    # Add bottom black background if requested
    if black_bg_params:
        height_pixels = int(target_height * (black_bg_params["height_percent"] / 100))
        y_position = target_height - height_pixels
        filter_complex += (
            f";[{current_stage}]drawbox=x=0:y={y_position}:w={target_width}:h={height_pixels}:"
            f"color=black@{black_bg_params['opacity']}:t=fill[bg]"
        )
        current_stage = "bg"

    # Process icon positioning
    icon_params = icon_params or {"width": 500, "x_position": "c", "y_position": 12.5}
    icon_width = icon_params["width"]
    
    # Calculate X position
    x_pos = icon_params["x_position"]
    if x_pos == "c":
        x_formula = "(main_w-overlay_w)/2"
    elif x_pos == "l":
        x_formula = "10"
    elif x_pos == "r":
        x_formula = "main_w-overlay_w-10"
    else:
        x_formula = f"main_w*{float(x_pos)/100}"
    
    # Calculate Y position
    y_formula = f"main_h*{icon_params['y_position']/100}"

    # Add the brand icon overlay
    filter_complex += (
        f";[1:v]scale={icon_width}:-1[icon];"
        f"[{current_stage}][icon]overlay={x_formula}:{y_formula}"
    )
    
    return filter_complex

def process_video(video_args):
    """
    Encodes a single video with FFmpeg using NVENC for hardware acceleration.

    Parameters:
        video_args (tuple): Contains input_path, brand_icon, output_path, filter_complex.

    Returns:
        str: Path to the processed video file.
    """
    input_path, brand_icon, output_path, target_dimensions, black_bg_params, \
    video_position_params, top_bg_params, icon_params = video_args
    
    filter_complex = generate_filter_complex(
        input_path, brand_icon, target_dimensions, black_bg_params,
        video_position_params, top_bg_params, icon_params
    )

    command = [
        "ffmpeg",                # Use "ffmpeg" directly (ensure it's in PATH)
        "-i", input_path,        # Input video file
        "-i", brand_icon,        # Input brand icon image
        "-filter_complex", filter_complex,  # Complex filter for scaling, padding, and overlay
        "-c:v", "h264_nvenc",    # Use NVIDIA NVENC encoder
        "-preset", "p4",         # Preset for balance between speed and quality
        "-cq", "20",             # Constant quality parameter (lower is better quality)
        "-c:a", "copy",          # Copy audio without re-encoding
        "-y",                    # Overwrite output files without asking
        output_path              # Output video file
    ]

    try:
        # Run FFmpeg and capture output for debugging
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg failed for {input_path}:\n{e.stderr}")
        raise e

def get_validated_input(prompt_message, is_folder=False, is_file=False):
    """
    Prompts the user for input and validates the provided path.

    Parameters:
        prompt_message (str): The message displayed to the user.
        is_folder (bool): If True, validates the input as a folder path.
        is_file (bool): If True, validates the input as a file path.

    Returns:
        str: A validated path entered by the user.
    """
    while True:
        path = input(prompt_message).strip('"').strip("'")  # Remove potential quotes
        if is_folder:
            if os.path.isdir(path):
                return path
            else:
                print(f"[ERROR] The folder '{path}' does not exist. Please enter a valid folder path.\n")
        elif is_file:
            if os.path.isfile(path):
                return path
            else:
                print(f"[ERROR] The file '{path}' does not exist. Please enter a valid file path.\n")
        else:
            # If no validation is required
            return path

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("[WARNING] config.yaml not found, using hardcoded defaults")
        return None

def get_platform_choice():
    """Get user's choice of platform"""
    platforms = {
        '1': ('YouTube Shorts', 'youtube_shorts'),
        '2': ('Instagram', 'instagram'),
        '3': ('TikTok', 'tiktok'),
        '4': ('YouTube Long', 'youtube_long')
    }
    
    print("\nSelect target platform:")
    for key, (name, _) in platforms.items():
        print(f"{key}. {name}")
    
    while True:
        choice = input("Enter your choice (1-4): ").strip()
        if choice in platforms:
            return platforms[choice][1]

def use_default_settings():
    """Ask user if they want to use default settings from config"""
    while True:
        choice = input("\nUse default settings from config.json? (y/n): ").lower()
        if choice in ['y', 'n']:
            return choice == 'y'

def get_parameters_from_config(config, platform_defaults=None):
    """Convert config values to parameter dictionaries"""
    if not config:
        return None, None, None, None
        
    # Video position parameters
    video_position = None
    if config["TOP_BAR_BACKGROUND"] == "y":
        video_position = {
            "bottom_height_percent": config["TOP_BAR_BACKGROUND_HEIGHT_IN_PERCENTAGE"],
            "opacity": config["TOP_BAR_BACKGROUND_TRANSPARENCY"]
        }
    
    # Top background parameters
    top_bg = None
    if config["TOP_BLACK_BACKGROUND"] == "y":
        top_bg = {
            "height_percent": config["TOP_BLACK_BACKGROUND_HEIGHT_IN_PERCENTAGE"],
            "opacity": config["BLACK_BACKGROUND_TRANSPARENCY"]
        }
    
    # Bottom background parameters
    bottom_bg = None
    if config["BOTTOM_BLACK_BACKGROUND"] == "y":
        bottom_bg = {
            "height_percent": config["BOTTOM_BLACK_BACKGROUND_HEIGHT_IN_PERCENTAGE"],
            "opacity": config["BOTTOM_BLACK_BACKGROUND_TRANSPARENCY"]
        }
    
    # Icon parameters
    icon = {
        "width": config["ICON_WIDTH_RANGE"],
        "x_position": config["ICON_X_POSITION"],
        "y_position": config["ICON_Y_OFFSET_IN_PERCENTAGE"]
    }
    
    # Override with platform-specific defaults if available
    if platform_defaults:
        if platform_defaults.get("bottom_bg") == "y":
            bottom_bg = {
                "height_percent": platform_defaults["bottom_bg_height"],
                "opacity": config["BOTTOM_BLACK_BACKGROUND_TRANSPARENCY"]
            }
        icon.update({
            "width": platform_defaults["icon_width"],
            "x_position": platform_defaults["icon_x_pos"],
            "y_position": platform_defaults["icon_y_position"]
        })
    
    return video_position, top_bg, bottom_bg, icon

def get_platform_defaults(config, platform):
    """Get default settings for specific platform"""
    if not config or "PLATFORM_DEFAULTS" not in config:
        return None
    return config["PLATFORM_DEFAULTS"].get(platform)

def get_ratio_choice_with_platform(platform_defaults=None):
    """Get ratio choice with platform-specific default"""
    if platform_defaults and 'aspect_ratio' in platform_defaults:
        # Map aspect ratio numbers to descriptions
        ratio_descriptions = {
            "1": "Square (1:1)",
            "2": "Portrait (9:16)",
            "3": "Landscape (16:9)",
            "custom": "Custom"
        }
        default_ratio = platform_defaults['aspect_ratio']
        
        # Show only the current platform's default ratio
        ratio_desc = ratio_descriptions.get(default_ratio, "Custom")
        print(f"\nPlatform default aspect ratio: {ratio_desc}")
        
        while True:
            override = input("Do you want to override the default aspect ratio? (y/n): ").lower()
            if override in ['y', 'n']:
                if override == 'y':
                    print("\nChoose new aspect ratio:")
                    return get_ratio_choice()  # Return user's choice immediately
                # Use platform default
                if default_ratio == "custom":
                    print("Using custom ratio from platform defaults")
                    return (
                        platform_defaults.get('width', 1080),
                        platform_defaults.get('height', 1920)
                    )
                print(f"Using platform default: {ratio_desc}")
                return {'1': (1080, 1080), '2': (1080, 1920), '3': (1920, 1080)}[default_ratio]
                
    # If no platform defaults available, show regular choice menu
    return get_ratio_choice()

def main():
    print("=== Video Processing Script ===\n")
    
    # Load config and get platform choice
    config = load_config()
    platform = get_platform_choice()
    platform_defaults = get_platform_defaults(config, platform)
    
    # Determine if using defaults
    use_defaults = use_default_settings() if config else False
    
    # Get source folder
    source_folder = get_validated_input(
        prompt_message="Enter the path to the source videos folder: ",
        is_folder=True
    )

    # Set up output folder based on platform
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_output = os.path.join(script_dir, "ai.waverider")
    output_folder = os.path.join(base_output, platform)
    
    # Define brand icon path
    brand_icon = "assets/fullicon.png"
    if not os.path.isfile(brand_icon):
        print(f"[ERROR] Brand icon not found at '{brand_icon}'. Please verify the path.")
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Get parameters either from config or user input
    if use_defaults:
        video_position_params, top_bg_params, black_bg_params, icon_params = get_parameters_from_config(config, platform_defaults)
        # Always call get_ratio_choice_with_platform to allow override option
        target_dimensions = get_ratio_choice_with_platform(platform_defaults)
    else:
        # If not using defaults, don't pass platform_defaults to get regular choice
        target_dimensions = get_ratio_choice_with_platform(None)
        video_position_params = get_video_positioning_preferences()
        top_bg_params = get_top_background_preferences()
        black_bg_params = get_black_background_preferences()
        icon_params = get_icon_preferences()

    # Collect video files
    video_paths = []
    for video_file in os.listdir(source_folder):
        if video_file.lower().endswith((".mp4", ".mov")):
            input_path = os.path.join(source_folder, video_file)
            output_path = os.path.join(output_folder, f"processed_{video_file}")
            video_paths.append((input_path, brand_icon, output_path, target_dimensions,
                              black_bg_params, video_position_params, top_bg_params, icon_params))

    if not video_paths:
        print("[INFO] No videos found in the source folder to process.")
        sys.exit(0)

    print(f"\n[INFO] Found {len(video_paths)} video(s) to process.\n")

    # Set up multiprocessing Pool with initializer to ignore SIGINT in workers
    pool = Pool(processes=4, initializer=init_worker)  # Adjust 'processes' based on CPU cores

    try:
        # Use imap_unordered for better responsiveness to interrupts
        for result in pool.imap_unordered(process_video, video_paths):
            print(f"Processed: {result}")
        print("\n[INFO] Batch processing completed!")
    except KeyboardInterrupt:
        print("\n[INFO] Caught Ctrl+C! Terminating all processes...")
        pool.terminate()
        pool.join()
        print("[INFO] All processes terminated.")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {str(e)}")
        pool.terminate()
        pool.join()
        sys.exit(1)
    else:
        pool.close()
        pool.join()

if __name__ == "__main__":
    main()
