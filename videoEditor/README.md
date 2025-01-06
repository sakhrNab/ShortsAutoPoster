# Video Automater - Social Media Video Processor

A powerful video processing tool designed to automatically format and brand videos for multiple social media platforms.

## Overview

This application automates the process of preparing videos for different social media platforms by:
1. Reformatting videos to platform-specific dimensions
2. Adding customizable branding (logo overlay)
3. Adding professional black bars and backgrounds
4. Maintaining high quality through hardware acceleration

## Features

### Platform Support
- Instagram (Portrait, Square)
- TikTok
- YouTube Shorts
- YouTube Long-form

### Video Processing
- Automatic aspect ratio conversion (1:1, 9:16, 16:9)
- Smart video scaling and positioning
- Hardware-accelerated encoding (NVIDIA NVENC)
- Maintains video quality
- Preserves original audio

### Branding Elements
- Customizable logo placement
- Adjustable logo size
- Position control (top, center, bottom)
- Opacity settings

### Background Options
- Top black bar (optional)
- Bottom black bar (optional)
- Adjustable opacity
- Customizable heights

## Requirements

### System Requirements
- Python 3.7+
- FFmpeg with NVENC support
- NVIDIA GPU
- Windows/Linux/macOS

### Python Dependencies
```
certifi>=2024.12.14
charset-normalizer>=3.4.1
idna>=3.10
instaloader>=4.14
numpy>=2.2.1
opencv-contrib-python>=4.10.0.84
pillow>=11.1.0
PyYAML>=6.0.2
requests>=2.32.3
tk>=0.1.0
urllib3>=2.3.0
```

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Install FFmpeg with NVENC support
4. Place your brand icon in `assets/fullicon.png`

## Usage

### Quick Start
```bash
python video-automater11.py
```

### Configuration

#### Using config.yaml
Create/modify `config.yaml` to set default values for:
- Platform-specific settings
- Background preferences
- Icon positioning
- Video dimensions

#### Interactive Mode
1. Select target platform
2. Choose aspect ratio
3. Configure backgrounds:
   - Top bar (optional)
   - Bottom bar (optional)
4. Set icon preferences:
   - Size (100-1000px)
   - Position (center/left/right)
   - Vertical offset

### Platform-Specific Presets

#### Instagram
- Portrait (9:16)
- 600px icon width
- Centered logo
- 15% bottom background

#### TikTok
- Portrait (9:16)
- 500px icon width
- 20% bottom background
- Optimized for mobile viewing

#### YouTube Shorts
- Portrait (9:16)
- 550px icon width
- 15% bottom background

#### YouTube Long
- Landscape (16:9)
- 400px icon width
- 12% bottom background

## Output Structure

```
ai.waverider/
├── instagram/
├── tiktok/
├── youtube_shorts/
└── youtube_long/
```

## Best Practices

1. Input Videos:
   - Use high-quality source videos
   - MP4 or MOV format
   - Clean, uncompressed footage

2. Branding:
   - Use PNG format for logo
   - Transparent background
   - High resolution

3. Performance:
   - Process multiple videos simultaneously
   - Utilizes GPU acceleration
   - Maintains original audio quality

## Troubleshooting

Common issues and solutions:
1. FFmpeg not found: Add FFmpeg to system PATH
2. NVIDIA GPU required: Ensure proper GPU drivers
3. Icon not found: Check assets/fullicon.png path

## Contributing

Feel free to contribute by:
1. Reporting bugs
2. Suggesting features
3. Creating pull requests

## License

[Your License Type] - See LICENSE file for details

## Contact

sakhr270@gmail.com