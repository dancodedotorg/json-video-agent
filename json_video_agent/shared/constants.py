from google import genai
import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_CLIENT = genai.Client(
    api_key=GOOGLE_API_KEY,
)