# Viral Hook Generator - Backend

Python FastAPI backend for generating viral video hooks from product images.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

3. Run the server:
```bash
uvicorn main:app --reload --port 8000
```

## API Endpoints

- `POST /api/analyze-product` - Upload product image and get script JSON
- `POST /api/generate-video` - Start video generation process
- `GET /api/generation-status/{ad_id}` - Get generation status
- `GET /api/files/{filename}` - Serve uploaded files
- `GET /api/videos/{filename}` - Serve generated videos

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key for GPT-4o vision
- `GEMINI_API_KEY` - Google Gemini API key (alternative)
- `WAN_API_KEY` - Wan 2.6 API key from Alibaba Model Studio (DashScope)
- `WAN_API_URL` - Wan 2.6 API endpoint URL (default: https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation)

### Getting Alibaba Model Studio API Key

1. Go to [Alibaba Model Studio Console](https://modelstudio.console.alibabacloud.com/)
2. Navigate to API Keys section
3. Create or copy your DashScope API key
4. Set it in your `.env` file as `WAN_API_KEY`

**Note**: If the default endpoint doesn't work, check the Alibaba Model Studio documentation for the correct endpoint URL for your region/service.

## Requirements

- Python 3.8+
- FFmpeg (for video processing)
- SQLite (database)

