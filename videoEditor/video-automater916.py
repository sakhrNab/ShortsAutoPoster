import os
import subprocess
import signal
from multiprocessing import Pool

def init_worker():
    """
    Ignore SIGINT in worker processes to allow the main process to handle it.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def process_video(video_args):
    input_path, brand_icon, output_path, filter_complex = video_args
    command = [
        "ffmpeg",
        "-i", input_path,
        "-i", brand_icon,
        "-filter_complex", filter_complex,
        "-c:v", "h264_nvenc",     # Use NVIDIA NVENC encoder
        "-preset", "p4",          # Preset for balance between speed and quality
        "-cq", "20",              # Constant quality parameter
        "-c:a", "copy",           # Copy audio without re-encoding
        "-y",                     # Overwrite output files without asking
        output_path
    ]
    try:
        # Run FFmpeg and capture output for debugging
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg failed for {input_path}:\n{e.stderr}")
        raise e

def main():
    # Define paths
    source_folder = "C:/Users/sakhr/OneDrive/Goals/AI Wave Rider/scripts/downloads/youtube"
    output_folder = "C:/Users/sakhr/OneDrive/Documents/Wondershare/Wondershare Filmora/AIWaverider"
    brand_icon    = "C:/Users/sakhr/OneDrive/Goals/AI Wave Rider/fullicon.png"  # Path to brand icon

    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Define filter_complex for 9:16 aspect ratio and larger icon
    filter_complex = (
        "[0:v]scale=1080:-1:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
        "drawbox=x=0:y=0:w=1080:h=108:color=black@0.7:t=0,"
        "format=rgba[bg];"
        "[1:v]scale=500:-1[icon];"  # Increased icon size to 500px width
        "[bg][icon]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/8"
    )

    # Collect all video files to process
    video_paths = []
    for video_file in os.listdir(source_folder):
        if video_file.lower().endswith((".mp4", ".mov")):
            input_path = os.path.join(source_folder, video_file)
            output_path = os.path.join(output_folder, f"processed_{video_file}")
            video_paths.append((input_path, brand_icon, output_path, filter_complex))

    # Set up multiprocessing Pool
    pool = Pool(processes=4, initializer=init_worker)  # Adjust 'processes' based on CPU cores

    try:
        # Map the video processing function across all videos
        results = pool.map(process_video, video_paths)
        print("Batch processing completed!")
    except KeyboardInterrupt:
        print("\n[INFO] Caught Ctrl+C! Terminating all processes...")
        pool.terminate()
        pool.join()
        print("All processes terminated.")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {str(e)}")
        pool.terminate()
        pool.join()
    finally:
        pool.close()
        pool.join()

if __name__ == "__main__":
    main()
