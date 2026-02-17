"""Environment-aware CORS configuration."""

import os


def get_cors_origins() -> list[str]:
    """Get allowed CORS origins based on ENVIRONMENT env var."""
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        origins = os.getenv("CORS_ORIGINS", "").split(",")
        configured = [o.strip() for o in origins if o.strip()]
        return configured or ["https://gateway.deos.dev"]
    return [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:9999",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
