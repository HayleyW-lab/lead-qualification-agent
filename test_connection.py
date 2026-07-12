import os
from dotenv import load_dotenv
from google import genai

# Load the .env file so we can read GEMINI_API_KEY
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("No API key found — check your .env file")

# Create the client
client = genai.Client(api_key=api_key)

# Send a simple test prompt
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Reply with exactly one sentence confirming you're working."
)

print(response.text)