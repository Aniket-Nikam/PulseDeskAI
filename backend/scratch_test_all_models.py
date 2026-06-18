import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ai.providers.groq_provider import GroqProvider

async def main():
    provider = GroqProvider()
    client = provider._get_client()
    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        print(f"Testing {len(model_ids)} models...")
        for model_name in model_ids:
            try:
                client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": "Hello! Are you online?",
                        }
                    ],
                    max_tokens=10,
                )
                print(f"SUCCESS: {model_name}")
            except Exception:
                # print(f"Failed with {model_name}: {e}")
                pass
    except Exception as e:
        print(f"Error listing/testing: {e}")

if __name__ == "__main__":
    asyncio.run(main())

