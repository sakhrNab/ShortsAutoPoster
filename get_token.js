require('dotenv').config(); // Load environment variables from .env
const {google} = require('googleapis');
const readline = require('readline');

// Load your credentials from environment variables
const CLIENT_ID = process.env.YOUTUBE_CLIENT_ID;
const CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET;
const REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob';

const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  REDIRECT_URI
);

// This scope allows for uploading videos to YouTube
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
