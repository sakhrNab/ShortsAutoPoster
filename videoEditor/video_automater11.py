import os
import subprocess
import signal
import sys
import yaml
from tqdm import tqdm

def init_worker():
    """Ignore SIGINT in worker processes."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None

def get_platform_defaults(config, platform):
    if not config or "PLATFORM_DEFAULTS" not in config:
        return None
    return config["PLATFORM_DEFAULTS"].get(platform)

def get_parameters_from_config(config, platform_defaults=None):
    """Convert config values to parameter dictionaries."""
    if not config:
        return None, None, None, None

    video_position = None
    if config.get("TOP_BAR_BACKGROUND", "n").lower() == "y":
        video_position = {
            "bottom_height_percent": config.get("TOP_BAR_BACKGROUND_HEIGHT_IN_PERCENTAGE", 10),
            "opacity": config.get("TOP_BAR_BACKGROUND_TRANSPARENCY", 0.7)
        }

    top_bg = None
    if config.get("TOP_BLACK_BACKGROUND", "n").lower() == "y":
        top_bg = {
            "height_percent": config.get("TOP_BLACK_BACKGROUND_HEIGHT_IN_PERCENTAGE", 10),
            "opacity": config.get("BLACK_BACKGROUND_TRANSPARENCY", 0.7)
        }

    bottom_bg = None
    if config.get("BOTTOM_BLACK_BACKGROUND", "n").lower() == "y":
        bottom_bg = {
            "height_percent": config.get("BOTTOM_BLACK_BACKGROUND_HEIGHT_IN_PERCENTAGE", 10),
            "opacity": config.get("BOTTOM_BLACK_BACKGROUND_TRANSPARENCY", 0.7)
        }

    icon = {
        "width": config.get("ICON_WIDTH_RANGE", 500),
        "x_position": config.get("ICON_X_POSITION", "c"),
        "y_position": config.get("ICON_Y_OFFSET_IN_PERCENTAGE", 12.5)
    }

    if platform_defaults:
        if platform_defaults.get("bottom_bg") == "y":
            bottom_bg = {
                "height_percent": platform_defaults.get("bottom_bg_height", 10),
                "opacity": config.get("BOTTOM_BLACK_BACKGROUND_TRANSPARENCY", 0.7)
            }
        icon.update({
            "width": platform_defaults.get("icon_width", icon["width"]),
            "x_position": platform_defaults.get("icon_x_pos", icon["x_position"]),
            "y_position": platform_defaults.get("icon_y_position", icon["y_position"])
        })

    return video_position, top_bg, bottom_bg, icon

def build_ffmpeg_filter(
    target_width,
    target_height,
    black_bg_params=None,
    video_position_params=None,
    top_bg_params=None,
    icon_params=None,
    text_overlays=None
):
    """
    Returns a string that does the following in FFmpeg:
    1) scale [0:v] => [base]
    2) draw top background (drawbox) => [step1]
    3) draw bottom background => [step2]
    4) draw "video position" black bar => [step3]
    5) overlay icon => [step4]
    6) apply drawtext for each text overlay => final
    """

    text_overlays = text_overlays or []
    icon_params = icon_params or {}
    # We'll chain them using labels step by step.
    filter_cmds = []

    # Step 1: scale main video
    # Force aspect ratio = none for demonstration
    filter_cmds.append(
        f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease," 
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black[base]"
    )
    current_label = "[base]"

    # Step 2: top background
    if top_bg_params and "enabled" in top_bg_params and top_bg_params["enabled"]:
        h_percent = float(top_bg_params["height_percent"])
        top_h = int(target_height * (h_percent / 100.0))
        opacity = float(top_bg_params["opacity"])
        # drawbox => label = [step1]
        filter_cmds.append(
            f"{current_label}drawbox=x=0:y=0:w={target_width}:h={top_h}:"
            f"color=black@{opacity}:t=fill[step1]"
        )
        current_label = "[step1]"

    # Step 3: bottom background
    if black_bg_params and "enabled" not in black_bg_params:
        # If 'enabled' is missing, assume we do it
        pass
    if black_bg_params:
        if "height_percent" in black_bg_params:
            h_percent = float(black_bg_params["height_percent"])
            bot_h = int(target_height * (h_percent / 100.0))
            opacity = float(black_bg_params["opacity"])
            y_pos = target_height - bot_h
            filter_cmds.append(
                f"{current_label}drawbox=x=0:y={y_pos}:w={target_width}:h={bot_h}:"
                f"color=black@{opacity}:t=fill[step2]"
            )
            current_label = "[step2]"

    # Step 4: "video position" black bar (like a bottom bar?), if present
    if video_position_params and "bottom_height_percent" in video_position_params:
        bar_h = int(target_height * (video_position_params["bottom_height_percent"] / 100.0))
        opacity = float(video_position_params["opacity"])
        y_pos = target_height - bar_h
        filter_cmds.append(
            f"{current_label}drawbox=x=0:y={y_pos}:w={target_width}:h={bar_h}:"
            f"color=black@{opacity}:t=fill[step3]"
        )
        current_label = "[step3]"

    # Step 5: overlay icon => scale brand icon => label it [icon], then overlay
    icon_w = icon_params.get("width", 400)
    # X pos
    x_p = icon_params.get("x_position", "c")
    if x_p == "c":
        x_formula = "(main_w-overlay_w)/2"
    elif x_p == "l":
        x_formula = "10"
    elif x_p == "r":
        x_formula = "main_w-overlay_w-10"
    else:
        # assume it's numeric
        x_formula = f"main_w*({float(x_p)}/100.0)"

    # Y pos
    y_pos = float(icon_params.get("y_position", 90.0))
    y_formula = f"main_h*({y_pos}/100.0)"

    filter_cmds.append(
        f"[1:v]scale={icon_w}:-1[icon];"
        f"{current_label}[icon]overlay={x_formula}:{y_formula}[step4]"
    )
    current_label = "[step4]"

    # Step 6: For each text overlay, do a separate drawtext
    # We'll sequentially label them [txt0], [txt1], etc.
    for i, ov in enumerate(text_overlays):
        # Basic drawtext example
        # x and y in pixels => we compute them from % if we want
        fontfile = "Arial.ttf"  # or path to a real TTF
        text_str = ov.get("text", "Text")
        size = int(ov.get("size", 40))
        color_hex = ov.get("color", "#FFFFFF")
        # Convert #RRGGBB => 0xRRGGBB
        color_hex_ffmpeg = "0x" + color_hex.lstrip("#")[:6]
        # X, Y
        x_pct = ov.get("x", 50.0)
        y_pct = ov.get("y", 50.0)
        x_draw = f"(main_w*{x_pct/100.0} - text_w/2)"
        y_draw = f"(main_h*{y_pct/100.0} - text_h/2)"

        filter_cmds.append(
            f"{current_label}drawtext="
            f"fontfile='{fontfile}':"
            f"text='{text_str}':"
            f"x={x_draw}:y={y_draw}:"
            f"fontsize={size}:fontcolor={color_hex_ffmpeg}:"
            f"alpha=1[txt{i}]"
        )
        current_label = f"[txt{i}]"

    # Final label is what ends up as video
    return ";".join(filter_cmds), current_label

def process_video(video_args):
    """
    1) Build a more advanced filter that respects black backgrounds, text overlays, etc.
    2) Then call ffmpeg with the generated filter.
    """
    (
        input_path,
        brand_icon,
        output_path,
        target_dimensions,
        black_bg_params,
        video_position_params,
        top_bg_params,
        icon_params,
        text_overlays
    ) = video_args

    target_width, target_height = target_dimensions

    # Build the filter chain
    filter_cmd_str, final_label = build_ffmpeg_filter(
        target_width,
        target_height,
        black_bg_params=black_bg_params,
        video_position_params=video_position_params,
        top_bg_params=top_bg_params,
        icon_params=icon_params,
        text_overlays=text_overlays
    )

    # We'll pass something like: -filter_complex "[0:v]scale=...;...drawtext=...[txt0]" -map "[txt0]"
    # But if final_label is e.g. [txt0], we need to map that. Or if no text overlays, final_label might be [step4]
    # We'll map that as the final video output.

    command = [
        "ffmpeg",
        "-i", input_path,
        "-i", brand_icon,
        "-filter_complex", filter_cmd_str,
        "-map", f"{final_label}",
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "20",
        "-c:a", "copy",
        "-y",
        output_path
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg failed for {input_path}:\n{e.stderr}")
        raise e
    except Exception as e:
        print(f"[ERROR] Unexpected error processing {input_path}: {str(e)}")
        raise e

#
# The rest of the script below could remain the same if you have
# CLI-based usage, e.g. main() or any multiprocess logic.
# Omitted for brevity since your GUI calls `process_video(...)` directly.
#

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
        choice = input("\nUse default settings from config.yaml? (y/n): ").lower()
        if choice in ['y', 'n']:
            return choice == 'y'

def get_parameters_from_config(config, platform_defaults=None):
    """Convert config values to parameter dictionaries"""
    if not config:
        return None, None, None, None
        
    # Video position parameters
    video_position = None
    if config.get("TOP_BAR_BACKGROUND", "n").lower() == "y":
        video_position = {
            "bottom_height_percent": config.get("TOP_BAR_BACKGROUND_HEIGHT_IN_PERCENTAGE", 10),
            "opacity": config.get("TOP_BAR_BACKGROUND_TRANSPARENCY", 0.7)
        }
    
    # Top background parameters
    top_bg = None
    if config.get("TOP_BLACK_BACKGROUND", "n").lower() == "y":
        top_bg = {
            "height_percent": config.get("TOP_BLACK_BACKGROUND_HEIGHT_IN_PERCENTAGE", 10),
            "opacity": config.get("BLACK_BACKGROUND_TRANSPARENCY", 0.7)
        }
    
    # Bottom background parameters
    bottom_bg = None
    if config.get("BOTTOM_BLACK_BACKGROUND", "n").lower() == "y":
        bottom_bg = {
            "height_percent": config.get("BOTTOM_BLACK_BACKGROUND_HEIGHT_IN_PERCENTAGE", 10),
            "opacity": config.get("BOTTOM_BLACK_BACKGROUND_TRANSPARENCY", 0.7)
        }
    
    # Icon parameters
    icon = {
        "width": config.get("ICON_WIDTH_RANGE", 500),
        "x_position": config.get("ICON_X_POSITION", "c"),
        "y_position": config.get("ICON_Y_OFFSET_IN_PERCENTAGE", 12.5)
    }
    
    # Override with platform-specific defaults if available
    if platform_defaults:
        if platform_defaults.get("bottom_bg") == "y":
            bottom_bg = {
                "height_percent": platform_defaults.get("bottom_bg_height", 10),
                "opacity": config.get("BOTTOM_BLACK_BACKGROUND_TRANSPARENCY", 0.7)
            }
        icon.update({
            "width": platform_defaults.get("icon_width", icon["width"]),
            "x_position": platform_defaults.get("icon_x_pos", icon["x_position"]),
            "y_position": platform_defaults.get("icon_y_position", icon["y_position"])
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
        # Initialize tqdm progress bar
        with tqdm(total=len(video_paths), desc="Processing Videos", unit="video") as pbar:
            # Use imap_unordered for better responsiveness to interrupts
            for result in pool.imap_unordered(process_video, video_paths):
                print(f"Processed: {result}")
                pbar.update(1)
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
