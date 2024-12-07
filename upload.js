require('dotenv').config();
const fs = require('fs');
const { google } = require('googleapis');

// Load OAuth2 client credentials from environment
const CLIENT_ID = process.env.YOUTUBE_CLIENT_ID;
const CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET;
const REFRESH_TOKEN = process.env.YOUTUBE_REFRESH_TOKEN;

// Create an OAuth2 client
const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  'urn:ietf:wg:oauth:2.0:oob'
);

// Set credentials with the refresh token
oauth2Client.setCredentials({ refresh_token: REFRESH_TOKEN });

// Create a YouTube API client
const youtube = google.youtube({
  version: 'v3',
  auth: oauth2Client
});

async function uploadVideo() {
  try {
    const videoPath = 'C:/Users/sakhr/Downloads/test.mp4'; // Path to your test video
    const videoTitle = 'Test Upload from API'; // Title of the uploaded video
    const videoDescription = 'This is a test upload using the YouTube Data API.';
    const videoTags = ['test', 'api', 'nodejs'];

    const res = await youtube.videos.insert({
      part: 'snippet,status',
      requestBody: {
        snippet: {
          title: videoTitle,
          description: videoDescription,
          tags: videoTags,
          categoryId: '22' // "People & Blogs" category, as an example
        },
        status: {
          privacyStatus: 'private' // Upload as private to test without making it public
        }
      },
      media: {
        body: fs.createReadStream(videoPath)
      }
    });

    console.log('Video uploaded successfully!');
    console.log('Video URL: https://www.youtube.com/watch?v=' + res.data.id);
  } catch (error) {
    console.error('Error uploading video:', error);
  }
}

uploadVideo();
