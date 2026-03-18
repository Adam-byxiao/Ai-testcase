# prompts.py

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
