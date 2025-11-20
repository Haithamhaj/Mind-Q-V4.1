import os
from dotenv import load_dotenv
from openai import OpenAI

# 1. تحميل المفتاح
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ Error: No API Key found. Please check your .env file.")
    exit()

client = OpenAI(api_key=api_key)

print(f"🔑 Connecting with key ending in: ...{api_key[-4:]}")
print("⏳ Fetching model list from OpenAI...")

try:
    # 2. طلب القائمة من الشركة
    models = client.models.list()
    
    found_5 = False
    print("\n--- Available GPT Models ---")
    
    # 3. طباعة الموديلات المهمة فقط
    for m in sorted(models.data, key=lambda x: x.id):
        # نركز على موديلات gpt و o1
        if "gpt" in m.id or "o1" in m.id:
            print(f"✅ {m.id}")
            if "gpt-5" in m.id:
                found_5 = True

    print("\n----------------------------")
    if found_5:
        print("🎉 GPT-5 found! The name in the code is correct.")
    else:
        print("⚠️ GPT-5 NOT found in your list.")
        print("If 'gpt-5.1' exists publicly, your API Key might not have access to it yet.")
        print("Please choose one of the '✅' models above to fix the code.")

except Exception as e:
    print(f"❌ Connection Failed: {e}")
