import os
import sys
from dotenv import load_dotenv

# 1. Load environment variables
print("--- 1. Loading Environment ---")
load_dotenv()  # This looks for .env file

openai_key = os.getenv("OPENAI_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

# Function to print masked key
def mask_key(k):
    if not k: return "None"
    return k[:6] + "..." + k[-4:] if len(k) > 10 else "INVALID"

print(f"OPENAI_API_KEY found: {mask_key(openai_key)}")
print(f"ANTHROPIC_API_KEY found: {mask_key(anthropic_key)}")

# 2. Test Connection
print("\n--- 2. Testing Connection ---")

try:
    if openai_key:
        print("Attempting OpenAI connection...")
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # using cheap model for test
            messages=[{"role": "user", "content": "Say 'Hello Mind-Q'"}]
        )
        print("✅ OpenAI Success! Response:", response.choices[0].message.content)
    
    elif anthropic_key:
        print("Attempting Anthropic connection...")
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'Hello Mind-Q'"}]
        )
        print("✅ Anthropic Success! Response:", message.content[0].text)
    
    else:
        print("❌ NO KEYS FOUND. Please check your .env file.")
        
except Exception as e:
    print(f"❌ CONNECTION FAILED: {str(e)}")
    print("Type of error:", type(e).__name__)
