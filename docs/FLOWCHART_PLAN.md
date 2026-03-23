# 流程图识别方案（JSON + 视觉）

## 目标
- 使用 Figma JSON + 视觉线索识别流程图节点及其语义。
- 识别节点之间的顺序/边。
- 分三步执行：1）节点语义 2）组件提取 3）边顺序。

## 约束
- 节点形态不限定为圆形，可能是多种形状。
- 必须以 Figma JSON 作为结构、位置与文本的来源。
- 视觉仅用于语义补充与图标/状态/波形/加载等线索识别。

## 阶段 1（优先执行）：节点语义
### 目标
- 对每个候选节点（container/frame/shape）输出：
  - 节点标签（可读）
  - 节点类型（state/action/decision/end/start）
  - 关键组件（text/button/icon/timer/spinner）
  - 置信度

### 输入
- Figma JSON 节点（layer 级，包含 bbox）
- 视觉截图（页面或 frame）
- 可选：视觉组件列表

### 输出（JSON）
```
{
  "nodes": [
    {
      "id": "n1",
      "label": "Joining (Countdown)",
      "kind": "state",
      "components": ["Timer(3)", "Cancel Button"],
      "bbox": [x, y, w, h],
      "confidence": 0.82
    }
  ]
}
```

### Prompt 增强
- 强制结合 JSON 结构 + 视觉线索
- 只允许 JSON 输出
- 每个容器输出一条节点记录

## 阶段 2：组件提取（细粒度）
- 在每个节点内部提取关键 UI 组件与角色。
- 使用 JSON 文本 + 视觉图标进行分类。

## 阶段 3：边顺序
- 边识别来源：
  - JSON 连接器（若存在）
  - 空间布局（左到右 / 上到下）
  - OpenCV 线/箭头检测
- 输出可选的边标签。

## 实施说明
- JSON 为主结构。
- 视觉只用于补充/消歧。
- 输出需受限于大小，避免上下文溢出。
