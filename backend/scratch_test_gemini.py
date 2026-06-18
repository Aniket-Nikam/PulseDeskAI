import asyncio
import httpx
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment!")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    print("Listing Gemini models...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=20.0)
            if response.status_code == 200:
                data = response.json()
                for model in data.get("models", []):
                    print(f"Model Name: {model.get('name')}")
                    print(f"  Supported Methods: {model.get('supportedGenerationMethods')}")
                    print("-" * 30)
            else:
                print(f"Failed with status code {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())

