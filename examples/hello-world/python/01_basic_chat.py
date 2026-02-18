"""
Example 1: Basic Chat Completion through the AI Control Plane

This is the simplest possible example. It shows that you use the standard
OpenAI SDK — the only difference is `base_url` points to the control plane.
"""

from openai import OpenAI

# Connect to the AI Control Plane instead of OpenAI directly.
# The master key works for testing; in production, use team-scoped keys.
client = OpenAI(
    base_url="http://localhost:4000",
    api_key="$LITELLM_KEY",
)

# Make a chat completion — works with any of 100+ models
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is an AI control plane and why do enterprises need one?"},
    ],
    max_tokens=200,
)

print("Model:", response.model)
print("Usage:", response.usage)
print()
print(response.choices[0].message.content)
