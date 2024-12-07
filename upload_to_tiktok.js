require('dotenv').config();
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');

// TikTok API Credentials
const TIKTOK_ACCESS_TOKEN = process.env.TIKTOK_ACCESS_TOKEN;

/**
 * Initialize an upload session with TikTok
 * @returns {Promise<string>} Upload session URL
 */
async function initializeUploadSession() {
  try {
    const response = await axios.post(
      'https://open.tiktokapis.com/v1.3/video/init_upload',
      {},
      {
        headers: {
          Authorization: `Bearer ${TIKTOK_ACCESS_TOKEN}`,
        },
      }
    );

    if (response.data && response.data.data && response.data.data.upload_url) {
      console.log('Initialized upload session:', response.data.data.upload_url);
      return response.data.data.upload_url;
    } else {
      throw new Error('Failed to initialize upload session.');
    }
  } catch (error) {
    console.error('Error initializing upload session:', error.response?.data || error.message);
    throw error;
  }
}

/**
 * Upload the video in chunks to TikTok
 * @param {string} uploadUrl - The TikTok upload URL
 * @param {string} filePath - Path to the video file
 */
async function uploadVideoInChunks(uploadUrl, filePath) {
  const CHUNK_SIZE = 4 * 1024 * 1024; // 4 MB per chunk
  const fileStats = fs.statSync(filePath);
  const fileSize = fileStats.size;

  console.log(`Uploading video in chunks: ${filePath} (${fileSize} bytes)`);

  const fileStream = fs.createReadStream(filePath, { highWaterMark: CHUNK_SIZE });
  let chunkIndex = 0;

  for await (const chunk of fileStream) {
    console.log(`Uploading chunk ${chunkIndex + 1}...`);

    try {
      const response = await axios.post(uploadUrl, chunk, {
        headers: {
          'Content-Type': 'application/octet-stream',
          'Content-Length': chunk.length,
          'Content-Range': `bytes ${chunkIndex * CHUNK_SIZE}-${Math.min(
            (chunkIndex + 1) * CHUNK_SIZE - 1,
            fileSize - 1
          )}/${fileSize}`,
        },
      });

      console.log(`Chunk ${chunkIndex + 1} uploaded successfully.`);
      chunkIndex++;
    } catch (error) {
      console.error(`Error uploading chunk ${chunkIndex + 1}:`, error.response?.data || error.message);
      throw error;
    }
  }

  console.log('All chunks uploaded successfully!');
}

/**
 * Finalize the video upload and set metadata
 * @param {string} videoId - The uploaded video ID
 * @param {string} caption - Caption for the video
 */
async function finalizeUpload(videoId, caption = 'Uploaded via API') {
  try {
    const response = await axios.post(
      'https://open.tiktokapis.com/v1.3/video/publish/',
      {
        video_id: videoId,
        caption: caption,
      },
      {
        headers: {
          Authorization: `Bearer ${TIKTOK_ACCESS_TOKEN}`,
        },
      }
    );

    if (response.data && response.data.data) {
      console.log('Video published successfully:', response.data.data);
    } else {
      throw new Error('Failed to publish video.');
    }
  } catch (error) {
    console.error('Error finalizing upload:', error.response?.data || error.message);
    throw error;
  }
}

/**
 * Main function to upload a video to TikTok
 */
(async () => {
  const videoFilePath = 'C:/Users/sakhr/Downloads/test.mp4'; // Replace with your video file path

  try {
    // Step 1: Initialize upload session
    const uploadUrl = await initializeUploadSession();

    // Step 2: Upload video in chunks
    await uploadVideoInChunks(uploadUrl, videoFilePath);

    // Step 3: Finalize and publish the video
    await finalizeUpload(uploadUrl, 'My first video uploaded via TikTok API!');
  } catch (error) {
    console.error('Failed to upload video:', error.message);
  }
})();
