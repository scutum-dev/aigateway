"""
Example 2: Multi-Model Comparison

Send the same prompt to models from different providers through one control plane.
Compare response quality, latency, and cost — without managing multiple SDKs.
"""

import time
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000",
    api_key="$LITELLM_KEY",
)

MODELS = [
    "gpt-4o-mini",          # OpenAI
    "claude-haiku-4.5",     # Anthropic
    "gemini-2.5-flash",     # Google
]

PROMPT = "Explain microservices vs monolith in exactly 2 sentences."


def query_model(model: str) -> dict:
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=150,
        )
        elapsed = time.time() - start
        return {
            "model": model,
            "response": response.choices[0].message.content,
            "tokens_in": response.usage.prompt_tokens,
            "tokens_out": response.usage.completion_tokens,
            "latency_ms": int(elapsed * 1000),
        }
    except Exception as e:
        return {"model": model, "error": str(e), "latency_ms": int((time.time() - start) * 1000)}


print(f"Prompt: {PROMPT}\n")
print("=" * 70)

for model in MODELS:
    result = query_model(model)
    print(f"\n[{result['model']}] ({result['latency_ms']}ms)")
    if "error" in result:
        print(f"  Error: {result['error']}")
    else:
        print(f"  Tokens: {result['tokens_in']} in / {result['tokens_out']} out")
        print(f"  Response: {result['response']}")
    print("-" * 70)

print("\nAll requests went through one AI Control Plane endpoint (localhost:4000).")
print("Cost tracking happened automatically — check the Admin Console at localhost:5173.")
