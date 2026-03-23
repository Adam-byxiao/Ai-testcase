import json
import os
from typing import Any, Dict
from openai import OpenAI
from prompts import FLOWCHART_VISION_PROMPT
import base64

VISION_DEFAULT_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

VISION_PROMPT = """
You are a senior UI/UX analyst. Analyze the UI screenshot and return a JSON object only.
Output must be valid JSON with the following shape:
{
  "summary": string,
  "components": [
    {
      "type": string,
      "label": string,
      "bbox": [x, y, w, h] | null,
      "bbox_units": "relative_0_1",
      "confidence": number
    }
  ],
  "layout": {"primary_structure": string, "notes": string}
}

Type taxonomy (choose exactly one):
["Text","Button","Input","Card","Image","Icon","List","Nav","Container","Chart","Toggle","Badge","Avatar","Table","Modal","Background","Other"]

Rules:
- Treat each visible layer-level UI element as a component (text labels, buttons, inputs, cards, tabs, icons, images).
- Use only the type taxonomy above. If unsure, use "Other".
- Provide up to 80 components when possible.
- Use relative bounding boxes where x,y,w,h are between 0 and 1 (relative to image width/height).
- If unsure about bbox, set it to null.
- Do not include any extra text outside JSON.
"""

FLOW_BANNER_PROMPT = """
You are a UI analyst. Identify all "Flow Banner" labels/titles in the screenshot.
Return ONLY valid JSON in the following shape:
{
  "banners": [
    {
      "label": string,
      "bbox": [x, y, w, h],
      "bbox_units": "relative_0_1",
      "confidence": number
    }
  ],
  "notes": string
}

Rules:
- A Flow Banner is a rectangular label/title strip that introduces a function section.
- The label text is the title of the Flow Banner.
- Use relative bounding boxes (0..1) for the full banner region (not just text).
- If unsure, still output your best estimate with lower confidence.
"""

def _load_prompt_file(filename: str, fallback: str) -> str:
    try:
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return fallback


FLOW_BANNER_GROUP_PROMPT = _load_prompt_file(
    "flow_banner_groups.md",
    "You are a UX analyst. Return JSON with groups/feature_label/banner_bbox/nodes/edges."
)

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


def parse_ui_from_image(image_url: str, model: str | None = None) -> Dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)
    response = client.responses.create(
        model=model or VISION_DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": VISION_PROMPT},
                {"type": "input_image", "image_url": image_url}
            ]
        }]
    )

    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from vision model")
    text = _strip_json_fences(text)
    return json.loads(text)


def parse_flowchart_from_image(image_url: str, model: str | None = None) -> Dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)
    response = client.responses.create(
        model=model or VISION_DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": FLOWCHART_VISION_PROMPT},
                {"type": "input_image", "image_url": image_url}
            ]
        }]
    )

    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from flowchart vision model")
    text = _strip_json_fences(text)
    return json.loads(text)


def parse_flow_banners_from_image(image_url: str, model: str | None = None) -> Dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)
    response = client.responses.create(
        model=model or VISION_DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": FLOW_BANNER_PROMPT},
                {"type": "input_image", "image_url": image_url}
            ]
        }]
    )
    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from flow banner vision model")
    text = _strip_json_fences(text)
    return json.loads(text)


def parse_flow_banner_groups_from_image(image_url: str, model: str | None = None) -> Dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)
    response = client.responses.create(
        model=model or VISION_DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": FLOW_BANNER_GROUP_PROMPT},
                {"type": "input_image", "image_url": image_url}
            ]
        }]
    )
    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from flow banner group model")
    text = _strip_json_fences(text)
    return json.loads(text)


def parse_flowchart_from_image_bytes(image_bytes: bytes, image_mime: str = "image/png", model: str | None = None) -> Dict[str, Any]:
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{image_mime};base64,{b64}"
    response = client.responses.create(
        model=model or VISION_DEFAULT_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": FLOWCHART_VISION_PROMPT},
                {"type": "input_image", "image_url": data_url}
            ]
        }]
    )

    text = _extract_text_from_response(response)
    if not text:
        raise ValueError("Empty response from flowchart vision model")
    text = _strip_json_fences(text)
    return json.loads(text)
