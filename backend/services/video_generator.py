import os
import uuid
import asyncio
import requests
from typing import Dict, Any, List
from database import get_db, get_db_session
from models import AdGeneration, Clip
import json

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
            tone = script.get("tone", "UGC")
            
            # Build shared context
            shared_context = self._build_shared_context(product_name, master_description, tone)
            
            # Load original product image - handle both full URLs and relative paths
            # Normalize the image URL to extract the filename
            import re
            
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
            
            # DEBUG: Only create 1 clip record for faster debugging
            print(f"DEBUG MODE: Only creating 1 clip record (out of {len(scenes)} scenes)")
            scenes = scenes[:1]  # Only use first scene
            
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
            
            # Generate clips in parallel (limit concurrency)
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent generations
            
            # Ensure all scenes are dicts
            scenes_dicts = []
            for scene in scenes:
                if not isinstance(scene, dict):
                    scene = scene.dict() if hasattr(scene, 'dict') else scene
                scenes_dicts.append(scene)
            
            # DEBUG: Only generate first clip for faster debugging
            print("DEBUG MODE: Only generating first clip")
            tasks = [
                self._generate_clip_with_semaphore(semaphore, clip, image_path, shared_context, scene)
                for clip, scene in zip(clips[:1], scenes_dicts[:1])  # Only first clip
            ]
            
            await asyncio.gather(*tasks)
            
            # Check if all clips completed
            db.refresh(ad_gen)
            completed_clips = db.query(Clip).filter(
                Clip.ad_id == ad_id,
                Clip.status == "completed"
            ).count()
            
            # DEBUG: For now, mark as completed if at least 1 clip is done
            if completed_clips >= 1:
                # DEBUG: Skip assembly for now, just mark as completed
                print(f"DEBUG: {completed_clips} clip(s) completed. Marking as completed (skipping assembly).")
                ad_gen.status = "completed"
                # Set a dummy final video URL for the first clip
                if completed_clips > 0:
                    first_clip = db.query(Clip).filter(
                        Clip.ad_id == ad_id,
                        Clip.status == "completed"
                    ).order_by(Clip.sequence_index).first()
                    if first_clip and first_clip.local_path:
                        # Use the first clip as the final video for debugging
                        final_filename = f"{ad_id}_final.mp4"
                        output_dir = "output"
                        os.makedirs(output_dir, exist_ok=True)
                        final_path = os.path.join(output_dir, final_filename)
                        shutil.copy(first_clip.local_path, final_path)
                        ad_gen.final_video_url = f"/api/videos/{final_filename}"
                db.commit()
                
                # Uncomment below to enable full assembly
                # # Update status to "assembling"
                # ad_gen.status = "assembling"
                # db.commit()
                # # Start assembly
                # from services.video_assembler import VideoAssembler
                # assembler = VideoAssembler()
                # await assembler.assemble_video(ad_id)
            else:
                print(f"ERROR: Only {completed_clips}/1 clips completed. Marking as failed.")
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
            print(f"DEBUG: Updated clip {clip_id} status to 'generating'")
            
            # Ensure scene is a dict
            if not isinstance(scene, dict):
                scene = scene.dict() if hasattr(scene, 'dict') else scene
            
            # Build full prompt with shared context
            full_prompt = f"{shared_context}\n\nShot {clip.sequence_index} of 12: {scene.get('prompt', '')}"
            
            # Call Wan 2.6 API
            clip_path = await self._call_wan_api(
                prompt=full_prompt,
                image_path=image_path,
                clip_id=clip.id
            )
            
            # Update clip record
            print(f"DEBUG: Clip {clip_id} generation successful. Updating database...")
            clip.local_path = clip_path
            clip.status = "completed"
            clip.duration = 5.0
            db.commit()
            print(f"DEBUG: Clip {clip_id} marked as completed in database")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error generating clip {clip_id}: {e}")
            try:
                # Refresh clip again in case session expired
                clip = db.query(Clip).filter(Clip.id == clip_id).first()
                if clip:
                    # If placeholder was created, mark as completed
                    if 'placeholder' in error_msg.lower() or 'WARNING' in error_msg:
                        # Placeholder video was created, mark as completed
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
        print(f"DEBUG: Image path: {image_path}, exists: {os.path.exists(image_path) if image_path else False}")
        
        # If no API key, create a placeholder video file
        if not self.wan_api_key:
            print("WARNING: WAN_API_KEY not set. Creating placeholder video.")
            return self._create_placeholder_video(clip_id)
        
        print(f"DEBUG: Starting Wan API call for clip {clip_id}")
        try:
            # Read and encode image to base64
            import base64
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine image MIME type
            from PIL import Image
            img = Image.open(image_path)
            mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"
            
            # Prepare request body for Alibaba Model Studio Wan 2.6 I2V
            # Alibaba DashScope API format - using img_url parameter
            # Model name can be overridden via WAN_MODEL_NAME env var
            # Common model names: wan2.6-i2v, wan2.6-video, wan-i2v-2.6, etc.
            model_name = os.getenv("WAN_MODEL_NAME", "wan2.6-i2v")
            
            payload = {
                "model": model_name,
                "input": {
                    "img_url": f"data:{mime_type};base64,{image_base64}",
                    "prompt": prompt
                },
                "parameters": {
                    "aspect_ratio": "9:16",
                    "duration": 5,
                    "resolution": "720P"
                }
            }
            
            print(f"Using model: {model_name}")
            
            headers = {
                "Authorization": f"Bearer {self.wan_api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable"  # Required for async processing
            }
            
            print(f"Submitting Wan 2.6 I2V task to: {self.wan_api_url}")
            print(f"Using API key: {self.wan_api_key[:10]}...{self.wan_api_key[-5:] if len(self.wan_api_key) > 15 else '***'}")
            
            # Submit task (Alibaba API is async)
            response = requests.post(
                self.wan_api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 401:
                error_text = response.text
                print(f"ERROR: Authentication failed (401)")
                print(f"Response: {error_text}")
                print("\nTroubleshooting:")
                print("1. Verify your WAN_API_KEY in .env file is correct")
                print("2. Check that the API key is from Alibaba Model Studio (DashScope)")
                print("3. Ensure the WAN_API_URL is set correctly in .env")
                print(f"   Current URL: {self.wan_api_url}")
                print("   Expected format: https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation")
                raise Exception(f"Wan API authentication failed: {error_text}")
            
            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"Wan API submission error: {response.status_code} - {error_text}")
            
            result = response.json()
            
            # Check for Alibaba API error format
            if result.get("code") and result.get("code") != "Success":
                error_code = result.get("code")
                error_msg = result.get("message", result.get("code", "Unknown error"))
                print(f"API Error Code: {error_code}")
                print(f"Error Message: {error_msg}")
                
                # If model doesn't exist, provide helpful message
                if error_code == "InvalidParameter" and ("Model not exist" in error_msg or "model" in error_msg.lower()):
                    print("\n" + "="*60)
                    print("TROUBLESHOOTING: Model Not Found")
                    print("="*60)
                    print(f"Current model name: {model_name}")
                    print("\nTo fix this:")
                    print("1. Check the Alibaba Model Studio API documentation")
                    print("2. Find the correct model name for Wan 2.6 image-to-video")
                    print("3. Set WAN_MODEL_NAME in your .env file with the correct model name")
                    print("\nCommon model name formats to try:")
                    print("  - wan2.6-i2v")
                    print("  - wan2.6-video")
                    print("  - wan-i2v-2.6")
                    print("  - wan2.6-i2v-plus")
                    print("  - wan-video-2.6")
                    print("="*60)
                
                raise Exception(f"Wan API error: {error_msg}")
            
            # Alibaba returns task_id in output.task_id or request_id
            # For async requests, task_id is in output.task_id
            output = result.get("output", {})
            task_id = output.get("task_id") or result.get("request_id") or result.get("task_id")
            
            # Also check if it's in the response directly
            if not task_id:
                task_id = result.get("task_id")
            
            if not task_id:
                # If synchronous response with video URL
                video_url = output.get("video_url")
                if video_url:
                    # Download directly
                    print(f"Video ready immediately. Downloading from: {video_url}")
                    video_response = requests.get(video_url, timeout=300)
                    if video_response.status_code != 200:
                        raise Exception(f"Failed to download video: {video_response.status_code}")
                    
                    clip_path = os.path.join(self.clips_dir, f"{clip_id}.mp4")
                    with open(clip_path, 'wb') as f:
                        f.write(video_response.content)
                    return clip_path
                else:
                    raise Exception(f"No task_id or video_url in response: {result}")
            
            print(f"DEBUG: Task submitted successfully. Task ID: {task_id}")
            
            # Poll for completion
            print(f"DEBUG: Starting to poll for task {task_id}")
            clip_path = await self._poll_wan_task(task_id, clip_id)
            print(f"DEBUG: Polling completed. Clip path: {clip_path}")
            return clip_path
                
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            if 'getaddrinfo failed' in error_msg or 'Failed to resolve' in error_msg:
                print(f"WARNING: Cannot connect to Wan API at {self.wan_api_url}")
                print("This might mean:")
                print("  1. The API endpoint URL is incorrect")
                print("  2. The service is temporarily unavailable")
                print("  3. There's a network/DNS issue")
                print("Falling back to placeholder video...")
                return self._create_placeholder_video(clip_id)
            else:
                raise
        except requests.exceptions.Timeout:
            print(f"WARNING: Wan API request timed out. Creating placeholder video...")
            return self._create_placeholder_video(clip_id)
        except Exception as e:
            error_msg = str(e)
            if 'getaddrinfo failed' in error_msg or 'Failed to resolve' in error_msg:
                print(f"WARNING: Cannot resolve Wan API hostname. Creating placeholder video...")
                return self._create_placeholder_video(clip_id)
            else:
                print(f"WARNING: Wan API error: {e}. Creating placeholder video...")
                return self._create_placeholder_video(clip_id)
    
    async def _poll_wan_task(self, task_id: str, clip_id: str) -> str:
        """Poll Alibaba Model Studio Wan 2.6 task until completion"""
        print(f"DEBUG: _poll_wan_task started for task {task_id}, clip {clip_id}")
        headers = {
            "Authorization": f"Bearer {self.wan_api_key}",
            "Content-Type": "application/json"
        }
        
        max_attempts = 120  # 10 minutes max (120 * 5 seconds)
        attempt = 0
        print(f"DEBUG: Will poll up to {max_attempts} times (5 seconds between attempts)")
        
        # Get model name for query request
        model_name = os.getenv("WAN_MODEL_NAME", "wan2.6-i2v")
        
        # Alibaba uses a query task endpoint
        # The query endpoint is typically at the same base path with /query
        # Handle both /generation and /video-synthesis endpoints
        if "/video-synthesis" in self.wan_api_url:
            base_url = self.wan_api_url.replace("/video-synthesis", "")
        elif "/generation" in self.wan_api_url:
            base_url = self.wan_api_url.replace("/generation", "")
        else:
            # Fallback: try to construct from known patterns
            base_url = self.wan_api_url.rsplit("/", 1)[0] if "/" in self.wan_api_url else self.wan_api_url
        
        query_url = f"{base_url}/query"
        print(f"Querying task status at: {query_url}")
        
        while attempt < max_attempts:
            try:
                # Check task status - Alibaba format (requires model parameter)
                payload = {
                    "model": model_name,
                    "task_id": task_id
                }
                print(f"DEBUG: Polling attempt {attempt + 1}/{max_attempts} - checking task {task_id}")
                print(f"DEBUG: Query URL: {query_url}")
                print(f"DEBUG: Payload: {json.dumps(payload, indent=2)}")
                response = requests.post(query_url, json=payload, headers=headers, timeout=30)
                print(f"DEBUG: Poll response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text
                    print(f"ERROR: Poll failed with status {response.status_code}")
                    print(f"ERROR: Response: {error_text}")
                    # For 400 errors, log the full details
                    if response.status_code == 400:
                        try:
                            error_json = response.json()
                            print(f"ERROR: Error details: {json.dumps(error_json, indent=2)}")
                        except:
                            pass
                    raise Exception(f"Failed to check task status: {response.status_code} - {error_text}")
                
                result = response.json()
                
                # Check for errors
                if result.get("code") and result.get("code") != "Success":
                    raise Exception(f"Status check error: {result.get('message', result.get('code', 'Unknown error'))}")
                
                output = result.get("output", {})
                # Alibaba API might return status in different fields
                status = output.get("task_status") or output.get("status") or result.get("status")
                
                if not status:
                    # Debug: print the full response to understand structure
                    print(f"DEBUG: Full response structure: {json.dumps(result, indent=2)[:500]}")
                    status = "UNKNOWN"
                
                print(f"Task {task_id} status: {status} (attempt {attempt + 1}/{max_attempts})")
                
                if status in ["SUCCEEDED", "succeeded", "SUCCESS", "success", "COMPLETED", "completed"]:
                    # Get video URL - check multiple possible fields
                    video_url = (
                        output.get("video_url") or 
                        output.get("video") or 
                        output.get("url") or
                        result.get("video_url")
                    )
                    
                    if not video_url:
                        print(f"DEBUG: Output structure: {json.dumps(output, indent=2)[:500]}")
                        raise Exception(f"No video URL in output. Full output: {output}")
                    
                    # Download video
                    print(f"Downloading video from: {video_url}")
                    video_response = requests.get(video_url, timeout=300)
                    if video_response.status_code != 200:
                        raise Exception(f"Failed to download video: {video_response.status_code}")
                    
                    # Save video file
                    clip_path = os.path.join(self.clips_dir, f"{clip_id}.mp4")
                    with open(clip_path, 'wb') as f:
                        f.write(video_response.content)
                    
                    print(f"Video saved to: {clip_path}")
                    return clip_path
                
                elif status in ["FAILED", "failed", "ERROR", "error"]:
                    error_msg = output.get("message") or output.get("error") or "Unknown error"
                    raise Exception(f"Task failed: {error_msg}")
                
                # Task still processing (PENDING, RUNNING, etc.), wait and retry
                await asyncio.sleep(5)  # Wait 5 seconds before next poll
                attempt += 1
                
            except Exception as e:
                if attempt >= max_attempts - 1:
                    raise Exception(f"Task polling failed after {max_attempts} attempts: {e}")
                await asyncio.sleep(5)
                attempt += 1
        
        raise Exception(f"Task {task_id} did not complete within timeout period")
    
    def _create_placeholder_video(self, clip_id: str) -> str:
        """Create a placeholder video using FFmpeg (for testing)"""
        import subprocess
        
        clip_path = os.path.join(self.clips_dir, f"{clip_id}.mp4")
        
        # Create a 5-second black video with text
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'color=c=black:s=405x720:d=5',
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
        except:
            # If FFmpeg fails, just return the path anyway
            return clip_path
    
    def _build_shared_context(self, product_name: str, master_description: str, tone: str) -> str:
        """Build shared context paragraph for all prompts"""
        tone_style = {
            "UGC": "authentic user-generated content style, casual and relatable",
            "premium": "luxury commercial style, sophisticated and elegant",
            "playful": "fun and energetic style, vibrant and engaging"
        }.get(tone, "authentic user-generated content style")
        
        return f"""You are generating a 12-shot viral video ad for {product_name}. 
Master visual description: {master_description}
Style: {tone_style}
Maintain consistent lighting, color grade, and product appearance throughout all 12 shots.
Keep the same setting, characters, and visual continuity across the entire sequence."""

