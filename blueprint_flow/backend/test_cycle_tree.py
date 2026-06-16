#!/usr/bin/env python
"""
测试工具：验证循环流程图的树构建逻辑
用法: python test_cycle_tree.py
"""

import json
import sys
from app import _build_flow_tree_with_cycles, _find_sccs, _find_cycle_blocks

def print_tree(node, indent=0):
    """递归打印树结构"""
    prefix = "  " * indent
    node_id = node.get("id", "?")
    node_type = node.get("type", "normal")
    is_exit = node.get("exit", False)
    cycle_id = node.get("entry_of")

    if node_type == "cycle_node":
        if cycle_id is not None:
            print(f"{prefix}├─ [{node_id}] (cycle block #{cycle_id}, entry)")
        else:
            print(f"{prefix}├─ [{node_id}] (cycle_node)")
    elif is_exit:
        print(f"{prefix}├─ [{node_id}] (EXIT)")
    else:
        print(f"{prefix}├─ [{node_id}]")

    for child in node.get("children", []):
        print_tree(child, indent + 1)


def test_case(name, graph):
    """执行一个测试用例"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    print(f"\n图结构:")
    print(f"  节点: {[n['id'] for n in graph['nodes']]}")
    print(f"  边: {[(e['from'], e['to']) for e in graph['edges']]}")

    # 分析 SCC
    adj = {}
    for n in graph["nodes"]:
        adj[n["id"]] = []
    for e in graph["edges"]:
        if e["from"] in adj:
            adj[e["from"]].append({"id": e["to"], "pins": e.get("pins", [])})

    scc_map, scc_list = _find_sccs(graph["nodes"], adj)
    print(f"\nSCC 分析:")
    print(f"  SCC数量: {len(scc_list)}")
    for i, scc in enumerate(scc_list):
        print(f"  SCC#{i}: {scc}")

    cycles = _find_cycle_blocks(scc_list, adj)
    print(f"  循环块: {list(cycles.keys())}")

    # 构建树
    result = _build_flow_tree_with_cycles(graph)

    print(f"\n构建结果:")
    print(f"  根节点: {result['roots']}")
    print(f"  循环数: {result['stats'].get('cycle_count', 0)}")
    print(f"  循环块详情:")
    for cid, block in result.get("cycles", {}).items():
        print(f"    #{cid}: entry={block['entry']}, internal={block['internal']}")
        print(f"           exits=[{[(e['from'], e['to']) for e in block['exits']]}]")

    print(f"\n树结构:")
    for tree in result["trees"]:
        print_tree(tree)

    return result


def main():
    # 测试1: 简单链式（无循环）
    test_case("1. 简单链式 A → B → C", {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"}
        ]
    })

    # 测试2: 简单循环 A → B → A
    test_case("2. 简单循环 A ↔ B", {
        "nodes": [{"id": "A"}, {"id": "B"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "A"}
        ]
    })

    # 测试3: 带出口的循环 A → [B ↔ C] → D
    test_case("3. 带出口的循环 A → B → C → B (出口到D)", {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
            {"from": "C", "to": "B"},  # 循环回去
            {"from": "C", "to": "D"}    # 出口到D
        ]
    })

    # 测试4: 自环
    test_case("4. 自环节点 A", {
        "nodes": [{"id": "A"}],
        "edges": [
            {"from": "A", "to": "A"}
        ]
    })

    # 测试5: 多层嵌套循环
    #   A → B → C → B (内循环)
    #   B → D → B (外循环)
    test_case("5. 嵌套循环", {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
            {"from": "C", "to": "B"},  # B↔C 循环
            {"from": "B", "to": "D"},
            {"from": "D", "to": "B"}   # B↔D 循环（与上面共享B）
        ]
    })

    # 测试6: 菱形结构（有公共节点但无循环）
    test_case("6. 菱形结构 A → B/C → D", {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
            {"from": "B", "to": "D"},
            {"from": "C", "to": "D"}
        ]
    })

    # 测试7: 选择分支循环（常见场景）
    #   开始 → 添加商品 → 继续添加? → [是] → 添加商品
    #                            → [否] → 结账 → 结束
    test_case("7. 选择分支循环（典型购物流程）", {
        "nodes": [{"id": "开始"}, {"id": "添加商品"}, {"id": "继续添加?"}, {"id": "结账"}, {"id": "结束"}],
        "edges": [
            {"from": "开始", "to": "添加商品"},
            {"from": "添加商品", "to": "继续添加?"},
            {"from": "继续添加?", "to": "添加商品", "pins": [{"name": "是/继续"}]},  # YES loop
            {"from": "继续添加?", "to": "结账", "pins": [{"name": "否/结束"}]},       # NO exit
            {"from": "结账", "to": "结束"}
        ]
    })

    # 测试8: 复杂选择（多选择互连）
    test_case("8. 复杂选择互连", {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
            {"from": "B", "to": "C"},
            {"from": "C", "to": "B"},  # B↔C 互连
            {"from": "B", "to": "D"},
            {"from": "C", "to": "D"}
        ]
    })

    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()
