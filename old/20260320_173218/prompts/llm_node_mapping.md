# 视觉节点与 JSON 节点映射提示词

你是资深 UX 分析师。请将视觉节点与 JSON 节点进行语义映射，输出严格 JSON。

## 输入
视觉节点：
{visual_nodes}

JSON 节点：
{json_nodes}

## 输出格式
```
{
  "mappings": [
    {
      "visual_label": string,
      "json_name": string,
      "score": 0.0
    }
  ]
}
```

## 规则
- 优先按语义匹配（状态/功能含义），其次参考名称相似度。
- 如果视觉节点是状态（例如 “Recording in progress”），应映射到最接近的 JSON 状态名（例如 “Recording”）。
- 每个 visual_label 只能映射到一个 json_name。
- score 取 0~1，代表匹配置信度。
- 只输出 JSON，不要额外文本。
