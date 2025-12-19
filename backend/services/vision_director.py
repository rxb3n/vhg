import os
import json
import hashlib
from pathlib import Path
from openai import OpenAI
from google import generativeai as genai
from typing import Dict, Any
from dotenv import load_dotenv

# Load .env file from the backend directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class VisionDirector:
    def __init__(self):
        self.openai_client = None
        self.gemini_client = None
        
        # Try to initialize OpenAI (fallback)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key.strip():
            try:
                self.openai_client = OpenAI(api_key=openai_key)
                print("Initialized OpenAI client")
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client: {e}")
        
        # Initialize Gemini with gemini-2.5-flash
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and gemini_key.strip():
            try:
                genai.configure(api_key=gemini_key)
                # Use gemini-2.5-flash (faster and more available)
                self.gemini_client = genai.GenerativeModel('gemini-2.5-flash')
                print("Successfully initialized Gemini with gemini-2.5-flash")
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini client: {e}")
        else:
            print("Warning: GEMINI_API_KEY not found in environment variables")
    
    async def analyze_and_script(self, image_path: str) -> Dict[str, Any]:
        """Analyze product image and generate 12-scene script"""
        
        # Check cache first
        image_hash = self._get_image_hash(image_path)
        cache_path = f"cache/scripts/{image_hash}.json"
        
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)
        
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Use Gemini if available, otherwise OpenAI
        if self.gemini_client:
            script = await self._analyze_with_gemini(image_path)
        elif self.openai_client:
            script = await self._analyze_with_openai(image_data)
        else:
            raise Exception("No vision API key configured. Please set GEMINI_API_KEY or OPENAI_API_KEY")
        
        # Cache the result
        os.makedirs("cache/scripts", exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(script, f, indent=2)
        
        return script
    
    def _get_image_hash(self, image_path: str) -> str:
        """Generate hash of image for caching"""
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    async def _analyze_with_gemini(self, image_path: str) -> Dict[str, Any]:
        """Analyze using Gemini 1.5/2.5 Flash"""
        import PIL.Image
        
        img = PIL.Image.open(image_path)
        
        system_prompt = """You are an expert TikTok Content Strategist. 
Analyze the product image and generate a script for a viral, authentic UGC (User Generated Content) video.
The video must be exactly 60 seconds, broken down into 12 scenes of 5 seconds each.

STRICT VISUAL STYLE GUIDE:
All scenes MUST follow this exact visual formula to ensure consistency:
"Vertical 9:16 video of a [person matching target audience] in a [bright, aesthetic setting like a bathroom/kitchen/living room] holding the [Product Name] close to the camera, talking directly to the viewer like a TikTok creator. They say '[Short Line matching the scene role]', while [action like applying/showing texture/pointing] and smiling at the camera. Soft natural daylight, clean white and pastel background, subtle text on screen: '[Key Benefit/Hook]'. Handheld phone style, authentic UGC testimonial vibe, smooth 5-second clip, high-definition, readable label on the product."

Rules:
1. Extract the exact product name, type, and physical details (color, material) from the image.
2. Structure the 12 scenes to tell a story: Hook (1-3) -> Problem (4-6) -> Solution/Demo (7-9) -> Social Proof/CTA (10-12).
3. Ensure strict visual continuity: same actor, same setting, same lighting in every prompt.
4. The 'prompt' field in the JSON must be the full, detailed generation prompt following the style guide above.
5. Return ONLY valid JSON."""

        prompt = f"""{system_prompt}

Return a JSON object with:
{{
  "product_name": "string",
  "master_description": "detailed visual description of product and consistent actor/setting",
  "scenes": [
    {{
      "id": 1,
      "action": "short description of action",
      "prompt": "Vertical 9:16 video of a young woman in a bright bathroom holding a...",
      "role": "hook|problem|solution|proof|CTA",
      "shot_type": "medium close-up",
      "continuity_constraints": "same actor, bright bathroom setting"
    }}
  ]
}}"""

        try:
            response = self.gemini_client.generate_content([prompt, img])
            
            # Handle different response formats
            content = None
            if hasattr(response, 'text') and response.text:
                content = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                if len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        if len(candidate.content.parts) > 0:
                            content = candidate.content.parts[0].text
            
            if not content:
                # Try to get any text from the response
                try:
                    content = str(response)
                except:
                    pass
                    
            if not content:
                raise Exception(f"Gemini API response has no text.")

            # Clean up markdown
            content = content.replace('```json', '').replace('```', '').strip()
            
            try:
                script = json.loads(content)
                # Enforce tone
                script['tone'] = 'UGC'
                return script
            except json.JSONDecodeError:
                # Fallback extraction
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = content[start_idx:end_idx]
                    script = json.loads(json_str)
                    script['tone'] = 'UGC'
                    return script
                raise
                
        except Exception as e:
            print(f"Error calling Gemini: {e}")
            raise

    async def _analyze_with_openai(self, image_data: bytes) -> Dict[str, Any]:
        """Analyze using GPT-4o (Fallback)"""
        import base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        system_prompt = """You are an expert TikTok Content Strategist. 
Analyze the product image and generate a script for a viral, authentic UGC (User Generated Content) video.
The video must be exactly 60 seconds, broken down into 12 scenes of 5 seconds each.

STRICT VISUAL STYLE GUIDE:
All scenes MUST follow this exact visual formula to ensure consistency:
"Vertical 9:16 video of a [person matching target audience] in a [bright, aesthetic setting like a bathroom/kitchen/living room] holding the [Product Name] close to the camera, talking directly to the viewer like a TikTok creator. They say '[Short Line matching the scene role]', while [action like applying/showing texture/pointing] and smiling at the camera. Soft natural daylight, clean white and pastel background, subtle text on screen: '[Key Benefit/Hook]'. Handheld phone style, authentic UGC testimonial vibe, smooth 5-second clip, high-definition, readable label on the product."
"""
        # ... (rest of OpenAI logic similar to Gemini, ensuring strict JSON output)
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Generate the 12-scene JSON script."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        script = json.loads(content)
        script['tone'] = 'UGC'
        return script