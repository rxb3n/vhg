from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from services.vision_director import VisionDirector
from services.video_generator import VideoGenerator
from services.video_assembler import VideoAssembler
from database import get_db, init_db, get_db_session
from models import AdGeneration, Clip

app = FastAPI(title="Viral Hook Generator API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Initialize services
vision_director = VisionDirector()
video_generator = VideoGenerator()
video_assembler = VideoAssembler()


class ScriptData(BaseModel):
    product_name: str
    master_description: str
    scenes: List[dict]
    tone: Optional[str] = None


class GenerateVideoRequest(BaseModel):
    script: ScriptData
    imageUrl: str


@app.get("/")
async def root():
    return {"message": "Viral Hook Generator API"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify API keys and services"""
    import os
    return {
        "status": "ok",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "wan_configured": bool(os.getenv("WAN_API_KEY")),
        "vision_service_ready": vision_director.openai_client is not None or vision_director.gemini_client is not None
    }


@app.post("/api/analyze-product")
async def analyze_product(image: UploadFile = File(...)):
    """Analyze product image and generate script JSON"""
    import traceback
    import uuid
    
    try:
        # Save uploaded image temporarily
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate a safe filename
        file_ext = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
        safe_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            content = await image.read()
            f.write(content)
        
        # Verify file was saved
        if not os.path.exists(file_path):
            raise Exception("Failed to save uploaded image")
        
        # Generate script using Vision Director
        print(f"Starting image analysis for: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        print(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 0} bytes")
        script_data = await vision_director.analyze_and_script(file_path)
        print(f"Script generated successfully with {len(script_data.get('scenes', []))} scenes")
        
        # Return image URL (relative path for consistency)
        # The frontend will convert to full URL if needed
        image_url = f"/api/files/{safe_filename}"
        
        # Verify the file exists before returning
        if not os.path.exists(file_path):
            raise Exception(f"Failed to save uploaded image to {file_path}")
        
        print(f"Image saved successfully: {file_path} -> {image_url}")
        
        return {
            "imageUrl": image_url,
            "script": script_data
        }
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(f"Error in analyze_product: {error_detail}")
        import logging
        logging.error(f"Error in analyze_product: {error_detail}")
        # Return more detailed error for debugging
        raise HTTPException(
            status_code=500, 
            detail=f"Error analyzing product: {str(e)}. Check server logs for details."
        )


@app.post("/api/generate-video")
async def generate_video(request: GenerateVideoRequest):
    """Start video generation process"""
    try:
        import uuid
        db = get_db_session()
        try:
            # Create ad generation record
            ad_gen = AdGeneration(
                id=str(uuid.uuid4()),
                product_image_url=request.imageUrl,
                script_data=request.script.dict(),
                status="pending"
            )
            db.add(ad_gen)
            db.commit()
            db.refresh(ad_gen)
            
            ad_id = ad_gen.id
            ad_status = ad_gen.status
            
            # Start async generation
            import asyncio
            # Convert Pydantic model to dict for the video generator
            script_dict = request.script.dict() if hasattr(request.script, 'dict') else request.script
            asyncio.create_task(video_generator.generate_all_clips(ad_id, script_dict, request.imageUrl))
            
            return {
                "id": ad_id,
                "status": ad_status,
                "clips": []
            }
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/generation-status/{ad_id}")
async def get_generation_status(ad_id: str):
    """Get status of video generation"""
    import traceback
    db = get_db_session()
    try:
        ad_gen = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
        
        if not ad_gen:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        clips = db.query(Clip).filter(Clip.ad_id == ad_id).order_by(Clip.sequence_index).all()
        
        # Safely convert clips to dict
        clips_data = []
        for clip in clips:
            try:
                clips_data.append(clip.to_dict())
            except Exception as e:
                print(f"Error converting clip {clip.id} to dict: {e}")
                clips_data.append({
                    "id": clip.id,
                    "sequence_index": clip.sequence_index,
                    "status": clip.status or "unknown"
                })
        
        # Debug logging
        print(f"DEBUG: Status endpoint - ad_id: {ad_id}, status: {ad_gen.status}, clips_count: {len(clips_data)}")
        for i, clip in enumerate(clips_data[:3]):  # Log first 3 clips
            print(f"DEBUG:   Clip {i+1}: id={clip.get('id', 'N/A')[:8]}, status={clip.get('status', 'N/A')}")
        
        return {
            "id": ad_gen.id,
            "status": ad_gen.status,
            "clips": clips_data,
            "final_video_url": ad_gen.final_video_url
        }
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(f"Error in get_generation_status: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/files/{filename}")
async def get_file(filename: str):
    """Serve uploaded files"""
    file_path = os.path.join("uploads", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/videos/{filename}")
async def get_video(filename: str):
    """Serve generated videos"""
    file_path = os.path.join("output", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

