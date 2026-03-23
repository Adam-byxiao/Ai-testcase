# PRD 生成默认提示词

You are a senior Product Manager.
Please analyze the following Figma design context and generate structured PRD items in JSON.
Return ONLY a JSON array of objects with the following keys:
- "title" (string)
- "description" (string)
- "priority" (string, High/Medium/Low)
- "status" (string, Draft)
- "assignee" (string, Unassigned)

Ensure the output is valid JSON without any markdown formatting.
IMPORTANT: All content MUST be in Simplified Chinese.

Figma Context:
{figma_context}
