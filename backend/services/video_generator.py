import os
import uuid
import asyncio
import requests
import shutil
import base64
import subprocess
import logging
from typing import Dict, Any, List
from database import get_db, get_db_session
from models import AdGeneration, Clip
import json
from PIL import Image
import io

# Configure logger for this module
logger = logging.getLogger(__name__)

class VideoGenerator:
    def __init__(self):
        self.wan_api_key = os.getenv("WAN_API_KEY")
        # Alibaba Model Studio Wan 2.6 API endpoint
        self.wan_api_url = os.getenv("WAN_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation")
        self.clips_dir = "clips"
        os.makedirs(self.clips_dir, exist_ok=True)
    
    async def generate_all_clips(self, ad_id: str, script: Dict[str, Any], image_url: str):
        """Generate all 12 clips for an ad"""
        db = get_db_session()
        logger.info(f"Starting generate_all_clips for Ad {ad_id}")
        print(f"DEBUG: Starting generate_all_clips for Ad {ad_id}", flush=True)
        
        try:
            # Update status to generating
            ad_gen = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
            if not ad_gen:
                logger.error(f"Ad generation {ad_id} not found")
                return
            
            ad_gen.status = "generating"
            db.commit()
            
            # Ensure script is a dict
            if hasattr(script, 'dict'):
                script = script.dict()
            elif hasattr(script, '__dict__'):
                script = script.__dict__
            
            # Get master description and shared context
            master_description = script.get("master_description", "")
            product_name = script.get("product_name", "product")
            
            # FORCE UGC TONE
            shared_context = self._build_shared_context(product_name, master_description)
            
            # Normalize image path
            normalized_url = image_url
            if '://' in normalized_url:
                normalized_url = '/' + '/'.join(normalized_url.split('/')[3:])
            
            if normalized_url.startswith('/api/files/'):
                filename = normalized_url.replace('/api/files/', '')
            else:
                filename = normalized_url.split('/')[-1]
            
            image_path = os.path.join("uploads", filename)
            
            if not os.path.exists(image_path):
                logger.error(f"Image not found at {image_path}")
                raise Exception(f"Product image not found: {image_path}")
            
            logger.info(f"Using product image: {image_path}")
            
            # Create clip records
            scenes = script.get("scenes", [])
            if not scenes:
                raise Exception("Script has no scenes")
            
            logger.info(f"Processing {len(scenes)} scenes from script")

            # --- FULL PRODUCTION MODE: Process ALL scenes ---
            clips = []
            for scene in scenes:
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
            logger.info(f"Created {len(clips)} clip records in database")
            
            # Generate clips in parallel (limit concurrency)
            semaphore = asyncio.Semaphore(2)
            
            scenes_dicts = []
            for scene in scenes:
                if not isinstance(scene, dict):
                    scene = scene.dict() if hasattr(scene, 'dict') else scene
                scenes_dicts.append(scene)
            
            logger.info(f"Starting generation for all {len(clips)} clips...")
            tasks = [
                self._generate_clip_with_semaphore(semaphore, clip, image_path, shared_context, scene)
                for clip, scene in zip(clips, scenes_dicts)
            ]
            
            await asyncio.gather(*tasks)
            
            # Check completion
            db.refresh(ad_gen)
            completed_clips = db.query(Clip).filter(
                Clip.ad_id == ad_id,
                Clip.status == "completed"
            ).count()
            
            logger.info(f"Generation finished. Completed: {completed_clips}/{len(scenes)}")
            
            if completed_clips == len(scenes):
                logger.info(f"All {completed_clips} clips completed. Starting assembly.")
                
                ad_gen.status = "assembling"
                db.commit()
                
                from services.video_assembler import VideoAssembler
                assembler = VideoAssembler()
                await assembler.assemble_video(ad_id)
                
            else:
                logger.error(f"Only {completed_clips}/{len(scenes)} clips completed. Marking as failed.")
                ad_gen.status = "failed"
                db.commit()
                
        except Exception as e:
            logger.error(f"Error generating clips: {e}", exc_info=True)
            ad_gen = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
            if ad_gen:
                ad_gen.status = "failed"
                db.commit()
    
    async def _generate_clip_with_semaphore(self, semaphore, clip, image_path, shared_context, scene):
        async with semaphore:
            await self._generate_clip(clip, image_path, shared_context, scene)
    
    async def _generate_clip(self, clip: Clip, image_path: str, shared_context: str, scene: Dict[str, Any]):
        db = get_db_session()
        clip_id = clip.id
        
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip: raise Exception(f"Clip {clip_id} not found")
            
            logger.debug(f"Starting generation for clip {clip_id} (seq {clip.sequence_index})")
            clip.status = "generating"
            db.commit()
            
            if not isinstance(scene, dict):
                scene = scene.dict() if hasattr(scene, 'dict') else scene
            
            full_prompt = f"{shared_context}\n\nShot {clip.sequence_index} of 12: {scene.get('prompt', '')}"
            
            clip_path = await self._call_wan_api(prompt=full_prompt, image_path=image_path, clip_id=clip.id)
            
            if clip_path:
                filename = os.path.basename(clip_path)
                web_friendly_path = f"clips/{filename}"
                
                logger.info(f"Clip {clip_id} generation successful. Path: {web_friendly_path}")
                clip.local_path = web_friendly_path
                clip.status = "completed"
                clip.duration = 5.0
            else:
                 logger.error(f"Clip {clip_id} returned None path")
                 clip.status = "failed"
                 
            db.commit()
            
        except Exception as e:
            logger.error(f"Error generating clip {clip_id}: {e}")
            try:
                clip = db.query(Clip).filter(Clip.id == clip_id).first()
                if clip: clip.status = "failed"
                db.commit()
            except: pass
        finally:
            db.close()
    
    async def _call_wan_api(self, prompt: str, image_path: str, clip_id: str) -> str:
        logger.debug(f"_call_wan_api called for clip {clip_id}")
        
        if not self.wan_api_key:
            logger.warning("WAN_API_KEY not set. Creating placeholder video.")
            return self._create_placeholder_video(clip_id)
        
        try:
            with open(image_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            headers = {
                "Authorization": f"Bearer {self.wan_api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable"
            }
            
            payload = {
                "model": "wan2.1-i2v-plus",
                "input": {"prompt": prompt, "image": f"data:image/jpeg;base64,{image_base64}"},
                "parameters": {"size": "720*1280", "duration": 5, "n": 1}
            }
            
            logger.debug(f"Submitting task for clip {clip_id}...")
            response = requests.post(self.wan_api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"API Submission failed: {response.text}")
                raise Exception(f"API Submission failed: {response.text}")
                
            task_data = response.json()
            if 'output' in task_data and 'task_id' in task_data['output']:
                task_id = task_data['output']['task_id']
            elif 'task_id' in task_data:
                task_id = task_data['task_id']
            else:
                raise Exception(f"No task_id in response: {task_data}")
                
            logger.info(f"Task submitted. Task ID: {task_id}")
            
            return await self._poll_wan_task(task_id, clip_id)

        except Exception as e:
            logger.exception(f"Exception in _call_wan_api: {e}")
            raise e

    async def _poll_wan_task(self, task_id, clip_id):
        logger.debug(f"_poll_wan_task started for task {task_id}")
        
        if "dashscope-intl" in self.wan_api_url:
            base_host = "https://dashscope-intl.aliyuncs.com"
        else:
            base_host = "https://dashscope.aliyuncs.com"
            
        query_url = f"{base_host}/api/v1/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {self.wan_api_key}", "Content-Type": "application/json"}

        for i in range(120):
            try:
                response = requests.get(query_url, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    logger.error(f"Poll failed: {response.status_code}")
                    if response.status_code >= 500:
                        await asyncio.sleep(5)
                        continue
                    return None

                data = response.json()
                task_status = data.get("output", {}).get("task_status")

                if task_status == "SUCCEEDED":
                    video_url = data.get("output", {}).get("video_url")
                    logger.info(f"Task {task_id} SUCCEEDED. Video URL: {video_url}")
                    
                    if video_url:
                        try:
                            video_resp = requests.get(video_url, timeout=300)
                            if video_resp.status_code == 200:
                                filename = f"{clip_id}.mp4"
                                clip_path = os.path.join(self.clips_dir, filename)
                                with open(clip_path, 'wb') as f:
                                    f.write(video_resp.content)
                                logger.info(f"Video saved to: {clip_path}")
                                return clip_path
                            else:
                                logger.error(f"Download failed: {video_resp.status_code}")
                                return None
                        except Exception as dl_err:
                            logger.error(f"Download exception: {dl_err}")
                            return None
                    return None
                
                elif task_status == "FAILED":
                    logger.error(f"Task {task_id} FAILED: {data}")
                    return None
                
            except Exception as e:
                logger.error(f"Polling exception: {e}")

            await asyncio.sleep(5)

        logger.error(f"Polling timed out for task {task_id}")
        return None
    
    def _create_placeholder_video(self, clip_id: str) -> str:
        filename = f"{clip_id}.mp4"
        clip_path = os.path.join(self.clips_dir, filename)
        if os.path.exists(clip_path): return clip_path
            
        logger.info(f"Creating placeholder video for {clip_id}...")
        if shutil.which('ffmpeg') is None:
            with open(clip_path, 'wb') as f: f.write(b'placeholder')
            return clip_path

        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=405x720:d=5',
            '-vf', f'drawtext=text=Clip\\ {clip_id[:8]}:fontcolor=white:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p', '-y', clip_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return clip_path
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")
            return clip_path
    
    def _build_shared_context(self, product_name: str, master_description: str) -> str:
        return f"""You are generating a 12-shot viral video ad for {product_name}. 
Master visual description: {master_description}
Style: authentic user-generated content style, casual and relatable.
Visual Language: Handheld phone camera aesthetic, natural lighting, real-life texture. 
Avoid: Oversaturated colors, fake 3D renders, studio lighting, corporate feel.
Subject: A consistent creator/user interacting with the product in a real environment.
"""