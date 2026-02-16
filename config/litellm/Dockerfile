FROM ghcr.io/berriai/litellm:main-latest

COPY guardrail_requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/guardrail_requirements.txt

# Download the prompt injection model at build time so first request is fast
RUN python -c "from llm_guard.input_scanners import PromptInjection; PromptInjection()" || true

COPY guardrail_handler.py /app/
