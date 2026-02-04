"""
GPU Stub Service

Returns clear error messages when local GPU models are requested
but no GPU backend (vLLM/Ollama) is available.

Replace this with actual vLLM when GPU is available.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="GPU Stub Service")

GPU_ERROR = {
    "error": {
        "message": "GPU backend not available. Local models (llama, mistral, etc.) require GPU. "
                   "Please use cloud models (gpt-4o, claude-3-5-sonnet, grok-3) instead, "
                   "or deploy vLLM/Ollama with GPU support.",
        "type": "gpu_not_available",
        "code": "gpu_required"
    }
}


@app.get("/health")
@app.get("/v1/health")
async def health():
    return {
        "status": "stub",
        "message": "GPU stub service running. No GPU backend configured.",
        "gpu_available": False
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "gpu-required",
                "object": "model",
                "created": 0,
                "owned_by": "local",
                "description": "GPU backend not configured. Deploy vLLM or Ollama with GPU."
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "unknown")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "message": f"Model '{model}' requires GPU backend. No GPU configured. "
                           f"Use cloud models (gpt-4o, claude-3-5-sonnet, grok-3) instead.",
                "type": "gpu_not_available",
                "code": "gpu_required",
                "param": "model"
            }
        }
    )


@app.post("/v1/completions")
async def completions(request: Request):
    return await chat_completions(request)


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "message": "Local embeddings require GPU backend. Use cloud embeddings instead.",
                "type": "gpu_not_available",
                "code": "gpu_required"
            }
        }
    )


# Catch-all for any other endpoints
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(path: str):
    return JSONResponse(
        status_code=503,
        content=GPU_ERROR
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
