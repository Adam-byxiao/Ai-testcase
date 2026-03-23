import json
import os
from typing import Any
from openai import OpenAI

CIRCLE_VERIFY_PROMPT = """
You are given an image crop of a camera device screen. Determine if this crop is a valid device screen state.
If it is a screen, extract the state label and key components.
Return JSON only:
{
  "is_screen": true/false,
  "label": "Start/Joining/Recording/Standby/Initiating/Other",
  "components": ["Timer","Cancel","Spinner","WaveDots",...]
}
"""


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


def verify_screen_crop(image_bytes: bytes, model: str | None = None) -> dict:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)

    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"

    response = client.responses.create(
        model=model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": CIRCLE_VERIFY_PROMPT},
                {"type": "input_image", "image_url": data_url}
            ]
        }]
    )

    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from screen verifier")
    text = _strip_json_fences(text)
    return json.loads(text)
