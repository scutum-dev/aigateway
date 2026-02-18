FROM ghcr.io/berriai/litellm:main-latest

COPY guardrail_requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/guardrail_requirements.txt

COPY guardrail_handler.py /etc/litellm/
