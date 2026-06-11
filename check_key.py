from dotenv import load_dotenv
import os

load_dotenv()

key = os.getenv("GEMINI_API_KEY")

print("Loaded:", key[:10] if key else None)
print("Length:", len(key) if key else 0)