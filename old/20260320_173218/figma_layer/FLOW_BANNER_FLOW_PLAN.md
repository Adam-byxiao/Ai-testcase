# Flow Banner 分组与 PRD 转化方案

## 目标
识别 Figma 中的 Flow Banner 作为“二级功能标题”，并将其右侧的流程节点/箭头关联为该功能的流程，最终输出可直接转化为 PRD 条目的结构化结果。

## 输入来源
- JSON 层
  - `layer_links`：解析自箭头节点（如 `A -> B`）。
  - `layer_arrow_nodes`：包含箭头命名的原始节点列表。
  - `frames/instances`：用于定位节点与名称。
- 视觉层（Figma MCP）
  - `get_design_context`：结构化设计上下文（用于 name/层级）。
  - `get_screenshot`：整体画布截图（用于视觉识别 Flow Banner）。

## 核心策略
1. 使用多模态模型在截图中识别所有 Flow Banner 的视觉区域（bbox）。
2. 将每个 Flow Banner 右侧区域定义为该功能的“流程候选区域”。
3. 在 JSON 中筛选位于该区域内的节点与箭头关系。
4. 组合为 `feature -> flow` 的结构化分组结果。

## 绑定规则
- Flow Banner 作为功能标题，右侧区域作为对应流程。
- 箭头关系优先使用 `layer_links`（结构化关系）。
- 节点 bbox 落入区域内即归属该 Flow Banner。
- 如果节点同时命中多个 Flow Banner，选择水平距离最近的标题。

## 结构化输出
```
[
  {
    "feature_label": "Flow Banner 标题",
    "banner_bbox": [x, y, w, h],
    "nodes": ["Standby", "Joining", "Recording"],
    "edges": [{ "from": "Standby", "to": "Joining" }],
    "raw_arrows": ["Standby -> Joining", "..."]
  }
]
```

## PRD 转化规则
1. 功能标题 = `feature_label`
2. 主流程步骤 = 按 `edges` 拓扑顺序生成步骤
3. 子功能描述 = 节点名 + 状态描述（必要时由 LLM 补全）
4. 输出为 PRD 条目

## PRD 输出结构
```
{
  "title": "会议录音流程（Flow Banner 标题）",
  "description": "系统支持从 Standby -> Joining -> Recording 的完整流程...",
  "steps": ["Standby -> Joining", "Joining -> Recording"],
  "priority": "High",
  "status": "Draft",
  "assignee": "Unassigned"
}
```

## 实施顺序
1. 视觉识别 Flow Banner bbox（MCP 预览图）
2. 绑定右侧流程节点与箭头
3. 输出分组流程结构
4. 基于分组结构生成 PRD 条目
