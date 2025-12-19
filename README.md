# Viral Hook Generator

A web application that generates viral-style 60-second video hooks from a single product image using AI. The pipeline ensures product fidelity by re-injecting the original product image into every scene generation.

## Features

- **Image-to-Video Pipeline**: Uses Image-to-Video (I2V) architecture to maintain product consistency
- **12-Scene Script Generation**: AI-powered vision director creates structured 12-scene scripts
- **720p Vertical Videos**: Generates 9:16 aspect ratio videos optimized for social media
- **Audio & Color Normalization**: Professional post-processing with FFmpeg
- **Caching**: Product analysis cached by image hash for efficiency
- **Clean Architecture**: Separate frontend (Next.js) and backend (Python FastAPI)

## Project Structure

```
.
├── app/                    # Next.js frontend
│   ├── page.tsx           # Main page
│   ├── layout.tsx         # Root layout
│   └── globals.css        # Global styles
├── components/            # React components
│   ├── ImageUpload.tsx    # Image upload component
│   ├── ScriptReview.tsx   # Script review/editing
│   └── VideoPreview.tsx   # Video preview component
├── backend/               # Python FastAPI backend
│   ├── main.py           # API endpoints
│   ├── models.py         # Database models
│   ├── database.py       # Database setup
│   └── services/         # Business logic
│       ├── vision_director.py    # Vision LLM integration
│       ├── video_generator.py    # Wan 2.6 integration
│       └── video_assembler.py   # FFmpeg processing
└── types/                # TypeScript types
```

## Setup

### Frontend (Next.js)

```bash
npm install
npm run dev
```

Frontend runs on http://localhost:3000

### Backend (Python)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn main:app --reload --port 8000
```

Backend runs on http://localhost:8000

## Environment Variables

Create `backend/.env` with:

```env
OPENAI_API_KEY=your_key_here
# OR
GEMINI_API_KEY=your_key_here

WAN_API_KEY=your_wan_key_here
WAN_API_URL=https://api.wan.ai/v1/generate
```

## Requirements

- Node.js 18+
- Python 3.8+
- FFmpeg (for video processing)
- API keys for OpenAI/Gemini and Wan 2.6

## Workflow

1. **Upload Image**: User uploads product image
2. **Analyze**: Vision LLM analyzes image and generates 12-scene script
3. **Review**: User reviews and edits script JSON
4. **Generate**: System generates 12 clips (5 seconds each) using Wan 2.6
5. **Assemble**: FFmpeg concatenates clips with audio/color normalization
6. **Output**: Final 60-second video ready for download

## Technical Details

- **Resolution**: 720p (1280x720 for 9:16 = 405x720)
- **Aspect Ratio**: 9:16 (vertical)
- **Duration**: 60 seconds (12 scenes × 5 seconds)
- **Video Format**: MP4 (H.264/AAC)
- **Database**: SQLite

## License

MIT

