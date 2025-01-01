import asyncio
import aiohttp
import os
import pandas as pd
import json
from googleapiclient.discovery import build
from TikTokApi import TikTokApi
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get YouTube API Key from environment variable
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY environment variable is not set")

# Function to fetch YouTube videos based on a tag and filter
def fetch_youtube_videos(tag, filter_type, max_results=10):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    search_request = youtube.search().list(
        q=tag,
        part="snippet",
        type="video",
        maxResults=max_results,
        order=filter_type  # date (latest), viewCount (most views), rating (most likes)
    )

    response = search_request.execute()
    
    print(f"\nYouTube Videos for tag '{tag}' sorted by '{filter_type}':")
    video_details = []
    for idx, item in enumerate(response.get("items", []), start=1):
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        channel = item["snippet"]["channelTitle"]
        published_at = item["snippet"]["publishedAt"]
        video_link = f"https://www.youtube.com/watch?v={video_id}"
        video_details.append({"id": video_id, "title": title, "channel": channel, "link": video_link, "published_at": published_at})
        print(f"{idx}. {title} - Channel: {channel} - Link: {video_link}")
    
    return video_details

# Function to fetch additional video stats like views and likes
def fetch_youtube_video_stats(video_ids):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    video_ids_str = ",".join(video_ids)

    stats_request = youtube.videos().list(
        part="statistics",
        id=video_ids_str
    )

    response = stats_request.execute()
    stats = {}
    for item in response.get("items", []):
        video_id = item["id"]
        stats[video_id] = {
            "views": int(item["statistics"].get("viewCount", 0)),
            "likes": int(item["statistics"].get("likeCount", 0))
        }
    return stats

# Function to download videos using yt-dlp with metadata in filename
def download_youtube_videos(video_details, stats, download_path="downloads/youtube"):
    os.makedirs(download_path, exist_ok=True)
    for video in video_details:
        video_id = video["id"]
        views = stats[video_id]["views"]
        likes = stats[video_id]["likes"]
        date_posted = datetime.strptime(video["published_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%d.%m.%y")
        filename = f"{likes}Likes, {views}Views, {date_posted}.%(ext)s"
        print(f"Downloading: {video['link']} as {filename}")
        subprocess.run(["yt-dlp", "-o", os.path.join(download_path, filename), video['link']])

# Function to save video details into an Excel file
def save_to_excel(video_details, stats, platform, output_file="videos_report.xlsx"):
    data = []
    for video in video_details:
        if platform == "youtube":
            video_id = video["id"]
            views = stats[video_id]["views"]
            likes = stats[video_id]["likes"]
            date_posted = datetime.strptime(video["published_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%d.%m.%y")
            data.append({
                "Video Title": video["title"],
                "Channel": video["channel"],
                "URL": video["link"],
                "Views": views,
                "Likes": likes,
                "Posted On": date_posted
            })
        elif platform == "tiktok":
            data.append({
                "Video Title": video["title"],
                "Author": video["author"],
                "URL": video["link"],
                "Views": video["views"],
                "Likes": video["likes"],
                "Posted On": video["posted_on"]
            })
    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False)
    print(f"Video details saved to {output_file}")

# Fetch TikTok Videos
def fetch_tiktok_videos(tag, max_results=10):
    print(f"\nFetching TikTok Videos for tag '{tag}'...")
    videos = []
    hashtag_url = f"https://www.tiktok.com/tag/{tag}"
    output_dir = "downloads/tiktok"

    os.makedirs(output_dir, exist_ok=True)
    print(f"Using yt-dlp to fetch videos for hashtag '{tag}'...")

    # Run yt-dlp to download metadata
    subprocess.run([
        "yt-dlp",
        "--max-downloads", str(max_results),
        "--write-info-json",
        "--skip-download",
        "--flat-playlist",
        "-o", f"{output_dir}/%(id)s.json",
        hashtag_url
    ])

    # Parse metadata from JSON files
    for file in os.listdir(output_dir):
        if file.endswith(".json"):
            with open(os.path.join(output_dir, file), "r") as f:
                data = json.load(f)
                videos.append({
                    "title": data.get("title", "No Title"),
                    "author": data.get("uploader", "Unknown"),
                    "views": data.get("view_count", 0),
                    "likes": data.get("like_count", 0),
                    "posted_on": datetime.fromtimestamp(data.get("upload_date", 0)).strftime("%d.%m.%y"),
                    "link": data.get("webpage_url", "")
                })
    return videos

# Download TikTok Videos
def download_tiktok_videos(videos, download_path="downloads/tiktok"):
    os.makedirs(download_path, exist_ok=True)
    for video in videos:
        filename = f"{video['likes']}Likes, {video['views']}Views, {video['posted_on']}.%(ext)s"
        print(f"Downloading: {video['link']} as {filename}")
        subprocess.run(["yt-dlp", "-o", os.path.join(download_path, filename), video['link']])

async def main():
    print("Video Fetcher Script")
    print("Select Platform:")
    print("1. YouTube")
    print("2. TikTok")
    
    choice = input("Enter your choice (1/2): ").strip()
    tag = input("Enter a tag or keyword: ").strip()
    
    if choice == '1':
        print("Select Filter:")
        print("1. Latest uploaded")
        print("2. Most views")
        print("3. Most likes")
        print("4. Latest uploaded and sort by most views/likes")
        
        filter_choice = input("Enter filter choice (1/2/3/4): ").strip()
        filter_mapping = {'1': 'date', '2': 'viewCount', '3': 'rating'}
        if filter_choice == '4':
            video_details = fetch_youtube_videos(tag, 'date')
            video_ids = [video["id"] for video in video_details]
            stats = fetch_youtube_video_stats(video_ids)
            download_youtube_videos(video_details, stats)
            save_to_excel(video_details, stats, "youtube")
        else:
            filter_type = filter_mapping.get(filter_choice, 'date')
            video_details = fetch_youtube_videos(tag, filter_type)
            video_ids = [video["id"] for video in video_details]
            stats = fetch_youtube_video_stats(video_ids)
            download_youtube_videos(video_details, stats)
            save_to_excel(video_details, stats, "youtube")
    elif choice == '2':
        max_results = int(input("How many TikTok videos to fetch? ").strip())
        videos = fetch_tiktok_videos(tag, max_results)
        download_tiktok_videos(videos)
        save_to_excel(videos, {}, "tiktok")
    else:
        print("Invalid choice.")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
