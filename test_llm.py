#!/usr/bin/env python3
"""Test OpenAI API connection and LLM functionality."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
backend_dir = Path(__file__).parent / "backend"
llm_env_path = backend_dir / "llm.env"

if llm_env_path.exists():
    load_dotenv(llm_env_path)
    print(f"✓ Loaded environment from: {llm_env_path}")
else:
    print(f"✗ Environment file not found: {llm_env_path}")
    sys.exit(1)

# Get API key
api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_MODEL", "gpt-4")

if not api_key:
    print("✗ OPENAI_API_KEY not found in environment")
    sys.exit(1)

# Mask the key for display
masked_key = f"{api_key[:10]}...{api_key[-10:]}" if len(api_key) > 20 else "***"
print(f"✓ API Key found: {masked_key}")
print(f"✓ Model: {model}")
print()

# Try to import OpenAI
try:
    import openai
    print("✓ OpenAI library imported successfully")
except ImportError:
    print("✗ OpenAI library not installed. Installing...")
    os.system("pip install openai")
    import openai
    print("✓ OpenAI library installed and imported")

# Test the API connection
print("\n" + "="*60)
print("Testing OpenAI API Connection...")
print("="*60 + "\n")

try:
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    
    # Simple test prompt
    print("Sending test prompt to API...")
    
    # Prepare the request parameters
    request_params = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that responds concisely."},
            {"role": "user", "content": "Say 'Hello! The LLM is working correctly.' in one sentence."}
        ],
        "temperature": 0.7
    }
    
    # Use max_completion_tokens for newer models, max_tokens for older ones
    if "gpt-4" in model.lower() or "gpt-5" in model.lower():
        request_params["max_completion_tokens"] = 50
    else:
        request_params["max_tokens"] = 50
    
    response = client.chat.completions.create(**request_params)
    
    result = response.choices[0].message.content
    
    print("\n" + "="*60)
    print("✓ SUCCESS! API Response:")
    print("="*60)
    print(f"\n{result}\n")
    print("="*60)
    print(f"\nModel used: {response.model}")
    print(f"Tokens used: {response.usage.total_tokens}")
    print(f"  - Prompt: {response.usage.prompt_tokens}")
    print(f"  - Completion: {response.usage.completion_tokens}")
    print("\n✓ LLM is working correctly!")
    
except openai.AuthenticationError:
    print("\n✗ AUTHENTICATION ERROR")
    print("The API key is invalid or has been revoked.")
    print("Please check your OPENAI_API_KEY in backend/llm.env")
    sys.exit(1)
    
except openai.RateLimitError:
    print("\n✗ RATE LIMIT ERROR")
    print("You've exceeded your rate limit or quota.")
    sys.exit(1)
    
except openai.APIError as e:
    print(f"\n✗ API ERROR: {e}")
    sys.exit(1)
    
except Exception as e:
    print(f"\n✗ UNEXPECTED ERROR: {type(e).__name__}")
    print(f"Message: {e}")
    sys.exit(1)
