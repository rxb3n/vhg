import os
import uuid
import asyncio
import requests
import shutil
import base64
import subprocess
from typing import Dict, Any, List
from database import get_db, get_db_session
from models import AdGeneration, Clip
import json
from PIL import Image
import io

class VideoGenerator:
    def __init__(self):
        self.wan_api_key = os.getenv("WAN_API_KEY")
        # Alibaba Model Studio Wan 2.6 API endpoint
        # Default endpoint - user should set WAN_API_URL in .env if different
        self.wan_api_url = os.getenv("WAN_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation")
        self.clips_dir = "clips"
        os.makedirs(self.clips_dir, exist_ok=True)
    
    async def generate_all_clips(self, ad_id: str, script: Dict[str, Any], image_url: str):
        """Generate all 12 clips for an ad"""
        db = get_db_session()
        
        try:
            # Update status to generating
            ad_gen = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
            if not ad_gen:
                print(f"ERROR: Ad generation {ad_id} not found")
                return
            
            ad_gen.status = "generating"
            db.commit()
            
            # Ensure script is a dict (handle Pydantic models)
            if hasattr(script, 'dict'):
                script = script.dict()
            elif hasattr(script, '__dict__'):
                script = script.__dict__
            
            # Get master description and shared context
            master_description = script.get("master_description", "")
            product_name = script.get("product_name", "product")
            
            # FORCE UGC TONE (ignoring script input)
            shared_context = self._build_shared_context(product_name, master_description)
            
            # Load original product image - handle both full URLs and relative paths
            # Normalize the image URL to extract the filename
            
            # Remove protocol and domain if present
            normalized_url = image_url
            if '://' in normalized_url:
                # Extract path from full URL (e.g., http://localhost:8000/api/files/image.jpg -> /api/files/image.jpg)
                normalized_url = '/' + '/'.join(normalized_url.split('/')[3:])
            
            # Extract filename from path (e.g., /api/files/image.jpg -> image.jpg)
            if normalized_url.startswith('/api/files/'):
                filename = normalized_url.replace('/api/files/', '')
            else:
                # Fallback: extract filename from end of path
                filename = normalized_url.split('/')[-1]
            
            image_path = os.path.join("uploads", filename)
            
            # Verify file exists
            if not os.path.exists(image_path):
                # List available files for debugging
                upload_dir = "uploads"
                available_files = os.listdir(upload_dir) if os.path.exists(upload_dir) else []
                raise Exception(
                    f"Product image not found: {image_path}\n"
                    f"Extracted from URL: {image_url}\n"
                    f"Normalized URL: {normalized_url}\n"
                    f"Filename: {filename}\n"
                    f"Available files in uploads/: {available_files[:5]}"
                )
            
            print(f"Using product image: {image_path} (from URL: {image_url})")
            
            # Update status to "generating"
            ad_gen.status = "generating"
            db.commit()
            
            # Create clip records
            scenes = script.get("scenes", [])
            if not scenes:
                raise Exception("Script has no scenes")
            
            # --- FULL PRODUCTION MODE: Process ALL scenes ---
            clips = []
            for scene in scenes:
                # Handle both dict and Pydantic model scenes
                if not isinstance(scene, dict):
                    scene = scene.dict() if hasattr(scene, 'dict') else scene
                
                clip = Clip(
                    id=str(uuid.uuid4()),
                    ad_id=ad_id,
                    sequence_index=scene.get("id", len(clips) + 1),
                    role=scene.get("role", ""),
                    prompt=scene.get("prompt", ""),
                    status="pending"
                )
                db.add(clip)
                clips.append(clip)
            
            db.commit()
            print(f"DEBUG: Created {len(clips)} clip record(s) in database")
            
            # Generate clips in parallel (limit concurrency to avoid rate limits)
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent generations
            
            # Ensure all scenes are dicts
            scenes_dicts = []
            for scene in scenes:
                if not isinstance(scene, dict):
                    scene = scene.dict() if hasattr(scene, 'dict') else scene
                scenes_dicts.append(scene)
            
            print(f"Starting generation for all {len(clips)} clips...")
            tasks = [
                self._generate_clip_with_semaphore(semaphore, clip, image_path, shared_context, scene)
                for clip, scene in zip(clips, scenes_dicts)
            ]
            
            await asyncio.gather(*tasks)
            
            # Check if all clips completed
            db.refresh(ad_gen)
            completed_clips = db.query(Clip).filter(
                Clip.ad_id == ad_id,
                Clip.status == "completed"
            ).count()
            
            if completed_clips == len(scenes):
                print(f"DEBUG: All {completed_clips} clips completed. Starting assembly.")
                
                # Update status to "assembling"
                ad_gen.status = "assembling"
                db.commit()
                
                # Start assembly
                from services.video_assembler import VideoAssembler
                assembler = VideoAssembler()
                await assembler.assemble_video(ad_id)
                
            else:
                print(f"ERROR: Only {completed_clips}/{len(scenes)} clips completed. Marking as failed.")
                # If we have some clips, we might want to let the user see them, 
                # but technically the full generation failed.
                ad_gen.status = "failed"
                db.commit()
                
        except Exception as e:
            error_msg = f"Error generating clips: {e}"
            print(error_msg)
            import traceback
            print(traceback.format_exc())
            ad_gen = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
            if ad_gen:
                ad_gen.status = "failed"
                db.commit()
    
    async def _generate_clip_with_semaphore(self, semaphore, clip, image_path, shared_context, scene):
        """Generate a single clip with semaphore control"""
        async with semaphore:
            await self._generate_clip(clip, image_path, shared_context, scene)
    
    async def _generate_clip(self, clip: Clip, image_path: str, shared_context: str, scene: Dict[str, Any]):
        """Generate a single 5-second clip"""
        db = get_db_session()
        clip_id = clip.id  # Store ID before refreshing from database
        
        try:
            # Refresh clip from database
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip:
                raise Exception(f"Clip {clip_id} not found")
            
            print(f"DEBUG: Starting generation for clip {clip_id} (sequence {clip.sequence_index})")
            clip.status = "generating"
            db.commit()
            
            # Ensure scene is a dict
            if not isinstance(scene, dict):
                scene = scene.dict() if hasattr(scene, 'dict') else scene
            
            # Build full prompt with shared context
            # We append the specific scene prompt to the shared context
            full_prompt = f"{shared_context}\n\nShot {clip.sequence_index} of 12: {scene.get('prompt', '')}"
            
            # Call Wan 2.6 API
            # This returns the LOCAL path (clips/filename.mp4)
            clip_path = await self._call_wan_api(
                prompt=full_prompt,
                image_path=image_path,
                clip_id=clip.id
            )
            
            # Ensure we store the relative path with forward slashes for the frontend
            # The _call_wan_api returns the full relative path e.g., "clips/abcd.mp4"
            filename = os.path.basename(clip_path)
            web_friendly_path = f"clips/{filename}"
            
            # Update clip record
            print(f"DEBUG: Clip {clip_id} generation successful. Path: {web_friendly_path}")
            clip.local_path = web_friendly_path
            clip.status = "completed"
            clip.duration = 5.0
            db.commit()
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error generating clip {clip_id}: {e}")
            try:
                # Refresh clip again in case session expired
                clip = db.query(Clip).filter(Clip.id == clip_id).first()
                if clip:
                    # If placeholder was created (in dev mode without key), mark as completed
                    if 'placeholder' in error_msg.lower() or 'WARNING' in error_msg:
                        if clip.local_path and os.path.exists(clip.local_path):
                            clip.status = "completed"
                            clip.duration = 5.0
                            print(f"Clip {clip_id} completed with placeholder video")
                        else:
                            clip.status = "failed"
                    else:
                        clip.status = "failed"
                
                db.commit()
            except Exception as db_error:
                print(f"Error updating clip status: {db_error}")
            
            if 'placeholder' not in error_msg.lower() and 'WARNING' not in error_msg:
                raise
        finally:
            db.close()
    
    async def _call_wan_api(self, prompt: str, image_path: str, clip_id: str) -> str:
        """Call Wan 2.6 API for image-to-video generation"""
        print(f"DEBUG: _call_wan_api called for clip {clip_id}")
        
        # If no API key, create a placeholder video file
        if not self.wan_api_key:
            print("WARNING: WAN_API_KEY not set. Creating placeholder video.")
            return self._create_placeholder_video(clip_id)
        
        try:
            # Read and encode image to base64 for API transmission
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine correct headers based on API docs
            headers = {
                "Authorization": f"Bearer {self.wan_api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable"  # Required for async tasks
            }
            
            # Payload for Wan 2.6 Image-to-Video
            payload = {
                "model": "wan2.1-i2v-plus", # Using the stable endpoint model
                "input": {
                    "prompt": prompt,
                    "image": f"data:image/jpeg;base64,{image_base64}"
                },
                "parameters": {
                    "size": "720*1280", # 9:16 vertical
                    "duration": 5,
                    "n": 1
                }
            }
            
            # Submit Task
            print(f"DEBUG: Submitting task for clip {clip_id} to {self.wan_api_url}")
            response = requests.post(self.wan_api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"ERROR: API Submission failed: {response.status_code} - {response.text}")
                raise Exception(f"API Submission failed: {response.text}")
                
            task_data = response.json()
            # Check for output.task_id (standard DashScope response)
            if 'output' in task_data and 'task_id' in task_data['output']:
                task_id = task_data['output']['task_id']
            # Sometimes it might be at root depending on specific endpoint version
            elif 'task_id' in task_data:
                task_id = task_data['task_id']
            else:
                raise Exception(f"No task_id in response: {task_data}")
                
            print(f"DEBUG: Task submitted successfully. Task ID: {task_id}")
            
            # Poll for completion and download
            clip_path = await self._poll_wan_task(task_id, clip_id)
            
            if not clip_path:
                raise Exception("Polling failed or timed out")
                
            return clip_path

        except Exception as e:
            print(f"Exception in _call_wan_api: {e}")
            # Fallback for dev/demo if API fails
            # return self._create_placeholder_video(clip_id) 
            raise e

    async def _poll_wan_task(self, task_id, clip_id):
        """
        Polls the Wan API for task status and downloads result on success.
        """
        print(f"DEBUG: _poll_wan_task started for task {task_id}, clip {clip_id}")
        
        # Determine base host for polling (remove specific path)
        # DashScope standard polling is GET /api/v1/tasks/{task_id}
        if "dashscope-intl" in self.wan_api_url:
            base_host = "https://dashscope-intl.aliyuncs.com"
        else:
            base_host = "https://dashscope.aliyuncs.com"
            
        query_url = f"{base_host}/api/v1/tasks/{task_id}"

        headers = {
            "Authorization": f"Bearer {self.wan_api_key}",
            "Content-Type": "application/json"
        }

        print("DEBUG: Will poll up to 120 times (5 seconds between attempts)")
        for i in range(120):
            try:
                # Poll status using GET
                response = requests.get(query_url, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    print(f"ERROR: Poll failed with status {response.status_code}")
                    if response.status_code >= 500:
                        await asyncio.sleep(5)
                        continue
                    return None

                data = response.json()
                output = data.get("output", {})
                task_status = output.get("task_status")

                if task_status == "SUCCEEDED":
                    video_url = output.get("video_url")
                    print(f"DEBUG: Task {task_id} SUCCEEDED. Remote URL: {video_url}")
                    
                    if video_url:
                        # --- DOWNLOAD LOGIC ---
                        try:
                            print(f"Downloading video for clip {clip_id}...")
                            video_resp = requests.get(video_url, timeout=300)
                            
                            if video_resp.status_code == 200:
                                filename = f"{clip_id}.mp4"
                                clip_path = os.path.join(self.clips_dir, filename)
                                
                                with open(clip_path, 'wb') as f:
                                    f.write(video_resp.content)
                                
                                print(f"Video saved locally to: {clip_path}")
                                return clip_path  # Return local file system path
                            else:
                                print(f"ERROR: Failed to download video: {video_resp.status_code}")
                                return None
                        except Exception as dl_err:
                            print(f"ERROR: Exception downloading video: {dl_err}")
                            return None
                    else:
                        print("ERROR: Task succeeded but no video_url found")
                        return None
                
                elif task_status == "FAILED":
                    print(f"ERROR: Task {task_id} FAILED")
                    print(f"ERROR: Details: {data}")
                    return None
                
                # If PENDING or RUNNING, just continue loop
                
            except Exception as e:
                print(f"ERROR: Exception during polling: {e}")

            # Wait before next poll
            await asyncio.sleep(5)

        print(f"ERROR: Polling timed out for task {task_id}")
        return None
    
    def _create_placeholder_video(self, clip_id: str) -> str:
        """Create a placeholder video using FFmpeg if API is unavailable"""
        filename = f"{clip_id}.mp4"
        clip_path = os.path.join(self.clips_dir, filename)
        
        if os.path.exists(clip_path):
            return clip_path
            
        print(f"Creating placeholder video for {clip_id}...")
        
        # Check if ffmpeg is available
        if shutil.which('ffmpeg') is None:
            print("ERROR: ffmpeg not found. Cannot create placeholder video.")
            # Create a dummy empty file just to avoid crashes, though it won't play
            with open(clip_path, 'wb') as f:
                f.write(b'placeholder')
            return clip_path

        # Create a 5-second black video with text
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'color=c=black:s=405x720:d=5', # 9:16 aspect ratio approximation
            '-vf', f'drawtext=text=Clip\\ {clip_id[:8]}:fontcolor=white:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-y',
            clip_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return clip_path
        except Exception as e:
            print(f"Error creating placeholder with ffmpeg: {e}")
            return clip_path
    
    def _build_shared_context(self, product_name: str, master_description: str) -> str:
        """Build shared context paragraph for all prompts"""
        # FORCED UGC TONE
        tone_style = "authentic user-generated content style, casual and relatable"
        
        return f"""You are generating a 12-shot viral video ad for {product_name}. 
Master visual description: {master_description}
Style: {tone_style}.
Visual Language: Handheld phone camera aesthetic, natural lighting, real-life texture. 
Avoid: Oversaturated colors, fake 3D renders, studio lighting, corporate feel.
Subject: A consistent creator/user interacting with the product in a real environment.
"""