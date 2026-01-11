import asyncio
import httpx
import json

API_URL = "https://api.fireflies.ai/graphql"
API_KEY = "78f2d852-8d4a-4fe8-bdc9-351c94d9b475"
TRANSCRIPT_ID = "01KE9K6ZGSD9CJ9ZPJ8F9D8VBZ"

async def test_get_audio():
    query = """
    query Transcript($id: String!) {
      transcript(id: $id) {
        id
        title
        audio_url
        video_url
        duration
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            json={"query": query, "variables": {"id": TRANSCRIPT_ID}},
            headers=headers,
            timeout=30,
        )

        data = response.json()
        print("Response:")
        print(json.dumps(data, indent=2))
        
        transcript = data.get("data", {}).get("transcript", {})
        if transcript.get("audio_url"):
            print(f"\n✅ Audio URL: {transcript['audio_url']}")
        else:
            print("\n❌ No audio URL available")

asyncio.run(test_get_audio())
