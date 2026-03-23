import json
import os
from typing import Any
from openai import OpenAI
from prompts import FLOWCHART_ALIGN_PROMPT

ALIGN_DEFAULT_MODEL = os.getenv("OPENAI_FLOW_ALIGN_MODEL", os.getenv("OPENAI_VISION_MODEL", "gpt-4o"))


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


def align_flowchart_with_llm(image_url: str, cv_struct: dict, semantic_nodes: dict) -> dict:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)

    max_chars = int(os.getenv("FLOW_ALIGN_PROMPT_MAX_CHARS", "20000"))
    payload = {
        "cv": cv_struct,
        "semantic": semantic_nodes
    }
    text_payload = json.dumps(payload, ensure_ascii=False)
    if len(text_payload) > max_chars:
        text_payload = text_payload[:max_chars]

    response = client.responses.create(
        model=ALIGN_DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": FLOWCHART_ALIGN_PROMPT},
                {"type": "input_text", "text": text_payload},
                {"type": "input_image", "image_url": image_url}
            ]
        }]
    )

    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from flowchart align model")
    text = _strip_json_fences(text)
    return json.loads(text)
