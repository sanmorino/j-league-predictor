import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("--- Listing available models ---")
try:
    for model in client.models.list():
        print(f"Name: {model.name}, Supported Methods: {model.supported_methods}")
except Exception as e:
    print(f"Error listing models: {e}")
