# 流程图 Prompt 模板（项目级）

本文档定义了“按项目定制”的流程图 Prompt 模板与筛选指导。

---

## 模板 A：camera_device（圆屏 + TV 显示）

### 背景
- 设备为 AI 摄像头，**主屏为圆形**（主要交互）。
- 系统可连接 **TV 屏幕**，**仅用于显示**（非交互）。
- 流程图节点应优先 **主设备圆屏状态**；TV 显示元素默认忽略，除非明确标注为控制。

### 节点筛选规则
- 优先选择 bbox **近似正方形**（w≈h）且尺寸大于阈值的容器。
- 优先选择名称/文本包含：`Joining`、`Recording`、`Initiating`、`Standby`、`Start`、`Listening`、`Processing`。
- **排除** TV 屏幕相关容器：
  - 名称包含 `TV`、`Display`、`Screen Mirroring`、`Cast`、`HDMI`。
  - 超宽比例（w/h >= 1.6），倾向 TV 布局。
- **排除** 装饰/背景层：`Background`、`Glow`、`Stroke`、`Mask`、`Shadow`。

### 节点语义优先级
- 识别圆屏上的 **状态切换**：
  - Countdown / Joining / Initiating / Recording
- 抽取核心组件：
  - Timer、Cancel 按钮、录音图标、波形点阵、Spinner、状态文案

### Prompt 模板（节点语义）
```
你正在分析一个“摄像头设备 UI”的流程图。
设备包含：
- 圆形主屏（主要交互）
- TV 显示屏（仅显示，不交互）
只把“圆形主屏”的状态视为流程节点。
TV 显示元素默认排除，除非明确标注为控制。

返回 JSON，节点仅包含圆形主屏状态。
对每个节点，推断状态与关键组件（倒计时、取消、录音图标、加载）。
若节点明显是 TV-only（超宽矩形、TV 标签），直接排除。
```

---

## 模板 B：web_ui（占位）

### 背景
- 标准 Web UI（矩形布局）。
- 流程节点通常为面板、卡片或页面。

### 节点筛选规则（占位）
- 优先选择大矩形容器。
- 优先 frame 名称：`Step`、`Page`、`Screen`、`Form`、`Confirm`、`Complete`。

### Prompt 模板（占位）
```
你正在分析一个 Web UI 的流程图。
优先选择代表页面或步骤的矩形节点。
忽略装饰背景与图标（除非表达状态）。
返回 JSON，包含节点标签与关键组件。
```

---

## 配置钩子（建议）
- `FLOW_NODE_INCLUDE_REGEX`
- `FLOW_NODE_IGNORE_REGEX`
- `FLOW_NODE_MIN_W`, `FLOW_NODE_MIN_H`
- `FLOW_NODE_ASPECT_RATIO_BIAS=circle|rect|mixed`
- `FLOW_NODE_TV_EXCLUDE_REGEX=TV|Display|Screen Mirroring|Cast|HDMI`

```
# 摄像头设备推荐默认值
FLOW_NODE_ASPECT_RATIO_BIAS=circle
FLOW_NODE_TV_EXCLUDE_REGEX=TV|Display|Screen Mirroring|Cast|HDMI
```
