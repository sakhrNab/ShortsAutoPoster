/**
 * YouTube OAuth2 Token Generator
 * 
 * This script handles the one-time OAuth2 authorization process for YouTube API access.
 * It generates a refresh token that can be used for subsequent API calls without
 * requiring user intervention.
 * 
 * Flow:
 * 1. Load credentials from .env file
 * 2. Create OAuth2 client
 * 3. Generate authorization URL
 * 4. User visits URL and authorizes app
 * 5. User enters authorization code
 * 6. Exchange code for access and refresh tokens
 * 
 * Usage:
 * 1. Run script: node get_token.js
 * 2. Visit displayed URL
 * 3. Authorize app and copy code
 * 4. Paste code into terminal
 * 5. Save displayed refresh token in .env file
 */

require('dotenv').config(); // Load environment variables from .env
const {google} = require('googleapis');
const readline = require('readline');

// Load your credentials from environment variables
const CLIENT_ID = process.env.YOUTUBE_CLIENT_ID;
const CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET;
const REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob';

/**
 * Create OAuth2 client with credentials
 * REDIRECT_URI is set to 'urn:ietf:wg:oauth:2.0:oob' for command-line applications
 */
const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  REDIRECT_URI
);

/**
 * Define required YouTube API scope
 * youtube.upload scope allows for video upload permissions
 */
const SCOPES = ['https://www.googleapis.com/auth/youtube.upload'];

const authUrl = oauth2Client.generateAuthUrl({
  access_type: 'offline',
  scope: SCOPES,
});

console.log('Authorize this app by visiting this URL:', authUrl);

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

rl.question('Enter the code from that page here: ', (code) => {
  rl.close();
  oauth2Client.getToken(code, (err, token) => {
    if (err) return console.error('Error retrieving access token:', err);
    console.log('Access Token:', token.access_token);
    console.log('Refresh Token:', token.refresh_token);
    console.log('Save your refresh token in your .env file as YOUTUBE_REFRESH_TOKEN=...');
  });
});
