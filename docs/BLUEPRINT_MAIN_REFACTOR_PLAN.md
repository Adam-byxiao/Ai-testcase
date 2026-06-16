# Blueprint Main 重构方案

日期：2026-03-30
分支：`blueprint_main`
状态：执行方案

## 1. 重构目标

围绕以下核心主链进行一次面向领域的重构：

1. `Figma 流程图结构 -> 蓝图模式`
2. `蓝图模式 -> 流程图 + 流程树`
3. `流程图/树 -> 测试路径 + 测试点`
4. `测试路径/点 -> 测试用例集`

这次重构的重点不是先做“界面重写”或“仓库拆分”，而是先把核心流水线收敛成一个稳定、可测试、可扩展的主模块。

## 2. 当前问题

结合现有代码，当前主要问题如下：

1. 核心链路分散在 `main_api.py`、`figma_layer/`、`vision_parser.py`、`flowchart_*`、`blueprint_flow/backend/app.py` 等多个位置，职责交叉明显。
2. 上游识别、中间结构、下游测试生成之间缺少统一的数据协议。
3. `blueprint_flow` 与主工程共享部分能力，但边界还不够清楚，容易出现双实现和双维护。
4. 当前实现偏“接口驱动”和“功能堆叠”，后续做测试路径推导时会越来越依赖中间模型稳定性。
5. `main_api.py` 已经承担过多编排职责，不适合继续承接这条主链的演进。

## 3. 重构原则

### 3.1 先整合逻辑，再决定是否拆仓

本次重构先在当前仓库内完成领域整合，不立即拆成独立仓库。

### 3.2 按流水线阶段拆分，而不是按技术手段拆分

不按“OpenCV 模块”“LLM 模块”“Figma 模块”来组织，而按“输入归一化 -> 蓝图构建 -> 流程构建 -> 测试设计 -> 用例生成”来组织。

### 3.3 中间产物必须显式化

后续所有逻辑应围绕以下中间对象稳定演进：

1. `BlueprintSnapshot`
2. `FlowGraph`
3. `FlowTree`
4. `TestPathSet`
5. `TestPointSet`
6. `TestCaseSet`

### 3.4 API 只是外壳，核心逻辑要下沉到 service / domain

FastAPI 路由仅负责输入输出、鉴权、错误包装；领域转换逻辑不再直接堆在接口函数中。

## 4. 建议目录结构

建议新增一个统一主模块，例如 `blueprint_main/`，在当前仓库中作为核心流水线目录：

```text
blueprint_main/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── blueprint_routes.py
│   ├── flow_routes.py
│   └── testcase_routes.py
├── domain/
│   ├── __init__.py
│   ├── figma_input.py
│   ├── blueprint.py
│   ├── flow_graph.py
│   ├── flow_tree.py
│   ├── test_design.py
│   └── testcase.py
├── services/
│   ├── __init__.py
│   ├── ingest_service.py
│   ├── blueprint_builder.py
│   ├── flow_graph_builder.py
│   ├── flow_tree_builder.py
│   ├── test_path_builder.py
│   ├── test_point_builder.py
│   └── testcase_generator.py
├── adapters/
│   ├── __init__.py
│   ├── figma_adapter.py
│   ├── vision_adapter.py
│   ├── llm_adapter.py
│   └── snapshot_repository.py
├── prompts/
│   ├── blueprint_mapping.md
│   ├── flow_tree_reasoning.md
│   └── testcase_generation.md
├── mappers/
│   ├── __init__.py
│   ├── figma_to_blueprint.py
│   ├── blueprint_to_graph.py
│   ├── graph_to_tree.py
│   └── tree_to_test_design.py
└── tests/
    ├── test_ingest_service.py
    ├── test_blueprint_builder.py
    ├── test_flow_graph_builder.py
    ├── test_flow_tree_builder.py
    ├── test_test_path_builder.py
    └── test_testcase_generator.py
```

## 5. 核心领域模型

### 5.1 FigmaInputBundle

统一管理 Figma 输入层的数据：

- `file_key`
- `node_id`
- `raw_json`
- `image_url`
- `layer_links`
- `visual_nodes`
- `visual_edges`
- `meta`

作用：把来自 Figma JSON、视觉识别、Layer 关系、人工补充的数据先归一化。

### 5.2 BlueprintSnapshot

这是整个系统最关键的中间对象，建议作为第一优先级标准化：

- `meta`
- `nodes[]`
- `pins[]`
- `edges[]`
- `sections[]`
- `source_refs`

其中：

- `node` 代表蓝图卡片
- `pin` 代表节点上的输入/输出挂点
- `edge` 代表 pin 级连接

要求：

1. 能完整还原 UI 蓝图视图
2. 能被保存/加载
3. 能被后续 graph/tree 构建复用

### 5.3 FlowGraph

从蓝图快照中抽象出来的计算图：

- `nodes[]`
- `edges[]`
- `starts[]`
- `ends[]`
- `branches[]`
- `cycles[]`
- `entrypoints[]`

要求：

1. 不关心蓝图渲染细节
2. 关注流程连接关系
3. 能支持路径搜索和覆盖率分析

### 5.4 FlowTree

从 `FlowGraph` 中提炼出的主流程树：

- `root`
- `children`
- `branch_type`
- `merge_points`
- `depth`

作用：

1. 给 PRD 和测试设计提供可解释结构
2. 支持主流程 / 分支流程 / 异常流程区分

### 5.5 TestDesign

建议拆成两层：

1. `TestPath`
   - 从起点到终点的一条可执行路径
2. `TestPoint`
   - 每个路径上的关键验证点、断言点、状态转换点

这一步是把“流程结构”转为“测试设计结构”的关键桥梁，不建议直接从 FlowGraph 跳到 TestCase。

### 5.6 TestCaseSet

最终输出层：

- `case_id`
- `title`
- `path_id`
- `covered_nodes`
- `covered_edges`
- `preconditions`
- `steps`
- `assertions`
- `priority`
- `tags`

## 6. 模块职责

### 6.1 ingest_service

负责统一上游输入：

1. 拉取 Figma JSON
2. 获取图片
3. 解析 layer links
4. 读取视觉识别结果
5. 组装 `FigmaInputBundle`

### 6.2 blueprint_builder

负责将 `FigmaInputBundle` 转成 `BlueprintSnapshot`：

1. 节点识别
2. pin 识别
3. section 归类
4. 边关系标准化
5. 快照保存

这是现阶段最核心的模块。

### 6.3 flow_graph_builder

负责把蓝图快照转换成图结构：

1. 节点抽象
2. pin-to-node 映射
3. graph edge 生成
4. 起点/终点/分支/环检测

### 6.4 flow_tree_builder

负责把图结构折叠成可解释的流程树：

1. 主干识别
2. 分支展开
3. 合流点识别
4. 树结构生成

### 6.5 test_path_builder

负责枚举测试路径：

1. 主路径
2. 分支路径
3. 异常路径
4. 边界路径

### 6.6 test_point_builder

负责给每条路径打测试点：

1. 页面到达点
2. 状态切换点
3. 分支判定点
4. 输入校验点
5. 结果断言点

### 6.7 testcase_generator

负责从结构化设计生成测试用例：

1. 将 `TestPath + TestPoint` 转成结构化 case draft
2. 按模板或 LLM 补全文案
3. 输出标准测试用例集

## 7. API 重构建议

建议不要再继续扩大 `main_api.py`，而是新增独立路由组，逐步迁移。

### 第一阶段保留兼容接口

旧接口继续可用，但内部调用新 service。

### 第二阶段新增核心接口

建议新增如下接口：

1. `POST /api/blueprint-main/ingest`
   输入 Figma URL / file key / node id，返回 `FigmaInputBundle` 摘要

2. `POST /api/blueprint-main/build-blueprint`
   返回 `BlueprintSnapshot`

3. `POST /api/blueprint-main/build-graph`
   输入 snapshot，返回 `FlowGraph`

4. `POST /api/blueprint-main/build-tree`
   输入 graph，返回 `FlowTree`

5. `POST /api/blueprint-main/build-test-design`
   输入 graph/tree，返回 `TestPathSet + TestPointSet`

6. `POST /api/blueprint-main/generate-testcases`
   输入 test design，返回测试用例集

7. `GET /api/blueprint-main/snapshot/{id}`
   加载蓝图快照

8. `GET /api/blueprint-main/flow/{id}`
   加载 graph/tree 结果

## 8. 与现有代码的迁移映射

### 8.1 建议保留并迁移的代码来源

可优先迁移以下已有能力：

1. `figma_mcp.py`
2. `figma_image_exporter.py`
3. `vision_parser.py`
4. `figma_layer/figma_layer_links.py`
5. `figma_layer/flowchart_from_links.py`
6. `figma_layer/flow_banner_grouping.py`
7. `figma_layer/node_matcher.py`
8. `blueprint_flow/backend/app.py` 中关于 snapshot / flow graph 的逻辑
9. `blueprint_flow/backend/test_cycle_tree.py`

### 8.2 建议逐步淡化的入口

以下位置建议后续只保留兼容层，不再持续堆功能：

1. `main_api.py`
2. `blueprint_flow/backend/app.py`

### 8.3 迁移策略

不是复制代码，而是：

1. 先抽出标准 schema
2. 再把旧逻辑包装成 builder/service
3. 最后由新 API 调用新 service

## 9. 推荐执行顺序

### Phase 1：标准化蓝图快照

目标：确定 `BlueprintSnapshot` 结构，统一节点、pin、edge 规范。

交付物：

1. `domain/blueprint.py`
2. `services/blueprint_builder.py`
3. `snapshot_repository.py`
4. 快照单元测试

### Phase 2：统一 graph/tree 生成

目标：把快照稳定转换成 `FlowGraph` 和 `FlowTree`。

交付物：

1. `domain/flow_graph.py`
2. `domain/flow_tree.py`
3. `services/flow_graph_builder.py`
4. `services/flow_tree_builder.py`

### Phase 3：落地测试设计层

目标：引入 `TestPath` 和 `TestPoint`，不要直接从 tree 跳用例。

交付物：

1. `domain/test_design.py`
2. `services/test_path_builder.py`
3. `services/test_point_builder.py`

### Phase 4：输出测试用例集

目标：从结构化测试设计稳定生成用例集。

交付物：

1. `domain/testcase.py`
2. `services/testcase_generator.py`
3. `prompts/testcase_generation.md`

### Phase 5：接口和前端接入

目标：让主项目和蓝图前端都消费统一主链。

交付物：

1. `api/` 新路由
2. 旧接口兼容层
3. `blueprint_flow/frontend` 接入新接口

## 10. 测试策略

建议测试分三层：

### 10.1 Schema / Builder 单元测试

验证：

1. 输入归一化是否正确
2. snapshot 生成是否稳定
3. graph/tree 推导是否符合预期

### 10.2 夹具驱动集成测试

引入固定夹具：

1. Figma 原始 JSON
2. 视觉识别结果
3. 标准 snapshot
4. 预期 graph/tree

确保每次重构都可回归。

### 10.3 端到端流程测试

至少覆盖：

1. `Figma -> Blueprint`
2. `Blueprint -> Graph -> Tree`
3. `Graph/Tree -> TestDesign`
4. `TestDesign -> TestCases`

## 11. 分支工作方式建议

`blueprint_main` 分支建议作为这条核心流水线的主开发分支，后续短周期分支可从这里派生：

1. `blueprint_main`
   长期主分支，承接这条链路的集成

2. `feature/blueprint-schema`
   做领域 schema 和 snapshot 标准化

3. `feature/flow-graph-tree`
   做 graph/tree builder

4. `feature/test-design`
   做 path / point 推导

5. `feature/testcase-gen`
   做测试用例集生成

## 12. 近期落地建议

如果只做最关键的第一步，我建议接下来优先完成以下事项：

1. 新建 `blueprint_main/` 目录并放入 domain / services / adapters 基础骨架
2. 先定义 `BlueprintSnapshot`、`FlowGraph`、`FlowTree` 三个核心 schema
3. 把 `blueprint_flow/backend/app.py` 中快照与 graph 逻辑迁移为 service
4. 给这三个核心对象补一组 fixture 测试
5. 再开始补 `TestPath` 和 `TestPoint`

## 13. 最终判断

这部分代码已经足够形成一个独立领域主线，应该单独整合。

但最合理的路径不是立刻彻底拆仓，而是先在当前仓库内以 `blueprint_main` 为核心分支，完成：

1. 领域模型统一
2. 核心流水线收口
3. API 与前端逐步迁移
4. 测试基线建立

等这条主链稳定后，再决定是否把 `blueprint_main` 升级为独立子工程或独立仓库。
