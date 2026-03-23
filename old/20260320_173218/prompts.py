# prompts.py
import os

DESIGN_TO_PRD_PROMPT = """
You are an expert Product Manager and UX Designer.
Your task is to analyze the following JSON structure, which represents a Figma design file.
The JSON contains hierarchical information about Screens (Frames), UI Elements (Text, Buttons), and Components.

### Input Data (Figma Structure):
{figma_context}

### Instructions:
1.  **Analyze the Structure**: Identify the main screens (Top-level Frames).
2.  **Identify Elements**: Look for interactive elements like Buttons (often INSTANCE or COMPONENT), Inputs, and Navigation links.
3.  **Infer Functionality**: Based on the text content (e.g., "Login", "Submit", "Error") and structure, infer the intended functionality.
4.  **Generate a PRD**: Create a Product Requirement Document in Markdown format.
5.  **Language**: The output MUST be in Simplified Chinese (zh-CN).

### Output Format (Markdown):
# 产品需求文档 (PRD)

## 1. 概述
[根据设计简要描述功能模块]

## 2. 用户流程
[描述用户在页面间的流转路径]

## 3. 页面详情
### [页面名称]
*   **元素**:
    *   [元素名称/文案]: [类型] - [描述]
*   **交互**:
    *   [动作]: [结果]
*   **逻辑**:
    *   [隐含的校验或状态变化]

(Repeat for all screens)
"""

PRD_TO_TEST_CASE_PROMPT = """
You are a Senior QA Engineer.
Your task is to generate a comprehensive set of test cases based on the provided Product Requirement Document (PRD).

### Input PRD:
{prd_content}

### Instructions:
1.  **Cover All Scenarios**: Include Happy Path (Success), Edge Cases (Errors, Empty States), and UI Validation.
2.  **Structure**: Output the test cases in a clear Markdown table.
3.  **Language**: The output MUST be in Simplified Chinese (zh-CN).

### Output Format (Markdown Table):
| 用例编号 | 测试场景 | 前置条件 | 测试步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-001 | [场景名称] | [前置条件] | 1. [步骤 1]<br>2. [步骤 2] | [预期结果] | High/Med/Low |

"""

FIGMA_FUSION_PROMPT = """
You are a senior UI/UX analyst. You are given two sources:
1) JSON structural context extracted from Figma
2) Visual context extracted from a screenshot

Your task is to merge them into a single JSON context that is closest to what a human sees.

Rules:
- Use the JSON structure as the skeleton.
- Use the visual context to correct, enrich, and fill missing components.
- If there is a conflict, prefer the visual interpretation.
- Output valid JSON only. No markdown or extra text.
- Normalize component types to this taxonomy:
  ["Text","Button","Input","Card","Image","Icon","List","Nav","Container","Chart","Toggle","Badge","Avatar","Table","Modal","Background","Other"]

JSON Context:
{json_context}

Visual Context:
{visual_context}
"""

FLOWCHART_VISION_PROMPT = """
You are a senior UX analyst. The input is a flowchart screenshot.
Extract the flowchart as JSON only (no markdown).

Return format:
{
  "nodes": [
    {"id": "n1", "label": "Start", "shape": "ellipse|rectangle|diamond|parallelogram|circle|hexagon|other"}
  ],
  "edges": [
    {"from": "n1", "to": "n2", "label": "Yes/No/..." }
  ]
}

Rules:
- Use only the listed shape values; if unsure use "other".
- If an edge label is not visible, use empty string.
- Deduplicate nodes with same label and shape if they refer to the same box.
- Keep ids stable within the response (n1, n2, ...).
"""

FLOWCHART_NODE_SEMANTIC_PROMPT = """
You are a senior UX analyst. Your task is to identify flowchart nodes and their semantics.
You are given two inputs:
1) Figma JSON structure (layer-level with bbox and text)
2) Visual context (screenshot + optional detected components)

Return JSON only with this shape:
{
  "nodes": [
    {
      "id": "n1",
      "label": "Human readable node label",
      "kind": "state|action|decision|start|end|other",
      "components": ["Timer(3)","Cancel Button", "..."],
      "bbox": [x, y, w, h],
      "confidence": 0.0
    }
  ]
}

Rules:
- Use JSON structure as the primary source for bbox and text.
- Use visual context to infer icons/state (spinner, recording, wave dots).
- Do not invent nodes not supported by JSON structure.
- Output valid JSON only, no markdown.
"""

FLOWCHART_ALIGN_PROMPT = """
You are a multimodal flowchart aligner.
You are given:
1) OpenCV structural detection (nodes/edges with bbox/shape)
2) LLM semantic nodes (labels/components)
3) The original screenshot

Your task: align and correct the flowchart.
Output JSON only:
{
  "nodes": [
    {"id":"n1","label":"Joining","kind":"state","bbox":[x,y,w,h], "components":[...]}
  ],
  "edges": [
    {"from":"n1","to":"n2","label":""}
  ],
  "notes": "short explanation"
}

Rules:
- Keep node count minimal; merge duplicates.
- Prefer OpenCV geometry for bbox/edge structure.
- Prefer semantic labels from LLM if consistent with image.
- If unsure, keep structure from OpenCV and label as "Unknown".
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


def get_prd_flow_banner_prompt() -> str:
    return _load_prompt_file(
        "prd_from_flow_banner.md",
        "Please generate PRD items in JSON."
    )


def get_prd_default_prompt() -> str:
    return _load_prompt_file(
        "prd_default.md",
        "Please generate PRD items in JSON."
    )


def get_node_mapping_prompt() -> str:
    return _load_prompt_file(
        "llm_node_mapping.md",
        "Return JSON mappings for visual nodes and json nodes."
    )
