# 蓝图流程实现方案（两阶段）

日期：2026-03-23  
负责人：Codex + 用户  
状态：草案

## 目标
构建 UE5 蓝图式 UI，把 Figma 结构转为可连线节点，支持人工连线与重组。

## 阶段 1：单节点蓝图（MVP）
### 目标
将单个 Figma 大节点渲染为一个 UE5 风格蓝图卡片，并拆分子项为 pin。

### 输入
- 单节点 Figma URL
- 后端 JSON

### 输出
- 一个蓝图卡片
- header + sections + pins
- 可视预览图

### 映射规则
- Node = Frame/Component
- Pin = 子层级
- Section = Fixed / Scroll / Main

### 样式
- 深色网格背景
- 节点卡片 + 标题栏
- 彩色 pin

---

## 阶段 2：多节点蓝图 + 连线
### 目标
渲染多个节点 + 支持手动连线

### 输入
- 父级节点 URL
- 多节点 JSON

### 输出
- 多节点蓝图
- 手动连线

### 规则
- L1 为节点
- L2 为 pin
- 支持拖动节点
- 保存连线

---

## 数据模型
### Node
- id, title, bbox, pins[], meta

### Pin
- id, label, type, side, node_id

### Edge
- from_pin, to_pin

---

## 前端模块
1. 数据加载
2. 画布
3. 节点渲染
4. pin 渲染
5. 连线
6. 交互控制

---

## 后端需求
- `GET /api/blueprint/node`
- `GET /api/blueprint/layers`
- `POST /api/blueprint/connections`

---

## 备注
- 优先满足可视化与人工连线
- 自动连线暂缓
