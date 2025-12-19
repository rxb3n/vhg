# Setup Instructions

## Prerequisites

- Node.js 18+ and npm
- Python 3.8+
- FFmpeg installed and in PATH
- API keys for:
  - OpenAI (GPT-4o) OR Google Gemini
  - Wan 2.6 (for video generation)

## Installation

### 1. Frontend Setup

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will be available at http://localhost:3000

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your API keys:
# OPENAI_API_KEY=your_key_here
# OR
# GEMINI_API_KEY=your_key_here
# WAN_API_KEY=your_wan_key_here
# WAN_API_URL=https://api.wan.ai/v1/generate

# Run backend server
uvicorn main:app --reload --port 8000
```

Backend will be available at http://localhost:8000

## FFmpeg Installation

### Windows
Download from https://ffmpeg.org/download.html and add to PATH

### Mac
```bash
brew install ffmpeg
```

### Linux
```bash
sudo apt-get install ffmpeg
```

## Testing Without API Keys

The system includes placeholder functionality:
- If Wan API key is not set, placeholder videos will be generated using FFmpeg
- This allows testing the pipeline without actual video generation API calls

## Usage

1. Open http://localhost:3000 in your browser
2. Upload a product image
3. Review and edit the generated script (optional)
4. Click "Generate Video"
5. Wait for generation to complete (may take several minutes)
6. Download the final 60-second video

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (should be 3.8+)
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check if port 8000 is available

### Frontend won't start
- Check Node.js version: `node --version` (should be 18+)
- Delete `node_modules` and run `npm install` again
- Check if port 3000 is available

### FFmpeg errors
- Verify FFmpeg is installed: `ffmpeg -version`
- Ensure FFmpeg is in your system PATH
- On Windows, restart terminal after adding FFmpeg to PATH

### Video generation fails
- Check API keys in `.env` file
- Verify Wan 2.6 API endpoint is correct
- Check backend logs for detailed error messages

