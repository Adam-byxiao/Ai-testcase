# Figma 识别模块化方案

## 目标
将 Figma 识别拆分为模块化流水线，从而有选择地处理 JSON 的相关子集。全量数据仍用于功能/PRD 提取，而流程图识别只关注与流程相关的节点。流程图管线使用 OpenCV 进行边/形状识别。

## 核心原则
- JSON 是主结构，视觉用于语义增强。
- 每个模块定义一个 **选择器**，只抽取所需的 JSON 子集。
- 各模块输出归一化结果并可缓存。
- 流程图管线用 OpenCV 进行形状/边检测，并通过 bbox 与 JSON 对齐。

---

## 流水线概览

### 0. JSON 采集与索引（基础层）
**目标：** 为全量 JSON 构建可复用索引，便于选择性查询。
**输出：**
- `node_index`: id -> {type, name, bbox, parent_id, children_ids}
- `text_index`: id -> {text, bbox, parent_id}
- `frame_index`: 顶层 frame/section 及其 bbox
- `component_index`: instance/component
- `line_index`: vector/line 节点（候选连线）

该基础索引在所有模块中共享。

---

### 1. 通用 UI 功能模块（全量 JSON）
**用途：** PRD/测试用例生成，全局功能抽取。
**选择器：** 全文档或指定 frames。
**输出：** UI 语义树 + 功能列表。

---

### 2. 流程图识别模块（选择性 JSON + 视觉 + OpenCV）
**用途：** 识别流程节点、组件与边。

**选择器：**
- 若提供 node_id 则优先使用；否则通过启发式定位流程图 frame：
  - frame 名包含关键词：`flow`、`diagram`、`journey`、`process`、`steps`、`sequence`
  - frame 内有大量箭头/连线或重复节点
  - 具备明显的从左到右对齐

**子步骤：**
1) **流程节点候选提取（JSON）**
   - 仅保留选定流程图 frame 内的顶层 frame/group。
   - 依据 bbox 尺寸阈值过滤。
   - 忽略 background/stroke 等装饰层。

2) **组件提取（JSON + 视觉）**
   - JSON：节点 bbox 内的文字。
   - 视觉：图标/加载圈/波形/录音等视觉线索。

3) **OpenCV 形状检测（节点验证）**
   - 检测矩形/菱形/圆形等形状。
   - 通过 bbox 重叠将形状与 JSON 节点匹配。

4) **OpenCV 边检测（流程顺序）**
   - 通过 Hough 线 + 箭头启发式找边。
   - 将边端点映射到最近的节点 bbox 中心。

5) **融合与输出**
   - 合并 JSON 节点标签 + 视觉语义 + OpenCV 边。
   - 输出标准化流程图 JSON。

**输出（流程图 JSON）：**
```
{
  "nodes": [
    {"id":"n1","label":"Joining (Countdown)","kind":"state","bbox":[...],"components":[...]}
  ],
  "edges": [
    {"from":"n1","to":"n2","label":""}
  ]
}
```

---

### 3. 组件库模块（选择性 JSON）
**用途：** 识别可复用组件/实例，便于 UI 复用与 QA 映射。
**选择器：** 仅 INSTANCE/COMPONENT 节点。
**输出：** 组件目录。

---

## 实施阶段

### Phase A（当前）
- 构建 JSON 索引与选择器。
- 流程图模块：节点候选提取 + OpenCV 边。
- 节点语义视觉 Prompt。

### Phase B
- 增加 OpenCV 形状检测与 JSON/视觉对齐。
- 使用 OCR 改善边标签。

### Phase C
- 跨模块融合（将流程图结果与 PRD 功能关联）。

---

## OpenCV 集成细节（流程图模块）
- **形状检测：** 轮廓 + 多边形拟合 + 圆度判断。
- **边检测：** Canny + HoughLinesP。
- **箭头检测（可选）：** 通过三角形轮廓识别箭头。
- **映射：** bbox 重叠 / 最近中心点匹配。

---

## 数据过滤规则（流程图）
- 仅包含选定 frame bbox 内节点。
- 排除名称匹配：`Background|BG|Stroke|Mask|Shadow|Glow`。
- 最小 bbox 尺寸阈值（可配置）。

---

## 建议配置
- `FLOW_NODE_MIN_W=200`
- `FLOW_NODE_MIN_H=200`
- `FLOW_NODE_IGNORE_REGEX=Background|BG|Stroke|Mask|Shadow|Glow`
- `FLOWCHART_MAX_NODES=50`

---

## 成功标准
- 能正确识别简单流程图的全部节点与顺序。
- 节点语义与可见文案/图标一致。
- 边顺序与箭头/空间顺序一致（左到右）。
