import os
import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import shutil
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Logging - FIX: Set level to DEBUG and format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True # Force reconfiguration of logging
)
logger = logging.getLogger(__name__)

# Initialize database
from database import init_db, get_db
from models import AdGeneration, Clip

# Initialize DB on startup
init_db()

app = FastAPI(title="VideoGen API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("clips", exist_ok=True)
os.makedirs("output", exist_ok=True)

# ... (Keep existing Pydantic models) ...
class ScriptRequest(BaseModel):
    product_name: str
    master_description: str
    scenes: List[Dict[str, Any]]
    tone: Optional[str] = "UGC"

# ... (Keep existing routes) ...

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    try:
        file_ext = file.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join("uploads", filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.debug(f"Image uploaded: {file_path}")
        return {"url": f"/api/files/{filename}"}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/{filename}")
async def get_file(filename: str):
    """Serve uploaded files and generated clips"""
    # 1. Check uploads folder
    upload_path = os.path.join("uploads", filename)
    if os.path.exists(upload_path):
        return FileResponse(upload_path)
    
    # 2. Check clips folder (Fix for 404 error)
    clip_path = os.path.join("clips", filename)
    if os.path.exists(clip_path):
        return FileResponse(clip_path)
        
    # 3. Check output folder
    output_path = os.path.join("output", filename)
    if os.path.exists(output_path):
        return FileResponse(output_path)
        
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/api/analyze-image")
async def analyze_image(request: Dict[str, str]):
    image_url = request.get("image_url")
    if not image_url:
        raise HTTPException(status_code=400, detail="Missing image_url")
    
    try:
        # Extract filename from URL
        filename = image_url.split("/")[-1]
        image_path = os.path.join("uploads", filename)
        
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image file not found")
            
        from services.vision_director import VisionDirector
        director = VisionDirector()
        script = await director.analyze_and_script(image_path)
        
        return script
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-video")
async def generate_video(
    background_tasks: BackgroundTasks,
    script: ScriptRequest,
    image_url: str = Form(...)  # Expect image_url as form field or query, usually JSON body is better but adhering to existing pattern if any
):
    # NOTE: If your frontend sends JSON, use this signature instead:
    # async def generate_video(request: VideoGenerationRequest, background_tasks: BackgroundTasks):
    pass

# Corrected route for JSON body
class VideoGenRequest(BaseModel):
    script: Dict[str, Any]
    image_url: str

@app.post("/api/generate-video-json")
async def generate_video_json(
    request: VideoGenRequest,
    background_tasks: BackgroundTasks
):
    try:
        ad_id = str(uuid.uuid4())
        logger.info(f"Starting video generation for Ad {ad_id}")
        
        # Create initial DB record
        from database import get_db_session
        db = get_db_session()
        ad = AdGeneration(id=ad_id, status="processing")
        db.add(ad)
        db.commit()
        db.close()
        
        # Start background task
        from services.video_generator import VideoGenerator
        generator = VideoGenerator()
        
        background_tasks.add_task(
            generator.generate_all_clips, 
            ad_id, 
            request.script, 
            request.image_url
        )
        
        return {"ad_id": ad_id, "status": "processing"}
    except Exception as e:
        logger.error(f"Generation start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ad-status/{ad_id}")
async def get_ad_status(ad_id: str):
    from database import get_db_session
    db = get_db_session()
    try:
        ad = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")
            
        # Get clips
        clips = db.query(Clip).filter(Clip.ad_id == ad_id).all()
        
        return {
            "id": ad.id,
            "status": ad.status,
            "final_video_url": ad.final_video_url,
            "clips": [
                {
                    "id": c.id,
                    "sequence_index": c.sequence_index,
                    "status": c.status,
                    "local_path": c.local_path
                }
                for c in clips
            ]
        }
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)