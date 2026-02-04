"""Seed model routing configuration with all providers.

Revision ID: 002
Revises: 001
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Seed all models from all providers
    op.execute("""
        INSERT INTO model_routing_config (model_id, provider, tier, cost_per_1k_input, cost_per_1k_output, supports_streaming, supports_function_calling, supports_vision, default_latency_sla_ms)
        VALUES
            -- OpenAI
            ('gpt-5', 'openai', 'premium', 0.002, 0.008, TRUE, TRUE, TRUE, 5000),
            ('gpt-5.2', 'openai', 'premium', 0.003, 0.012, TRUE, TRUE, TRUE, 6000),
            ('gpt-5-mini', 'openai', 'budget', 0.0001, 0.0004, TRUE, TRUE, FALSE, 2000),
            ('o3', 'openai', 'premium', 0.01, 0.04, TRUE, TRUE, FALSE, 10000),
            ('o3-pro', 'openai', 'premium', 0.015, 0.06, TRUE, TRUE, FALSE, 15000),
            ('o4-mini', 'openai', 'standard', 0.003, 0.012, TRUE, TRUE, FALSE, 5000),
            ('gpt-4o', 'openai', 'standard', 0.0025, 0.010, TRUE, TRUE, TRUE, 5000),
            ('gpt-4o-mini', 'openai', 'budget', 0.00015, 0.0006, TRUE, TRUE, TRUE, 3000),
            -- Anthropic
            ('claude-opus-4.5', 'anthropic', 'premium', 0.015, 0.075, TRUE, TRUE, TRUE, 8000),
            ('claude-sonnet-4.5', 'anthropic', 'premium', 0.003, 0.015, TRUE, TRUE, TRUE, 5000),
            ('claude-haiku-4.5', 'anthropic', 'budget', 0.0002, 0.001, TRUE, TRUE, FALSE, 2000),
            ('claude-opus-4', 'anthropic', 'premium', 0.015, 0.075, TRUE, TRUE, TRUE, 8000),
            ('claude-sonnet-4', 'anthropic', 'standard', 0.003, 0.015, TRUE, TRUE, TRUE, 5000),
            ('claude-3-5-sonnet', 'anthropic', 'standard', 0.003, 0.015, TRUE, TRUE, TRUE, 5000),
            ('claude-3-haiku', 'anthropic', 'budget', 0.00025, 0.00125, TRUE, TRUE, FALSE, 2000),
            -- Google
            ('gemini-3-pro', 'google', 'premium', 0.00125, 0.005, TRUE, TRUE, TRUE, 5000),
            ('gemini-3-flash', 'google', 'budget', 0.00005, 0.0002, TRUE, TRUE, TRUE, 2000),
            ('gemini-2.5-pro', 'google', 'standard', 0.00125, 0.005, TRUE, TRUE, TRUE, 5000),
            ('gemini-2.5-flash', 'google', 'budget', 0.000075, 0.0003, TRUE, TRUE, TRUE, 2000),
            ('gemini-2.5-flash-lite', 'google', 'budget', 0.00005, 0.0002, TRUE, TRUE, FALSE, 1500),
            -- xAI
            ('grok-4', 'xai', 'premium', 0.005, 0.02, TRUE, TRUE, TRUE, 5000),
            ('grok-4-heavy', 'xai', 'premium', 0.01, 0.04, TRUE, TRUE, TRUE, 8000),
            ('grok-3', 'xai', 'standard', 0.001, 0.004, TRUE, TRUE, TRUE, 4000),
            ('grok-3-mini', 'xai', 'budget', 0.0005, 0.002, TRUE, TRUE, FALSE, 2000),
            -- DeepSeek
            ('deepseek-v3', 'deepseek', 'budget', 0.00007, 0.00027, TRUE, TRUE, FALSE, 3000),
            ('deepseek-r1', 'deepseek', 'standard', 0.0005, 0.002, TRUE, TRUE, FALSE, 8000),
            ('deepseek-coder', 'deepseek', 'budget', 0.0001, 0.0004, TRUE, TRUE, FALSE, 3000),
            -- AWS Bedrock
            ('bedrock-claude-opus-4.5', 'bedrock', 'premium', 0.015, 0.075, TRUE, TRUE, TRUE, 8000),
            ('bedrock-claude-sonnet-4.5', 'bedrock', 'premium', 0.003, 0.015, TRUE, TRUE, TRUE, 5000),
            ('bedrock-claude-haiku-4.5', 'bedrock', 'budget', 0.0002, 0.001, TRUE, TRUE, FALSE, 2000),
            ('bedrock-llama-4-405b', 'bedrock', 'premium', 0.00265, 0.0035, TRUE, FALSE, FALSE, 10000),
            ('bedrock-llama-4-70b', 'bedrock', 'standard', 0.00099, 0.00099, TRUE, FALSE, FALSE, 5000),
            ('bedrock-llama-3.3-70b', 'bedrock', 'standard', 0.00099, 0.00099, TRUE, FALSE, FALSE, 5000),
            ('bedrock-llama-3.2-90b', 'bedrock', 'standard', 0.0012, 0.0012, TRUE, FALSE, TRUE, 6000),
            ('bedrock-llama-3.1-70b', 'bedrock', 'standard', 0.00099, 0.00099, TRUE, FALSE, FALSE, 5000),
            ('bedrock-llama-3.1-8b', 'bedrock', 'budget', 0.0003, 0.0006, TRUE, FALSE, FALSE, 2000),
            ('bedrock-mistral-large-3', 'bedrock', 'standard', 0.002, 0.006, TRUE, TRUE, TRUE, 5000),
            ('bedrock-mistral-large', 'bedrock', 'standard', 0.002, 0.006, TRUE, TRUE, FALSE, 5000),
            ('bedrock-ministral-8b', 'bedrock', 'budget', 0.0001, 0.0003, TRUE, TRUE, FALSE, 2000),
            ('bedrock-nova-pro', 'bedrock', 'standard', 0.0008, 0.0032, TRUE, TRUE, TRUE, 4000),
            ('bedrock-nova-lite', 'bedrock', 'budget', 0.00006, 0.00024, TRUE, TRUE, TRUE, 2000),
            ('bedrock-nova-micro', 'bedrock', 'budget', 0.000035, 0.00014, TRUE, TRUE, FALSE, 1500),
            ('bedrock-titan-text-premier', 'bedrock', 'standard', 0.0005, 0.0015, TRUE, FALSE, FALSE, 4000),
            ('bedrock-deepseek-r1', 'bedrock', 'standard', 0.00135, 0.00548, TRUE, TRUE, FALSE, 8000),
            ('bedrock-cohere-command-r-plus', 'bedrock', 'standard', 0.003, 0.015, TRUE, TRUE, FALSE, 5000),
            ('bedrock-cohere-command-r', 'bedrock', 'budget', 0.0005, 0.0015, TRUE, TRUE, FALSE, 3000),
            ('bedrock-jamba-1.5-large', 'bedrock', 'standard', 0.002, 0.008, TRUE, FALSE, FALSE, 5000),
            -- Google Vertex AI
            ('vertex-gemini-3-pro', 'vertex', 'premium', 0.00125, 0.005, TRUE, TRUE, TRUE, 5000),
            ('vertex-gemini-3-flash', 'vertex', 'budget', 0.00005, 0.0002, TRUE, TRUE, TRUE, 2000),
            ('vertex-gemini-2.5-pro', 'vertex', 'standard', 0.00125, 0.005, TRUE, TRUE, TRUE, 5000),
            ('vertex-gemini-2.5-flash', 'vertex', 'budget', 0.000075, 0.0003, TRUE, TRUE, TRUE, 2000),
            ('vertex-gemini-2.5-flash-lite', 'vertex', 'budget', 0.00005, 0.0002, TRUE, TRUE, FALSE, 1500),
            ('vertex-claude-opus-4.5', 'vertex', 'premium', 0.015, 0.075, TRUE, TRUE, TRUE, 8000),
            ('vertex-claude-haiku-4.5', 'vertex', 'budget', 0.0002, 0.001, TRUE, TRUE, FALSE, 2000),
            ('vertex-claude-sonnet', 'vertex', 'standard', 0.003, 0.015, TRUE, TRUE, TRUE, 5000),
            ('vertex-deepseek-v3', 'vertex', 'budget', 0.00007, 0.00027, TRUE, TRUE, FALSE, 3000),
            -- Azure OpenAI
            ('azure-gpt-5.2', 'azure', 'premium', 0.003, 0.012, TRUE, TRUE, TRUE, 6000),
            ('azure-gpt-5.1', 'azure', 'premium', 0.002, 0.008, TRUE, TRUE, TRUE, 5000),
            ('azure-gpt-4.1', 'azure', 'premium', 0.002, 0.008, TRUE, TRUE, TRUE, 5000),
            ('azure-gpt-4.1-nano', 'azure', 'budget', 0.0001, 0.0004, TRUE, TRUE, FALSE, 2000),
            ('azure-o4-mini', 'azure', 'standard', 0.003, 0.012, TRUE, TRUE, FALSE, 5000),
            ('azure-o3', 'azure', 'premium', 0.01, 0.04, TRUE, TRUE, FALSE, 10000),
            ('azure-o3-mini', 'azure', 'standard', 0.003, 0.012, TRUE, TRUE, FALSE, 5000),
            ('azure-o1', 'azure', 'premium', 0.015, 0.06, TRUE, TRUE, FALSE, 10000),
            ('azure-gpt-4o', 'azure', 'standard', 0.0025, 0.010, TRUE, TRUE, TRUE, 5000),
            ('azure-gpt-4o-mini', 'azure', 'budget', 0.00015, 0.0006, TRUE, TRUE, TRUE, 3000),
            -- Local (Ollama)
            ('llama-3.1-70b', 'ollama', 'standard', 0, 0, TRUE, FALSE, FALSE, 8000),
            ('llama-3.1-8b', 'ollama', 'budget', 0, 0, TRUE, FALSE, FALSE, 3000),
            ('mistral', 'ollama', 'budget', 0, 0, TRUE, FALSE, FALSE, 3000),
            ('codellama', 'ollama', 'budget', 0, 0, TRUE, FALSE, FALSE, 3000)
        ON CONFLICT (model_id) DO UPDATE SET
            provider = EXCLUDED.provider,
            tier = EXCLUDED.tier,
            cost_per_1k_input = EXCLUDED.cost_per_1k_input,
            cost_per_1k_output = EXCLUDED.cost_per_1k_output,
            supports_streaming = EXCLUDED.supports_streaming,
            supports_function_calling = EXCLUDED.supports_function_calling,
            supports_vision = EXCLUDED.supports_vision,
            default_latency_sla_ms = EXCLUDED.default_latency_sla_ms,
            updated_at = CURRENT_TIMESTAMP
    """)


def downgrade() -> None:
    op.execute("DELETE FROM model_routing_config")
