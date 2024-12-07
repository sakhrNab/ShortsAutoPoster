require('dotenv').config();
const axios = require('axios');

const ACCESS_TOKEN = process.env.INSTAGRAM_ACCESS_TOKEN;
const BUSINESS_ACCOUNT_ID = process.env.INSTAGRAM_BUSINESS_ACCOUNT_ID;
const VIDEO_URL = process.env.INSTAGRAM_VIDEO_URL;

async function uploadInstagramReel() {
  try {
    // Step 1: Create a media object with the video_url
    // Note: For reels, we use the same endpoint as other media, but specify 'VIDEO' as the media type.
    
    const caption = "Check out my new reel! #myreel #test";
    
    console.log("Creating media container on Instagram...");
    const createMediaResponse = await axios.post(
      `https://graph.facebook.com/v17.0/${BUSINESS_ACCOUNT_ID}/media`,
      {
        media_type: 'VIDEO',
        video_url: VIDEO_URL,
        caption: caption,
        // No thumbnail is required but can be added if you have a thumbnail_url
      },
      {
        params: {
          access_token: ACCESS_TOKEN
        }
      }
    );

    const creationId = createMediaResponse.data.id;
    console.log("Media container created:", creationId);

    // Step 2: Publish the created media as a reel
    // This finalizes the reel on your account.
    console.log("Publishing the reel...");
    const publishResponse = await axios.post(
      `https://graph.facebook.com/v17.0/${BUSINESS_ACCOUNT_ID}/media_publish`,
      {
        creation_id: creationId
      },
      {
        params: {
          access_token: ACCESS_TOKEN
        }
      }
    );

    console.log("Reel published successfully!");
    console.log("Publish Response:", publishResponse.data);
    console.log("Check your Instagram profile for the new reel.");
  } catch (error) {
    console.error("Error uploading Instagram Reel:", error.response ? error.response.data : error.message);
  }
}

uploadInstagramReel();
