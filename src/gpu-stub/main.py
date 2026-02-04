"""
GPU Stub Service

Returns clear error messages when local GPU models are requested
but Ollama is not running.

Install Ollama: https://ollama.com/download
- macOS: brew install ollama
- Windows: Download from ollama.com
- Linux: curl -fsSL https://ollama.com/install.sh | sh

Then run: ollama serve && ollama pull llama3.1:8b
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="GPU Stub Service")

GPU_ERROR = {
    "error": {
        "message": "Ollama not running. Local models require Ollama. "
                   "Install: https://ollama.com/download then run 'ollama serve'. "
                   "Or use cloud models (gpt-4o, claude-3-5-sonnet, grok-3) instead.",
        "type": "ollama_not_running",
        "code": "ollama_required"
    }
}


@app.get("/health")
@app.get("/v1/health")
async def health():
    return {
        "status": "stub",
        "message": "Ollama not running. Install from https://ollama.com/download",
        "ollama_running": False
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "ollama-required",
                "object": "model",
                "created": 0,
                "owned_by": "local",
                "description": "Ollama not running. Install from https://ollama.com/download"
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
                "message": f"Model '{model}' requires Ollama. Install from https://ollama.com/download, "
                           f"then run 'ollama serve' and 'ollama pull llama3.1:8b'. "
                           f"Or use cloud models (gpt-4o, claude-3-5-sonnet, grok-3).",
                "type": "ollama_not_running",
                "code": "ollama_required",
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
                "message": "Local embeddings require Ollama. Install from https://ollama.com/download",
                "type": "ollama_not_running",
                "code": "ollama_required"
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
