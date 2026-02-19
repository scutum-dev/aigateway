"""
Example 3: Streaming Responses

Streaming works identically to the OpenAI SDK — the AI Control Plane proxies
Server-Sent Events transparently. Cost tracking still works.
"""

import os

from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000",
    api_key=os.getenv("LITELLM_KEY") or os.getenv("LITELLM_MASTER_KEY", ""),
)

print("Streaming from claude-haiku-4.5 via the AI Control Plane:\n")

stream = client.chat.completions.create(
    model="claude-haiku-4.5",
    messages=[
        {"role": "user", "content": "Write a haiku about API gateways."},
    ],
    max_tokens=100,
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)

print("\n\nStreaming complete. The control plane tracked tokens and cost automatically.")
