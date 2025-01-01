#!/usr/bin/env python3
"""
Instagram Media Downloader

This script provides functionality to download Instagram videos either from specific profiles
or hashtags. It supports authentication, filtering by likes/views, and batch downloading.

Features:
    - Profile-based or hashtag-based video downloads
    - Optional authentication for private profile access
    - Filtering options: most liked, most viewed, or chronological
    - Progress tracking and detailed download status
    - Automatic file naming with engagement metrics

Requirements:
    - instaloader
    - tqdm
    - typing
    - logging
"""

import instaloader
from instaloader import Hashtag, Post
import sys
import getpass
from typing import List
from tqdm import tqdm
import os
import logging

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed logs

def abbreviate_number(num):
    """
    Convert large numbers into abbreviated string format.

    Args:
        num (int): The number to abbreviate

    Returns:
        str: Abbreviated number (e.g., "1.5K", "2.5M", "3.2B")

    Examples:
        >>> abbreviate_number(1500)
        '1.5K'
        >>> abbreviate_number(2500000)
        '2.5M'
    """
    if isinstance(num, int):
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
    return str(num)

def authenticate_instaloader(L: instaloader.Instaloader):
    """
    Handle Instagram authentication process with session management.

    Args:
        L (instaloader.Instaloader): Instaloader instance to authenticate

    Raises:
        SystemExit: If authentication fails or is cancelled
        Exception: For unexpected authentication errors
    """
    login_choice = input("Do you want to log in to download from private profiles? (y/n): ").strip().lower()
    if login_choice == 'y':
        username = input("Enter your Instagram username: ").strip()
        try:
            # Attempt to load a saved session
            L.load_session_from_file(username)
            print("Session loaded successfully.\n")
        except FileNotFoundError:
            # If no session file exists, proceed to login
            password = getpass.getpass("Enter your Instagram password: ").strip()
            try:
                L.login(username, password)
                print("Login successful.\n")
                # Save the session for future use
                L.save_session_to_file()
            except instaloader.exceptions.BadCredentialsException:
                print("Error: Invalid username or password.")
                sys.exit(1)
            except instaloader.exceptions.TwoFactorAuthRequiredException:
                print("Error: Two-factor authentication is enabled. Please use an App Password.")
                sys.exit(1)
            except instaloader.exceptions.ConnectionException as e:
                print(f"Connection error during login: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"An unexpected error occurred during login: {e}")
                sys.exit(1)
    else:
        print("Proceeding without logging in.\n")

def download_posts(L: instaloader.Instaloader, posts: List[Post], download_type: str, target: str):
    """
    Download Instagram posts with progress tracking and metadata handling.

    Args:
        L (instaloader.Instaloader): Configured Instaloader instance
        posts (List[Post]): List of Instagram posts to download
        download_type (str): Type of download ("most liked", "most viewed", or default)
        target (str): Target directory for downloads

    Notes:
        - Files are renamed to include engagement metrics
        - Progress is displayed using tqdm
        - Failed downloads are logged but don't stop the process
    """
    count = 0
    total = len(posts)
    print(f"\nStarting download of the {download_type} {total} videos...\n")

    # Initialize tqdm for download progress
    for post in tqdm(posts, desc="Downloading videos", unit="video"):
        try:
            # Download the post
            L.download_post(post, target=target)

            # Define the original filename
            original_filename = f"{post.shortcode}.mp4"
            original_path = os.path.join(target, original_filename)

            if not os.path.isfile(original_path):
                print(f"MP4 video file for post {post.shortcode} not found in '{target}'.\n")
                continue

            # Retrieve likes and views
            likes = post.likes
            views = post.video_view_count if post.is_video else "N/A"
            likes_abbr = abbreviate_number(likes)
            views_abbr = abbreviate_number(views) if isinstance(views, int) else "N/A"

            # Determine new filename based on download type
            if download_type == "most liked":
                new_filename = f"{likes_abbr}Likes_{views_abbr}Views.mp4"
            elif download_type == "most viewed":
                new_filename = f"{views_abbr}Views_{likes_abbr}Likes.mp4"
            else:
                new_filename = f"{post.shortcode}.mp4"

            new_path = os.path.join(target, new_filename)

            # Rename the file to include likes and views
            os.rename(original_path, new_path)

            print(f"Successfully downloaded: {post.shortcode}")
            print(f"Likes: {likes} ({likes_abbr}Likes)")
            print(f"Views: {views} ({views_abbr}Views)")
            print(f"Path: {os.path.abspath(new_path)}\n")

            count += 1
        except Exception as e:
            print(f"Failed to download {post.shortcode}: {e}\n")
    print(f"Download completed. {count} posts downloaded in './{target}/' directory.")

def main():
    """
    Main execution flow of the Instagram downloader.

    Program Flow:
        1. Initialize Instaloader with optimized settings
        2. Optional user authentication
        3. Source selection (profile/hashtag)
        4. Download configuration (count/filters)
        5. Content retrieval and download
        6. Status reporting and error handling
    """
    # Initialize Instaloader with necessary parameters
    L = instaloader.Instaloader(
        sleep=True,                        # Automatically sleep between requests
        quiet=False,                       # Show detailed output
        download_pictures=False,           # Disable picture downloads
        download_videos=True,              # Enable video downloads
        download_video_thumbnails=False,   # Disable video thumbnails
        download_geotags=False,            # Skip downloading geotags
        download_comments=False,           # Skip downloading comments
        save_metadata=False,               # Disable metadata downloads to prevent .json.xz files
        compress_json=False,               # Not needed since metadata is disabled
        post_metadata_txt_pattern="",      # No additional metadata text files
        storyitem_metadata_txt_pattern="", # No story metadata text files
        max_connection_attempts=3,         # Retry up to 3 times on connection failures
        request_timeout=300,               # Timeout for requests set to 5 minutes
        rate_controller=None,              # Use default rate controller
        resume_prefix="iterator",          # Prefix for resume files
        check_resume_bbd=True,             # Check for valid resume files
        slide=None,                        # Not used for this script
        fatal_status_codes=None,           # Use default fatal status codes
        iphone_support=True,               # Enable iPhone media format support
        title_pattern=None,                # No title files
        sanitize_paths=False               # Do not sanitize file paths
    )

    print("=== Instagram Media Downloader ===\n")

    # Step 0: Optional Login for Private Profiles
    authenticate_instaloader(L)

    # Step 1: Choose the source (specific profile or explore via hashtag)
    source_choices = {
        '1': "Download from a specific user's profile",
        '2': "Download from Explore (Popular Posts via Hashtag)"
    }
    print("Select the source of the videos:")
    for key, value in source_choices.items():
        print(f"{key}: {value}")
    source_choice = input("Enter your choice (1/2): ").strip()

    if source_choice == '1':
        # Prompt for the Instagram username
        profile_username = input("\nEnter the Instagram username: ").strip()
        try:
            print(f"\nFetching profile '{profile_username}'...")
            profile = instaloader.Profile.from_username(L.context, profile_username)
            print(f"Profile '{profile_username}' fetched successfully.\n")
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"Error: The profile '{profile_username}' does not exist.")
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            sys.exit(1)

        # Step 2: Choose the number of videos to download
        num_choices = {
            '10': 'First 10 videos',
            '20': 'First 20 videos',
            '40': 'First 40 videos',
            '80': 'First 80 videos',
            '100': 'First 100 videos'
        }
        print("\nHow many videos would you like to download?")
        for key, value in num_choices.items():
            print(f"{key}: {value}")
        num_choice = input("Enter your choice (10/20/40/80/100): ").strip()
        if num_choice not in num_choices:
            print("Invalid number entered. Exiting.")
            sys.exit(1)
        num_videos = int(num_choice)

        # Step 3: Choose to filter by most liked or most viewed
        filter_choices = {
            '1': 'No filter (download as they appear)',
            '2': 'Download the most liked videos',
            '3': 'Download the most viewed videos'
        }
        print("\nDo you want to apply any filters?")
        for key, value in filter_choices.items():
            print(f"{key}: {value}")
        filter_choice = input("Enter your choice (1/2/3): ").strip()

        if filter_choice in ['2', '3']:
            # Inform the user about the need to fetch all posts for filtering
            print("\nFetching all video posts to apply filters. This may take some time...\n")
            posts = []
            try:
                for post in tqdm(profile.get_posts(), desc="Fetching all video posts", unit="post"):
                    if post.is_video:
                        posts.append(post)
            except Exception as e:
                print(f"An error occurred while fetching posts: {e}")
                sys.exit(1)

            print(f"\nTotal video posts fetched: {len(posts)}\n")

            if filter_choice == '2':
                # Sort posts by number of likes (descending)
                print("Sorting posts by the number of likes (most liked first)...\n")
                sorted_posts = sorted(posts, key=lambda p: p.likes, reverse=True)
                download_type = "most liked"
            elif filter_choice == '3':
                # Sort posts by number of views (descending)
                print("Sorting posts by the number of views (most viewed first)...\n")
                sorted_posts = sorted(posts, key=lambda p: p.video_view_count or 0, reverse=True)
                download_type = "most viewed"

            # Select top N posts after sorting
            posts_to_download = sorted_posts[:num_videos]
            print(f"Top {num_videos} {download_type} videos selected for download.\n")
        else:
            # No filtering; fetch only the required number of video posts
            print(f"\nNo filters applied. Retrieving the first {num_videos} videos...\n")
            posts_to_download = []
            fetched = 0
            try:
                for post in profile.get_posts():
                    if post.is_video:
                        posts_to_download.append(post)
                        fetched += 1
                        if fetched >= num_videos:
                            break
            except Exception as e:
                print(f"An error occurred while fetching posts: {e}")
                sys.exit(1)
            download_type = "as they appear"

            if not posts_to_download:
                print("No videos to download based on the selected criteria.")
                sys.exit(0)
            print(f"Retrieved {len(posts_to_download)} videos for download.\n")

        target = profile_username

    elif source_choice == '2':
        # For Explore, use a popular hashtag as a proxy
        print("\nDownloading from Explore is not directly supported by Instaloader.")
        print("As an alternative, you can download from a popular hashtag.\n")
        hashtag = input("Enter a popular hashtag (without #): ").strip()
        try:
            # Use Instaloader's built-in Hashtag class
            hashtag_obj = Hashtag.from_name(L.context, hashtag)
            print(f"\nFetching hashtag '#{hashtag}'...")
        except instaloader.exceptions.InvalidArgumentException:
            print(f"Error: The hashtag '#{hashtag}' does not exist or is invalid.")
            sys.exit(1)
        except instaloader.exceptions.QueryReturnedNotFoundException:
            print(f"Error: The hashtag '#{hashtag}' does not exist.")
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred while accessing the hashtag: {e}")
            sys.exit(1)

        print(f"Hashtag '#{hashtag}' fetched successfully.\n")

        # Step 2: Choose the number of videos to download
        num_choices = {
            '10': 'First 10 videos',
            '20': 'First 20 videos',
            '40': 'First 40 videos',
            '80': 'First 80 videos',
            '100': 'First 100 videos'
        }
        print("\nHow many videos would you like to download?")
        for key, value in num_choices.items():
            print(f"{key}: {value}")
        num_choice = input("Enter your choice (10/20/40/80/100): ").strip()
        if num_choice not in num_choices:
            print("Invalid number entered. Exiting.")
            sys.exit(1)
        num_videos = int(num_choice)

        # Step 3: Choose to filter by most liked or most viewed
        filter_choices = {
            '1': 'No filter (download as they appear)',
            '2': 'Download the most liked videos',
            '3': 'Download the most viewed videos'
        }
        print("\nDo you want to apply any filters?")
        for key, value in filter_choices.items():
            print(f"{key}: {value}")
        filter_choice = input("Enter your choice (1/2/3): ").strip()

        if filter_choice in ['2', '3']:
            # Inform the user about the need to fetch posts for filtering
            print("\nFetching video posts to apply filters. This may take some time...\n")
            posts = []
            try:
                for post in tqdm(hashtag_obj.get_posts(), desc="Fetching video posts", unit="post"):
                    if post.is_video:
                        posts.append(post)
            except Exception as e:
                print(f"An error occurred while fetching posts: {e}")
                sys.exit(1)

            print(f"\nTotal video posts fetched: {len(posts)}\n")

            if filter_choice == '2':
                # Sort posts by number of likes (descending)
                print("Sorting posts by the number of likes (most liked first)...\n")
                sorted_posts = sorted(posts, key=lambda p: p.likes, reverse=True)
                download_type = "most liked"
            elif filter_choice == '3':
                # Sort posts by number of views (descending)
                print("Sorting posts by the number of views (most viewed first)...\n")
                sorted_posts = sorted(posts, key=lambda p: p.video_view_count or 0, reverse=True)
                download_type = "most viewed"

            # Select top N posts after sorting
            posts_to_download = sorted_posts[:num_videos]
            print(f"Top {num_videos} {download_type} videos selected for download.\n")
        else:
            # No filtering; fetch only the required number of video posts
            print(f"\nNo filters applied. Retrieving the first {num_videos} videos...\n")
            posts_to_download = []
            fetched = 0
            try:
                for post in hashtag_obj.get_posts():
                    if post.is_video:
                        posts_to_download.append(post)
                        fetched += 1
                        if fetched >= num_videos:
                            break
            except Exception as e:
                print(f"An error occurred while fetching posts: {e}")
                sys.exit(1)
            download_type = "as they appear"

            if not posts_to_download:
                print("No videos to download based on the selected criteria.")
                sys.exit(0)
            print(f"Retrieved {len(posts_to_download)} videos for download.\n")

        target = f"hashtag_{hashtag}"

    else:
        print("Invalid source choice. Exiting.")
        sys.exit(1)

    # Step 4: Download the specified number of videos
    download_posts(L, posts_to_download, download_type, target)

if __name__ == "__main__":
    main()
