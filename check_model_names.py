import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API_KEY not found")
else:
    genai.configure(api_key=api_key)
    print("--- Listing models using google-generativeai SDK ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model ID: {m.name}")
    except Exception as e:
        print(f"Error: {e}")
