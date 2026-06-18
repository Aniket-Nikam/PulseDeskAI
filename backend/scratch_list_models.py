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
        print("Available Groq Models:")
        for model in models.data:
            print(f"ID: {model.id}")
            print(f"  Owned By: {model.owned_by}")
            print("-" * 30)
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    asyncio.run(main())
