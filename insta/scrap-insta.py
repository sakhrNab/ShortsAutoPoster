#!/usr/bin/env python3
"""
scrap-insta.py

A comprehensive Instagram video downloader that supports:
 - Profile or Hashtag downloads
 - Optional login for private profiles
 - Filtering: most liked, most viewed, latest, or no filter
 - Aspect ratio filtering: 1:1, 9:16, 16:9
 - Organized subfolders for each ratio
 - Renaming files to "<Topic>_<XViews>_<XLikes>_<Date>.mp4"
 - Excel export with metadata
 - Retry logic for downloads
 - Parallel (threaded) downloads
 - Dry Run mode (no actual downloads)
 - Color-coded console logs for clarity

Dependencies:
    pip install instaloader pandas openpyxl tqdm requests pillow

Author: ChatGPT
"""

import os
import sys
import time
import getpass
import logging
import requests
import pandas as pd
from io import BytesIO
from PIL import Image
from tqdm import tqdm
from datetime import datetime
from typing import List
import instaloader
from instaloader import Post, Hashtag, Profile
from concurrent.futures import ThreadPoolExecutor, as_completed


# -------------------- Color-Coded Console Output --------------------
def log_message(msg: str, level: str = "info", silent: bool = False):
    """
    Print messages with ANSI color-coded prefixes.
    level can be: 'info', 'success', 'warning', 'error', 'debug'
    If silent=True, we skip printing altogether.
    """
    if silent:
        return

    colors = {
        "info": "\033[94m",     # blue
        "success": "\033[92m",  # green
        "warning": "\033[93m",  # yellow
        "error": "\033[91m",    # red
        "debug": "\033[90m",    # grey
    }
    endc = "\033[0m"

    prefix = {
        "info":    "[INFO]",
        "success": "[SUCCESS]",
        "warning": "[WARNING]",
        "error":   "[ERROR]",
        "debug":   "[DEBUG]",
    }.get(level, "[LOG]")

    print(f"{colors.get(level, '')}{prefix} {msg}{endc}")


# -------------------- Number Abbreviation --------------------
def abbreviate_number(num: int) -> str:
    """
    Convert large numbers into an abbreviated string (e.g. 1200 => '1.2K').
    """
    if isinstance(num, int):
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
    return str(num)


# -------------------- Aspect Ratio Helpers --------------------
def get_aspect_ratio(post: Post) -> float:
    """
    Determine aspect ratio by downloading the post's thumbnail.
    Fallback to 1.0 if something fails.
    """
    try:
        resp = requests.get(post.url)
        img = Image.open(BytesIO(resp.content))
        w, h = img.size
        return w / h if h != 0 else 1.0
    except Exception as e:
        logging.debug(f"Failed to get aspect ratio for {post.shortcode}: {e}")
        return 1.0

def is_desired_ratio(ratio: float, desired_ratios: List[str]) -> bool:
    """
    Check if ratio matches any of the user-selected aspect ratios.
    Mappings:
      1:1 -> (0.9, 1.1)
      9:16 -> (0.5, 0.65)
      16:9 -> (1.7, 1.8)
    """
    ratio_map = {
        "1:1":  (0.9, 1.1),
        "9:16": (0.5, 0.65),
        "16:9": (1.7, 1.8)
    }
    for r in desired_ratios:
        min_r, max_r = ratio_map[r]
        if min_r <= ratio <= max_r:
            return True
    return False

def get_ratio_folder(ratio: float) -> str:
    """
    Return a subfolder name based on ratio:
      1_1_square, 9_16_vertical, 16_9_horizontal, other_ratios
    """
    if 0.9 <= ratio <= 1.1:
        return "1_1_square"
    elif 0.5 <= ratio <= 0.65:
        return "9_16_vertical"
    elif 1.7 <= ratio <= 1.8:
        return "16_9_horizontal"
    else:
        return "other_ratios"


# -------------------- Excel Export --------------------
def export_to_excel(posts: List[Post], file_names: List[str], excel_path: str, silent: bool):
    """
    Export post data to Excel with improved formatting.
    Excel will be saved in the target folder with timestamp.
    """
    data = []
    for post, final_name in zip(posts, file_names):
        caption = post.caption or ""
        title = caption.split('\n')[0][:50] if caption else "No Title"
        hashtags = " ".join(post.caption_hashtags) if post.caption_hashtags else ""
        
        data.append({
            'Video Title': title,
            'Description': caption,
            'Hashtags': hashtags,
            'Likes': post.likes,
            'Views': post.video_view_count if post.is_video else 0,
            'Date': post.date_local.strftime("%Y-%m-%d %H:%M:%S"),
            'Filename': final_name
        })

    df = pd.DataFrame(data)
    
    # Apply some Excel formatting
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Video Data')
        worksheet = writer.sheets['Video Data']
        
        # Adjust column widths
        worksheet.column_dimensions['A'].width = 50  # Title
        worksheet.column_dimensions['B'].width = 100  # Description
        worksheet.column_dimensions['C'].width = 50  # Hashtags
        worksheet.column_dimensions['D'].width = 15  # Likes
        worksheet.column_dimensions['E'].width = 15  # Views
        worksheet.column_dimensions['F'].width = 20  # Date
        worksheet.column_dimensions['G'].width = 50  # Filename

    abs_path = os.path.abspath(excel_path)
    log_message(f"Excel file created at: {abs_path}", "success", silent)
    return abs_path


# -------------------- Download + Rename (with Retry) --------------------
# -------------------- Download Videos with Retry --------------------
def download_video_with_retry(
    L: instaloader.Instaloader,
    post: Post,
    target_folder: str,
    desired_ratios: List[str],
    silent: bool,
    max_retries: int = 3
):
    """Download a single post with retry logic without renaming."""
    
    try:
        # Check aspect ratio before downloading
        ratio = get_aspect_ratio(post)
        if desired_ratios and not is_desired_ratio(ratio, desired_ratios):
            log_message(f"Skipping download for {post.shortcode}: aspect ratio mismatch.", "warning", silent)
            return False, post, None

        # Attempt to download with retries
        attempt = 0
        while attempt < max_retries:
            try:
                attempt += 1
                log_message(f"Download attempt {attempt} for {post.shortcode}", "info", silent)
                
                # Download the post
                L.download_post(post, target=target_folder)
                time.sleep(1)  # Ensure the file system has updated
                
                # Determine the downloaded file path
                downloaded_file = os.path.join(target_folder, f"{post.shortcode}.mp4")
                
                if os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 0:
                    log_message(f"Downloaded {post.shortcode} successfully.", "success", silent)
                    return True, post, downloaded_file
                else:
                    log_message(f"Downloaded file for {post.shortcode} is incomplete. Retrying...", "warning", silent)
                    time.sleep(2)
                    
            except Exception as e:
                log_message(f"Error downloading {post.shortcode} on attempt {attempt}: {e}", "error", silent)
                time.sleep(2)
        
        log_message(f"Failed to download {post.shortcode} after {max_retries} attempts.", "error", silent)
        return False, post, None
            
    except Exception as e:
        log_message(f"Unexpected error for {post.shortcode}: {e}", "error", silent)
        return False, post, None



# -------------------- Main Download Flow --------------------
# -------------------- Main Download Flow --------------------
def download_posts(
    L: instaloader.Instaloader,
    posts: List[Post],
    download_type: str,
    target_folder: str,
    desired_ratios: List[str],
    concurrency: int,
    dry_run: bool,
    silent: bool
):
    """
    Download the given posts with concurrency.
    If dry_run=True, just list what would happen without downloading.
    """
    log_message(f"\nSelected {len(posts)} videos to download: {download_type}", "info", silent)

    if dry_run:
        log_message("DRY RUN: No files will be downloaded.", "warning", silent)
        for p in posts:
            log_message(f"[DRY RUN] Would download post => {p.shortcode}", "debug", silent)
        return [], []

    os.makedirs(target_folder, exist_ok=True)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    tasks = {}
    success_posts = []
    success_files = []

    log_message(f"Starting parallel downloads with concurrency={concurrency}", "info", silent)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for post in posts:
            if not post.is_video:
                continue

            # Submit the download task
            fut = executor.submit(
                download_video_with_retry,
                L,
                post,
                target_folder,
                desired_ratios,
                silent
            )
            tasks[fut] = post

        # Gather results
        for fut in tqdm(as_completed(tasks), total=len(tasks), desc="Downloading", unit="video"):
            success, p, file_path = fut.result()
            if success and file_path:
                success_posts.append(p)
                success_files.append(file_path)

    log_message(f"Downloaded {len(success_posts)}/{len(posts)} videos successfully.", "success", silent)
    return success_posts, success_files

# -------------------- Rename Videos --------------------
def rename_videos(
    downloaded_posts: List[Post],
    downloaded_files: List[str],
    target_folder: str,
    desired_ratios: List[str],
    silent: bool
) -> List[str]:
    """
    Rename downloaded videos based on the pattern:
    "<Topic>_<XViews>Views_<XLikes>Likes_<Date>.mp4"
    Returns a list of new filenames.
    """
    log_message("Starting renaming of downloaded videos...", "info", silent)
    renamed_files = []

    for post, file_path in tqdm(zip(downloaded_posts, downloaded_files), total=len(downloaded_posts), desc="Renaming", unit="video"):
        try:
            # Determine aspect ratio
            ratio = get_aspect_ratio(post)
            if desired_ratios and not is_desired_ratio(ratio, desired_ratios):
                log_message(f"Skipping renaming for {post.shortcode}: aspect ratio mismatch.", "warning", silent)
                continue

            # Determine subfolder based on aspect ratio
            subfolder = get_ratio_folder(ratio)
            final_folder = os.path.join(target_folder, subfolder)
            os.makedirs(final_folder, exist_ok=True)

            # Extract and sanitize title
            caption = post.caption or ""
            title = caption.split('\n')[0][:30] if caption else "NoTopic"
            safe_title = "".join(c for c in title if c.isalnum() or c == ' ').strip().replace(' ', '_')
            if not safe_title:
                safe_title = "NoTopic"

            # Abbreviate views and likes
            views = post.video_view_count or 0
            likes = post.likes or 0
            date_str = post.date_local.strftime("%m%d%y")

            # Prepare new filename
            new_filename = f"{safe_title}_{abbreviate_number(views)}Views_{abbreviate_number(likes)}Likes_{date_str}.mp4"
            new_path = os.path.join(final_folder, new_filename)

            # Check if new file already exists to avoid overwriting
            if os.path.exists(new_path):
                log_message(f"File {new_filename} already exists in {final_folder}. Skipping.", "warning", silent)
                continue

            # Move and rename the file
            os.rename(file_path, new_path)
            log_message(f"Renamed to {new_filename}", "success", silent)
            renamed_files.append(new_filename)

        except Exception as e:
            log_message(f"Error renaming {post.shortcode}: {e}", "error", silent)

    log_message(f"Renamed {len(renamed_files)}/{len(downloaded_posts)} videos successfully.", "success", silent)
    return renamed_files


# -------------------- Main Program --------------------
# -------------------- Main Program --------------------
def main():
    logging.basicConfig(level=logging.INFO)

    print("=== Instagram Media Downloader (Comprehensive) ===\n")

    # ----------------- Instaloader Setup -----------------
    L = instaloader.Instaloader(
        sleep=True,
        quiet=False,  # We'll do our own printing
        download_pictures=False,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        filename_pattern="{shortcode}",  # Ensures <shortcode>.mp4
        storyitem_metadata_txt_pattern="",
        max_connection_attempts=3,
        request_timeout=300,
        rate_controller=None,
        resume_prefix="iterator",
        check_resume_bbd=True,
        fatal_status_codes=None,
        iphone_support=True,
        title_pattern=None,
        sanitize_paths=False
    )

    # --------------- Optional Login -----------------
    do_login = input("Do you want to log in to download from private profiles? (y/n): ").strip().lower()
    if do_login == 'y':
        username = input("Enter your Instagram username: ").strip()
        try:
            L.load_session_from_file(username)
            print("Session loaded successfully.\n")
        except FileNotFoundError:
            password = getpass.getpass("Enter your Instagram password: ").strip()
            try:
                L.login(username, password)
                print("Login successful.\n")
                L.save_session_to_file()
            except Exception as e:
                print(f"Login failed: {e}")
                sys.exit(1)
    else:
        print("Proceeding without logging in.\n")

    # --------------- Choose Source (Profile or Hashtag) ----------------
    print("Select the source of videos:")
    print("1: Download from a specific user's profile")
    print("2: Download from a hashtag")
    source_choice = input("Enter choice (1/2): ").strip()

    posts_to_download = []
    download_type = "as they appear"
    source_name = "Unknown"
    target = ""  # Initialize target variable

    if source_choice == '1':
        profile_username = input("Enter the Instagram username: ").strip()
        source_name = f"Profile '{profile_username}'"
        try:
            profile = Profile.from_username(L.context, profile_username)
        except Exception as e:
            print(f"Error fetching profile: {e}")
            sys.exit(1)

        # How many videos?
        num_choice = input("How many videos to download? (10/20/40/80/100): ").strip()
        if not num_choice.isdigit():
            num_videos = 10
        else:
            num_videos = int(num_choice)

        # Filter: likes, views, date
        print("\nFilter Options:")
        print("1: No filter")
        print("2: Most liked")
        print("3: Most viewed")
        print("4: Latest uploaded")
        filter_choice = input("Enter filter (1/2/3/4): ").strip()

        print("\nAspect Ratio options (multiple allowed, e.g., '1 2' => 1:1 & 9:16):")
        print("1: 1:1")
        print("2: 9:16")
        print("3: 16:9")
        print("4: All")
        ratio_input = input("Enter your choice(s): ").strip().split()
        ratio_map = {'1': '1:1', '2': '9:16', '3': '16:9'}
        desired_ratios = []
        for r in ratio_input:
            if r in ratio_map:
                desired_ratios.append(ratio_map[r])
        if not desired_ratios or '4' in ratio_input:
            desired_ratios = ["1:1", "9:16", "16:9"]  # All ratios

        # concurrency
        concurrency_str = input("Enter concurrency (number of threads, e.g., 1/2/4): ").strip()
        if concurrency_str.isdigit() and int(concurrency_str) > 0:
            concurrency = int(concurrency_str)
        else:
            log_message("Invalid concurrency value. Defaulting to 1.", "warning")
            concurrency = 1

        # Dry run?
        dry_run_input = input("Do a dry run (no actual downloads)? (y/n): ").strip().lower()
        dry_run = (dry_run_input == 'y')

        # Silent?
        silent_input = input("Silent mode (less console output)? (y/n): ").strip().lower()
        silent = (silent_input == 'y')

        # Collect all videos from profile
        log_message("Fetching videos from profile...", "info", silent)
        all_videos = []
        try:
            for post in tqdm(profile.get_posts(), desc="Fetching posts", unit="post"):
                if post.is_video:
                    all_videos.append(post)
                    if len(all_videos) >= num_videos and filter_choice == '1':
                        # For no filter, we can stop once we have enough
                        break
        except Exception as e:
            log_message(f"Error fetching posts: {e}", "error", silent)
            sys.exit(1)

        log_message(f"Found {len(all_videos)} videos total", "info", silent)

        # Apply filter
        if filter_choice == '2':
            log_message("Sorting by likes...", "info", silent)
            all_videos.sort(key=lambda p: p.likes or 0, reverse=True)
            download_type = "most liked"
        elif filter_choice == '3':
            log_message("Sorting by views...", "info", silent)
            all_videos.sort(key=lambda p: p.video_view_count or 0, reverse=True)
            download_type = "most viewed"
        elif filter_choice == '4':
            log_message("Sorting by date...", "info", silent)
            all_videos.sort(key=lambda p: p.date_utc, reverse=True)
            download_type = "latest"
        # Else: filter_choice == '1', keep original order

        posts_to_download = all_videos[:num_videos]
        log_message(f"Selected {len(posts_to_download)} videos for download", "info", silent)

        target = profile_username  # Use profile name as target directory

        if not posts_to_download:
            log_message("No videos match your criteria.", "error", silent)
            sys.exit(0)

        # Now do the actual downloads
        downloaded, file_names = download_posts(
            L=L,
            posts=posts_to_download,
            download_type=download_type,
            target_folder=target,
            desired_ratios=desired_ratios,
            concurrency=concurrency,
            dry_run=dry_run,
            silent=silent
        )

        if downloaded and not dry_run:
            # Rename Phase
            log_message("Starting renaming phase...", "info", silent)
            renamed_files = rename_videos(
                downloaded_posts=downloaded,
                downloaded_files=file_names,
                target_folder=target,
                desired_ratios=desired_ratios,
                silent=silent
            )

            # Create Excel file in the target directory
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"video_data_{timestamp}.xlsx"
            excel_path = os.path.join(target, excel_filename)
            
            try:
                final_path = export_to_excel(downloaded, renamed_files, excel_path, silent)
                log_message(f"\nExcel file location: {final_path}", "success", silent)
            except Exception as e:
                log_message(f"Failed to create Excel file: {e}", "error", silent)
        print("\nDone.")

    elif source_choice == '2':
        hashtag = input("Enter the hashtag (without #): ").strip()
        source_name = f"Hashtag '#{hashtag}'"
        target = f"hashtag_{hashtag}"  # Set target directory for hashtag
        
        try:
            hashtag_posts = Hashtag.from_name(L.context, hashtag)
        except Exception as e:
            log_message(f"Error fetching hashtag: {e}", "error", False)
            sys.exit(1)

        # How many videos?
        num_choice = input("How many videos to download? (10/20/40/80/100): ").strip()
        num_videos = int(num_choice) if num_choice.isdigit() else 10

        # Filter options
        print("\nFilter Options:")
        print("1: No filter")
        print("2: Most liked")
        print("3: Most viewed")
        print("4: Latest uploaded")
        filter_choice = input("Enter filter (1/2/3/4): ").strip()

        print("\nAspect Ratio options (multiple allowed, e.g., '1 2' => 1:1 & 9:16):")
        print("1: 1:1")
        print("2: 9:16")
        print("3: 16:9")
        print("4: All")
        ratio_input = input("Enter your choice(s): ").strip().split()
        ratio_map = {'1': '1:1', '2': '9:16', '3': '16:9'}
        desired_ratios = [ratio_map[r] for r in ratio_input if r in ratio_map]
        if not desired_ratios or '4' in ratio_input:
            desired_ratios = ["1:1", "9:16", "16:9"]

        # Concurrency
        concurrency_str = input("Enter concurrency (number of threads, e.g., 1/2/4): ").strip()
        concurrency = int(concurrency_str) if concurrency_str.isdigit() and int(concurrency_str) > 0 else 1

        # Dry run
        dry_run = input("Do a dry run (no actual downloads)? (y/n): ").strip().lower() == 'y'
        
        # Silent mode
        silent = input("Silent mode (less console output)? (y/n): ").strip().lower() == 'y'

        # Collect videos
        log_message("Fetching videos from hashtag...", "info", silent)
        all_videos = []
        try:
            for post in tqdm(hashtag_posts.get_posts(), desc="Fetching posts", unit="post"):
                if post.is_video:
                    all_videos.append(post)
                    if len(all_videos) >= num_videos and filter_choice == '1':
                        break
        except Exception as e:
            log_message(f"Error fetching posts: {e}", "error", silent)
            sys.exit(1)

        log_message(f"Found {len(all_videos)} videos total", "info", silent)

        # Apply filter
        if filter_choice == '2':
            all_videos.sort(key=lambda p: p.likes or 0, reverse=True)
            download_type = "most liked"
        elif filter_choice == '3':
            all_videos.sort(key=lambda p: p.video_view_count or 0, reverse=True)
            download_type = "most viewed"
        elif filter_choice == '4':
            all_videos.sort(key=lambda p: p.date_utc, reverse=True)
            download_type = "latest"

        posts_to_download = all_videos[:num_videos]
        
        if not posts_to_download:
            log_message("No videos match your criteria.", "error", silent)
            sys.exit(0)

        # Download posts
        downloaded, file_names = download_posts(
            L=L,
            posts=posts_to_download,
            download_type=download_type,
            target_folder=target,
            desired_ratios=desired_ratios,
            concurrency=concurrency,
            dry_run=dry_run,
            silent=silent
        )

        if downloaded and not dry_run:
            # Rename Phase
            renamed_files = rename_videos(
                downloaded_posts=downloaded,
                downloaded_files=file_names,
                target_folder=target,
                desired_ratios=desired_ratios,
                silent=silent
            )

            # Create Excel file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"video_data_{timestamp}.xlsx"
            excel_path = os.path.join(target, excel_filename)
            
            try:
                final_path = export_to_excel(downloaded, renamed_files, excel_path, silent)
                log_message(f"\nExcel file location: {final_path}", "success", silent)
            except Exception as e:
                log_message(f"Failed to create Excel file: {e}", "error", silent)

    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
