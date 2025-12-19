#!/usr/bin/env python3
"""Test script to verify the setup is correct"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 50)
print("SETUP VERIFICATION")
print("=" * 50)

# Check Python version
print(f"\n[OK] Python version: {sys.version.split()[0]}")

# Check environment variables
print("\n--- Environment Variables ---")
gemini_key = os.getenv("GEMINI_API_KEY")
wan_key = os.getenv("WAN_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

if gemini_key and gemini_key != "":
    print(f"[OK] GEMINI_API_KEY: SET (length: {len(gemini_key)})")
else:
    print("[X] GEMINI_API_KEY: NOT SET")

if wan_key and wan_key != "":
    print(f"[OK] WAN_API_KEY: SET (length: {len(wan_key)})")
else:
    print("[X] WAN_API_KEY: NOT SET")

if openai_key and openai_key != "":
    print(f"[OK] OPENAI_API_KEY: SET (length: {len(openai_key)})")
else:
    print("[ ] OPENAI_API_KEY: NOT SET (optional if using Gemini)")

# Check required dependencies
print("\n--- Dependencies ---")
dependencies = {
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "google.generativeai": "Google Generative AI",
    "openai": "OpenAI",
    "PIL": "Pillow",
    "requests": "Requests",
    "aiofiles": "Aiofiles",
    "dotenv": "python-dotenv",
}

missing = []
for module, name in dependencies.items():
    try:
        __import__(module)
        print(f"[OK] {name}: Installed")
    except ImportError:
        print(f"[X] {name}: MISSING")
        missing.append(name)

# Check optional dependencies
print("\n--- Optional Dependencies ---")
try:
    import ffmpeg
    print("[OK] FFmpeg Python bindings: Installed")
except ImportError:
    print("[ ] FFmpeg Python bindings: Not installed (FFmpeg binary still required)")

# Check if FFmpeg binary is available
print("\n--- FFmpeg Binary ---")
import subprocess
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"[OK] FFmpeg: {version_line}")
    else:
        print("[X] FFmpeg: Not found or error")
except (FileNotFoundError, subprocess.TimeoutExpired):
    print("[X] FFmpeg: Not found in PATH (required for video processing)")

# Summary
print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)

if missing:
    print(f"\n[!] Missing dependencies: {', '.join(missing)}")
    print("   Run: pip install -r requirements.txt")
else:
    print("\n[OK] All required dependencies are installed")

if gemini_key and wan_key:
    print("[OK] API keys are configured")
    print("\n[SUCCESS] Setup looks good! You should be able to run the application.")
else:
    print("\n[!] Some API keys are missing. Check your .env file.")

print("\n" + "=" * 50)

