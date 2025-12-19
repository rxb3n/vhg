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
    
    async def _analyze_with_openai(self, image_data: bytes) -> Dict[str, Any]:
        """Analyze using GPT-4o"""
        import base64
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        system_prompt = """You are an expert TV Commercial Director. You will receive an image of a product. Your task is to write a script for a 60-second viral video, broken down into exactly 12 scenes of 5 seconds each.

Rules:
1. Analyze First: Extract a physical description of the product (color, material, label text) and insert this description into EVERY scene prompt to help the video AI.
2. Visual Continuity: Ensure scenes flow logically (e.g., establishing shot -> close up -> usage -> lifestyle).
3. Prompt Structure: Use the format: 'Cinematic shot, [Visual Description], [Action/Movement], [Lighting/Environment]'.
4. Each scene should include: id, action, prompt, role (hook/problem/solution/proof/CTA), shot_type, continuity_constraints.
5. Output: Return ONLY valid JSON."""

        user_prompt = """Analyze this product image and generate a 12-scene script. Return a JSON object with:
{
  "product_name": "string",
  "master_description": "detailed visual description",
  "scenes": [
    {
      "id": 1,
      "action": "string",
      "prompt": "string",
      "role": "hook|problem|solution|proof|CTA",
      "shot_type": "string",
      "continuity_constraints": "string"
    }
  ]
}"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from response
        try:
            # Try to parse as-is
            script = json.loads(content)
        except:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                script = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    script = json.loads(json_match.group(1))
                else:
                    raise Exception("Could not parse JSON from response")
        
        # Validate structure
        if "scenes" not in script or len(script["scenes"]) != 12:
            raise Exception("Script must contain exactly 12 scenes")
        
        return script
    
    async def _analyze_with_gemini(self, image_path: str) -> Dict[str, Any]:
        """Analyze using Gemini 2.5 Flash"""
        from PIL import Image
        
        if not self.gemini_client:
            raise Exception("Gemini client not initialized. Check GEMINI_API_KEY in .env file.")
        
        image = Image.open(image_path)
        
        system_prompt = """You are an expert TV Commercial Director. Analyze the product image and generate a script for a 60-second viral video, broken down into exactly 12 scenes of 5 seconds each.

Rules:
1. Extract a physical description of the product (color, material, label text) and insert this description into EVERY scene prompt.
2. Ensure scenes flow logically (establishing shot -> close up -> usage -> lifestyle).
3. Use format: 'Cinematic shot, [Visual Description], [Action/Movement], [Lighting/Environment]'.
4. Each scene should include: id, action, prompt, role (hook/problem/solution/proof/CTA), shot_type, continuity_constraints.
5. Return ONLY valid JSON."""

        prompt = f"""{system_prompt}

Return a JSON object with:
{{
  "product_name": "string",
  "master_description": "detailed visual description",
  "scenes": [
    {{
      "id": 1,
      "action": "string",
      "prompt": "string",
      "role": "hook|problem|solution|proof|CTA",
      "shot_type": "string",
      "continuity_constraints": "string"
    }}
  ]
}}"""

        try:
            print(f"Calling Gemini API with image: {image_path}")
            print(f"Image format: {image.format}, size: {image.size}")
            
            # Generate content with error handling
            response = self.gemini_client.generate_content([prompt, image])
            
            if not response:
                raise Exception("Gemini API returned empty response")
            
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
                    raise Exception(f"Gemini API response has no text. Response type: {type(response)}, attributes: {dir(response)}")
            
            print(f"Gemini response received, length: {len(content)}")
            print(f"First 200 chars: {content[:200]}")
            
        except Exception as e:
            error_msg = f"Gemini API error: {str(e)}"
            print(f"ERROR: {error_msg}")
            import traceback
            print(traceback.format_exc())
            raise Exception(error_msg)
        
        # Extract JSON
        import re
        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                script = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    script = json.loads(json_match.group(1))
                else:
                    # Try to find JSON object directly
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        script = json.loads(json_match.group(0))
                    else:
                        script = json.loads(content)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON from Gemini response. Error: {str(e)}\nResponse content: {content[:500]}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
        if "scenes" not in script:
            raise Exception(f"Script missing 'scenes' key. Got keys: {list(script.keys())}")
        
        if len(script["scenes"]) != 12:
            raise Exception(f"Script must contain exactly 12 scenes, got {len(script['scenes'])}")
        
        return script

