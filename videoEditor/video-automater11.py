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

def generate_filter_complex(input_path, brand_icon):
    """
    Generate the filter_complex string based on the input video aspect ratio.

    Parameters:
        input_path (str): Path to the input video file.
        brand_icon (str): Path to the brand icon image.

    Returns:
        str: The filter_complex string.
    """
    width, height = calculate_aspect_ratio(input_path)
    aspect_ratio = width / height

    if (aspect_ratio > 1):
        # Landscape
        scale_filter = f"scale=1080:-1:force_original_aspect_ratio=decrease"
    else:
        # Portrait or square
        scale_filter = f"scale=-1:1080:force_original_aspect_ratio=decrease"

    filter_complex = (
        f"[0:v]{scale_filter},"
        "pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black,"
        "drawbox=x=0:y=0:w=1080:h=108:color=black@0.7:t=0,"
        "format=rgba[bg];"
        "[1:v]scale=500:-1[icon];"
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
    input_path, brand_icon, output_path = video_args
    filter_complex = generate_filter_complex(input_path, brand_icon)

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

    # Collect all video files to process
    video_paths = []
    for video_file in os.listdir(source_folder):
        if video_file.lower().endswith((".mp4", ".mov")):
            input_path = os.path.join(source_folder, video_file)
            output_path = os.path.join(output_folder, f"processed_{video_file}")
            video_paths.append((input_path, brand_icon, output_path))

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
