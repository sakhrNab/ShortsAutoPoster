"""
Multi-platform Video Downloader Script

This script downloads videos from YouTube, Instagram, and TikTok using their URLs.
It uses different methods for each platform:
- YouTube: Official API + yt-dlp
- TikTok: Web scraping
- Instagram: Instaloader
"""

import os
from dotenv import load_dotenv
import requests
from pytube import YouTube
import instaloader
from bs4 import BeautifulSoup

# Load environment variables at the start
load_dotenv()

# Directory setup
def setup_directories(platform):
    """
    Create and return the path to platform-specific download directory.
    
    Args:
        platform (str): The platform name (youtube, instagram, or tiktok)
    
    Returns:
        str: Path to the created directory
    """
    path = f"downloads/{platform}"
    os.makedirs(path, exist_ok=True)
    return path

# YouTube video download using API
def download_youtube_video(api_key, url):
    """
    Download a YouTube video using the YouTube Data API and yt-dlp.
    
    Args:
        api_key (str): YouTube Data API key
        url (str): YouTube video URL
    """
    try:
        # Extract video ID from URL
        video_id = None
        if "youtube.com" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be" in url:
            video_id = url.split("/")[-1]

        if not video_id:
            print("Invalid YouTube URL. Unable to extract video ID.")
            return

        # Fetch video details using YouTube Data API
        api_url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,contentDetails&key={api_key}"
        response = requests.get(api_url)

        if response.status_code != 200:
            print(f"Failed to fetch video details: {response.status_code}")
            return

        video_data = response.json()

        if "items" not in video_data or len(video_data["items"]) == 0:
            print("Video not found or unavailable.")
            return

        video_title = video_data["items"][0]["snippet"]["title"]
        print(f"Fetching video: {video_title}")

        # Use yt-dlp for downloading
        from yt_dlp import YoutubeDL

        ydl_opts = {
            "format": "best",
            "outtmpl": f"{setup_directories('youtube')}/{video_title}.mp4"
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print(f"YouTube video downloaded successfully: {video_title}.mp4")
    except Exception as e:
        print(f"Failed to download YouTube video: {e}")

# TikTok video download
def download_tiktok_video(page_url):
    """
    Download a TikTok video using web scraping.
    
    Args:
        page_url (str): TikTok video URL
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(page_url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        video_tag = soup.find("video")
        if video_tag and video_tag.get("src"):
            video_url = video_tag["src"]
            print(f"Downloading TikTok video from URL: {video_url}")
            video_response = requests.get(video_url, stream=True)
            if video_response.status_code == 200:
                filename = os.path.join(setup_directories("tiktok"), "tiktok_video.mp4")
                with open(filename, "wb") as f:
                    for chunk in video_response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                print(f"TikTok video downloaded successfully to {filename}")
            else:
                print("Failed to download TikTok video: Unable to fetch the content.")
        else:
            print("No video found on the TikTok page.")
    except Exception as e:
        print(f"Failed to download TikTok video: {e}")

# Instagram video download
def download_instagram_video(page_url):
    """
    Download an Instagram video using Instaloader.
    
    Args:
        page_url (str): Instagram post URL
    
    Note:
        Requires Instagram credentials to be set in the function.
    """
    try:
        loader = instaloader.Instaloader()
        username = "your_username"  # Replace with your username
        password = "your_password"  # Replace with your password
        loader.login(username, password)

        shortcode = page_url.split("/")[-2]
        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        print(f"Downloading Instagram video from URL: {page_url}")
        loader.download_post(post, target="downloads/instagram")

        # Remove unwanted files, keeping only the .mp4
        dir_path = setup_directories("instagram")
        for filename in os.listdir(dir_path):
            if not filename.endswith(".mp4"):
                os.remove(os.path.join(dir_path, filename))
        print("Instagram video downloaded successfully!")
    except Exception as e:
        print(f"Failed to download Instagram video: {e}")

# Main function to handle user input
def main():
    """
    Main function that handles user input and directs to appropriate download function
    based on the URL provided.
    """
    # Enter your YouTube API Key here
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")  # Replace with your actual API key

    url = input("Enter the URL of the video (YouTube, Instagram, or TikTok): ").strip()
    if "youtube.com" in url or "youtu.be" in url:
        download_youtube_video(youtube_api_key, url)
    elif "instagram.com" in url:
        download_instagram_video(url)
    elif "tiktok.com" in url:
        download_tiktok_video(url)
    else:
        print("Unsupported URL. Please provide a URL from YouTube, Instagram, or TikTok.")

if __name__ == "__main__":
    main()
