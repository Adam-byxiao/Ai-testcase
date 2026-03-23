# Figma 视觉优化方案

## 背景
当前视觉解析与 JSON 解析在类型体系上不一致，导致重叠度接近 0，视觉结果对融合影响很有限。阶段 1 的目标是对齐类型体系，并通过 Prompt 约束模型输出，使视觉结果在融合中真正生效。

## 阶段 1（当前执行）：类型对齐 + Prompt 约束

### 目标
- 将 JSON（Figma 节点类型）与视觉输出（UI 语义）归一到同一类型体系。
- 强制视觉模型只输出该类型体系中的类型。
- 指标对比使用归一化类型（而非原始 Figma 类型）。
- 融合 Prompt 明确优先语义对齐。

### 交付物
1. **共享类型体系**
   - 定义统一 UI 类型（如 Text、Button、Input、Card、Icon、Image、List、Nav、Container 等）。
   - 将 Figma 节点类型映射到该体系（规则映射）。
   - 将视觉模型标签归一到同一体系（同义词归一）。

2. **视觉 Prompt 更新**
   - 输出 type 只能来自类型列表。
   - 强制 layer 级组件输出并限制数量。
   - 采用相对 bbox（若可行）。

3. **融合 Prompt 更新**
   - 明确提及类型体系。
   - 要求融合前对 JSON 节点进行类型归一。

4. **指标更新**
   - 统计归一化类型的重叠度。
   - 在 API 响应中输出归一化统计，便于调试。

### 需要改动的文件（阶段 1）
- `D:\work\Repository\Ai-testcase\vision_parser.py`
- `D:\work\Repository\Ai-testcase\prompts.py`
- `D:\work\Repository\Ai-testcase\semantic_metrics.py`

## 阶段 2（下一步）：视觉叠加与层级匹配
- 将视觉 bbox 叠加到截图。
- 展示 JSON layer 的 bbox 并可视化匹配对。
- 在 UI 中显示置信度与不匹配提示。

## 阶段 3（后续）：按 Frame 多图融合
- 按 frame 导出图片。
- 对每个 frame 运行视觉解析。
- 合并为全局语义树。
