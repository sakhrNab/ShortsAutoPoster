"""
TikTok Video Fetcher and Downloader

This script automates the process of fetching and downloading TikTok videos based on hashtags.
It uses Playwright for web scraping and handles video downloads with proper metadata storage.

Requirements:
    - playwright
    - pandas
    - requests
    - asyncio
"""

import asyncio
import os
import pandas as pd
import requests
from datetime import datetime
from playwright.async_api import async_playwright

def save_tiktok_videos_to_excel(videos, output_file="tiktok_videos.xlsx"):
    """
    Save fetched video metadata to an Excel file.

    Args:
        videos (list): List of dictionaries containing video metadata
        output_file (str): Path to the output Excel file (default: "tiktok_videos.xlsx")

    Returns:
        None
    """
    data = []
    for video in videos:
        data.append({
            "Video Title": video["title"],
            "Author": video["author"],
            "URL": video["url"],
            "Views": video["views"],
            "Likes": video["likes"],
            "Posted On": video["posted_on"],
            "Downloaded File": video["filename"]
        })
    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False)
    print(f"Video details saved to {output_file}")

async def fetch_tiktok_videos(tag, max_results):
    """
    Fetch TikTok videos for a given hashtag using web scraping.

    Args:
        tag (str): TikTok hashtag to search for (without #)
        max_results (int): Maximum number of videos to fetch

    Returns:
        list: List of dictionaries containing video metadata and download info
    
    Raises:
        Exception: If there's an error during video fetching or downloading
    """
    async with async_playwright() as p:
        # Launch browser for debugging
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.set_viewport_size({"width":1280,"height":800})

        hashtag_url = f"https://www.tiktok.com/tag/{tag}"
        print(f"Navigating to: {hashtag_url}")

        # Navigate and wait for network to be idle
        await page.goto(hashtag_url, wait_until='networkidle')

        # Wait a bit to ensure content loads
        await page.wait_for_timeout(5000)

        # Wait for video items to appear
        await page.wait_for_selector('[data-e2e="challenge-item"]', timeout=30000)

        videos = []

        while len(videos) < max_results:
            video_elements = await page.query_selector_all('[data-e2e="challenge-item"]')

            for video_element in video_elements[:max_results - len(videos)]:
                try:
                    # Extract URL (link to individual video page)
                    video_link = await video_element.query_selector('a[href*="/video/"]')
                    video_url = await video_link.get_attribute('href') if video_link else "Unknown"

                    # Extract title
                    title_element = await video_element.query_selector('div[data-e2e="challenge-item-desc"] h1')
                    title = await title_element.inner_text() if title_element else "Unknown"

                    # Extract author
                    author_element = await video_element.query_selector('p[data-e2e="challenge-item-username"]')
                    author = await author_element.inner_text() if author_element else "Unknown"

                    # Views, likes, posted_on are unknown for now
                    views = "Unknown"
                    likes = "Unknown"
                    posted_on = "Unknown"

                    # Now open the video detail page to extract direct video URL
                    detail_page = await context.new_page()
                    await detail_page.goto(video_url, wait_until='networkidle')
                    await detail_page.wait_for_timeout(3000)

                    # The <video> tag should have a src attribute for the mp4
                    video_tag = await detail_page.query_selector('video')
                    video_src = await video_tag.get_attribute('src') if video_tag else None

                    filename = "video_" + video_url.split("/")[-1] + ".mp4"
                    if video_src:
                        # Download the video using requests
                        r = requests.get(video_src, timeout=30)
                        with open(filename, 'wb') as f:
                            f.write(r.content)
                        print(f"Downloaded video: {filename}")
                    else:
                        filename = "No_video_src_found.mp4"
                        print("No direct video URL found for:", video_url)

                    await detail_page.close()

                    videos.append({
                        "title": title.strip() if title else "Unknown",
                        "author": author.strip() if author else "Unknown",
                        "url": video_url.strip() if video_url else "Unknown",
                        "views": views,
                        "likes": likes,
                        "posted_on": posted_on,
                        "filename": filename
                    })
                except Exception as e:
                    print(f"Error fetching a video: {e}")

            if len(videos) < max_results:
                # Scroll down to load more
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000)

        await browser.close()
        return videos

async def main():
    """
    Main entry point for the TikTok video fetcher.
    Handles user input and orchestrates the fetching process.
    """
    tag = input("Enter a TikTok hashtag (without #): ").strip()
    max_results = int(input("Enter the number of videos to fetch: ").strip())

    print(f"Fetching TikTok videos for tag: {tag}")
    videos = await fetch_tiktok_videos(tag, max_results)

    print(f"Fetched {len(videos)} videos.")
    save_tiktok_videos_to_excel(videos)

if __name__ == "__main__":
    asyncio.run(main())
