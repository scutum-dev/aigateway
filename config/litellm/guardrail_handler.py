"""
Gateway Guardrail - LiteLLM Custom Guardrail integration.

Runs LLM Guard input/output scanners and Presidio PII detection as
pre_call / post_call hooks inside the LiteLLM proxy.

Configuration is read from the ``guardrail_configs`` table (via asyncpg)
and cached in Redis for 60 s.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import redis.asyncio as aioredis

logger = logging.getLogger("gateway_guardrail")

# ---------------------------------------------------------------------------
# Lazy scanner imports (only loaded when first needed)
# ---------------------------------------------------------------------------
_llm_guard_loaded = False
_input_scanners_mod = None
_output_scanners_mod = None


def _ensure_llm_guard():
    global _llm_guard_loaded, _input_scanners_mod, _output_scanners_mod
    if _llm_guard_loaded:
        return
    from llm_guard import input_scanners as _in, output_scanners as _out  # noqa: N812
    _input_scanners_mod = _in
    _output_scanners_mod = _out
    _llm_guard_loaded = True


# ---------------------------------------------------------------------------
# Env config
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://litellm:litellm@postgres:5432/litellm",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
ENABLE_GUARDRAILS = os.getenv("ENABLE_GUARDRAILS", "true").lower() == "true"
CONFIG_CACHE_TTL = int(os.getenv("GUARDRAIL_CONFIG_CACHE_TTL", "60"))

# ---------------------------------------------------------------------------
# Connection pools (initialised lazily on first request)
# ---------------------------------------------------------------------------
_db_pool: Optional[asyncpg.Pool] = None
_redis: Optional[aioredis.Redis] = None

_pool_lock = asyncio.Lock()


async def _get_db_pool() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is None:
        async with _pool_lock:
            if _db_pool is None:
                _db_pool = await asyncpg.create_pool(
                    DATABASE_URL, min_size=1, max_size=5
                )
    return _db_pool


async def _get_redis() -> Optional[aioredis.Redis]:
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            await _redis.ping()
        except Exception:
            logger.warning("Guardrail: Redis unavailable, config caching disabled")
            _redis = None
    return _redis


# ---------------------------------------------------------------------------
# Scanner cache  (config-hash → scanner instances)
# ---------------------------------------------------------------------------
_scanner_cache: Dict[str, Tuple[List, List]] = {}


def _build_input_scanners(cfg: dict) -> list:
    """Build LLM Guard input scanners from a guardrail config dict."""
    _ensure_llm_guard()
    scanners = []
    if cfg.get("enable_prompt_injection"):
        threshold = float(cfg.get("prompt_injection_threshold", 0.90))
        scanners.append(
            _input_scanners_mod.PromptInjection(threshold=threshold)
        )
    if cfg.get("enable_toxicity"):
        threshold = float(cfg.get("toxicity_threshold", 0.70))
        scanners.append(_input_scanners_mod.Toxicity(threshold=threshold))
    if cfg.get("enable_secrets_detection"):
        scanners.append(_input_scanners_mod.Secrets())
    if cfg.get("enable_invisible_text"):
        scanners.append(_input_scanners_mod.InvisibleText())
    banned = cfg.get("banned_topics") or []
    if banned:
        scanners.append(_input_scanners_mod.BanTopics(topics=banned))
    return scanners


def _build_output_scanners(cfg: dict) -> list:
    """Build LLM Guard output scanners from a guardrail config dict."""
    _ensure_llm_guard()
    scanners = []
    if cfg.get("enable_toxicity"):
        threshold = float(cfg.get("toxicity_threshold", 0.70))
        scanners.append(_output_scanners_mod.Toxicity(threshold=threshold))
    if cfg.get("enable_malicious_urls"):
        scanners.append(_output_scanners_mod.MaliciousURLs())
    if cfg.get("enable_sensitive_output"):
        scanners.append(_output_scanners_mod.Sensitive())
    return scanners


def _get_scanners(cfg: dict) -> Tuple[list, list]:
    """Return cached (input_scanners, output_scanners) for the config."""
    key = cfg.get("id", "default")
    updated = str(cfg.get("updated_at", ""))
    cache_key = f"{key}:{updated}"

    if cache_key not in _scanner_cache:
        inp = _build_input_scanners(cfg)
        out = _build_output_scanners(cfg)
        _scanner_cache[cache_key] = (inp, out)

    return _scanner_cache[cache_key]


# ---------------------------------------------------------------------------
# Config loading (DB + Redis cache)
# ---------------------------------------------------------------------------

async def _get_config(team_id: Optional[str] = None) -> Optional[dict]:
    """Read the active guardrail config, preferring team assignment."""
    redis = await _get_redis()

    # Try Redis cache first
    cache_key = f"guardrail_config:{team_id or 'default'}"
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    pool = await _get_db_pool()
    async with pool.acquire() as conn:
        row = None

        # If team_id, look for assigned config
        if team_id:
            row = await conn.fetchrow("""
                SELECT gc.* FROM guardrail_configs gc
                JOIN team_guardrails tg ON tg.guardrail_config_id = gc.id
                WHERE tg.team_id = $1 AND gc.is_active = TRUE
                ORDER BY tg.priority DESC
                LIMIT 1
            """, team_id)

        # Fallback to default profile
        if not row:
            row = await conn.fetchrow("""
                SELECT * FROM guardrail_configs
                WHERE name = 'default' AND is_active = TRUE
            """)

        if not row:
            return None

        cfg = dict(row)
        # Serialise for cache (UUID / datetime → str)
        for k, v in cfg.items():
            if hasattr(v, "isoformat"):
                cfg[k] = v.isoformat()
            elif hasattr(v, "hex"):
                cfg[k] = str(v)

        if redis:
            try:
                await redis.set(cache_key, json.dumps(cfg), ex=CONFIG_CACHE_TTL)
            except Exception:
                pass

        return cfg


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

async def _log_event(
    event_type: str,
    scanner_name: str,
    risk_score: Optional[float] = None,
    action_taken: str = "blocked",
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    model: Optional[str] = None,
    details: Optional[dict] = None,
):
    try:
        pool = await _get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guardrail_events
                    (event_type, scanner_name, user_id, team_id, model,
                     risk_score, action_taken, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                event_type, scanner_name, user_id, team_id, model,
                risk_score, action_taken,
                json.dumps(details or {}),
            )
    except Exception as exc:
        logger.warning("Failed to log guardrail event: %s", exc)


# ---------------------------------------------------------------------------
# PII handling via Presidio
# ---------------------------------------------------------------------------

_presidio_analyzer = None
_presidio_anonymizer = None


def _get_presidio():
    global _presidio_analyzer, _presidio_anonymizer
    if _presidio_analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _presidio_analyzer = AnalyzerEngine()
        _presidio_anonymizer = AnonymizerEngine()
    return _presidio_analyzer, _presidio_anonymizer


def _anonymize_pii(text: str, entities: list, action: str = "anonymize") -> Tuple[str, list]:
    """Detect and optionally anonymize PII using Presidio."""
    analyzer, anonymizer = _get_presidio()
    results = analyzer.analyze(text=text, entities=entities, language="en")

    if not results:
        return text, []

    if action == "anonymize":
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text, [
            {"entity_type": r.entity_type, "score": round(r.score, 4),
             "start": r.start, "end": r.end}
            for r in results
        ]

    # action == "detect" — just report, don't modify
    return text, [
        {"entity_type": r.entity_type, "score": round(r.score, 4),
         "start": r.start, "end": r.end}
        for r in results
    ]


# ---------------------------------------------------------------------------
# LiteLLM Custom Guardrail class
# ---------------------------------------------------------------------------

try:
    from litellm.integrations.custom_guardrail import CustomGuardrail
    _BASE_CLASS = CustomGuardrail
except ImportError:
    # Fallback if running outside LiteLLM (e.g. unit tests)
    class _FallbackBase:  # type: ignore[no-redef]
        def __init__(self, **kwargs):
            pass
    _BASE_CLASS = _FallbackBase


class GatewayGuardrail(_BASE_CLASS):
    """Content-safety guardrail using LLM Guard + Presidio."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # ----- pre-call (input scanning) -----

    async def async_pre_call_hook(
        self,
        user_api_key_dict: dict,
        cache: Any,
        data: dict,
        call_type: str,
    ) -> Optional[Exception]:
        if not ENABLE_GUARDRAILS:
            return None

        team_id = data.get("metadata", {}).get("team_id")
        user_id = (
            data.get("metadata", {}).get("user_api_key_user_id")
            or data.get("user")
        )
        model = data.get("model", "")

        try:
            cfg = await _get_config(team_id)
        except Exception as exc:
            logger.warning("Guardrail config fetch failed, allowing: %s", exc)
            return None

        if cfg is None:
            return None

        messages = data.get("messages") or []
        combined_text = " ".join(
            m.get("content", "") for m in messages
            if isinstance(m.get("content"), str)
        )

        if not combined_text.strip():
            return None

        # --- PII detection/anonymization ---
        if cfg.get("enable_pii_detection"):
            pii_entities = cfg.get("pii_entities") or []
            pii_action = cfg.get("pii_action", "anonymize")

            if pii_entities:
                anonymized_text, pii_findings = _anonymize_pii(
                    combined_text, pii_entities, pii_action
                )
                if pii_findings:
                    await _log_event(
                        event_type="pii_detected",
                        scanner_name="presidio",
                        user_id=user_id,
                        team_id=team_id,
                        model=model,
                        risk_score=max(f["score"] for f in pii_findings),
                        action_taken=pii_action,
                        details={"entities": pii_findings},
                    )
                    if pii_action == "anonymize":
                        # Replace the last user message with anonymized text
                        for msg in reversed(messages):
                            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                                msg["content"] = anonymized_text
                                break

        # --- LLM Guard input scanners ---
        input_scanners, _ = _get_scanners(cfg)
        scanned_text = combined_text
        for scanner in input_scanners:
            scanner_name = type(scanner).__name__
            try:
                scanned_text, is_valid, score = scanner.scan(scanned_text)
            except Exception as exc:
                logger.warning("Scanner %s failed: %s", scanner_name, exc)
                continue

            if not is_valid:
                on_fail = cfg.get("on_fail", "block")
                await _log_event(
                    event_type="input_blocked",
                    scanner_name=scanner_name,
                    user_id=user_id,
                    team_id=team_id,
                    model=model,
                    risk_score=float(score) if isinstance(score, (int, float)) else None,
                    action_taken=on_fail,
                    details={"direction": "input"},
                )
                if on_fail == "block":
                    raise ValueError(
                        f"Request blocked by guardrail ({scanner_name}). "
                        "Your message was flagged by the content safety system."
                    )

        return None

    # ----- post-call (output scanning) -----

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: dict,
        response,
    ):
        if not ENABLE_GUARDRAILS:
            return response

        team_id = data.get("metadata", {}).get("team_id")
        user_id = (
            data.get("metadata", {}).get("user_api_key_user_id")
            or data.get("user")
        )
        model = data.get("model", "")

        # Extract output text
        output_text = ""
        try:
            choices = getattr(response, "choices", []) or []
            if choices:
                msg = getattr(choices[0], "message", None)
                if msg:
                    output_text = getattr(msg, "content", "") or ""
        except Exception:
            pass

        if not output_text.strip():
            return response

        try:
            cfg = await _get_config(team_id)
        except Exception:
            return response

        if cfg is None:
            return response

        _, output_scanners = _get_scanners(cfg)
        scanned_text = output_text
        for scanner in output_scanners:
            scanner_name = type(scanner).__name__
            try:
                scanned_text, is_valid, score = scanner.scan(scanned_text)
            except Exception as exc:
                logger.warning("Output scanner %s failed: %s", scanner_name, exc)
                continue

            if not is_valid:
                on_fail = cfg.get("on_fail", "block")
                await _log_event(
                    event_type="output_blocked",
                    scanner_name=scanner_name,
                    user_id=user_id,
                    team_id=team_id,
                    model=model,
                    risk_score=float(score) if isinstance(score, (int, float)) else None,
                    action_taken=on_fail,
                    details={"direction": "output"},
                )
                if on_fail == "block":
                    raise ValueError(
                        f"Response blocked by guardrail ({scanner_name}). "
                        "The model output was flagged by the content safety system."
                    )

        return response
