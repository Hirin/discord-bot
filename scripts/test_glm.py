#!/usr/bin/env python3
"""
Test GLM API
Run: uv run scripts/test_glm.py
"""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("GLM_API_KEY")
base_url = os.getenv("GLM_BASE_URL", "https://api.z.ai/api/paas/v4/")
model = os.getenv("GLM_MODEL", "glm-4.6")

print(f"API Key: {api_key[:20]}..." if api_key else "❌ No API key")
print(f"Base URL: {base_url}")
print(f"Model: {model}")
print()

client = OpenAI(api_key=api_key, base_url=base_url)

try:
    print("🔄 Testing GLM API...")
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in Vietnamese"}
        ],
        max_tokens=100
    )
    
    print("✅ Success!")
    print(f"Response: {completion.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ Error: {e}")
