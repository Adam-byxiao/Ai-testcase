# Structured FlowTree 设计方案

日期：2026-03-31
状态：设计稿
适用分支：`blueprint_main`

## 1. 目标

我们并不追求把流程图强行转换成标准二叉树或普通树。

真正目标是将 `FlowGraph` 转换成一种**结构化流程树**，用于：

1. 测试流程分析
2. 测试 PRD 文档生成
3. 测试点提炼
4. 测试路径枚举
5. 子流程和回路的可解释表达

因此，这里的 “FlowTree” 更接近：

- 控制流结构树
- 语义流程树
- AST 风格流程表示

而不是传统图论意义上的普通树。

## 2. 总体思想

### 2.1 图先是图，树只是结构化表达

原始流程是一个有向图，其中可能包含：

1. 顺序流
2. 条件分支
3. 汇合
4. 回路
5. 嵌套子回路

这类结构无法自然表示为普通树。

所以正确做法不是“硬拆成树”，而是：

1. 先识别流程图中的结构块
2. 再将结构块组织成树状语义结构

### 2.2 回路不展开，而是提升为语义节点

例如：

- `A -> B`
- `B -> C`
- `C.cancel -> A`

这不应被拆成无限展开的树，也不应简单断边。

而应表示成：

```text
Loop(entry=A)
  Body:
    Sequence
      A
      B
      C
  BackEdges:
    C.cancel -> A
```

## 3. 推荐节点类型

建议 `FlowTree` 使用以下结构节点：

### 3.1 `step`

表示单个业务步骤或界面节点。

示例：

- 输入 setup code
- 点击 next
- 选择 bot

推荐字段：

```json
{
  "type": "step",
  "id": "node-A",
  "title": "Enter setup code",
  "meta": {}
}
```

### 3.2 `sequence`

表示顺序执行的一组步骤。

示例：

- `A -> B -> C`

推荐字段：

```json
{
  "type": "sequence",
  "children": []
}
```

### 3.3 `branch`

表示条件分支。

示例：

- 是否继续
- 是否成功
- 是否授权

推荐字段：

```json
{
  "type": "branch",
  "id": "decision-X",
  "title": "是否继续?",
  "branches": [
    {
      "label": "yes",
      "child": {}
    },
    {
      "label": "no",
      "child": {}
    }
  ]
}
```

### 3.4 `loop`

表示一个带回路的结构块。

示例：

- 取消返回上一步
- 重试流程
- 重复录入

推荐字段：

```json
{
  "type": "loop",
  "entry": "A",
  "members": ["A", "B", "C"],
  "body": {},
  "back_edges": [],
  "exit_edges": []
}
```

### 3.5 `merge`

表示多个分支重新汇合。

这个节点不一定总要显式输出，但在分析测试路径和文档结构时很有用。

推荐字段：

```json
{
  "type": "merge",
  "id": "merge-Y",
  "sources": ["B1", "B2"],
  "target": "D"
}
```

### 3.6 `subflow`

表示一个局部子流程块。

适用于：

1. 独立功能段
2. 可复用模块
3. 嵌套的子回路区域

推荐字段：

```json
{
  "type": "subflow",
  "title": "设备绑定流程",
  "child": {}
}
```

## 4. 推荐树结构

最终树可以是一个递归结构：

```json
{
  "type": "sequence",
  "children": [
    {
      "type": "step",
      "id": "start"
    },
    {
      "type": "loop",
      "entry": "A",
      "members": ["A", "B", "C"],
      "body": {
        "type": "sequence",
        "children": [
          {"type": "step", "id": "A"},
          {"type": "step", "id": "B"},
          {"type": "step", "id": "C"}
        ]
      },
      "back_edges": [
        {"from": "C", "to": "A", "label": "cancel"}
      ],
      "exit_edges": [
        {"from": "C", "to": "D", "label": "continue"}
      ]
    },
    {
      "type": "step",
      "id": "D"
    }
  ]
}
```

## 5. 图到结构树的转换步骤

## 5.1 输入

输入是标准化后的 `FlowGraph`：

```json
{
  "nodes": [],
  "edges": []
}
```

边可以带 label / pin / source 信息。

## 5.2 第一步：识别强连通分量 SCC

使用经典算法：

1. Tarjan SCC
2. 或 Kosaraju

用途：

1. 找到所有回路区域
2. 找到嵌套或局部闭环结构

规则：

- `|SCC| > 1` 是循环块
- 单节点自环也是循环块

## 5.3 第二步：缩点

将每个非平凡 SCC 压缩成一个超级节点。

得到的图是一个 DAG。

这一步非常关键，因为：

1. DAG 更容易构建主流程结构
2. 回路块可以作为单独语义节点处理

## 5.4 第三步：在 DAG 上识别主结构

在 DAG 上识别以下模式：

1. 顺序段
2. 分支
3. 汇合
4. 子流程边界

然后组装成 `sequence / branch / merge / subflow`

## 5.5 第四步：展开循环块

对每个 SCC 形成的超级节点，构建 `loop` 结构。

需要识别：

1. `entry`
   从循环外进入循环的入口点

2. `members`
   SCC 内全部节点

3. `back_edges`
   从循环内部返回入口或前序节点的边

4. `exit_edges`
   从循环内部流向外部的边

5. `body`
   对循环内部再做一次结构化

## 5.6 第五步：生成结构化树

将 DAG 主结构和循环块结构合并，输出 `Structured FlowTree`。

## 6. 经典算法选择建议

### 6.1 基础方案：SCC + 缩点 + DAG 结构化

这是当前最推荐的工程方案。

优点：

1. 实现稳定
2. 容易调试
3. 容易与当前 `FlowGraph -> FlowTree` 重构兼容
4. 对大多数 UI 流程图已经足够

适合先落地。

### 6.2 增强方案：Dominator + Back Edge + Natural Loop

在控制流图领域，更经典的方法是：

1. 先构建 dominator tree
2. 再识别 back edge
3. 若 `v dominates u`，则 `u -> v` 为回边
4. 由回边推导 natural loop

优点：

1. 更适合准确定位 loop head
2. 更适合处理嵌套循环
3. 更符合经典 CFG 结构化方法

缺点：

1. 实现复杂度更高
2. 需要先定义唯一入口或超级入口

建议：

- 第一阶段使用 `SCC + DAG`
- 第二阶段若 loop head 识别精度不够，再补 `dominator` 增强

## 7. 针对子回路的处理

## 7.1 典型例子

图结构：

- `A -> B`
- `B -> C`
- `C.cancel -> A`
- `C.next -> D`

推荐结构化结果：

```text
Sequence
  Loop(entry=A)
    Body:
      Sequence
        A
        B
        C
    BackEdges:
      C.cancel -> A
    ExitEdges:
      C.next -> D
  Step(D)
```

## 7.2 若子回路嵌在更大流程中

推荐表示为：

```text
Sequence
  Step(前置流程)
  Subflow(绑定流程)
    Loop(entry=A)
      Body:
        Sequence
          A
          B
          C
      BackEdges:
        C.cancel -> A
      ExitEdges:
        C.next -> D
  Step(后置流程)
```

## 7.3 不建议的做法

不建议：

1. 直接断开回边
2. 将回路无限展开成树
3. 将所有回边都简单标记成“异常”

这些做法都不利于后续测试路径和测试点分析。

## 8. 结构化规则表

### 8.1 顺序段

条件：

- 一个节点只有一个主要后继
- 后继只有一个主要前驱
- 中间不存在明显分支/汇合

输出：

- `sequence`

### 8.2 分支

条件：

- 一个节点有多个语义上可区分的出口
- 常见为 yes/no、continue/cancel、success/fail

输出：

- `branch`

### 8.3 汇合

条件：

- 多条分支路径最终进入同一节点

输出：

- `merge`
  或在树中隐式合并，但建议保留元信息

### 8.4 回路

条件：

- 非平凡 SCC
- 或 natural loop

输出：

- `loop`

### 8.5 难结构化区域

条件：

- 多入口 SCC
- 交叉回边
- 无法自然识别单一入口

输出建议：

- `subflow`
- `loop_region`

即承认这是一个复杂局部图，而不是强行变成漂亮树。

## 9. 对测试分析的价值

这种结构树特别适合测试工作，因为可以直接映射出：

### 9.1 测试路径

- 主路径
- 分支路径
- 回路路径
- 退出路径

### 9.2 测试点

- step 节点产生页面/状态断言点
- branch 节点产生条件覆盖点
- loop 节点产生重复/取消/返回覆盖点
- merge 节点产生状态恢复与收敛点

### 9.3 PRD 文档

PRD 更容易按结构化流程输出：

1. 主流程
2. 分支流程
3. 回退与取消流程
4. 异常处理流程

## 10. 建议的数据结构

建议后续 `FlowTree` 不再只保留：

- `roots`
- `trees`
- `cycles`

而是逐步升级为：

```json
{
  "type": "sequence",
  "children": [],
  "meta": {
    "entry": "start",
    "source_graph": "graph-id"
  }
}
```

具体子节点为：

1. `step`
2. `sequence`
3. `branch`
4. `loop`
5. `merge`
6. `subflow`

## 11. 建议实现顺序

### Phase 1

保留当前已有的：

1. SCC 检测
2. cycle block 提取
3. DAG roots / tree 展开

### Phase 2

新增结构化节点类型：

1. `sequence`
2. `loop`
3. `branch`

优先让输出从“普通树 + cycle 标记”升级到“结构树”

### Phase 3

补强：

1. merge 表达
2. loop entry 精准识别
3. dominator/back-edge 增强

### Phase 4

将结构树直接接入：

1. 测试路径分析
2. PRD 主流程生成
3. 测试点总结

## 12. 当前推荐结论

结合当前项目阶段，推荐采用：

1. `SCC + 缩点 + DAG 主结构`
2. 对 SCC 输出 `loop`
3. 对复杂局部图输出 `subflow/loop_region`
4. 后续再引入 `dominator + natural loop` 做增强

这套方案既符合经典算法思想，也足够贴合你们当前“流程图 -> 测试分析”的目标。

## 13. 一句话总结

我们不需要把流程图变成“标准树”，而是要把它变成：

**一种面向流程理解、测试分析和 PRD 生成的结构化流程树。**

在这个结构中：

1. 顺序是 `sequence`
2. 条件是 `branch`
3. 回路是 `loop`
4. 局部复杂区域是 `subflow`

这样才是后续测试设计最自然、最稳定的基础。
