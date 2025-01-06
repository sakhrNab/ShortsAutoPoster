/**
 * @fileoverview YouTube Video Upload Automation Module
 * Handles authentication and automated video uploads to YouTube using OAuth2 and YouTube Data API v3.
 * Supports batch uploading from a directory with configurable scheduling.
 * 
 * @requires dotenv - For environment variable management
 * @requires fs - For file system operations
 * @requires googleapis - For YouTube API integration
 * 
 * @requires Environment Variables:
 * - YOUTUBE_CLIENT_ID: OAuth2 client ID
 * - YOUTUBE_CLIENT_SECRET: OAuth2 client secret
 * - YOUTUBE_REFRESH_TOKEN: OAuth2 refresh token
 */

require('dotenv').config();
const fs = require('fs');
const { google } = require('googleapis');

// Load OAuth2 client credentials from environment
const CLIENT_ID = process.env.YOUTUBE_CLIENT_ID;
const CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET;
const REFRESH_TOKEN = process.env.YOUTUBE_REFRESH_TOKEN;

/**
 * OAuth2 client configuration for YouTube API authentication
 * @constant {OAuth2Client}
 * @private
 */
const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  'urn:ietf:wg:oauth:2.0:oob'
);

// Set credentials with the refresh token
oauth2Client.setCredentials({ refresh_token: REFRESH_TOKEN });

/**
 * YouTube API client instance
 * @constant {youtube_v3.Youtube}
 * @private
 */
const youtube = google.youtube({
  version: 'v3',
  auth: oauth2Client
});

/**
 * Uploads a video to YouTube with specified metadata
 * @async
 * @function uploadVideo
 * @description Handles the upload of a single video file to YouTube with configurable metadata
 * 
 * @todo Implement folder scanning for batch uploads
 * @todo Add scheduling logic for timed uploads
 * @todo Integrate external metadata source (Excel/Google Docs)
 * 
 * @throws {Error} When video upload fails or authentication issues occur
 * @returns {Promise<void>}
 */
async function uploadVideo() {
  try {
    // Configure video file path
    // TODO: Implement folder scanning and scheduled uploads
    const videoPath = 'C:/Users/sakhr/Downloads/test.mp4'; // Path to your test video

    // Video metadata configuration
    // TODO: Implement dynamic metadata loading from external source
    const videoTitle = 'Test Upload from API'; // Title of the uploaded video
    const videoDescription = 'This is a test upload using the YouTube Data API.';
    const videoTags = ['test', 'api', 'nodejs'];

    // Execute video upload request
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

// Initialize video upload process
uploadVideo();
