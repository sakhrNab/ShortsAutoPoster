import os
import subprocess
import signal
import sys
from multiprocessing import Pool

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

def get_ratio_choice():
    """Get user's preferred aspect ratio choice."""
    print("\nSelect output aspect ratio:")
    print("1. Square (1:1)")
    print("2. Portrait (9:16)")
    print("3. Landscape (16:9)")
    while True:
        choice = input("Enter your choice (1-3): ").strip()
        if choice in ['1', '2', '3']:
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

def generate_filter_complex(input_path, brand_icon, target_dimensions, black_bg_params=None):
    """Generate the filter_complex string with properly chained filters."""
    target_width, target_height = target_dimensions
    
    # Start building the filter chain
    filter_complex = (
        # Initial scale and pad
        f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black[scaled];"
        
        # Add the top black background
        f"[scaled]drawbox=x=0:y=0:w={target_width}:h={int(target_height*0.1)}:"
        f"color=black@0.7:t=fill[top]"
    )

    # Add bottom black background if requested
    if black_bg_params:
        height_pixels = int(target_height * (black_bg_params["height_percent"] / 100))
        y_position = target_height - height_pixels
        filter_complex += (
            f";[top]drawbox=x=0:y={y_position}:w={target_width}:h={height_pixels}:"
            f"color=black@{black_bg_params['opacity']}:t=fill[bg]"
        )
    else:
        filter_complex += ";[top]copy[bg]"

    # Add the brand icon overlay
    filter_complex += (
        ";[1:v]scale=500:-1[icon];"
        "[bg][icon]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/8"
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
    input_path, brand_icon, output_path, target_dimensions, black_bg_params = video_args
    filter_complex = generate_filter_complex(input_path, brand_icon, target_dimensions, black_bg_params)

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

def main():
    print("=== Video Processing Script ===\n")

    # Prompt user for source folder path
    source_folder = get_validated_input(
        prompt_message="Enter the path to the source videos folder: ",
        is_folder=True
    )

    # Define the output folder relative to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_folder = os.path.join(script_dir, "ai.waverider")

    # Define the brand icon path (modify this path if needed)
    brand_icon = "assets/fullicon.png"

    # Check if the brand icon exists
    if not os.path.isfile(brand_icon):
        print(f"[ERROR] Brand icon not found at '{brand_icon}'. Please verify the path.")
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Get user's preferred aspect ratio and black background preferences
    target_dimensions = get_ratio_choice()
    black_bg_params = get_black_background_preferences()

    # Collect all video files to process
    video_paths = []
    for video_file in os.listdir(source_folder):
        if video_file.lower().endswith((".mp4", ".mov")):
            input_path = os.path.join(source_folder, video_file)
            output_path = os.path.join(output_folder, f"processed_{video_file}")
            video_paths.append((input_path, brand_icon, output_path, target_dimensions, black_bg_params))

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
