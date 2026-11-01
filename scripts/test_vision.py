import base64
from pathlib import Path

from openai import OpenAI

image_path = Path("environment_test/01_before.png")
image_base64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

response = client.chat.completions.create(
    model="llava:7b",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe what you see in this image briefly.",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    },
                },
            ],
        }
    ],
)

print(response.choices[0].message.content)