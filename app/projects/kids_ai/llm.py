"""Direct provider calls. No prompt/response text is stored — only usage."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic
from google import genai
from google.genai import types
from openai import OpenAI

from app.projects.kids_ai.pricing import (
    MODEL_MODERATION_A,
    MODEL_MODERATION_B,
    MODEL_PRIMARY,
    MODEL_TITLE,
    costs_usd,
)

logger = logging.getLogger(__name__)

# Keep Pass 1 + Claude inside a typical 30s request window.
MODERATION_TIMEOUT_SECONDS = 12
PRIMARY_TIMEOUT_SECONDS = 16
TITLE_TIMEOUT_SECONDS = 10
MODERATION_MAX_TOKENS = 400
PRIMARY_MAX_TOKENS = 2048
TITLE_MAX_TOKENS = 80


class LlmResult:
    def __init__(self, model, text=None, input_tokens=None, output_tokens=None, error=None):
        self.model = model
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.error = error

    @property
    def ok(self):
        return self.error is None and bool((self.text or "").strip())


def _anthropic_output_text(response):
    """Join visible text blocks. Sonnet 5 thinking blocks often come first and have no .text."""
    parts = []
    for block in response.content or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", None) or "")
    return "".join(parts).strip()


def _anthropic_text(system, messages, model, max_tokens, timeout=PRIMARY_TIMEOUT_SECONDS):
    client = Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        timeout=timeout,
    )
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        # Sonnet 5 adaptive-thinks by default; thinking can consume max_tokens and
        # leave an empty first content block, which we treated as a failed reply.
        "thinking": {"type": "disabled"},
    }
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    text = _anthropic_output_text(response)
    if not text:
        block_types = [getattr(b, "type", "?") for b in (response.content or [])]
        logger.warning(
            "Kids AI Claude returned no text (stop=%s blocks=%s)",
            getattr(response, "stop_reason", None),
            block_types,
        )
    usage = response.usage
    return LlmResult(
        model=model,
        text=text,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )


def _openai_text(system, user_prompt, model, max_tokens, timeout=MODERATION_TIMEOUT_SECONDS):
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=timeout,
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_prompt})
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_tokens,
        # gpt-5.6-luna rejects "minimal"; "none" is the right setting for Pass 1 JSON.
        reasoning_effort="none",
    )
    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        logger.warning(
            "Kids AI OpenAI returned no text (finish=%s)",
            getattr(choice, "finish_reason", None),
        )
    usage = response.usage
    return LlmResult(
        model=model,
        text=text,
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
    )


def _gemini_output_text(response):
    """Prefer response.text; fall back to candidate parts if .text is empty or raises."""
    try:
        text = (getattr(response, "text", None) or "").strip()
        if text:
            return text
    except Exception:
        pass
    parts = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            piece = getattr(part, "text", None)
            if piece:
                parts.append(piece)
    return "".join(parts).strip()


def _gemini_text(prompt, model, max_tokens, json_mode=False, timeout=MODERATION_TIMEOUT_SECONDS):
    client = genai.Client(
        api_key=os.getenv("GOOGLE_API_KEY"),
        http_options=types.HttpOptions(timeout=int(timeout * 1000)),
    )
    config = types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    if json_mode:
        config.response_mime_type = "application/json"
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    text = _gemini_output_text(response)
    if not text:
        finish = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish = getattr(candidates[0], "finish_reason", None)
        logger.warning("Kids AI Gemini returned no text (finish=%s)", finish)
    usage = getattr(response, "usage_metadata", None)
    return LlmResult(
        model=model,
        text=text,
        input_tokens=(getattr(usage, "prompt_token_count", None) if usage else None),
        output_tokens=(
            getattr(usage, "candidates_token_count", None) if usage else None
        ),
    )


def _safe_call(fn, model, *args, **kwargs):
    try:
        return fn(*args, model=model, **kwargs)
    except Exception as exc:
        logger.exception("Kids AI LLM call failed (%s)", model)
        return LlmResult(model=model, error=str(exc)[:500])


def call_primary(system, history_messages):
    """Claude: full conversation. history_messages are {role, content} user/assistant."""
    return _safe_call(
        _anthropic_text,
        MODEL_PRIMARY,
        system,
        history_messages,
        max_tokens=PRIMARY_MAX_TOKENS,
        timeout=PRIMARY_TIMEOUT_SECONDS,
    )


def call_moderation_a(prompt):
    return _safe_call(
        _gemini_text,
        MODEL_MODERATION_A,
        prompt,
        max_tokens=MODERATION_MAX_TOKENS,
        json_mode=True,
        timeout=MODERATION_TIMEOUT_SECONDS,
    )


def call_moderation_b(prompt):
    return _safe_call(
        _openai_text,
        MODEL_MODERATION_B,
        None,
        prompt,
        max_tokens=MODERATION_MAX_TOKENS,
    )


def call_title(prompt):
    return _safe_call(
        _gemini_text,
        MODEL_TITLE,
        prompt,
        max_tokens=TITLE_MAX_TOKENS,
        timeout=TITLE_TIMEOUT_SECONDS,
    )


def run_moderation_pair(prompt):
    """Run both moderation models in parallel. Returns (result_a, result_b)."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(call_moderation_a, prompt)
        future_b = pool.submit(call_moderation_b, prompt)
        wait = MODERATION_TIMEOUT_SECONDS + 3
        try:
            result_a = future_a.result(timeout=wait)
        except Exception as exc:
            result_a = LlmResult(model=MODEL_MODERATION_A, error=str(exc)[:500])
        try:
            result_b = future_b.result(timeout=wait)
        except Exception as exc:
            result_b = LlmResult(model=MODEL_MODERATION_B, error=str(exc)[:500])
        return result_a, result_b


def usage_costs(model, input_tokens, output_tokens):
    return costs_usd(model, input_tokens, output_tokens)
