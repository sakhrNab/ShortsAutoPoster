const express = require('express');
const bodyParser = require('body-parser');
const multer = require('multer');
const axios = require('axios');
const crypto = require('crypto');
const cookieParser = require('cookie-parser');
// const fetch = require('node-fetch'); // For handling TikTok API requests
const cors = require('cors');
require('dotenv').config(); // To load environment variables from .env file

// Initialize the app
const app = express();

// TikTok API credentials
const CLIENT_KEY = process.env.TIKTOK_CLIENT_KEY; // Your TikTok Client Key
const CLIENT_SECRET = process.env.TIKTOK_CLIENT_SECRET; // Your TikTok Client Secret
const REDIRECT_URI = 'http://127.0.0.1:5000/callback/'; // Redirect URI registered in TikTok Developer Dashboard
const session = require('express-session');

app.use(session({
    secret: 'your_secret_key', // Replace with a strong secret
    resave: false,
    saveUninitialized: true,
    cookie: { maxAge: 60000 } // 1-minute session
}));
// Middleware setup
app.use(cookieParser());
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Multer configuration for video uploads
const upload = multer({ dest: 'uploads/' });

// Routes

// OAuth Route: Redirects the user to TikTok's login/authorization page
app.get('/oauth', (req, res) => {
    const state = crypto.randomBytes(16).toString('hex');
    res.cookie('csrfState', state, { maxAge: 60000 }); // Store CSRF token in cookie

    const codeVerifier = crypto.randomBytes(64).toString('hex');
    const codeChallenge = crypto.createHash('sha256').update(codeVerifier).digest('base64url');

    req.session.codeVerifier = codeVerifier; // Store codeVerifier in session

    const url = `https://www.tiktok.com/v2/auth/authorize/` +
                `?client_key=${CLIENT_KEY}` +
                `&scope=user.info.basic` +
                `&response_type=code` +
                `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
                `&state=${state}` +
                `&code_challenge=${codeChallenge}` +
                `&code_challenge_method=S256`;

    res.redirect(url);
});


// TikTok Callback Endpoint: Handles TikTok's response after user authorization
app.get('/callback', async (req, res) => {
    const { code, state } = req.query;

    // Validate CSRF state
    if (req.cookies.csrfState !== state) {
        return res.status(403).send('Invalid state parameter. Potential CSRF attack.');
    }

    // Retrieve code_verifier from session
    const codeVerifier = req.session.codeVerifier;
    if (!codeVerifier) {
        return res.status(500).send('Code verifier not found. Authorization failed.');
    }

    try {
        const response = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                client_key: CLIENT_KEY,
                client_secret: CLIENT_SECRET,
                grant_type: 'authorization_code',
                code: code,
                redirect_uri: REDIRECT_URI,
                code_verifier: codeVerifier,
            }),
        });

        const data = await response.json();

        if (data.access_token) {
            res.status(200).send(`Access Token: ${data.access_token}`);
        } else {
            res.status(400).send('Failed to get access token: ' + JSON.stringify(data));
        }
    } catch (error) {
        res.status(500).send('Error exchanging token: ' + error.message);
    }
});

// Endpoint to handle TikTok video uploads
app.post('/post', upload.single('video'), async (req, res) => {
    const { description } = req.body;
    const videoPath = req.file.path;

    // Replace with the actual access token obtained from the OAuth process
    const ACCESS_TOKEN = 'your_tiktok_access_token'; // Replace this with a valid access token
    const API_URL = 'https://open.tiktokapis.com/v1/videos/upload/';

    try {
        // Upload video to TikTok
        const response = await axios.post(
            API_URL,
            {
                description: description,
                video: videoPath,
            },
            {
                headers: {
                    Authorization: `Bearer ${ACCESS_TOKEN}`,
                    'Content-Type': 'multipart/form-data',
                },
            }
        );

        res.status(200).send(response.data);
    } catch (error) {
        console.error('Error posting to TikTok:', error.response?.data || error.message);
        res.status(500).send({ error: error.response?.data || error.message });
    }
});

// TikTok Callback Handler for Uploads (Optional for debugging callbacks)
app.post('/tiktok/callback', (req, res) => {
    console.log('Callback received:', req.body);
    res.status(200).send({ status: 'success' });
});

// Start the server
const PORT = 5000;
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
