FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py agent.py diagnose.py llm.py actions.py risk.py admin_client.py notifier.py ./

# Shared library injected via docker compose --build-context shared=./src/shared
COPY --from=shared . /app/shared/

RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8092

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8092/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8092"]
