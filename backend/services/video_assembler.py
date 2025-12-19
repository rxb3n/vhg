import os
import subprocess
import uuid
from typing import List
from database import get_db, get_db_session
from models import AdGeneration, Clip

class VideoAssembler:
    def __init__(self):
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def assemble_video(self, ad_id: str):
        """Assemble all clips into final video with normalization"""
        db = get_db_session()
        
        try:
            ad_gen = db.query(AdGeneration).filter(AdGeneration.id == ad_id).first()
            if not ad_gen:
                print(f"ERROR: Ad generation {ad_id} not found")
                return
            
            # Get all clips in order
            clips = db.query(Clip).filter(
                Clip.ad_id == ad_id,
                Clip.status == "completed"
            ).order_by(Clip.sequence_index).all()
            
            if len(clips) != 12:
                error_msg = f"Expected 12 clips, got {len(clips)}"
                print(f"ERROR: {error_msg}")
                ad_gen.status = "failed"
                db.commit()
                raise Exception(error_msg)
            
            # Create concat file list
            concat_file = os.path.join(self.output_dir, f"{ad_id}_concat.txt")
            with open(concat_file, 'w') as f:
                for clip in clips:
                    if clip.local_path and os.path.exists(clip.local_path):
                        f.write(f"file '{os.path.abspath(clip.local_path)}'\n")
            
            # Step 1: Concatenate clips
            temp_output = os.path.join(self.output_dir, f"{ad_id}_temp.mp4")
            self._concatenate_clips(concat_file, temp_output)
            
            # Step 2: Normalize audio
            audio_normalized = os.path.join(self.output_dir, f"{ad_id}_audio_norm.mp4")
            self._normalize_audio(temp_output, audio_normalized)
            
            # Step 3: Normalize color (optional)
            final_output = os.path.join(self.output_dir, f"{ad_id}_final.mp4")
            self._normalize_color(audio_normalized, final_output)
            
            # Update ad generation
            final_filename = f"{ad_id}_final.mp4"
            ad_gen.final_video_url = f"/api/videos/{final_filename}"
            ad_gen.status = "completed"
            db.commit()
            
            # Clean up temp files
            if os.path.exists(temp_output):
                os.remove(temp_output)
            if os.path.exists(audio_normalized):
                os.remove(audio_normalized)
            if os.path.exists(concat_file):
                os.remove(concat_file)
            
            # Clean up individual clips (as per requirement)
            self._cleanup_clips(clips)
            
        except Exception as e:
            error_msg = f"Error assembling video: {e}"
            print(f"ERROR: {error_msg}")
            import traceback
            print(traceback.format_exc())
            
            # Ensure status is updated even if there's an error
            try:
                db.refresh(ad_gen)
                ad_gen.status = "failed"
                db.commit()
            except Exception as db_error:
                print(f"ERROR: Failed to update status in database: {db_error}")
        finally:
            db.close()
    
    def _concatenate_clips(self, concat_file: str, output_path: str):
        """Concatenate video clips using FFmpeg"""
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg concat failed: {result.stderr}")
    
    def _normalize_audio(self, input_path: str, output_path: str):
        """Normalize audio loudness using EBU R128"""
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-filter:a', 'loudnorm=I=-16:LRA=11:tp=-1',
            '-c:v', 'copy',
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # If loudnorm fails, just copy the file
            import shutil
            shutil.copy(input_path, output_path)
    
    def _normalize_color(self, input_path: str, output_path: str):
        """Apply light color normalization"""
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', 'eq=contrast=1.05:saturation=1.05:brightness=0.02',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # If color normalization fails, just copy the file
            import shutil
            shutil.copy(input_path, output_path)
    
    def _cleanup_clips(self, clips: List[Clip]):
        """Delete individual clip files after assembly"""
        for clip in clips:
            if clip.local_path and os.path.exists(clip.local_path):
                try:
                    os.remove(clip.local_path)
                except Exception as e:
                    print(f"Warning: Could not delete clip {clip.local_path}: {e}")

