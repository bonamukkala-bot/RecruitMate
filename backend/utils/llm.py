import os
import sys
import json
import re
import time
from datetime import datetime, timezone
from langchain_groq import ChatGroq
from config import Config
from utils.settings import get_settings
from utils.db import llm_usage_collection

class TokenBudgetExceededError(Exception):
    """Raised when a company exceeds its configured monthly token budget."""
    pass

def clean_reasoning_text(text: str) -> str:
    """Strips <think> and <thought> tags emitted by reasoning models and markdown code fences."""
    if not text:
        return ""
    cleaned = re.sub(r"<(think|thought)>[\s\S]*?</\1>", "", text, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", cleaned).strip()
    return cleaned

def extract_json_payload(text: str):
    """
    Robust JSON extractor:
    1. Strips reasoning blocks & markdown fences
    2. Searches for JSON object or array
    3. Parses via json.loads
    Returns dict/list on success, or None on failure.
    """
    if not text:
        return None
    cleaned = clean_reasoning_text(text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    
    # Check for markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except Exception:
            pass

    # Try array first if '[' appears before '{'
    bracket_pos = cleaned.find("[")
    brace_pos = cleaned.find("{")

    if bracket_pos != -1 and (brace_pos == -1 or bracket_pos < brace_pos):
        last_bracket = cleaned.rfind("]")
        if last_bracket > bracket_pos:
            try:
                return json.loads(cleaned[bracket_pos:last_bracket + 1].strip())
            except Exception:
                pass

    if brace_pos != -1:
        last_brace = cleaned.rfind("}")
        if last_brace > brace_pos:
            try:
                return json.loads(cleaned[brace_pos:last_brace + 1].strip())
            except Exception:
                pass

    return None

def get_company_monthly_tokens(company_id: str) -> int:
    """Calculates total tokens used by company in the current calendar month."""
    if not company_id:
        return 0
    try:
        now = datetime.now(timezone.utc)
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        pipeline = [
            {"$match": {"company_id": str(company_id), "ts": {"$gte": start_of_month}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_tokens"}}}
        ]
        agg = list(llm_usage_collection.aggregate(pipeline))
        return agg[0]["total"] if agg else 0
    except Exception as e:
        print(f"⚠️ [llm] Error aggregating token usage: {e}")
        return 0

def check_budget_limit(company_id: str, budget: int) -> tuple[bool, int, str]:
    """
    Checks if company token budget is exceeded.
    Returns (is_exceeded, used_tokens, status) where status is 'normal' | 'warning' | 'exceeded'.
    """
    try:
        budget_int = int(budget or 0)
    except (ValueError, TypeError):
        budget_int = 0

    if budget_int <= 0:
        return False, 0, "normal"
    
    used = get_company_monthly_tokens(company_id)
    percentage = (used / budget_int) * 100.0
    if percentage >= 100.0:
        return True, used, "exceeded"
    elif percentage >= 80.0:
        return False, used, "warning"
    return False, used, "normal"

def log_llm_usage(
    company_id: str | None,
    agent_name: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    success: bool
):
    """Safely logs an LLM call to llm_usage collection without breaking callers."""
    try:
        total_tokens = prompt_tokens + completion_tokens
        pricing = Config.GROQ_MODEL_PRICING.get(model, {"prompt": 0.20, "completion": 0.80})
        estimated_cost = (prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]) / 1_000_000.0

        usage_doc = {
            "company_id": str(company_id) if company_id else "global",
            "agent": agent_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "estimated_cost": round(estimated_cost, 6),
            "success": success,
            "ts": datetime.now(timezone.utc)
        }
        llm_usage_collection.insert_one(usage_doc)
    except Exception as log_err:
        print(f"⚠️ [llm] Usage logging failed (non-fatal): {log_err}")

def call_llm(
    company_id: str | None,
    agent_name: str,
    messages: list[dict],
    heavy: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    expect_json: bool = False,
    is_essential: bool = False,
    essential: bool | None = None,
    required_keys: set | list | None = None,
    output_language: str | None = None,
    tone: str | None = None,
    raise_on_budget_exceeded: bool = True,
    timeout: float | None = None
) -> dict:
    """
    Central LLM call dispatcher:
    - Resolves company settings (model, temperature, output language, tone, budget)
    - Enforces monthly token budget on non-essential calls
    - Automatically retries once on transient errors
    - Strips reasoning tokens (<think>/<thought>) and parses JSON cleanly
    - Logs prompt/completion tokens, latency, and estimated cost to MongoDB
    """
    if essential is not None:
        is_essential = essential

    settings = get_settings(company_id) if company_id else None
    ai_settings = settings.get("ai", {}) if settings else {}

    # Model resolution
    target_model = ai_settings.get("model_heavy" if heavy else "model_default")
    if not target_model or target_model not in Config.GROQ_ALLOWED_MODELS:
        target_model = Config.GROQ_MODEL_HEAVY if heavy else Config.GROQ_MODEL

    # Temperature & tokens
    temp = temperature if temperature is not None else ai_settings.get("temperature", 0.3)
    # Ensure sufficient token limit for reasoning models
    effective_max_tokens = max(max_tokens or (4096 if heavy else 2048), 2048)

    # Token budget check
    budget = ai_settings.get("monthly_token_budget", 0)
    if budget > 0 and not is_essential and company_id:
        exceeded, used, _ = check_budget_limit(company_id, budget)
        if exceeded:
            err_msg = f"Monthly AI token budget exceeded ({used:,} / {budget:,} tokens used). Non-essential AI operations are paused."
            if raise_on_budget_exceeded:
                raise TokenBudgetExceededError(err_msg)
            return {"success": False, "error": err_msg, "budget_exceeded": True}

    # Language and tone directives
    effective_lang = output_language or ai_settings.get("output_language", "English")
    effective_tone = tone or ai_settings.get("tone", "professional")

    final_messages = list(messages)
    directives = []
    if effective_lang and effective_lang != "English":
        directives.append(
            f"Language Directive: Generate candidate-facing responses in {effective_lang}."
            + (" Strictly retain all JSON property keys in standard English." if expect_json else "")
        )
    if effective_tone and effective_tone != "professional":
        directives.append(f"Tone Directive: Use a {effective_tone} communication tone.")

    if directives:
        directive_text = " ".join(directives)
        if final_messages and final_messages[0].get("role") == "system":
            final_messages[0] = {
                "role": "system",
                "content": final_messages[0]["content"] + f"\n\n{directive_text}"
            }
        else:
            final_messages.insert(0, {"role": "system", "content": directive_text})

    llm = ChatGroq(
        groq_api_key=Config.GROQ_API_KEY,
        model_name=target_model,
        temperature=temp,
        max_tokens=effective_max_tokens,
        timeout=float(timeout) if timeout is not None else 45.0
    )

    start_time = time.time()
    last_err = None
    response = None
    prompt_tokens = 0
    completion_tokens = 0

    # Transient retry (up to 2 attempts)
    for attempt in range(2):
        try:
            response = llm.invoke(final_messages)
            raw_content = response.content if hasattr(response, "content") else str(response)
            if isinstance(raw_content, list):
                # LangChain multi-part response
                raw_content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in raw_content)

            cleaned_content = clean_reasoning_text(raw_content)
            if not cleaned_content and attempt == 0:
                # Retry once if reasoning consumed all tokens or model gave empty response
                time.sleep(0.5)
                continue
            
            # Extract token metadata
            resp_meta = getattr(response, "response_metadata", {}) or {}
            usage_dict = resp_meta.get("token_usage", {}) or getattr(response, "usage_metadata", {}) or {}
            prompt_tokens = usage_dict.get("prompt_tokens", 0) or usage_dict.get("input_tokens", 0)
            completion_tokens = usage_dict.get("completion_tokens", 0) or usage_dict.get("output_tokens", 0)
            if not prompt_tokens:
                prompt_tokens = len(str(final_messages)) // 4
            if not completion_tokens:
                completion_tokens = len(raw_content) // 4

            latency_ms = int((time.time() - start_time) * 1000)

            # If expecting JSON, parse and validate
            if expect_json:
                parsed = extract_json_payload(raw_content)
                if required_keys:
                    missing = set(required_keys) - set(parsed.keys())
                    if missing:
                        raise ValueError(f"LLM omitted required keys: {sorted(list(missing))}")
                
                log_llm_usage(company_id, agent_name, target_model, prompt_tokens, completion_tokens, latency_ms, True)
                return {
                    "success": True,
                    "data": parsed,
                    "raw": raw_content,
                    "model": target_model,
                    "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
                }
            else:
                log_llm_usage(company_id, agent_name, target_model, prompt_tokens, completion_tokens, latency_ms, True)
                return {
                    "success": True,
                    "text": cleaned_content,
                    "raw": raw_content,
                    "model": target_model,
                    "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
                }

        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(0.5)
                continue

    # If both attempts failed
    latency_ms = int((time.time() - start_time) * 1000)
    log_llm_usage(company_id, agent_name, target_model, prompt_tokens, completion_tokens, latency_ms, False)
    print(f"❌ [call_llm] Agent '{agent_name}' call failed: {last_err}")
    return {
        "success": False,
        "error": str(last_err),
        "raw_response": getattr(response, "content", "") if response else ""
    }
