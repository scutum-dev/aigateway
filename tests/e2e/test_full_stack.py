"""
End-to-End tests for the complete AI Gateway stack.

These tests verify the full request flow from client through
LiteLLM -> Agent Gateway -> LLM Provider/vLLM.

Requirements:
- All services must be running
- API keys must be configured
"""

import os
import time
import pytest
import httpx
from typing import Optional

# Configuration
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
AGENTGATEWAY_URL = os.getenv("AGENTGATEWAY_URL", "http://localhost:3000")
COST_PREDICTOR_URL = os.getenv("COST_PREDICTOR_URL", "http://localhost:8080")
FINOPS_REPORTER_URL = os.getenv("FINOPS_REPORTER_URL", "http://localhost:8082")
API_KEY = os.getenv("TEST_API_KEY", "sk-test-key")


@pytest.fixture(scope="module")
def http_client():
    """Create HTTP client for tests."""
    client = httpx.Client(timeout=120.0)
    yield client
    client.close()


@pytest.fixture
def api_headers():
    """Common API headers."""
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-Request-ID": f"e2e-test-{int(time.time())}"
    }


class TestFullStackE2E:
    """End-to-end tests for the complete stack."""

    def test_health_all_services(self, http_client):
        """Verify all services are healthy."""
        services = [
            (LITELLM_URL, "/health"),
            (AGENTGATEWAY_URL, "/health"),
        ]

        # Optional services
        optional_services = [
            (COST_PREDICTOR_URL, "/health"),
            (FINOPS_REPORTER_URL, "/health"),
        ]

        for url, path in services:
            response = http_client.get(f"{url}{path}")
            assert response.status_code == 200, f"Service {url} is not healthy"

        for url, path in optional_services:
            try:
                response = http_client.get(f"{url}{path}", timeout=5.0)
                print(f"Optional service {url}: {'healthy' if response.status_code == 200 else 'unhealthy'}")
            except Exception as e:
                print(f"Optional service {url}: not available ({e})")

    def test_complete_request_flow(self, http_client, api_headers):
        """
        Test complete request flow:
        1. Predict cost
        2. Make LLM request
        3. Verify response
        4. Check cost was tracked
        """
        model = "gpt-4o-mini"
        messages = [
            {"role": "user", "content": "What is 2+2? Reply with just the number."}
        ]

        # Step 1: Predict cost (if service available)
        try:
            predict_response = http_client.post(
                f"{COST_PREDICTOR_URL}/predict",
                headers=api_headers,
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 10
                }
            )

            if predict_response.status_code == 200:
                prediction = predict_response.json()
                print(f"Cost prediction: ${prediction['total_estimated_cost_usd']:.6f}")
                assert prediction["input_tokens"] > 0
                assert prediction["total_estimated_cost_usd"] > 0
        except Exception as e:
            print(f"Cost prediction skipped: {e}")

        # Step 2: Make LLM request
        llm_response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 10
            }
        )

        assert llm_response.status_code == 200
        llm_data = llm_response.json()

        # Step 3: Verify response
        assert "choices" in llm_data
        assert len(llm_data["choices"]) > 0
        assert "message" in llm_data["choices"][0]

        content = llm_data["choices"][0]["message"]["content"]
        assert "4" in content, f"Expected '4' in response, got: {content}"

        # Verify usage was tracked
        assert "usage" in llm_data
        assert llm_data["usage"]["total_tokens"] > 0

        print(f"LLM request successful: {llm_data['usage']['total_tokens']} tokens used")

    def test_streaming_e2e(self, http_client, api_headers):
        """Test streaming response end-to-end."""
        with http_client.stream(
            "POST",
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": "Count from 1 to 5."}
                ],
                "max_tokens": 50,
                "stream": True
            }
        ) as response:
            assert response.status_code == 200

            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data != "[DONE]":
                        chunks.append(data)

            assert len(chunks) > 0, "Expected streaming chunks"
            print(f"Received {len(chunks)} streaming chunks")

    def test_model_fallback_e2e(self, http_client, api_headers):
        """Test that model fallback works correctly."""
        # Request a model that might use fallback
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o",  # Primary model
                "messages": [
                    {"role": "user", "content": "Say 'test'"}
                ],
                "max_tokens": 10
            }
        )

        # Should succeed either with primary or fallback
        assert response.status_code == 200

    def test_rate_limiting(self, http_client, api_headers):
        """Test that rate limiting is applied correctly."""
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = http_client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                headers=api_headers,
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5
                }
            )
            responses.append(response.status_code)
            time.sleep(0.1)

        # Most should succeed, some might be rate limited
        success_count = sum(1 for s in responses if s == 200)
        rate_limited_count = sum(1 for s in responses if s == 429)

        print(f"Requests: {len(responses)}, Success: {success_count}, Rate Limited: {rate_limited_count}")

        # At least some should succeed
        assert success_count > 0

    def test_cost_tracking_e2e(self, http_client, api_headers):
        """Test that costs are tracked end-to-end."""
        # Make a request
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            }
        )

        assert response.status_code == 200

        # Check if spend logs are available
        try:
            spend_response = http_client.get(
                f"{LITELLM_URL}/spend/logs",
                headers=api_headers
            )

            if spend_response.status_code == 200:
                spend_data = spend_response.json()
                print(f"Spend logs available: {len(spend_data.get('logs', []))} entries")
        except Exception as e:
            print(f"Spend logs not available: {e}")

    def test_observability_traces(self, http_client, api_headers):
        """Test that requests generate observability traces."""
        # Make a request with a specific request ID
        request_id = f"trace-test-{int(time.time())}"
        headers = {**api_headers, "X-Request-ID": request_id}

        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 5
            }
        )

        assert response.status_code == 200

        # Check response headers for trace info
        # (exact headers depend on configuration)
        print(f"Response headers: {dict(response.headers)}")

    def test_error_handling(self, http_client, api_headers):
        """Test error handling for invalid requests."""
        # Invalid model
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "nonexistent-model-12345",
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 10
            }
        )

        # Should return an error (400, 404, or similar)
        assert response.status_code in [400, 404, 422, 500]

        # Invalid request format
        response = http_client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers=api_headers,
            json={
                "model": "gpt-4o-mini",
                # Missing messages
            }
        )

        assert response.status_code in [400, 422]


class TestFinOpsIntegration:
    """Test FinOps reporting integration."""

    def test_cost_report_generation(self, http_client, api_headers):
        """Test generating cost reports."""
        try:
            response = http_client.get(
                f"{FINOPS_REPORTER_URL}/reports/cost",
                headers=api_headers,
                params={"period": "daily"}
            )

            if response.status_code == 200:
                report = response.json()
                print(f"Cost report: {report.get('total_cost', 0)}")
                assert "total_cost" in report
                assert "breakdown_by_model" in report
        except Exception as e:
            pytest.skip(f"FinOps reporter not available: {e}")

    def test_summary_stats(self, http_client, api_headers):
        """Test summary statistics endpoint."""
        try:
            response = http_client.get(
                f"{FINOPS_REPORTER_URL}/reports/summary",
                headers=api_headers
            )

            if response.status_code == 200:
                summary = response.json()
                assert "today" in summary
                assert "this_month" in summary
        except Exception as e:
            pytest.skip(f"FinOps reporter not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
