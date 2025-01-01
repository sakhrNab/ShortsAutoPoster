"""
Instagram Video Fetcher

A utility script to fetch Instagram videos by hashtag with filtering capabilities.
Supports various sorting options and metadata extraction.

Requirements:
    - instaloader: For Instagram API interactions
"""

import instaloader

def fetch_instagram_videos():
    """
    Main function to fetch Instagram videos based on user preferences.
    
    Features:
        - Hashtag-based video fetching
        - Configurable video count
        - Multiple sorting options (Most Viewed, Most Liked, Latest Uploaded)
        - Automatic filename generation with engagement metrics
    
    Returns:
        None: Prints video information to console
    """
    # Prompt user for inputs
    hashtag = input("Enter the hashtag (without #): ").strip()
    num_videos = int(input("How many videos do you want to fetch? ").strip())
    filter_option = input("Choose a filter (Most Viewed, Most Liked, Latest Uploaded): ").strip()

    # Initialize Instaloader
    loader = instaloader.Instaloader()

    # Load posts for the given hashtag
    print(f"Fetching videos for hashtag #{hashtag}...")
    posts = instaloader.Hashtag.from_name(loader.context, hashtag).get_posts()

    videos = []

    for post in posts:
        # Filter only video posts
        if post.is_video:
            videos.append({
                'url': post.video_url,
                'likes': post.likes,
                'views': post.video_view_count,
                'date': post.date
            })
        if len(videos) >= num_videos:
            break

    # Apply sorting based on filter
    if filter_option.lower() == "most viewed":
        videos.sort(key=lambda x: x.get('views', 0), reverse=True)
    elif filter_option.lower() == "most liked":
        videos.sort(key=lambda x: x.get('likes', 0), reverse=True)
    elif filter_option.lower() == "latest uploaded":
        videos.sort(key=lambda x: x.get('date', ''), reverse=True)

    # Display the results
    for i, video in enumerate(videos, start=1):
        filename = f"{video['views']}Views{video['likes']}Likes{video['date'].strftime('%d%b%y')}.mp4"
        print(f"{i}. Video URL: {video['url']}\n   Metadata: {filename}")

if __name__ == "__main__":
    fetch_instagram_videos()
