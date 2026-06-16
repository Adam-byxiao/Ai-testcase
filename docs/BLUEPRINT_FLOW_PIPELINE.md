# 蓝图流程管线方案（保存 → 图 → 树 → PRD）

日期：2026-03-23  
状态：草案

## 目标
将蓝图编辑结果变成可计算的流程结构，并最终输出 PRD 主流程。

---

## 第一步：蓝图数据保存

### 保存内容
- 节点（节点/子项/布局）
- 连线（pin 级连接）
- 元信息（文件、模式、时间）

### 文件结构
- 路径：`output/blueprint_snapshots/`
- 文件名：`{fileKey}_{nodeId}_{timestamp}.json`

### JSON 结构（示意）
```json
{
  "meta": {
    "file_key": "...",
    "node_id": "...",
    "mode": "A",
    "timestamp": "2026-03-23T12:00:00Z"
  },
  "nodes": [
    {
      "id": "node-id",
      "name": "Node Name",
      "bbox": [x,y,w,h],
      "sections": [
        {"title":"MAIN","pins":[{"id":"pin-id","name":"...","depth":1,"side":"left","bbox":[...]}]}
      ]
    }
  ],
  "edges": [
    {"from":"pin-id","to":"pin-id"}
  ]
}
```

### API
- `POST /api/blueprint/save`
- `GET /api/blueprint/snapshot/latest`

---

## 第二步：流程图生成

### 输入
- 蓝图快照

### 输出
- `flow_graph.json`

---

## 第三步：流程树生成

### 输入
- `flow_graph.json`

### 输出
- `flow_tree.json`

---

## 第四步：PRD 生成

### 输入
- `flow_tree.json`

### 输出
- PRD 主流程描述

---

## 备注
- 快照必须可完整还原
- 后续可加入 PRD 自动化
