import json
import os
from typing import Any
from openai import OpenAI
from prompts import FIGMA_FUSION_PROMPT

FUSION_DEFAULT_MODEL = os.getenv("OPENAI_FUSION_MODEL", os.getenv("OPENAI_VISION_MODEL", "gpt-4o"))


def _extract_text_from_response(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text
    output = getattr(response, "output", None)
    if not output:
        return ""
    texts = []
    for item in output:
        if getattr(item, "type", None) == "message":
            for content in getattr(item, "content", []) or []:
                ctype = getattr(content, "type", None)
                if ctype in ("output_text", "text"):
                    texts.append(content.text)
    return "\n".join(texts)


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```json"):
        return t[7:-3].strip()
    if t.startswith("```"):
        return t[3:-3].strip()
    return t


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def fuse_ui_contexts(json_context: str, visual_context: str, model: str | None = None) -> str:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)
    max_chars = int(os.getenv("FUSION_MAX_CHARS", "50000"))
    json_context_trim = _truncate_text(json_context, max_chars)
    visual_context_trim = _truncate_text(visual_context, max_chars)
    prompt = FIGMA_FUSION_PROMPT.format(json_context=json_context_trim, visual_context=visual_context_trim)
    response = client.responses.create(
        model=model or FUSION_DEFAULT_MODEL,
        input=[{"role": "user", "content": prompt}]
    )
    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from fusion model")
    return _strip_json_fences(text)
