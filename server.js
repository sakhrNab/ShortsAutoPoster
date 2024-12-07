const express = require('express');
const bodyParser = require('body-parser');
const multer = require('multer');
const axios = require('axios');

const app = express();

// Middleware to parse JSON and form data
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Multer configuration for video uploads
const upload = multer({ dest: 'uploads/' });

// TikTok callback endpoint
app.post('/tiktok/callback', (req, res) => {
    console.log('Callback received:', req.body);
    res.status(200).send({ status: 'success' });
});

// Endpoint to post videos to TikTok
app.post('/post', upload.single('video'), async (req, res) => {
    const { description } = req.body;
    const videoPath = req.file.path;

    // TikTok API credentials
    const ACCESS_TOKEN = "your_tiktok_access_token";
    const API_URL = "https://open.tiktokapis.com/v1/videos/upload/";

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
        console.error('Error posting to TikTok:', error.response.data);
        res.status(500).send({ error: error.response.data });
    }
});

// Start the server
const PORT = 5000;
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
