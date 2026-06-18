import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ai.providers.groq_provider import GroqProvider

async def main():
    provider = GroqProvider()
    client = provider._get_client()
    model_name = "qwen/qwen3-32b"
    print(f"Testing Groq model {model_name}...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": "Hello! Are you online?",
                }
            ],
            max_tokens=10,
        )
        print("Success! Response:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Failed with {model_name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
