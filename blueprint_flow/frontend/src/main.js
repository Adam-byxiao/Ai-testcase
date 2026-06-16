import './style.css';

const app = document.getElementById('app');

app.innerHTML = `
  <div class="toolbar">
    <input id="backend" value="http://127.0.0.1:8010" placeholder="Legacy Backend URL" />
    <input id="blueprintBackend" value="http://127.0.0.1:8020" placeholder="Blueprint Main URL" />
    <input id="figmaUrl" placeholder="Figma URL (可选，优先解析)" />
    <input id="fileKey" placeholder="Figma file key" />
    <input id="nodeId" placeholder="node id (可选)" />
    <input id="scale" value="0.18" style="width:70px" />
    <button id="loadBtn">加载节点</button>
    <button id="blueprintBtn" class="secondary">蓝图节点</button>
    <button id="saveBtn" class="secondary">保存连线</button>
    <button id="undoEdgeBtn" class="secondary">撤销连线</button>
    <button id="snapshotSaveBtn" class="secondary">保存蓝图</button>
    <button id="snapshotLoadBtn" class="secondary">加载蓝图</button>
    <button id="layoutBtn" class="secondary">布局: 还原</button>
    <div class="status" id="status">idle</div>
  </div>
  <div class="workspace">
    <div class="leftbar">
      <div class="side-title">视图切换</div>
      <button id="navBlueprintBtn" class="nav-btn active">蓝图</button>
      <button id="navTreeBtn" class="nav-btn">流程树</button>
      <button id="navStructuredBtn" class="nav-btn">结构树</button>
      <button id="navGraphBtn" class="nav-btn">流程图</button>
    </div>
    <div class="canvas" id="canvas"></div>
    <div class="sidebar">
      <div class="side-title">Layer 深度</div>
      <div class="side-hint">仅用于调试显示层级密度</div>
      <div class="side-row">
        <label>Max Depth</label>
        <input id="layerDepth" type="range" min="1" max="6" value="1" />
        <span id="layerDepthVal">1</span>
      </div>
      <div class="side-row">
        <button id="applyDepth" class="secondary">应用深度</button>
      </div>
      <div class="side-title">蓝图分层模式</div>
      <div class="side-row">
        <select id="blueprintMode">
          <option value="A">A / L1为节点</option>
          <option value="B">B / 视觉合并</option>
          <option value="C">C / 语义合并</option>
        </select>
        <button id="layerBlueprintBtn" class="secondary">蓝图分层</button>
      </div>
      <div class="side-title">蓝图交互</div>
      <div class="side-row">
        <button id="pinLinkBtn" class="secondary mode-btn">连线</button>
        <button id="pinViewBtn" class="secondary mode-btn">查看</button>
      </div>
      <div class="side-row">
        <label style="width:72px;">查看展开</label>
        <select id="viewDepthSelect">
          <option value="1">Depth 1</option>
          <option value="2">Depth 2</option>
          <option value="3">Depth 3</option>
        </select>
      </div>
      <div class="side-row">
        <button id="combineEnableBtn" class="secondary mode-btn">节点组合</button>
        <button id="combineDecisionBtn" class="secondary mode-btn" disabled>组合判断流程节点</button>
      </div>
      <div class="side-title">蓝图快照</div>
      <div class="side-row">
        <button id="snapshotSaveBtn" class="secondary">保存</button>
        <button id="snapshotLoadBtn" class="secondary">加载</button>
      </div>
      <div class="side-title">流程生成</div>
      <div class="side-row">
        <button id="flowGraphBtn" class="secondary">生成流程图</button>
        <button id="flowTreeBtn" class="secondary">生成流程树</button>
      </div>
      <div class="side-row">
        <button id="viewMixedBtn" class="secondary">混合</button>
        <button id="viewGraphBtn" class="secondary">仅图</button>
        <button id="viewTreeBtn" class="secondary">仅树</button>
      </div>
      <div class="side-title">流程树</div>
      <div class="side-list" id="flowTreeList"></div>
      <div class="side-title">节点层级</div>
      <div class="side-list" id="layerList"></div>
    </div>
  </div>
`;

const canvas = document.getElementById('canvas');
let scene = null;
let edgesSvg = null;
const status = document.getElementById('status');
let nodes = [];
let connections = [];
let pinConnections = [];
let pendingPin = null;
let lastPinConnection = null;
let selected = null;
let layoutMode = 'absolute';
let lastGroups = [];
let blueprintMode = false;
let lastData = null;
let lastBlueprint = null;
let previewPopover = null;
let previewImg = null;
let previewBox = null;
let previewPins = [];
let previewVisible = false;
let lastBlueprintNode = null;
let lastBlueprintRootBBox = null;
let zoomLevel = 1;
let baseSceneWidth = null;
let baseSceneHeight = null;
let didCenterScroll = false;
let infiniteEnabled = false;
let recenterPending = false;
const infiniteMargin = 200;
const infiniteCanvasPad = 6000;
const minSceneBaseSize = infiniteCanvasPad * 2;
let lastCenterPad = infiniteCanvasPad;
let activeBlueprintNode = null;
let isDraggingNode = false;
let dragStart = { x: 0, y: 0, left: 0, top: 0 };
let dragDebugCount = 0;
let dragOverlay = null;
let currentBlueprintNodes = [];
let currentBlueprintDepth = null;
let flowGraph = null;
let flowTree = null;
let structuredFlowTree = null;
let flowViewMode = 'mixed';
let treeLayoutNodes = [];
let treeLayoutEdges = [];
let graphLayoutNodes = [];
let pinMode = 'link';
let pinMetaById = new Map();
let activeView = 'blueprint';
let combineMode = false;
let combineSelectedIds = new Set();
let popoverDragging = false;
let popoverDragStart = { x: 0, y: 0, left: 0, top: 0 };
let popoverLastPos = null;
let viewSelectedNodeId = null;
let viewDepthOverrides = {};
let canvasStateKey = 'blueprint_canvas_state_v1';

function getLegacyBackend() {
  return document.getElementById('backend').value.trim();
}

function getBlueprintBackend() {
  return document.getElementById('blueprintBackend').value.trim() || getLegacyBackend();
}

function getFlowNodeName(id) {
  if (flowGraph && Array.isArray(flowGraph.nodes)) {
    const n = flowGraph.nodes.find(x => x.id === id);
    if (n) return n.name || n.id;
  }
  const b = (currentBlueprintNodes || []).find(x => (x.id || x.name) === id);
  if (b) return b.name || b.id;
  return id;
}

function getBlueprintNodeById(nodeId) {
  if (!nodeId) return null;
  const list = currentBlueprintNodes || [];
  return list.find(n => String(n.id || n.name) === String(nodeId)) || null;
}

function isGenericContainerName(name) {
  if (!name) return false;
  return /^(group|frame)\s*\d+/i.test(String(name).trim());
}

function isDecisionText(text) {
  if (!text) return false;
  const n = String(text).toLowerCase();
  return n.includes('?') || n.includes(' if ') || n.includes('是否') || n.includes('判断') || n.includes('判定');
}

function getDecisionLabelFromNode(node) {
  const sections = node?.sections || [];
  for (const sec of sections) {
    for (const p of sec.pins || []) {
      if (isDecisionText(p.name)) return p.name;
    }
  }
  return null;
}

function getBlueprintDisplayName(node) {
  if (!node) return 'Node';
  const raw = node.name || 'Node';
  if (isGenericContainerName(raw)) {
    const decision = getDecisionLabelFromNode(node);
    if (decision) return decision;
  }
  return raw;
}

function injectDecisionPins(node, pins) {
  const decision = getDecisionLabelFromNode(node);
  if (!decision) return pins;
  const base = `decision-${node.id || node.name || 'node'}`;
  const virtuals = [
    { id: `${base}-in`, name: 'IN', side: 'left', depth: 0, virtual: true },
    { id: `${base}-yes`, name: 'YES', side: 'right', depth: 0, virtual: true },
    { id: `${base}-no`, name: 'NO', side: 'right', depth: 0, virtual: true }
  ];
  const existingNames = new Set((pins || []).map(p => p.name));
  return [...virtuals.filter(v => !existingNames.has(v.name)), ...(pins || [])];
}

function combineDecisionNodes() {
  if (!lastBlueprint) return;
  const ids = Array.from(combineSelectedIds);
  if (ids.length < 2) return;
  const selectedNodes = (currentBlueprintNodes || []).filter(n => ids.includes(String(n.id || n.name)));
  if (selectedNodes.length < 2) return;

  // capture current positions from DOM before re-render
  const posMap = {};
  document.querySelectorAll('.bp-node').forEach((el) => {
    const id = el.dataset.nodeId;
    if (!id) return;
    const left = parseFloat(el.style.left || '0');
    const top = parseFloat(el.style.top || '0');
    posMap[id] = { x: Number.isNaN(left) ? 0 : left, y: Number.isNaN(top) ? 0 : top };
  });

  let decisionText = null;
  let polygonPin = null;
  selectedNodes.forEach(n => {
    const pins = (n.sections || []).flatMap(s => s.pins || []);
    if (!decisionText) {
      const found = pins.find(p => isDecisionText(p.name));
      if (found) decisionText = found.name;
    }
    if (!polygonPin) {
      const foundPoly = pins.find(p => String(p.type).toUpperCase() === 'POLYGON' || /polygon/i.test(p.name || ''));
      if (foundPoly) polygonPin = foundPoly;
    }
  });

  const baseName = decisionText || (selectedNodes[0]?.name || 'Decision');
  const newId = `decision-${Date.now()}`;
  const avgPos = selectedNodes.reduce((acc, n) => {
    const id = String(n.id || n.name);
    const pos = posMap[id];
    if (pos) {
      acc.x += pos.x;
      acc.y += pos.y;
      acc.c += 1;
    }
    return acc;
  }, { x: 0, y: 0, c: 0 });

  const newNode = {
    id: newId,
    name: baseName,
    type: 'DECISION',
    bbox: selectedNodes[0]?.bbox || null,
    x: avgPos.c ? avgPos.x / avgPos.c : undefined,
    y: avgPos.c ? avgPos.y / avgPos.c : undefined,
    sections: [
      {
        title: 'MAIN',
        pins: [
          polygonPin ? { ...polygonPin, id: `${newId}-poly`, name: 'Polygon', side: 'left', depth: 0 } : null,
          decisionText ? { id: `${newId}-q`, name: decisionText, side: 'left', depth: 0, virtual: true } : null,
          { id: `${newId}-in`, name: 'IN', side: 'left', depth: 0, virtual: true },
          { id: `${newId}-yes`, name: 'YES', side: 'right', depth: 0, virtual: true },
          { id: `${newId}-no`, name: 'NO', side: 'right', depth: 0, virtual: true }
        ].filter(Boolean)
      }
    ]
  };

  const remain = (currentBlueprintNodes || []).filter(n => !ids.includes(String(n.id || n.name))).map(n => {
    const id = String(n.id || n.name);
    const pos = posMap[id];
    if (pos) return { ...n, x: pos.x, y: pos.y };
    return n;
  });
  remain.push(newNode);
  currentBlueprintNodes = remain;
  if (lastBlueprint && Array.isArray(lastBlueprint.nodes)) {
    lastBlueprint.nodes = remain;
  }
  // remove pin connections that referenced removed nodes' pins
  const removePrefix = new Set(ids.map(id => `node-${id}`));
  pinConnections = pinConnections.filter(c => {
    if (removePrefix.has(c.from) || removePrefix.has(c.to)) return false;
    if (ids.some(id => String(c.from || '').includes(id) || String(c.to || '').includes(id))) return false;
    return true;
  });
  const maxDepth = currentBlueprintDepth ?? getDepthValue();
  renderBlueprintMulti({ nodes: currentBlueprintNodes, figma: lastBlueprint?.figma }, maxDepth);
  renderLayerListBlueprintMulti({ nodes: currentBlueprintNodes }, maxDepth);
}

function updateGridPosition() {
  const x = -canvas.scrollLeft;
  const y = -canvas.scrollTop;
  canvas.style.setProperty('--grid-x', x + 'px');
  canvas.style.setProperty('--grid-y', y + 'px');
}
let previewTransform = { scale: 1, offsetX: 0, offsetY: 0, viewW: 280, viewH: 280 };

function setPinMode(nextMode) {
  pinMode = nextMode === 'view' ? 'view' : 'link';
  if (pinLinkBtn) pinLinkBtn.classList.toggle('active', pinMode === 'link');
  if (pinViewBtn) pinViewBtn.classList.toggle('active', pinMode === 'view');
  if (pinMode === 'view' && pendingPin) {
    const prev = scene?.querySelector(`[data-pin-id="${pendingPin}"]`);
    if (prev) prev.classList.remove('pin-selected');
    pendingPin = null;
  }
}

function applyViewDepthChange(depth) {
  if (!viewSelectedNodeId) return;
  const d = parseInt(depth, 10);
  if (!Number.isFinite(d)) return;
  viewDepthOverrides[viewSelectedNodeId] = d;
  const maxDepth = currentBlueprintDepth ?? getDepthValue();
  renderBlueprintMulti({ nodes: currentBlueprintNodes, figma: lastBlueprint?.figma }, maxDepth);
  renderLayerListBlueprintMulti({ nodes: currentBlueprintNodes }, maxDepth);
}

function buildSnapshotNodesForSave() {
  const maxDepth = currentBlueprintDepth ?? getDepthValue();
  const nodes = (currentBlueprintNodes || []).map((n) => {
    const override = viewDepthOverrides[String(n.id || n.name)];
    const limit = typeof override === 'number' ? override : maxDepth;
    const sections = (n.sections || []).map((sec) => {
      const pins = (sec.pins || []).filter((p) => {
        if (limit === null || limit === undefined) return true;
        return typeof p.depth === 'number' ? p.depth <= limit : true;
      });
      return { ...sec, pins };
    });
    return { ...n, sections };
  });
  return normalizeDecisionNodes(nodes, pinConnections);
}

function normalizeDecisionNodesForDisplay(nodes) {
  const normalized = normalizeDecisionNodes(nodes || [], []);
  return Array.isArray(normalized) ? normalized : (normalized.nodes || nodes || []);
}

function normalizeDecisionNodes(nodes, edges) {
  if (!nodes || nodes.length === 0) return nodes;
  const isDecisionPin = (name) => isDecisionText(name);
  const isPolygonPin = (p) => {
    if (!p) return false;
    const t = String(p.type || '').toUpperCase();
    return t === 'POLYGON' || /polygon/i.test(p.name || '');
  };
  const byId = new Map(nodes.map(n => [String(n.id || n.name), n]));
  const used = new Set();
  const result = [];
  const idMap = new Map(); // oldId -> newId (kept)
  const pinRedirectMap = new Map(); // oldPinId -> newPinId

  const decisionPortFromPin = (pin, mode = 'source') => {
    if (!pin) return mode === 'target' ? 'in' : null;
    const rawName = String(pin.name || pin.pin_name || '').trim().toLowerCase();
    const rawType = String(pin.type || '').trim().toUpperCase();
    if (rawName === 'yes' || rawName.includes(' yes')) return 'yes';
    if (rawName === 'no' || rawName.includes(' no')) return 'no';
    if (rawName === 'in' || rawName.includes('input')) return 'in';
    if (isDecisionPin(pin.name) || rawType === 'POLYGON' || /polygon/i.test(pin.name || '')) return 'in';
    if (mode === 'target') return 'in';
    if (rawName.includes('cancel') || rawName.includes('return') || rawName.includes('back') || rawName.includes('close')) return 'no';
    if (rawName.includes('next') || rawName.includes('continue') || rawName.includes('confirm') || rawName.includes('submit') || rawName.includes('ok')) return 'yes';
    if (String(pin.side || '').toLowerCase() === 'left') return 'in';
    return 'yes';
  };

  const registerDecisionPinRedirects = (sourceNode, mergedId) => {
    const pins = (sourceNode.sections || []).flatMap(s => s.pins || []);
    pins.forEach((pin) => {
      if (!pin?.id) return;
      const port = decisionPortFromPin(pin, 'source');
      if (!port) return;
      pinRedirectMap.set(String(pin.id), `${mergedId}-${port}`);
    });
    pinRedirectMap.set(`node-${sourceNode.id || sourceNode.name}`, `${mergedId}-in`);
  };

  nodes.forEach((n) => {
    const nid = String(n.id || n.name);
    if (used.has(nid)) return;
    const pins = (n.sections || []).flatMap(s => s.pins || []);
    const hasDecisionText = pins.some(p => isDecisionPin(p.name));
    if (hasDecisionText) {
      // try to find a sibling polygon-only node to merge
      const polyNode = nodes.find(other => {
        const oid = String(other.id || other.name);
        if (oid === nid || used.has(oid)) return false;
        const opins = (other.sections || []).flatMap(s => s.pins || []);
        const hasPoly = opins.some(isPolygonPin);
        const hasQuestion = opins.some(p => isDecisionPin(p.name));
        return hasPoly && !hasQuestion;
      });
      if (polyNode) {
        const opins = (polyNode.sections || []).flatMap(s => s.pins || []);
        const poly = opins.find(isPolygonPin);
        const question = pins.find(p => isDecisionPin(p.name));
        const baseId = `decision-${nid}`;
        const merged = {
          id: baseId,
          name: question?.name || n.name,
          type: 'DECISION',
          bbox: n.bbox || polyNode.bbox || null,
          sections: [
            {
              title: 'MAIN',
              pins: [
                poly ? { ...poly, id: `${baseId}-poly`, name: 'Polygon', side: 'left', depth: 0 } : null,
                question ? { ...question, id: `${baseId}-q`, side: 'left', depth: 0 } : null,
                { id: `${baseId}-in`, name: 'IN', side: 'left', depth: 0, virtual: true },
                { id: `${baseId}-yes`, name: 'YES', side: 'right', depth: 0, virtual: true },
                { id: `${baseId}-no`, name: 'NO', side: 'right', depth: 0, virtual: true }
              ].filter(Boolean)
            }
          ]
        };
        used.add(nid);
        used.add(String(polyNode.id || polyNode.name));
        idMap.set(nid, baseId);
        idMap.set(String(polyNode.id || polyNode.name), baseId);
        registerDecisionPinRedirects(n, baseId);
        registerDecisionPinRedirects(polyNode, baseId);
        result.push(merged);
        return;
      }
    }
    result.push(n);
  });
  if (!edges) return result;
  // remap edges to merged decision ids + pins
  const newEdges = edges.map((e) => {
    let from = e.from;
    let to = e.to;
    if (pinRedirectMap.has(String(from))) {
      from = pinRedirectMap.get(String(from));
    }
    if (pinRedirectMap.has(String(to))) {
      const redirected = pinRedirectMap.get(String(to));
      to = redirected.endsWith('-yes') || redirected.endsWith('-no')
        ? redirected.replace(/-(yes|no)$/, '-in')
        : redirected;
    }
    const fromNodeMatch = String(from || '').match(/^node-(.+)$/);
    const toNodeMatch = String(to || '').match(/^node-(.+)$/);
    const fromRaw = fromNodeMatch ? fromNodeMatch[1] : null;
    const toRaw = toNodeMatch ? toNodeMatch[1] : null;
    if (fromRaw && idMap.has(fromRaw)) {
      from = `${idMap.get(fromRaw)}-in`;
    } else if (idMap.has(String(from))) {
      from = `${idMap.get(String(from))}-in`;
    }
    if (toRaw && idMap.has(toRaw)) {
      to = `${idMap.get(toRaw)}-in`;
    } else if (idMap.has(String(to))) {
      to = `${idMap.get(String(to))}-in`;
    }
    return { ...e, from, to };
  });
  return { nodes: result, edges: newEdges };
}

function setCombineMode(enabled) {
  combineMode = enabled;
  if (combineEnableBtn) combineEnableBtn.classList.toggle('active', combineMode);
  if (combineDecisionBtn) combineDecisionBtn.disabled = !combineMode;
  if (combineMode) {
    // avoid view-mode interception while selecting nodes to combine
    setPinMode('link');
  }
  if (!combineMode) {
    combineSelectedIds.clear();
    document.querySelectorAll('.bp-node.bp-combine-selected').forEach(el => el.classList.remove('bp-combine-selected'));
    document.querySelectorAll('.bp-combine-mark').forEach(el => el.remove());
  }
}

function toggleCombineSelect(card) {
  const nodeId = card.dataset.nodeId;
  if (combineSelectedIds.has(nodeId)) {
    combineSelectedIds.delete(nodeId);
    card.classList.remove('bp-combine-selected');
    const mark = card.querySelector('.bp-combine-mark');
    if (mark) mark.remove();
  } else {
    combineSelectedIds.add(nodeId);
    card.classList.add('bp-combine-selected');
    if (!card.querySelector('.bp-combine-mark')) {
      const mark = document.createElement('span');
      mark.className = 'bp-combine-mark';
      mark.textContent = '✓';
      const header = card.querySelector('.bp-header');
      if (header) header.appendChild(mark);
    }
  }
}

function getDepthValue() {
  const el = document.getElementById('layerDepth');
  const val = el && el.value ? el.value : '2';
  return parseInt(val, 10);
}

function getLayerListEl() {
  return document.getElementById('layerList');
}

function initScene() {
  if (!scene) {
    scene = document.createElement('div');
    scene.className = 'scene';
    edgesSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    edgesSvg.setAttribute('id', 'edgesSvg');
    scene.appendChild(edgesSvg);
    canvas.appendChild(scene);
  }
  if (baseSceneWidth === null || baseSceneHeight === null) {
    baseSceneWidth = Math.max(scene.offsetWidth || 0, canvas.clientWidth || 0, minSceneBaseSize);
    baseSceneHeight = Math.max(scene.offsetHeight || 0, canvas.clientHeight || 0, minSceneBaseSize);
  }
  restoreCanvasState();
  applyZoom(zoomLevel);
  updateGridPosition();
}

function setStatus(msg) {
  status.textContent = msg;
}

function clearCanvas() {
  if (scene) {
    scene.querySelectorAll('.node, .group-box, .group-label, .bp-node, .bp-title, .bp-image, .tree-node, .graph-node, .tree-root-label').forEach((n) => {
      if (n.closest('.bp-popover')) return;
      n.remove();
    });
  }
  connections = [];
  selected = null;
  drawEdges();
}

function drawEdges() {
  if (!scene || !edgesSvg) return;
  const rect = scene.getBoundingClientRect();
  const w = Math.max(scene.scrollWidth, scene.offsetWidth, rect.width);
  const h = Math.max(scene.scrollHeight, scene.offsetHeight, rect.height);
  edgesSvg.setAttribute('width', w);
  edgesSvg.setAttribute('height', h);
  edgesSvg.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="#2b7" />
      </marker>
    </defs>
  `;
  const makeLabel = (x, y, text, color = '#9fd4ff', dy = 0) => {
    if (!text) return;
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', x);
    t.setAttribute('y', y + dy);
    t.setAttribute('fill', color);
    t.setAttribute('font-size', '11');
    t.setAttribute('text-anchor', 'middle');
    t.textContent = text;
    edgesSvg.appendChild(t);
  };
  connections.forEach((c) => {
    const a = scene.querySelector('#node-' + c.from);
    const b = scene.querySelector('#node-' + c.to);
    if (!a || !b) return;
    const ra = a.getBoundingClientRect();
    const rb = b.getBoundingClientRect();
    const x1 = ra.left - rect.left + ra.width / 2;
    const y1 = ra.top - rect.top + ra.height / 2;
    const x2 = rb.left - rect.left + rb.width / 2;
    const y2 = rb.top - rect.top + rb.height / 2;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', x1);
    line.setAttribute('y1', y1);
    line.setAttribute('x2', x2);
    line.setAttribute('y2', y2);
    line.setAttribute('stroke', '#2b7');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('marker-end', 'url(#arrow)');
    edgesSvg.appendChild(line);
  });

  pinConnections.forEach((c, idx) => {
    const a = scene.querySelector(`[data-pin-id="${c.from}"]`);
    const b = scene.querySelector(`[data-pin-id="${c.to}"]`);
    if (!a || !b) return;
    const p1 = getPinPoint(a, rect);
    const p2 = getPinPoint(b, rect);
    if (!p1 || !p2) return;
    const { x: x1, y: y1 } = p1;
    const { x: x2, y: y2 } = p2;
    const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`);
    path.setAttribute('stroke', '#59a7ff');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('fill', 'none');
    path.setAttribute('marker-end', 'url(#arrow)');
    path.classList.add('pin-edge');
    edgesSvg.appendChild(path);
  });

  if (activeView === 'graph' && flowGraph) {
    (flowGraph.edges || []).forEach((e) => {
      const a = getNodeAnchorById(e.from, rect);
      const b = getNodeAnchorById(e.to, rect);
      if (!a || !b) return;
      const midX = (a.x + b.x) / 2;
      const points = `M ${a.x} ${a.y} L ${midX} ${a.y} L ${midX} ${b.y} L ${b.x} ${b.y}`;
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      let edgeColor = '#3fb0ff';
      const label = formatEdgePins(e);
      path.setAttribute('d', points);
      if (label) {
        const up = label.toUpperCase();
        if (up.includes('YES') && up.includes('NO')) edgeColor = '#ffd166';
        else if (up.includes('YES')) edgeColor = '#5ad67a';
        else if (up.includes('NO')) edgeColor = '#ff6b6b';
      }
      path.setAttribute('stroke', edgeColor);
      path.setAttribute('stroke-width', '2');
      path.setAttribute('fill', 'none');
      path.setAttribute('marker-end', 'url(#arrow)');
      edgesSvg.appendChild(path);
      if (label) {
        const up = label.toUpperCase();
        let dy = -6;
        if (up.includes('YES') && !up.includes('NO')) dy = -14;
        if (up.includes('NO') && !up.includes('YES')) dy = 10;
        makeLabel(midX, (a.y + b.y) / 2, label, edgeColor, dy);
      }
    });
  }

  if ((activeView === 'tree' || activeView === 'structured') && treeLayoutEdges.length > 0) {
    treeLayoutEdges.forEach((e) => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      let edgeColor = '#3fb0ff';
      line.setAttribute('x1', e.x1);
      line.setAttribute('y1', e.y1);
      line.setAttribute('x2', e.x2);
      line.setAttribute('y2', e.y2);
      if (e.label) {
        const up = e.label.toUpperCase();
        if (up.includes('YES') && up.includes('NO')) edgeColor = '#ffd166';
        else if (up.includes('YES')) edgeColor = '#5ad67a';
        else if (up.includes('NO')) edgeColor = '#ff6b6b';
      }
      line.setAttribute('stroke', edgeColor);
      line.setAttribute('stroke-width', '2');
      edgesSvg.appendChild(line);
      if (e.label) {
        const up = e.label.toUpperCase();
        let dy = -6;
        if (up.includes('YES') && !up.includes('NO')) dy = -14;
        if (up.includes('NO') && !up.includes('YES')) dy = 10;
        makeLabel((e.x1 + e.x2) / 2, (e.y1 + e.y2) / 2, e.label, edgeColor, dy);
      }
    });
  }
}

function shortPinName(name) {
  if (!name) return '';
  const parts = String(name).split(' / ');
  return parts[parts.length - 1] || name;
}

function formatEdgePins(edge) {
  const pins = edge?.pins;
  if (!Array.isArray(pins) || pins.length === 0) return '';
  const items = pins.map(p => `${shortPinName(p.from_name)}→${shortPinName(p.to_name)}`);
  const uniq = Array.from(new Set(items));
  const text = uniq.join(' | ');
  return text.length > 48 ? text.slice(0, 46) + '…' : text;
}

function buildPortSummary(graph) {
  const map = {};
  if (!graph || !Array.isArray(graph.edges)) return map;
  graph.edges.forEach((e) => {
    const pins = Array.isArray(e.pins) ? e.pins : [];
    if (!map[e.from]) map[e.from] = { in: [], out: [] };
    if (!map[e.to]) map[e.to] = { in: [], out: [] };
    pins.forEach((p) => {
      const outLabel = shortPinName(p.from_name) || shortPinName(p.from_pin) || 'pin';
      const inLabel = shortPinName(p.to_name) || shortPinName(p.to_pin) || 'pin';
      map[e.from].out.push(outLabel);
      map[e.to].in.push(inLabel);
    });
  });
  Object.keys(map).forEach((k) => {
    map[k].in = Array.from(new Set(map[k].in));
    map[k].out = Array.from(new Set(map[k].out));
  });
  if (Array.isArray(graph.nodes)) {
    graph.nodes.forEach((n) => {
      if (n?.ports) {
        if (!map[n.id]) map[n.id] = { in: [], out: [] };
        if (Array.isArray(n.ports.in)) map[n.id].in = Array.from(new Set([...map[n.id].in, ...n.ports.in]));
        if (Array.isArray(n.ports.out)) map[n.id].out = Array.from(new Set([...map[n.id].out, ...n.ports.out]));
      }
    });
  }
  return map;
}

function getFlowNodeById(id) {
  if (!flowGraph || !Array.isArray(flowGraph.nodes)) return null;
  return flowGraph.nodes.find(n => n.id === id) || null;
}

function estimateFlowNodeHeight(node, portSummary) {
  const base = 34;
  let h = base;
  const summary = portSummary?.[node.id];
  if (summary && (summary.in.length || summary.out.length)) {
    h += 18;
    if (summary.in.length) h += 14;
    if (summary.out.length) h += 14;
  }
  const sections = node.sections || [];
  sections.forEach((sec) => {
    h += 16;
    const pins = sec.pins || [];
    const show = pins.slice(0, 6);
    h += show.length * 14;
    if (pins.length > show.length) h += 12;
  });
  return Math.max(56, h);
}

function renderFlowNodeContent(div, node, portSummary, compact = false) {
  div.innerHTML = '';
  const title = document.createElement('div');
  title.className = 'flow-title';
  title.textContent = node.name || node.id;
  div.appendChild(title);
  const summary = portSummary?.[node.id];
  if (summary && (summary.in.length || summary.out.length)) {
    const ports = document.createElement('div');
    ports.className = 'flow-ports';
    if (summary.in.length) {
      const inLine = document.createElement('div');
      inLine.className = 'flow-port-line';
      inLine.textContent = `IN: ${summary.in.join(', ')}`;
      ports.appendChild(inLine);
    }
    if (summary.out.length) {
      const outLine = document.createElement('div');
      outLine.className = 'flow-port-line';
      outLine.textContent = `OUT: ${summary.out.join(', ')}`;
      ports.appendChild(outLine);
    }
    div.appendChild(ports);
  }
  const sections = node.sections || [];
  if (compact && sections.length === 0) return;
  sections.forEach((sec) => {
    const secWrap = document.createElement('div');
    secWrap.className = 'flow-section';
    const label = document.createElement('div');
    label.className = 'flow-section-title';
    label.textContent = sec.title;
    secWrap.appendChild(label);
    const pins = sec.pins || [];
    const limit = compact ? 2 : 6;
    const show = pins.slice(0, limit);
    show.forEach((p) => {
      const item = document.createElement('div');
      item.className = 'flow-pin';
      item.textContent = p.name || p.id;
      secWrap.appendChild(item);
    });
    if (pins.length > show.length) {
      const more = document.createElement('div');
      more.className = 'flow-pin flow-more';
      more.textContent = `+${pins.length - show.length} more`;
      secWrap.appendChild(more);
    }
    div.appendChild(secWrap);
  });
}

function getPinPoint(pinEl, sceneRect) {
  // For bp-pin, use its circle center; for header pin, use itself
  let target = pinEl;
  if (pinEl.classList.contains('bp-pin')) {
    const circle = pinEl.querySelector('.bp-pin-circle');
    if (circle) target = circle;
  }
  const r = target.getBoundingClientRect();
  if (!r) return null;
  return {
    x: r.left - sceneRect.left + r.width / 2,
    y: r.top - sceneRect.top + r.height / 2
  };
}

function renderNodes(list) {
  clearCanvas();
  const rect = canvas.getBoundingClientRect();
  const xs = list.map((n) => n.bbox[0]);
  const ys = list.map((n) => n.bbox[1]);
  const xe = list.map((n) => n.bbox[0] + n.bbox[2]);
  const ye = list.map((n) => n.bbox[1] + n.bbox[3]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xe);
  const maxY = Math.max(...ye);
  const w = Math.max(1, maxX - minX);
  const h = Math.max(1, maxY - minY);
  list.forEach((n, idx) => {
    const div = document.createElement('div');
    div.className = 'node';
    div.id = 'node-' + idx;
    div.textContent = n.name || 'node';
    const nx = ((n.bbox[0] - minX) / w) * (rect.width - 200) + 80;
    const ny = ((n.bbox[1] - minY) / h) * (rect.height - 200) + 80;
    div.style.left = nx + 'px';
    div.style.top = ny + 'px';
    div.onclick = () => {
      if (selected === null) {
        selected = idx;
        div.classList.add('selected');
      } else if (selected === idx) {
        selected = null;
        div.classList.remove('selected');
      } else {
        connections.push({ from: selected, to: idx });
        scene.querySelector('#node-' + selected).classList.remove('selected');
        selected = null;
        drawEdges();
      }
    };
    scene.appendChild(div);
  });
  updateSceneBaseSize();
  drawEdges();
}

const loadBtn = document.getElementById('loadBtn');
const blueprintBtn = document.getElementById('blueprintBtn');
const layerBlueprintBtn = document.getElementById('layerBlueprintBtn');
const saveBtn = document.getElementById('saveBtn');
const undoEdgeBtn = document.getElementById('undoEdgeBtn');
const snapshotSaveBtn = document.getElementById('snapshotSaveBtn');
const snapshotLoadBtn = document.getElementById('snapshotLoadBtn');
const flowGraphBtn = document.getElementById('flowGraphBtn');
const flowTreeBtn = document.getElementById('flowTreeBtn');
const viewMixedBtn = document.getElementById('viewMixedBtn');
const viewGraphBtn = document.getElementById('viewGraphBtn');
const viewTreeBtn = document.getElementById('viewTreeBtn');
const pinLinkBtn = document.getElementById('pinLinkBtn');
const pinViewBtn = document.getElementById('pinViewBtn');
const viewDepthSelect = document.getElementById('viewDepthSelect');
const combineEnableBtn = document.getElementById('combineEnableBtn');
const combineDecisionBtn = document.getElementById('combineDecisionBtn');
const flowTreeList = document.getElementById('flowTreeList');
const layoutBtn = document.getElementById('layoutBtn');
const navBlueprintBtn = document.getElementById('navBlueprintBtn');
const navTreeBtn = document.getElementById('navTreeBtn');
const navStructuredBtn = document.getElementById('navStructuredBtn');
const navGraphBtn = document.getElementById('navGraphBtn');

const snapshotModal = document.createElement('div');
snapshotModal.className = 'snapshot-modal';
snapshotModal.innerHTML = `
  <div class="snapshot-backdrop"></div>
  <div class="snapshot-body">
    <div class="snapshot-header">
      <span id="snapshotModalTitle">蓝图快照</span>
      <button id="snapshotModalClose">关闭</button>
    </div>
    <div class="snapshot-row">
      <label>文件夹</label>
      <select id="snapshotFolderSelect"></select>
    </div>
    <div class="snapshot-row" id="snapshotNameRow">
      <label>名称</label>
      <input id="snapshotNameInput" placeholder="保存名称" />
    </div>
    <div class="snapshot-row" id="snapshotFileRow">
      <label>文件</label>
      <select id="snapshotFileSelect"></select>
    </div>
    <div class="snapshot-actions">
      <button id="snapshotModalOk" class="primary">确定</button>
    </div>
  </div>
`;
document.body.appendChild(snapshotModal);
const snapshotModalTitle = snapshotModal.querySelector('#snapshotModalTitle');
const snapshotModalClose = snapshotModal.querySelector('#snapshotModalClose');
const snapshotFolderSelect = snapshotModal.querySelector('#snapshotFolderSelect');
const snapshotFileSelect = snapshotModal.querySelector('#snapshotFileSelect');
const snapshotNameInput = snapshotModal.querySelector('#snapshotNameInput');
const snapshotNameRow = snapshotModal.querySelector('#snapshotNameRow');
const snapshotFileRow = snapshotModal.querySelector('#snapshotFileRow');
const snapshotModalOk = snapshotModal.querySelector('#snapshotModalOk');
snapshotModal.querySelector('.snapshot-backdrop').onclick = () => snapshotModal.style.display = 'none';
snapshotModalClose.onclick = () => snapshotModal.style.display = 'none';

setPinMode('link');
if (pinLinkBtn) {
  pinLinkBtn.onclick = () => {
    setPinMode(pinMode === 'link' ? 'view' : 'link');
  };
}
if (pinViewBtn) {
  pinViewBtn.onclick = () => {
    setPinMode(pinMode === 'view' ? 'link' : 'view');
  };
}
if (viewDepthSelect) {
  viewDepthSelect.onchange = () => {
    applyViewDepthChange(viewDepthSelect.value);
  };
}
if (combineEnableBtn) {
  combineEnableBtn.onclick = () => {
    setCombineMode(!combineMode);
  };
}
if (combineDecisionBtn) {
  combineDecisionBtn.onclick = () => {
    if (!combineMode) return;
    if (combineSelectedIds.size < 2) return;
    combineDecisionNodes();
    setCombineMode(false);
  };
}

loadBtn.onclick = async () => {
  const backend = getLegacyBackend();
  const figmaUrl = document.getElementById('figmaUrl').value.trim();
  const fileKey = document.getElementById('fileKey').value.trim();
  const nodeId = document.getElementById('nodeId').value.trim();
  if (!figmaUrl && !fileKey) return alert('请输入 Figma URL 或 file key');
  setStatus('loading...');
  blueprintMode = false;
  const url = new URL(backend + '/api/blueprint/nodes');
  url.searchParams.set('file_key', figmaUrl || fileKey);
  if (nodeId) url.searchParams.set('node_id', nodeId);
  const res = await fetch(url);
  if (!res.ok) {
    setStatus('load failed: ' + res.status);
    return;
  }
  const data = await res.json();
  lastData = data;
  nodes = data.nodes || [];
  lastGroups = data.groups || [];
  initScene();
  if (data.groups && data.groups.length > 0) {
    if (layoutMode === 'absolute') {
      renderAbsolute(data.groups);
      setStatus('loaded ' + nodes.length + ' nodes (absolute)');
    } else {
      renderGroups(data.groups);
      setStatus('loaded ' + nodes.length + ' nodes in ' + data.groups.length + ' groups');
    }
  } else {
    renderNodes(nodes);
    setStatus('loaded ' + nodes.length + ' nodes');
  }
};

blueprintBtn.onclick = async () => {
  const backend = getLegacyBackend();
  const figmaUrl = document.getElementById('figmaUrl').value.trim();
  const fileKey = document.getElementById('fileKey').value.trim();
  const nodeId = document.getElementById('nodeId').value.trim();
  if (!figmaUrl && !fileKey) return alert('请输入 Figma URL 或 file key');
  setStatus('loading blueprint...');
  blueprintMode = true;
  const url = new URL(backend + '/api/blueprint/node');
  url.searchParams.set('file_key', figmaUrl || fileKey);
  if (nodeId) url.searchParams.set('node_id', nodeId);
  const res = await fetch(url);
  if (!res.ok) {
    setStatus('blueprint failed: ' + res.status);
    return;
  }
  const data = await res.json();
  lastData = data;
  lastBlueprint = data;
  resetDerivedFlowState();
  setActiveNav('blueprint');
  initScene();
  renderBlueprintNode(data);
  setStatus(`blueprint: ${data.node?.name || 'node'}`);
};

layerBlueprintBtn.onclick = async () => {
  try {
    const backend = getLegacyBackend();
    const figmaUrl = document.getElementById('figmaUrl').value.trim();
    const fileKey = document.getElementById('fileKey').value.trim();
    const nodeId = document.getElementById('nodeId').value.trim();
    const mode = document.getElementById('blueprintMode').value;
    if (!figmaUrl && !fileKey) return alert('请输入 Figma URL 或 file key');
    setStatus('loading blueprint layers...');
    blueprintMode = true;
    const url = new URL(backend + '/api/blueprint/layers');
    url.searchParams.set('file_key', figmaUrl || fileKey);
    if (nodeId) url.searchParams.set('node_id', nodeId);
    url.searchParams.set('mode', mode);
    const res = await fetch(url);
    if (!res.ok) {
      setStatus('blueprint layers failed: ' + res.status);
      return;
    }
    const data = await res.json();
    lastData = data;
    lastBlueprint = data;
    resetDerivedFlowState();
    setActiveNav('blueprint');
    initScene();
    const maxDepth = getDepthValue();
    try {
      renderBlueprintMulti(data, maxDepth);
      renderLayerListBlueprintMulti(data, maxDepth);
      setStatus(`blueprint layers: ${data.nodes?.length || 0}`);
    } catch (err) {
      console.error('renderBlueprintMulti failed', err, data);
      setStatus('blueprint layers error: render');
    }
  } catch (err) {
    console.error(err);
    setStatus('blueprint layers error: fetch ' + (err?.message || err));
  }
};

saveBtn.onclick = async () => {
  const backend = getLegacyBackend();
  const fileKey = document.getElementById('fileKey').value.trim();
  const nodeId = document.getElementById('nodeId').value.trim();
  if (!fileKey) return alert('请输入 file key');
  const payload = {
    file_key: fileKey,
    node_id: nodeId || null,
    connections: connections.map((c) => ({
      from: nodes[c.from]?.name || String(c.from),
      to: nodes[c.to]?.name || String(c.to)
    }))
  };
  setStatus('saving...');
  const res = await fetch(backend + '/api/blueprint/connections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  setStatus('saved: ' + (data.path || 'ok'));
};

snapshotSaveBtn.onclick = async () => {
  const backend = getBlueprintBackend();
  const figmaUrl = document.getElementById('figmaUrl').value.trim();
  const fileKey = document.getElementById('fileKey').value.trim();
  const nodeId = document.getElementById('nodeId').value.trim();
  const mode = document.getElementById('blueprintMode')?.value || 'A';
  const maxDepth = currentBlueprintDepth ?? getDepthValue();
  await openSnapshotModal('save', backend, figmaUrl || fileKey, nodeId, mode, maxDepth);
};

snapshotLoadBtn.onclick = async () => {
  const backend = getBlueprintBackend();
  const figmaUrl = document.getElementById('figmaUrl').value.trim();
  const fileKey = document.getElementById('fileKey').value.trim();
  const nodeId = document.getElementById('nodeId').value.trim();
  await openSnapshotModal('load', backend, figmaUrl || fileKey, nodeId);
};

async function getSelectedSnapshot() {
  const backend = getBlueprintBackend();
  const foldersRes = await fetch(backend + '/api/blueprint-main/snapshots/folders');
  const foldersData = foldersRes.ok ? await foldersRes.json() : { folders: [] };
  const list = Array.isArray(foldersData?.folders) && foldersData.folders.length ? foldersData.folders : ['default'];
  const folder = list[0];
  const listUrl = new URL(backend + '/api/blueprint-main/snapshots');
  listUrl.searchParams.set('folder', folder);
  const res = await fetch(listUrl);
  const payload = res.ok ? await res.json() : { items: [] };
  const files = payload?.items || [];
  if (!files.length) return null;
  return { folder, name: files[0].name };
}

function resetDerivedFlowState() {
  flowGraph = null;
  flowTree = null;
  structuredFlowTree = null;
  treeLayoutNodes = [];
  treeLayoutEdges = [];
  graphLayoutNodes = [];
  if (flowTreeList) flowTreeList.innerHTML = '';
  if (previewVisible) closePreviewPopover();
}

function buildCurrentSnapshotPayload(folder = 'autosave', name = `autosave_${Date.now()}`) {
  if (!currentBlueprintNodes || currentBlueprintNodes.length === 0) return null;
  const normalized = buildSnapshotNodesForSave();
  const nodes = Array.isArray(normalized) ? normalized : normalized.nodes;
  const edges = Array.isArray(normalized) ? pinConnections.slice() : (normalized.edges || pinConnections.slice());
  const fileKey = lastBlueprint?.figma?.file_key || lastBlueprint?.meta?.file_key || document.getElementById('fileKey')?.value.trim() || 'unknown';
  const nodeId = lastBlueprint?.figma?.node_id || lastBlueprint?.meta?.node_id || document.getElementById('nodeId')?.value.trim() || null;
  return {
    meta: {
      file_key: fileKey,
      node_id: nodeId,
      mode: document.getElementById('blueprintMode')?.value || lastBlueprint?.meta?.mode || 'A',
      depth: currentBlueprintDepth ?? getDepthValue(),
      folder,
      name,
      timestamp: new Date().toISOString()
    },
    nodes,
    edges
  };
}

async function saveTempSnapshot(backend) {
  const payload = buildCurrentSnapshotPayload('autosave');
  if (!payload) return null;
  const res = await fetch(backend + '/api/blueprint-main/snapshots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) return null;
  const data = await res.json();
  const path = data?.path || '';
  const fileName = path.split(/[/\\\\]/).pop();
  if (!fileName) return null;
  return { folder: 'autosave', name: fileName };
}

function getNodeAnchorById(nodeId, sceneRect) {
  if (flowViewMode === 'graph' && graphLayoutNodes.length) {
    const n = graphLayoutNodes.find(x => x.id === nodeId);
    if (n) {
      return { x: n.x + n.w / 2, y: n.y + n.h / 2 };
    }
  }
  const headerPin = scene.querySelector(`[data-pin-id="node-${nodeId}"]`);
  if (headerPin) return getPinPoint(headerPin, sceneRect);
  const card = scene.querySelector(`[data-node-id="${nodeId}"]`);
  if (!card) return null;
  const r = card.getBoundingClientRect();
  return {
    x: r.left - sceneRect.left + r.width / 2,
    y: r.top - sceneRect.top + 24
  };
}

function renderFlowTree() {
  if (!flowTreeList) return;
  flowTreeList.innerHTML = '';
  if (!flowTree || !(flowTree.trees || []).length) return;
  const renderNode = (node, depth) => {
    const div = document.createElement('div');
    div.className = 'tree-item';
    div.style.paddingLeft = (depth * 14) + 'px';
    div.textContent = getFlowNodeName(node.id);
    div.onclick = () => {
      highlightBlueprintNode(node.id);
      focusBlueprintNode(node.id);
    };
    flowTreeList.appendChild(div);
    (node.children || []).forEach((c) => renderNode(c, depth + 1));
  };
  flowTree.trees.forEach((t) => renderNode(t, 0));
}

function getStructuredNodeLabel(node) {
  if (!node) return '(empty)';
  switch (node.type) {
    case 'step':
      return node.title || node.id || 'step';
    case 'sequence':
      return 'Sequence';
    case 'branch':
      return `Branch: ${node.title || node.id || ''}`.trim();
    case 'loop':
    case 'loop_region':
      return `${node.type}: ${node.title || node.entry || node.id || ''}`.trim();
    case 'subflow':
      return `Subflow: ${node.title || node.id || ''}`.trim();
    default:
      return `${node.type || 'node'}: ${node.title || node.id || ''}`.trim();
  }
}

function getStructuredFocusId(node) {
  if (!node) return null;
  if (node.type === 'step') return node.id || null;
  if (node.type === 'branch') return node.id || null;
  if (node.type === 'loop' || node.type === 'loop_region') {
    return node.entry || (Array.isArray(node.members) ? node.members[0] : null);
  }
  return node.id || null;
}

function setActiveNav(view) {
  activeView = view;
  navBlueprintBtn.classList.toggle('active', view === 'blueprint');
  navTreeBtn.classList.toggle('active', view === 'tree');
  navStructuredBtn.classList.toggle('active', view === 'structured');
  navGraphBtn.classList.toggle('active', view === 'graph');
}

function layoutCompactTree(roots, options = {}) {
  const nodeW = options.nodeWidth || 260;
  const levelGap = options.levelGap || 220;
  const rowGap = options.rowGap || 36;
  const startX = options.startX || 120;
  const startY = options.startY || 80;
  const getId = options.getId || ((node) => node?.id || `${Math.random()}`);
  const getChildren = options.getChildren || (() => []);
  const getHeight = options.getHeight || (() => 72);
  const getEdgeLabel = options.getEdgeLabel || (() => '');
  const getRootLabel = options.getRootLabel || null;

  const nodes = [];
  const edges = [];
  const rootLabels = [];
  let cursorY = startY;

  const layoutNode = (node, depth, parentLayout = null, edgeLabel = '') => {
    const children = getChildren(node);
    const childLayouts = [];
    children.forEach((childInfo) => {
      const childNode = childInfo?.node;
      if (!childNode) return;
      const childLayout = layoutNode(childNode, depth + 1, null, getEdgeLabel(node, childInfo) || childInfo.label || '');
      if (childLayout) childLayouts.push({ ...childLayout, label: getEdgeLabel(node, childInfo) || childInfo.label || '' });
    });

    const h = getHeight(node);
    const x = startX + depth * levelGap;
    let y = cursorY;
    if (childLayouts.length) {
      const firstY = childLayouts[0].y;
      const lastY = childLayouts[childLayouts.length - 1].y + childLayouts[childLayouts.length - 1].h;
      y = firstY + (lastY - firstY) / 2 - h / 2;
    } else {
      cursorY += h + rowGap;
    }

    const layout = { node, x, y, w: nodeW, h, depth };
    nodes.push(layout);

    childLayouts.forEach((childLayout) => {
      edges.push({
        x1: x + nodeW,
        y1: y + h / 2,
        x2: childLayout.x,
        y2: childLayout.y + childLayout.h / 2,
        label: childLayout.label || '',
      });
    });

    if (!parentLayout && typeof getRootLabel === 'function') {
      const rootLabel = getRootLabel(node);
      if (rootLabel) {
        rootLabels.push({
          text: rootLabel,
          x,
          y: Math.max(24, y - 28),
        });
      }
    }

    return layout;
  };

  roots.forEach((root) => {
    const rootLayout = layoutNode(root, 0);
    if (rootLayout) {
      cursorY = Math.max(cursorY, rootLayout.y + rootLayout.h + rowGap * 2);
    }
  });

  return { nodes, edges, rootLabels };
}

function renderStructuredFlowTreeCanvas(forceCenter = false) {
  if (!structuredFlowTree || !structuredFlowTree.root) return;
  setActiveNav('structured');
  flowViewMode = 'tree';
  clearCanvas();
  treeLayoutNodes = [];
  treeLayoutEdges = [];
  const nodeW = 260;
  const hGap = 80;
  const vGap = 90;
  const startX = 120;
  const startY = 80;

  const estimateNodeHeight = (node) => 64 + ((node.type === 'loop' || node.type === 'loop_region') ? 36 : 0);
  const collectChildren = (node) => [
    ...(node.body ? [node.body] : []),
    ...(node.children || []),
    ...((node.branches || []).map((branch) => branch.child).filter(Boolean)),
  ];
  const measure = (node) => {
    const children = collectChildren(node);
    if (!children.length) return 1;
    return children.reduce((sum, child) => sum + measure(child), 0);
  };

  const layoutNodes = [];
  const layoutEdges = [];
  const depthHeights = {};

  const collectDepth = (node, depth) => {
    depthHeights[depth] = Math.max(depthHeights[depth] || 0, estimateNodeHeight(node));
    if (node.body) collectDepth(node.body, depth + 1);
    (node.children || []).forEach((child) => collectDepth(child, depth + 1));
    (node.branches || []).forEach((branch) => {
      if (branch.child) collectDepth(branch.child, depth + 2);
    });
  };
  collectDepth(structuredFlowTree.root, 0);

  const maxDepth = Math.max(0, ...Object.keys(depthHeights).map(Number));
  const depthOffset = [];
  let accY = startY;
  for (let d = 0; d <= maxDepth + 1; d += 1) {
    depthOffset[d] = accY;
    accY += (depthHeights[d] || 64) + vGap;
  }

  const place = (node, depth, xOffset) => {
    const span = measure(node);
    const width = span * (nodeW + hGap);
    const x = xOffset + width / 2 - nodeW / 2;
    const y = depthOffset[depth] ?? (startY + depth * (64 + vGap));
    const h = estimateNodeHeight(node);
    layoutNodes.push({ node, x, y, w: nodeW, h });

    let childCursor = xOffset;
    const placeChild = (child, childDepth, edgeLabel = '') => {
      const childSpan = measure(child);
      const childWidth = childSpan * (nodeW + hGap);
      const childX = childCursor + childWidth / 2 - nodeW / 2;
      const childY = depthOffset[childDepth] ?? (startY + childDepth * (64 + vGap));
      layoutEdges.push({
        x1: x + nodeW / 2,
        y1: y + h,
        x2: childX + nodeW / 2,
        y2: childY,
        label: edgeLabel,
      });
      place(child, childDepth, childCursor);
      childCursor += childWidth;
    };

    if (node.body) placeChild(node.body, depth + 1, 'body');
    (node.children || []).forEach((child) => placeChild(child, depth + 1));
    (node.branches || []).forEach((branch) => {
      if (branch.child) placeChild(branch.child, depth + 2, branch.label || 'branch');
    });
  };

  place(structuredFlowTree.root, 0, startX);

  const xs = layoutNodes.map((n) => n.x);
  const ys = layoutNodes.map((n) => n.y);
  const xe = layoutNodes.map((n) => n.x + n.w);
  const ye = layoutNodes.map((n) => n.y + n.h);
  if (xs.length) {
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xe);
    const maxY = Math.max(...ye);
    const pad = infiniteCanvasPad;
    scene.style.width = (maxX - minX + pad * 2) + 'px';
    scene.style.height = (maxY - minY + pad * 2) + 'px';
    const dx = pad - minX;
    const dy = pad - minY;
    layoutNodes.forEach((n) => { n.x += dx; n.y += dy; });
    layoutEdges.forEach((e) => { e.x1 += dx; e.x2 += dx; e.y1 += dy; e.y2 += dy; });
  }

  treeLayoutEdges = layoutEdges.slice();
  layoutNodes.forEach((item) => {
    const div = document.createElement('div');
    div.className = `tree-node structured-node structured-${item.node.type || 'node'}`;
    div.style.left = item.x + 'px';
    div.style.top = item.y + 'px';
    div.style.width = item.w + 'px';
    div.style.height = item.h + 'px';
    const focusId = getStructuredFocusId(item.node);
    if (focusId) div.setAttribute('data-node-id', focusId);
    const metaBits = [];
    if (item.node.entry) metaBits.push(`entry: ${item.node.entry}`);
    if (Array.isArray(item.node.members) && item.node.members.length) metaBits.push(`members: ${item.node.members.join(', ')}`);
    if (Array.isArray(item.node.exit_edges) && item.node.exit_edges.length) metaBits.push(`exits: ${item.node.exit_edges.map((edge) => edge.id).join(', ')}`);
    div.innerHTML = `
      <div class="structured-title">
        <span class="structured-badge structured-${item.node.type || 'node'}">${item.node.type || 'node'}</span>
        <span>${getStructuredNodeLabel(item.node)}</span>
      </div>
      ${metaBits.length ? `<div class="structured-meta">${metaBits.join(' | ')}</div>` : ''}
    `;
    div.onclick = () => {
      if (focusId) {
        highlightBlueprintNode(focusId);
        focusBlueprintNode(focusId);
      }
    };
    scene.appendChild(div);
  });

  updateSceneBaseSize();
  drawEdges();
  if (forceCenter) {
    forceCenterCanvas(600);
  } else {
    centerCanvasIfNeeded(600);
  }
}

function renderFlowTreeCanvas(forceCenter = false) {
  if (!flowTree || !(flowTree.trees || []).length) return;
  setActiveNav('tree');
  flowViewMode = 'tree';
  clearCanvas();
  treeLayoutNodes = [];
  treeLayoutEdges = [];
  const portSummary = buildPortSummary(flowGraph);

  const nameMap = {};
  if (flowGraph && Array.isArray(flowGraph.nodes) && flowGraph.nodes.length) {
    flowGraph.nodes.forEach((n) => {
      nameMap[n.id] = n.name || n.id;
    });
  } else {
    (currentBlueprintNodes || []).forEach((n) => {
      nameMap[n.id] = n.name || n.id;
    });
  }

  const nodeById = {};
  if (flowGraph && Array.isArray(flowGraph.nodes)) {
    flowGraph.nodes.forEach((n) => { nodeById[n.id] = n; });
  }

  const heightMap = {};
  Object.keys(nodeById).forEach((id) => {
    heightMap[id] = estimateFlowNodeHeight(nodeById[id], portSummary);
  });
  const nodeW = 220;
  const hGap = 60;
  const vGap = 90;
  const startX = 120;
  const startY = 80;

  const depthHeights = {};
  const collectDepth = (node, depth) => {
    const h = heightMap[node.id] || 56;
    depthHeights[depth] = Math.max(depthHeights[depth] || 0, h);
    (node.children || []).forEach((c) => collectDepth(c, depth + 1));
  };
  flowTree.trees.forEach((t) => collectDepth(t, 0));
  const maxDepth = Math.max(0, ...Object.keys(depthHeights).map(Number));
  const depthOffset = [];
  let accY = startY;
  for (let d = 0; d <= maxDepth; d += 1) {
    depthOffset[d] = accY;
    accY += (depthHeights[d] || 56) + vGap;
  }

  const measure = (node) => {
    if (!node.children || node.children.length === 0) return 1;
    return node.children.reduce((sum, c) => sum + measure(c), 0);
  };

  let cursorX = startX;
  const place = (node, depth, xOffset) => {
    const span = measure(node);
    const width = span * (nodeW + hGap);
    const x = xOffset + width / 2 - nodeW / 2;
    const y = depthOffset[depth] ?? (startY + depth * (56 + vGap));
    const h = heightMap[node.id] || 56;
    treeLayoutNodes.push({ id: node.id, x, y, w: nodeW, h });
    if (node.children) {
      let childX = xOffset;
      node.children.forEach((c) => {
        const childSpan = measure(c);
        const childWidth = childSpan * (nodeW + hGap);
        const childCenterX = childX + childWidth / 2 - nodeW / 2;
        const pins = Array.isArray(c.edge_pins) ? c.edge_pins : [];
        const label = pins.length ? formatEdgePins({ pins }) : '';
        treeLayoutEdges.push({
          x1: x + nodeW / 2,
          y1: y + h,
          x2: childCenterX + nodeW / 2,
          y2: depthOffset[depth + 1] ?? (startY + (depth + 1) * (56 + vGap)),
          label
        });
        place(c, depth + 1, childX);
        childX += childWidth;
      });
    }
  };

  flowTree.trees.forEach((t) => {
    const span = measure(t);
    const width = span * (nodeW + hGap);
    const label = document.createElement('div');
    label.className = 'tree-root-label';
    label.style.left = (cursorX + width / 2 - 80) + 'px';
    label.style.top = (startY - 32) + 'px';
    label.textContent = nameMap[t.id] || t.id;
    scene.appendChild(label);
    place(t, 0, cursorX);
    cursorX += width + hGap;
  });

  // set scene bounds
  const xs = treeLayoutNodes.map(n => n.x);
  const ys = treeLayoutNodes.map(n => n.y);
  const xe = treeLayoutNodes.map(n => n.x + n.w);
  const ye = treeLayoutNodes.map(n => n.y + n.h);
  if (xs.length) {
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xe);
    const maxY = Math.max(...ye);
    const pad = infiniteCanvasPad;
    scene.style.width = (maxX - minX + pad * 2) + 'px';
    scene.style.height = (maxY - minY + pad * 2) + 'px';
    // shift nodes into padded area
    const dx = pad - minX;
    const dy = pad - minY;
    treeLayoutNodes.forEach(n => { n.x += dx; n.y += dy; });
    treeLayoutEdges.forEach(e => { e.x1 += dx; e.x2 += dx; e.y1 += dy; e.y2 += dy; });
  }

  treeLayoutNodes.forEach((n) => {
    const div = document.createElement('div');
    div.className = 'tree-node';
    div.style.left = n.x + 'px';
    div.style.top = n.y + 'px';
    div.style.width = n.w + 'px';
    div.style.height = n.h + 'px';
    const nodeData = nodeById[n.id] || { id: n.id, name: nameMap[n.id] || n.id };
    if (nodeData?.type === 'DECISION') div.classList.add('flow-decision');
    renderFlowNodeContent(div, nodeData, portSummary);
    scene.appendChild(div);
  });

  updateSceneBaseSize();
  drawEdges();
  const pad = 600;
  if (forceCenter) {
    forceCenterCanvas(pad);
  } else {
    centerCanvasIfNeeded(pad);
  }
}

function renderFlowGraphCanvas() {
  if (!flowGraph) return;
  setActiveNav('graph');
  flowViewMode = 'graph';
  clearCanvas();
  graphLayoutNodes = [];
  const portSummary = buildPortSummary(flowGraph);
  const nodes = flowGraph.nodes || [];
  const edges = flowGraph.edges || [];
  const nodeW = 300;
  const hGap = 160;
  const vGap = 100;
  const startX = 120;
  const startY = 80;

  const collectTreeIds = (tree) => {
    const ids = [];
    const walk = (n) => {
      if (!n) return;
      if (n.id) ids.push(n.id);
      (n.children || []).forEach(walk);
    };
    walk(tree);
    return ids;
  };

  let components = [];
  if (flowTree && Array.isArray(flowTree.trees) && flowTree.trees.length) {
    components = flowTree.trees.map(t => collectTreeIds(t)).filter(c => c.length);
  }

  if (!components.length) {
    // build undirected adjacency for components
    const undirected = {};
    nodes.forEach(n => { undirected[n.id] = []; });
    edges.forEach(e => {
      if (undirected[e.from]) undirected[e.from].push(e.to);
      if (undirected[e.to]) undirected[e.to].push(e.from);
    });

    const visited = new Set();
    nodes.forEach(n => {
      if (visited.has(n.id)) return;
      const stack = [n.id];
      const comp = [];
      visited.add(n.id);
      while (stack.length) {
        const cur = stack.pop();
        comp.push(cur);
        (undirected[cur] || []).forEach(next => {
          if (!visited.has(next)) {
            visited.add(next);
            stack.push(next);
          }
        });
      }
      components.push(comp);
    });
  }

  let cursorY = startY;
  components.forEach((compIds) => {
    const compNodes = nodes.filter(n => compIds.includes(n.id));
    if (!compNodes.length) return;
    const compEdges = edges.filter(e => compIds.includes(e.from) && compIds.includes(e.to));
    const heightMap = {};
    compNodes.forEach(n => { heightMap[n.id] = estimateFlowNodeHeight(n, portSummary); });
    const indeg = {};
    const adj = {};
    const rev = {};
    compNodes.forEach(n => { indeg[n.id] = 0; adj[n.id] = []; });
    compEdges.forEach(e => {
      if (adj[e.from]) adj[e.from].push(e.to);
      if (indeg[e.to] !== undefined) indeg[e.to] += 1;
      if (!rev[e.to]) rev[e.to] = [];
      rev[e.to].push(e.from);
    });
    const queue = Object.keys(indeg).filter(k => indeg[k] === 0);
    const level = {};
    queue.forEach(k => level[k] = 0);
    while (queue.length) {
      const u = queue.shift();
      (adj[u] || []).forEach(v => {
        indeg[v] -= 1;
        if (indeg[v] === 0) {
          level[v] = (level[u] || 0) + 1;
          queue.push(v);
        }
      });
    }
    compNodes.forEach(n => { if (level[n.id] === undefined) level[n.id] = 0; });
    const layers = {};
    compNodes.forEach(n => { (layers[level[n.id]] ||= []).push(n); });
    const layerKeys = Object.keys(layers).map(Number).sort((a,b)=>a-b);

    const maxLayer = layerKeys.length ? Math.max(...layerKeys) : 0;
    const compWidth = (maxLayer + 1) * (nodeW + hGap);
    const layerHeights = layerKeys.map((lk) => {
      const list = layers[lk] || [];
      if (!list.length) return 0;
      return list.reduce((sum, n) => sum + (heightMap[n.id] || 56) + vGap, -vGap);
    });
    const compHeight = Math.max(...layerHeights, 56);
    layerKeys.forEach((lk) => {
      const list = layers[lk];
      // order nodes within layer by median of parent order to reduce crossings
      list.sort((a, b) => {
        const pa = (rev[a.id] || []).map(pid => (layers[lk - 1] || []).findIndex(x => x.id === pid)).filter(x => x >= 0);
        const pb = (rev[b.id] || []).map(pid => (layers[lk - 1] || []).findIndex(x => x.id === pid)).filter(x => x >= 0);
        const ma = pa.length ? pa.reduce((s, v) => s + v, 0) / pa.length : 0;
        const mb = pb.length ? pb.reduce((s, v) => s + v, 0) / pb.length : 0;
        return ma - mb;
      });
      let yCursor = cursorY;
      list.forEach((n) => {
        const h = heightMap[n.id] || 56;
        const x = startX + lk * (nodeW + hGap);
        const y = yCursor;
        graphLayoutNodes.push({ id: n.id, name: n.name, x, y, w: nodeW, h });
        yCursor += h + vGap;
      });
    });
    cursorY += Math.max(compHeight, 56 + vGap) + vGap * 2;
  });

  graphLayoutNodes.forEach((n) => {
    const div = document.createElement('div');
    div.className = 'graph-node';
    div.setAttribute('data-graph-id', n.id);
    div.style.left = n.x + 'px';
    div.style.top = n.y + 'px';
    div.style.width = n.w + 'px';
    div.style.height = n.h + 'px';
    const nodeData = getFlowNodeById(n.id) || { id: n.id, name: n.name };
    if (nodeData?.type === 'DECISION') div.classList.add('flow-decision');
    renderFlowNodeContent(div, nodeData, portSummary, true);
    scene.appendChild(div);
  });
  // set scene bounds
  const xs = graphLayoutNodes.map(n => n.x);
  const ys = graphLayoutNodes.map(n => n.y);
  const xe = graphLayoutNodes.map(n => n.x + n.w);
  const ye = graphLayoutNodes.map(n => n.y + n.h);
  if (xs.length) {
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xe);
    const maxY = Math.max(...ye);
    const pad = infiniteCanvasPad;
    scene.style.width = (maxX - minX + pad * 2) + 'px';
    scene.style.height = (maxY - minY + pad * 2) + 'px';
    const dx = pad - minX;
    const dy = pad - minY;
    graphLayoutNodes.forEach(n => { n.x += dx; n.y += dy; });
  }
  graphLayoutNodes.forEach((n) => {
    const el = scene.querySelector(`[data-graph-id="${n.id}"]`);
    if (el) {
      el.style.left = n.x + 'px';
      el.style.top = n.y + 'px';
    }
  });
  updateSceneBaseSize();
  drawEdges();
  forceCenterCanvas(infiniteCanvasPad);
}

function highlightBlueprintNode(nodeId) {
  const nodes = scene.querySelectorAll('.bp-node');
  nodes.forEach((n) => n.classList.remove('bp-highlight'));
  const target = scene.querySelector(`[data-node-id="${nodeId}"]`);
  if (target) target.classList.add('bp-highlight');
}

function focusBlueprintNode(nodeId) {
  const target = scene.querySelector(`[data-node-id="${nodeId}"]`);
  if (!target) return;
  const rect = target.getBoundingClientRect();
  const canvasRect = canvas.getBoundingClientRect();
  const cx = rect.left - canvasRect.left + rect.width / 2;
  const cy = rect.top - canvasRect.top + rect.height / 2;
  canvas.scrollLeft += cx - canvas.clientWidth / 2;
  canvas.scrollTop += cy - canvas.clientHeight / 2;
  updateGridPosition();
}

function forceCenterCanvas(pad) {
  canvas.scrollLeft = pad / 2;
  canvas.scrollTop = pad / 2;
  updateGridPosition();
}

flowGraphBtn.onclick = async () => {
  const backend = getBlueprintBackend();
  const selected = await saveTempSnapshot(backend);
  if (!selected) return alert('没有可用蓝图，请先加载');
  setStatus('building flow graph...');
  const res = await fetch(backend + '/api/blueprint-main/graphs/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...selected, scope: 'pin', save_output: true })
  });
  const data = await res.json();
  flowGraph = data.graph || null;
  setStatus('flow graph saved: ' + (data.path || 'ok'));
};

flowTreeBtn.onclick = async () => {
  const backend = getBlueprintBackend();
  const selected = await saveTempSnapshot(backend);
  if (!selected) return alert('没有可用蓝图，请先加载');
  setStatus('building flow tree...');
  const res = await fetch(backend + '/api/blueprint-main/trees/build', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...selected, scope: 'pin', cycle_aware: true, save_output: true })
  });
  const data = await res.json();
  flowTree = data.tree || null;
  structuredFlowTree = data.structured_tree || null;
  renderFlowTree();
  setStatus('flow tree saved: ' + (data.path || 'ok'));
};

viewMixedBtn.onclick = () => {
  flowViewMode = 'mixed';
  drawEdges();
};
viewGraphBtn.onclick = () => {
  setActiveNav('graph');
  flowViewMode = 'graph';
  drawEdges();
};
viewTreeBtn.onclick = () => {
  flowViewMode = 'tree';
  if (!flowTree && !structuredFlowTree) {
    setStatus('请先生成流程树');
    return;
  }
  if (activeView === 'structured' && structuredFlowTree) {
    renderStructuredFlowTreeCanvas(true);
    return;
  }
  renderFlowTreeCanvas(true);
};

navBlueprintBtn.onclick = () => {
  setActiveNav('blueprint');
  flowViewMode = 'mixed';
  if (!lastBlueprint) {
    setStatus('请先加载蓝图');
    return;
  }
  const maxDepth = currentBlueprintDepth ?? getDepthValue();
  if (lastBlueprint.nodes && Array.isArray(lastBlueprint.nodes)) {
    renderBlueprintMulti(lastBlueprint, maxDepth);
    renderLayerListBlueprintMulti(lastBlueprint, maxDepth);
  } else if (lastBlueprint.node) {
    renderBlueprintNode(lastBlueprint, maxDepth);
    renderLayerListBlueprint(lastBlueprint, maxDepth);
  }
  drawEdges();
};
navTreeBtn.onclick = () => {
  if (!flowTree) {
    setStatus('请先生成流程树');
    return;
  }
  renderFlowTreeCanvas(true);
};
navStructuredBtn.onclick = () => {
  if (!structuredFlowTree) {
    setStatus('请先生成结构化流程树');
    return;
  }
  renderStructuredFlowTreeCanvas(true);
};
navGraphBtn.onclick = () => {
  if (!flowGraph) {
    setStatus('请先生成流程图');
    return;
  }
  renderFlowGraphCanvas();
};

async function openSnapshotModal(mode, backend, fileKey, nodeId, bpMode = 'A', depth = 2) {
  snapshotModalTitle.textContent = mode === 'save' ? '保存蓝图' : '加载蓝图';
  snapshotNameRow.style.display = mode === 'save' ? 'flex' : 'none';
  snapshotFileRow.style.display = mode === 'load' ? 'flex' : 'none';
  snapshotModal.style.display = 'flex';

  let folders = [];
  try {
    const foldersRes = await fetch(backend + '/api/blueprint-main/snapshots/folders');
    const foldersData = foldersRes.ok ? await foldersRes.json() : { folders: [] };
    folders = foldersData?.folders || [];
  } catch (e) {
    folders = [];
  }
  const list = Array.isArray(folders) && folders.length ? folders : ['default'];
  snapshotFolderSelect.innerHTML = '';
  list.forEach((name) => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    snapshotFolderSelect.appendChild(opt);
  });

  const defaultName = `snapshot_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}`;
  snapshotNameInput.value = defaultName;

  const loadFiles = async () => {
    const folderName = snapshotFolderSelect.value;
    const listUrl = new URL(backend + '/api/blueprint-main/snapshots');
    if (fileKey) listUrl.searchParams.set('file_key', fileKey);
    if (nodeId) listUrl.searchParams.set('node_id', nodeId);
    if (folderName) listUrl.searchParams.set('folder', folderName);
    let data = { items: [] };
    try {
      const res = await fetch(listUrl);
      data = res.ok ? await res.json() : { items: [] };
    } catch (e) {
      data = { items: [] };
    }
    snapshotFileSelect.innerHTML = '';
    const items = Array.isArray(data?.items) ? data.items : [];
    if (items.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '(无快照)';
      snapshotFileSelect.appendChild(opt);
      return;
    }
    items.forEach((x) => {
      const opt = document.createElement('option');
      opt.value = x.name;
      opt.textContent = x.name;
      snapshotFileSelect.appendChild(opt);
    });
  };

  snapshotFolderSelect.onchange = () => {
    if (mode === 'load') loadFiles();
  };

  if (mode === 'load') {
    await loadFiles();
  }

  snapshotModalOk.onclick = async () => {
    if (mode === 'save') {
      if (!lastBlueprint) return alert('请先加载蓝图');
      const folderName = snapshotFolderSelect.value;
      const customName = snapshotNameInput.value.trim() || defaultName;
      const meta = {
        file_key: fileKey,
        node_id: nodeId || null,
        mode: bpMode,
        depth,
        folder: folderName,
        name: customName,
        timestamp: new Date().toISOString()
      };
  const normalized = buildSnapshotNodesForSave();
  const nodes = Array.isArray(normalized) ? normalized : normalized.nodes;
  const edges = Array.isArray(normalized) ? pinConnections.slice() : (normalized.edges || pinConnections.slice());
  const payload = {
    meta,
    nodes,
    edges
  };
      setStatus('saving snapshot...');
      const res = await fetch(backend + '/api/blueprint-main/snapshots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setStatus('snapshot saved: ' + (data.path || 'ok'));
    } else {
      const folderName = snapshotFolderSelect.value;
      const choice = snapshotFileSelect.value;
      if (!choice) return;
      const url = new URL(backend + '/api/blueprint-main/snapshots/' + encodeURIComponent(choice));
      if (folderName) url.searchParams.set('folder', folderName);
      setStatus('loading snapshot...');
      const res = await fetch(url);
      if (!res.ok) {
        setStatus('snapshot load failed: ' + res.status);
        return;
      }
      const data = await res.json();
      lastBlueprint = data;
      pinConnections = data.edges || [];
      resetDerivedFlowState();
      setActiveNav('blueprint');
      initScene();
      const maxDepth = data?.meta?.depth ?? getDepthValue();
      if (data.nodes && data.nodes.length > 0) {
        renderBlueprintMulti({ ...data, figma: { ...(data.figma || {}), root_bbox: data?.meta?.root_bbox || data?.figma?.root_bbox || null } }, maxDepth);
        renderLayerListBlueprintMulti(data, maxDepth);
      }
      renderFlowTree();
      setStatus('snapshot loaded');
    }
    snapshotModal.style.display = 'none';
  };
}

undoEdgeBtn.onclick = () => {
  if (pinConnections.length === 0) return;
  pinConnections.pop();
  lastPinConnection = null;
  drawEdges();
};

window.addEventListener('resize', drawEdges);
canvas.addEventListener('scroll', () => {
  updateGridPosition();
  drawEdges();
  persistCanvasState();
});

scene.addEventListener('contextmenu', (e) => {
  const deleted = tryDeleteEdgeAt(e.clientX, e.clientY);
  if (deleted) {
    e.preventDefault();
  }
});

canvas.addEventListener('contextmenu', (e) => {
  const deleted = tryDeleteEdgeAt(e.clientX, e.clientY);
  if (deleted) {
    e.preventDefault();
  }
});

canvas.addEventListener('wheel', (e) => {
  if (!(e.ctrlKey || e.metaKey)) return;
  e.preventDefault();
  e.stopPropagation();
  const delta = e.deltaY > 0 ? -0.1 : 0.1;
  applyZoom(zoomLevel + delta, e.clientX, e.clientY);
}, { passive: false });

window.addEventListener('wheel', (e) => {
  if (!(e.ctrlKey || e.metaKey)) return;
  e.preventDefault();
  if (canvas.contains(e.target)) {
    e.stopPropagation();
  }
}, { passive: false, capture: true });

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && (e.key === '+' || e.key === '=' || e.key === '-' || e.key === '0')) {
    e.preventDefault();
  }
}, { capture: true });

let isPanning = false;
let panStart = { x: 0, y: 0, left: 0, top: 0 };
canvas.addEventListener('mousedown', (e) => {
  if (e.button !== 1) return;
  e.preventDefault();
  isPanning = true;
  panStart = {
    x: e.clientX,
    y: e.clientY,
    left: canvas.scrollLeft,
    top: canvas.scrollTop
  };
  canvas.classList.add('panning');
});
window.addEventListener('mousemove', (e) => {
  if (!isPanning) return;
  const dx = e.clientX - panStart.x;
  const dy = e.clientY - panStart.y;
  canvas.scrollLeft = panStart.left - dx;
  canvas.scrollTop = panStart.top - dy;
});
window.addEventListener('mouseup', () => {
  if (!isPanning) return;
  isPanning = false;
  canvas.classList.remove('panning');
});

layoutBtn.onclick = () => {
  if (blueprintMode) return;
  layoutMode = layoutMode === 'absolute' ? 'grouped' : 'absolute';
  layoutBtn.textContent = layoutMode === 'absolute' ? '布局: 还原' : '布局: 分区';
  if (nodes.length === 0) return;
  if (layoutMode === 'absolute') {
    renderAbsolute(lastGroups || []);
  } else {
    renderGroups(lastGroups || []);
  }
};

function renderAbsolute(groups) {
  clearCanvas();
  lastGroups = groups;
  const scale = parseFloat(document.getElementById('scale').value || '0.18');
  const gb = groups.map(g => g.bbox).filter(Boolean);
  const xs = gb.map(b => b[0]);
  const ys = gb.map(b => b[1]);
  const xe = gb.map(b => b[0] + b[2]);
  const ye = gb.map(b => b[1] + b[3]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const maxX = Math.max(...xe);
  const maxY = Math.max(...ye);
  const w = Math.max(1, maxX - minX);
  const h = Math.max(1, maxY - minY);

  const contentW = w * scale + 200;
  const contentH = h * scale + 200;
  scene.style.width = contentW + 'px';
  scene.style.height = contentH + 'px';
  updateSceneBaseSize();

  groups.forEach(g => {
    if (!g.bbox) return;
    const [x, y, bw, bh] = g.bbox;
    const gx = ((x - minX) / w) * (w * scale) + 60;
    const gy = ((y - minY) / h) * (h * scale) + 60;
    const gw = (bw / w) * (w * scale);
    const gh = (bh / h) * (h * scale);
    const box = document.createElement('div');
    box.className = 'group-box';
    box.style.left = gx + 'px';
    box.style.top = gy + 'px';
    box.style.width = gw + 'px';
    box.style.height = gh + 'px';
    scene.appendChild(box);

    const label = document.createElement('div');
    label.className = 'group-label';
    label.textContent = g.group_name || 'Group';
    label.style.left = gx + 'px';
    label.style.top = (gy - 20) + 'px';
    scene.appendChild(label);
  });

  const allNodes = groups.flatMap(g => g.nodes || []);
  allNodes.forEach((n, idx) => {
    const div = document.createElement('div');
    div.className = 'node';
    div.id = 'node-' + idx;
    div.textContent = n.name || 'node';
    if (typeof n.depth === 'number') {
      const badge = document.createElement('span');
      badge.className = 'depth-badge';
      badge.textContent = `L${n.depth}`;
      div.appendChild(badge);
    }
    const nx = ((n.bbox[0] - minX) / w) * (w * scale) + 60;
    const ny = ((n.bbox[1] - minY) / h) * (h * scale) + 60;
    div.style.left = nx + 'px';
    div.style.top = ny + 'px';
    div.onclick = () => {
      if (selected === null) {
        selected = idx;
        div.classList.add('selected');
      } else if (selected === idx) {
        selected = null;
        div.classList.remove('selected');
      } else {
        connections.push({ from: selected, to: idx });
        scene.querySelector('#node-' + selected).classList.remove('selected');
        selected = null;
        drawEdges();
      }
    };
    scene.appendChild(div);
  });
  drawEdges();
}

function renderGroups(groups) {
  clearCanvas();
  const rect = canvas.getBoundingClientRect();
  let yOffset = 40;
  const padding = 60;
  groups.forEach((g, gi) => {
    const label = document.createElement('div');
    label.className = 'group-label';
    label.textContent = g.group_name || 'Group';
    label.style.left = '20px';
    label.style.top = yOffset + 'px';
    scene.appendChild(label);

    const groupRect = { x: 40, y: yOffset + 30, w: rect.width - 120, h: 260 };
    const box = document.createElement('div');
    box.className = 'group-box';
    box.style.left = groupRect.x + 'px';
    box.style.top = groupRect.y + 'px';
    box.style.width = groupRect.w + 'px';
    box.style.height = groupRect.h + 'px';
    scene.appendChild(box);

    const list = g.nodes || [];
    if (list.length === 0) {
      yOffset += groupRect.h + padding;
      return;
    }
    const xs = list.map(n => n.bbox[0]);
    const ys = list.map(n => n.bbox[1]);
    const xe = list.map(n => n.bbox[0] + n.bbox[2]);
    const ye = list.map(n => n.bbox[1] + n.bbox[3]);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xe);
    const maxY = Math.max(...ye);
    const w = Math.max(1, maxX - minX);
    const h = Math.max(1, maxY - minY);

    list.forEach((n, idx) => {
      const globalIdx = nodes.findIndex(nn => nn.id === n.id);
      const div = document.createElement('div');
      div.className = 'node';
      div.id = 'node-' + (globalIdx >= 0 ? globalIdx : `${gi}-${idx}`);
      div.textContent = n.name || 'node';
      if (typeof n.depth === 'number') {
        const badge = document.createElement('span');
        badge.className = 'depth-badge';
        badge.textContent = `L${n.depth}`;
        div.appendChild(badge);
      }
      const nx = ((n.bbox[0] - minX) / w) * (groupRect.w - 200) + groupRect.x + 80;
      const ny = ((n.bbox[1] - minY) / h) * (groupRect.h - 120) + groupRect.y + 40;
      div.style.left = nx + 'px';
      div.style.top = ny + 'px';
      div.onclick = () => {
        const nodeId = div.id.replace('node-','');
        if (selected === null) {
          selected = nodeId;
          div.classList.add('selected');
        } else if (selected === nodeId) {
          selected = null;
          div.classList.remove('selected');
        } else {
          connections.push({ from: selected, to: nodeId });
          scene.querySelector('#node-' + selected).classList.remove('selected');
          selected = null;
          drawEdges();
        }
      };
      scene.appendChild(div);
    });

    yOffset += groupRect.h + padding;
  });
  drawEdges();
  updateSceneBaseSize();
}

const depthSlider = document.getElementById('layerDepth');
const depthVal = document.getElementById('layerDepthVal');
const applyDepth = document.getElementById('applyDepth');

depthSlider.oninput = () => {
  depthVal.textContent = depthSlider.value;
};

applyDepth.onclick = () => {
  if (!lastData) return;
  const maxDepth = getDepthValue();
  const filterNodes = (list) => (list || []).filter(n => typeof n.depth === 'number' ? n.depth <= maxDepth : true);
  if (blueprintMode && lastBlueprint) {
    if (previewVisible) closePreviewPopover();
    if (lastBlueprint.nodes && Array.isArray(lastBlueprint.nodes)) {
      renderBlueprintMulti(lastBlueprint, maxDepth);
      renderLayerListBlueprintMulti(lastBlueprint, maxDepth);
    } else {
      renderBlueprintNode(lastBlueprint, maxDepth);
      renderLayerListBlueprint(lastBlueprint, maxDepth);
    }
    return;
  }
  if (lastData.groups && lastData.groups.length > 0) {
    const newGroups = lastData.groups.map(g => ({
      ...g,
      nodes: filterNodes(g.nodes)
    }));
    lastGroups = newGroups;
    if (layoutMode === 'absolute') {
      renderAbsolute(newGroups);
    } else {
      renderGroups(newGroups);
    }
  } else {
    nodes = filterNodes(lastData.nodes || []);
    renderNodes(nodes);
  }
  renderLayerList();
};

function renderLayerList() {
  const layerList = getLayerListEl();
  if (!layerList) return;
  layerList.innerHTML = '';
  if (!nodes || nodes.length === 0) return;
  const items = nodes
    .slice()
    .sort((a, b) => (a.depth ?? 0) - (b.depth ?? 0))
    .map((n) => {
      const div = document.createElement('div');
      div.className = 'side-item';
      div.textContent = `L${n.depth ?? '?'} · ${n.name || n.id}`;
      return div;
    });
  items.forEach(i => layerList.appendChild(i));
}

function renderBlueprintNode(data, maxDepth = null) {
  clearCanvas();
  const node = data.node || {};
  lastBlueprint = data;
  lastBlueprintNode = node;
  lastBlueprintRootBBox = data?.figma?.root_bbox || node.bbox || null;
  const sections = data.sections || [];
  currentBlueprintNodes = [node];
  currentBlueprintDepth = maxDepth;
  scene.classList.add('blueprint-scene');
  const pad = infiniteCanvasPad;
  lastCenterPad = pad;
  scene.style.width = (canvas.clientWidth + pad * 2) + 'px';
  scene.style.height = (canvas.clientHeight + pad * 2) + 'px';

  const title = document.createElement('div');
  title.className = 'bp-title';
  title.textContent = getBlueprintDisplayName(node);
  title.onclick = (e) => togglePreviewPopover(data, e);
  scene.appendChild(title);

  const card = document.createElement('div');
  card.className = 'bp-node';
  card.style.pointerEvents = 'auto';
  card.dataset.nodeId = node.id || node.name || 'node';
  card.dataset.nodeName = node.name || 'Node';
  card.style.left = (pad + 140) + 'px';
  card.style.top = (pad + 120) + 'px';
  card.style.width = '360px';
  scene.appendChild(card);
  updateSceneBaseSize();
  attachNodeHandlers(card);

  const header = document.createElement('div');
  header.className = 'bp-header';
  const headerTitle = document.createElement('span');
  headerTitle.className = 'bp-header-title';
  headerTitle.textContent = getBlueprintDisplayName(node);
  headerTitle.onpointerdown = (e) => {
    if (!combineMode) return;
    e.preventDefault();
    e.stopPropagation();
    toggleCombineSelect(card);
  };
  headerTitle.onclick = (e) => {
    if (!combineMode) return;
    e.preventDefault();
    e.stopPropagation();
  };
  header.appendChild(headerTitle);
  const headerPin = document.createElement('span');
  headerPin.className = 'bp-header-pin';
  headerPin.setAttribute('data-pin-id', `node-${node.id || node.name || 'node'}`);
  header.appendChild(headerPin);
  attachPinHandlers(headerPin);
  pinMetaById.set(`node-${node.id || node.name || 'node'}`, { data: { bbox: node.bbox }, node, root: data });
  card.appendChild(header);

  previewPins = [];

  sections.forEach((sec) => {
    const secWrap = document.createElement('div');
    secWrap.className = 'bp-section';
    const label = document.createElement('div');
    label.className = 'bp-section-title';
    label.textContent = sec.title;
    secWrap.appendChild(label);

    let pins = (sec.pins || []).filter(p => {
      if (maxDepth === null || maxDepth === undefined) return true;
      const override = viewDepthOverrides[String(node.id || node.name)];
      const limit = typeof override === 'number' ? override : maxDepth;
      return typeof p.depth === 'number' ? p.depth <= limit : true;
    });
    if (sec.title === 'MAIN') {
      pins = injectDecisionPins(node, pins);
    }
    pins.forEach((p) => {
      const pin = document.createElement('div');
      pin.className = 'bp-pin ' + (p.side === 'right' ? 'right' : 'left');
      pin.setAttribute('data-pin-id', p.id);
      if (p.bbox && node.bbox) {
        pin.setAttribute('data-bbox', JSON.stringify(p.bbox));
      }
      const circle = document.createElement('span');
      circle.className = 'bp-pin-circle';
      pin.appendChild(circle);
      const text = document.createElement('span');
      text.className = 'bp-pin-text';
      const depthLabel = p.depth === undefined || p.depth === null ? '?' : p.depth;
      text.textContent = `${p.name} (L${depthLabel})`;
      pin.appendChild(text);
      secWrap.appendChild(pin);
      attachPinHandlers(pin);
      if (p.id) pinMetaById.set(p.id, { data: p, node, root: data });

      pin.onmouseenter = () => {
        showPreviewBBox(p, node);
        pin.classList.add('hover');
      };
      pin.onmouseleave = () => {
        pin.classList.remove('hover');
      };
      pin.addEventListener('click', (e) => {
        if (pinMode !== 'view') return;
        viewSelectedNodeId = String(node.id || node.name);
        if (viewDepthSelect) viewDepthSelect.value = String(viewDepthOverrides[viewSelectedNodeId] ?? getDepthValue());
        openPreviewPopoverAt(data, e, node);
        showPreviewBBox(p, node);
      });

      previewPins.push({ pin, data: p, node });
    });

    card.appendChild(secWrap);
  });
  drawEdges();
  centerCanvasIfNeeded(pad);
}

function renderLayerListBlueprint(data, maxDepth = null) {
  const layerList = getLayerListEl();
  if (!layerList) return;
  layerList.innerHTML = '';
  const sections = data.sections || [];
  const pins = sections.flatMap(s => s.pins || []);
  const list = pins
    .filter(p => maxDepth === null || (typeof p.depth === 'number' ? p.depth <= maxDepth : true))
    .sort((a, b) => (a.depth ?? 0) - (b.depth ?? 0));
  list.forEach((p) => {
    const div = document.createElement('div');
    div.className = 'side-item';
    div.textContent = `L${p.depth ?? '?'} · ${p.name || p.id}`;
    layerList.appendChild(div);
  });
}

function renderLayerListBlueprintMulti(data, maxDepth = null) {
  const layerList = getLayerListEl();
  if (!layerList) return;
  layerList.innerHTML = '';
  const nodesData = data.nodes || [];
  const pins = nodesData.flatMap(n => (n.sections || []).flatMap(s => s.pins || []));
  const list = pins
    .filter(p => maxDepth === null || (typeof p.depth === 'number' ? p.depth <= maxDepth : true))
    .sort((a, b) => (a.depth ?? 0) - (b.depth ?? 0));
  list.forEach((p) => {
    const div = document.createElement('div');
    div.className = 'side-item';
    div.textContent = `L${p.depth ?? '?'} · ${p.name || p.id}`;
    layerList.appendChild(div);
  });
}

function renderBlueprintMulti(data, maxDepth = null) {
  clearCanvas();
  const nodesData = normalizeDecisionNodesForDisplay(data.nodes || []);
  lastBlueprint = data;
  lastBlueprintRootBBox = data?.figma?.root_bbox || null;
  previewPins = [];
  pinMetaById = new Map();
  pinMetaById = new Map();
  currentBlueprintNodes = nodesData.slice();
  currentBlueprintDepth = maxDepth;
  if (!nodesData.length) return;
  const pad = infiniteCanvasPad;
  lastCenterPad = pad;
  const columns = Math.max(2, Math.min(4, Math.ceil(nodesData.length / 2)));
  const cardW = 320;
  const gap = 40;
  const startX = pad + 80;
  const startY = pad + 120;
  nodesData.forEach((n, i) => {
    const col = i % columns;
    const row = Math.floor(i / columns);
    const x = (typeof n.x === 'number') ? n.x : (startX + col * (cardW + gap));
    const y = (typeof n.y === 'number') ? n.y : (startY + row * 420);
    renderBlueprintCard(n, x, y, maxDepth);
  });
  updateSceneBaseSize();
  scene.style.width = Math.max(scene.offsetWidth, canvas.clientWidth + pad * 2) + 'px';
  scene.style.height = Math.max(scene.offsetHeight, canvas.clientHeight + pad * 2) + 'px';
  centerCanvasIfNeeded(pad);
}

function renderBlueprintCard(node, x, y, maxDepth = null) {
  const sections = node.sections || [];
  const card = document.createElement('div');
  card.className = 'bp-node';
  card.style.pointerEvents = 'auto';
  card.dataset.nodeId = node.id || node.name || 'node';
  card.dataset.nodeName = node.name || 'Node';
  card.style.left = x + 'px';
  card.style.top = y + 'px';
  card.style.width = '320px';
  scene.appendChild(card);
  attachNodeHandlers(card);

  const header = document.createElement('div');
  header.className = 'bp-header';
  const headerTitle = document.createElement('span');
  headerTitle.className = 'bp-header-title';
  headerTitle.textContent = getBlueprintDisplayName(node);
  headerTitle.onpointerdown = (e) => {
    if (!combineMode) return;
    e.preventDefault();
    e.stopPropagation();
    toggleCombineSelect(card);
  };
  headerTitle.onclick = (e) => {
    if (!combineMode) return;
    e.preventDefault();
    e.stopPropagation();
  };
  header.appendChild(headerTitle);
  const headerPin = document.createElement('span');
  headerPin.className = 'bp-header-pin';
  headerPin.setAttribute('data-pin-id', `node-${node.id || node.name || 'node'}`);
  header.appendChild(headerPin);
  attachPinHandlers(headerPin);
  pinMetaById.set(`node-${node.id || node.name || 'node'}`, { data: { bbox: node.bbox }, node, root: lastBlueprint });
  card.appendChild(header);

  sections.forEach((sec) => {
    const secWrap = document.createElement('div');
    secWrap.className = 'bp-section';
    const label = document.createElement('div');
    label.className = 'bp-section-title';
    label.textContent = sec.title;
    secWrap.appendChild(label);

    let pins = (sec.pins || []).filter(p => {
      if (maxDepth === null || maxDepth === undefined) return true;
      const override = viewDepthOverrides[String(node.id || node.name)];
      const limit = typeof override === 'number' ? override : maxDepth;
      return typeof p.depth === 'number' ? p.depth <= limit : true;
    });
    if (sec.title === 'MAIN') {
      pins = injectDecisionPins(node, pins);
    }

    pins.forEach((p) => {
      const pin = document.createElement('div');
      pin.className = 'bp-pin ' + (p.side === 'right' ? 'right' : 'left');
      pin.setAttribute('data-pin-id', p.id);
      const circle = document.createElement('span');
      circle.className = 'bp-pin-circle';
      pin.appendChild(circle);
      const text = document.createElement('span');
      text.className = 'bp-pin-text';
      const depthLabel = p.depth === undefined || p.depth === null ? '?' : p.depth;
      text.textContent = `${p.name} (L${depthLabel})`;
      pin.appendChild(text);
      secWrap.appendChild(pin);
      attachPinHandlers(pin);
      if (p.id) pinMetaById.set(p.id, { data: p, node, root: lastBlueprint });

      pin.onmouseenter = () => {
        showPreviewBBox(p, node);
        pin.classList.add('hover');
      };
      pin.onmouseleave = () => {
        pin.classList.remove('hover');
      };
      pin.addEventListener('click', (e) => {
        if (pinMode !== 'view') return;
        viewSelectedNodeId = String(node.id || node.name);
        if (viewDepthSelect) viewDepthSelect.value = String(viewDepthOverrides[viewSelectedNodeId] ?? getDepthValue());
        openPreviewPopoverAt(lastBlueprint, e, node);
        showPreviewBBox(p, node);
      });
      previewPins.push({ pin, data: p, node });
    });

    card.appendChild(secWrap);
  });
}

function ensurePreviewPopover() {
  if (previewPopover) return;
  previewPopover = document.createElement('div');
  previewPopover.className = 'bp-popover';
  previewPopover.innerHTML = `
    <div class="bp-popover-header">
      <span>Figma Preview</span>
      <button class="bp-popover-close">Close</button>
    </div>
    <div class="bp-preview">
      <img class="bp-image" alt="preview" />
      <div class="bp-bbox"></div>
    </div>
  `;
  scene.appendChild(previewPopover);
  previewImg = previewPopover.querySelector('.bp-image');
  previewBox = previewPopover.querySelector('.bp-bbox');
  previewPopover.querySelector('.bp-popover-close').onclick = closePreviewPopover;
  const header = previewPopover.querySelector('.bp-popover-header');
  if (header) {
    header.onpointerdown = (e) => {
      if (e.button !== 0) return;
      popoverDragging = true;
      const left = parseFloat(previewPopover.style.left || '0');
      const top = parseFloat(previewPopover.style.top || '0');
      popoverDragStart = {
        x: e.clientX,
        y: e.clientY,
        left: Number.isNaN(left) ? 0 : left,
        top: Number.isNaN(top) ? 0 : top
      };
      header.setPointerCapture?.(e.pointerId);
      e.preventDefault();
      e.stopPropagation();
    };
    header.onpointermove = (e) => {
      if (!popoverDragging || !previewPopover) return;
      const dx = (e.clientX - popoverDragStart.x) / zoomLevel;
      const dy = (e.clientY - popoverDragStart.y) / zoomLevel;
      previewPopover.style.left = (popoverDragStart.left + dx) + 'px';
      previewPopover.style.top = (popoverDragStart.top + dy) + 'px';
    };
    header.onpointerup = () => {
      popoverDragging = false;
      if (previewPopover) {
        const left = parseFloat(previewPopover.style.left || '0');
        const top = parseFloat(previewPopover.style.top || '0');
        popoverLastPos = { left: Number.isNaN(left) ? 0 : left, top: Number.isNaN(top) ? 0 : top };
      }
    };
  }
  previewPopover.querySelector('.bp-preview').onclick = (e) => handlePreviewClick(e);
}

function togglePreviewPopover(data, evt = null) {
  if (!data?.figma?.image_url) return;
  ensurePreviewPopover();
  if (!previewVisible) {
    previewImg.src = data.figma.image_url;
    previewPopover.style.display = 'block';
    previewVisible = true;
    placePopoverFixed();
    updatePreviewCrop(null);
  } else {
    closePreviewPopover();
  }
}

function openPreviewPopoverAt(data, evt, node = null) {
  if (!data?.figma?.image_url) return;
  ensurePreviewPopover();
  previewImg.src = data.figma.image_url;
  previewPopover.style.display = 'block';
  previewVisible = true;
  placePopoverFixed(evt);
  updatePreviewCrop(node);
}

function closePreviewPopover() {
  if (!previewPopover) return;
  previewPopover.style.display = 'none';
  previewVisible = false;
  if (previewBox) previewBox.style.display = 'none';
}

function showPreviewBBox(p, node) {
  if (!previewPopover || previewPopover.style.display !== 'block') return;
  if (!previewImg || !previewBox || !p.bbox || !node || !node.bbox) return;
  const base = lastBlueprintRootBBox || node.bbox;
  const [nx, ny] = base;
  const [bx, by, bw, bh] = p.bbox;
  const { scale, offsetX, offsetY } = previewTransform;
  const x = (bx - nx) * scale + offsetX;
  const y = (by - ny) * scale + offsetY;
  const w = bw * scale;
  const h = bh * scale;
  previewBox.style.display = 'block';
  previewBox.style.left = x + 'px';
  previewBox.style.top = y + 'px';
  previewBox.style.width = w + 'px';
  previewBox.style.height = h + 'px';
}

function handlePreviewClick(e) {
  if (!previewImg || !previewBox || !lastBlueprintRootBBox) return;
  const rect = previewImg.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const [nx, ny] = lastBlueprintRootBBox;
  const { scale, offsetX, offsetY } = previewTransform;
  const absX = nx + (x - offsetX) / (scale || 1);
  const absY = ny + (y - offsetY) / (scale || 1);
  const found = previewPins.find(p => {
    const b = p.data.bbox;
    if (!b) return false;
    return absX >= b[0] && absX <= b[0] + b[2] && absY >= b[1] && absY <= b[1] + b[3];
  });
  previewPins.forEach(p => p.pin.classList.remove('active'));
  if (found) {
    found.pin.classList.add('active');
    showPreviewBBox(found.data, found.node || lastBlueprintNode || lastBlueprint?.node);
    found.pin.scrollIntoView({ behavior: 'smooth', block: 'center' });
    updatePreviewCrop(found.node || lastBlueprintNode || lastBlueprint?.node);
  }
}

function placePopoverFixed(evt = null) {
  if (!previewPopover || !scene) return;
  const sceneRect = scene.getBoundingClientRect();
  const popRect = previewPopover.getBoundingClientRect();
  const padding = 16;
  if (popoverLastPos) {
    previewPopover.style.left = popoverLastPos.left + 'px';
    previewPopover.style.top = popoverLastPos.top + 'px';
    return;
  }
  const x = Math.max(padding, (sceneRect.width - popRect.width) / 2);
  let y = Math.max(padding, (sceneRect.height - popRect.height) / 2);
  if (evt) {
    const anchorY = evt.clientY - sceneRect.top;
    y = Math.max(padding, Math.min(sceneRect.height - popRect.height - padding, anchorY - popRect.height / 2));
  }
  previewPopover.style.left = x + 'px';
  previewPopover.style.top = y + 'px';
}

function centerCanvasIfNeeded(pad) {
  if (didCenterScroll) return;
  canvas.scrollLeft = pad / 2;
  canvas.scrollTop = pad / 2;
  didCenterScroll = true;
  updateGridPosition();
}

function attachNodeHandlers(card) {
  const beginDrag = (e) => {
    console.log('[drag] down', { target: e.target, node: card.dataset.nodeName, type: e.type });
    if (e.button !== 0) return;
    if (e.target.closest('.bp-pin') || e.target.closest('.bp-header-pin')) return;
    if (combineMode && e.target.closest('.bp-header-title')) {
      toggleCombineSelect(card);
      return;
    }
    if (pinMode === 'view' && e.target.closest('.bp-header-title')) {
      const nodeId = card.dataset.nodeId;
      viewSelectedNodeId = nodeId;
      if (viewDepthSelect) viewDepthSelect.value = String(viewDepthOverrides[nodeId] ?? getDepthValue());
      const node = getBlueprintNodeById(nodeId);
      openPreviewPopoverAt(lastBlueprint, e, node || lastBlueprint?.node);
      showPreviewBBox({ bbox: node?.bbox }, node || lastBlueprint?.node);
      return;
    }
    e.preventDefault();
    isDraggingNode = true;
    dragDebugCount = 0;
    if (activeBlueprintNode && activeBlueprintNode !== card) {
      activeBlueprintNode.classList.remove('bp-selected');
    }
    activeBlueprintNode = card;
    const left = parseFloat(card.style.left || '0');
    const top = parseFloat(card.style.top || '0');
    dragStart = {
      x: e.clientX,
      y: e.clientY,
      left: Number.isNaN(left) ? 0 : left,
      top: Number.isNaN(top) ? 0 : top
    };
    card.classList.add('bp-selected');
    if (e.pointerId && card.setPointerCapture) {
      card.setPointerCapture(e.pointerId);
    }
    document.body.style.userSelect = 'none';
    ensureDragOverlay();
    dragOverlay.style.display = 'block';
  };
  card.onpointerdown = beginDrag;
  card.onmousedown = beginDrag;
  card.oncontextmenu = (e) => {
    e.preventDefault();
    activeBlueprintNode = card;
    card.classList.add('bp-selected');
    deleteActiveBlueprintNode();
  };
}

function attachPinHandlers(pinEl) {
  pinEl.addEventListener('click', (e) => {
    e.stopPropagation();
    if (pinMode !== 'link') {
      if (pinMode === 'view') {
        const pinId = pinEl.getAttribute('data-pin-id');
        const meta = pinId ? pinMetaById.get(pinId) : null;
        if (meta) {
          openPreviewPopoverAt(meta.root || lastBlueprint, e, meta.node || lastBlueprint?.node);
          if (meta.data) showPreviewBBox(meta.data, meta.node || lastBlueprint?.node);
        }
      }
      return;
    }
    const pinId = pinEl.getAttribute('data-pin-id');
    if (!pinId) return;
    if (!pendingPin) {
      pendingPin = pinId;
      pinEl.classList.add('pin-selected');
      return;
    }
    if (pendingPin === pinId) {
      pendingPin = null;
      pinEl.classList.remove('pin-selected');
      return;
    }
    const conn = { from: pendingPin, to: pinId };
    pinConnections.push(conn);
    lastPinConnection = conn;
    const prev = scene.querySelector(`[data-pin-id="${pendingPin}"]`);
    if (prev) prev.classList.remove('pin-selected');
    pendingPin = null;
    drawEdges();
  });
}

function onDragMove(e) {
  if (!isDraggingNode || !activeBlueprintNode) return;
  if (dragDebugCount < 5) {
    console.log('[drag] move', { x: e.clientX, y: e.clientY });
    dragDebugCount += 1;
  }
  const dx = (e.clientX - dragStart.x) / zoomLevel;
  const dy = (e.clientY - dragStart.y) / zoomLevel;
  activeBlueprintNode.style.left = (dragStart.left + dx) + 'px';
  activeBlueprintNode.style.top = (dragStart.top + dy) + 'px';
  drawEdges();
}

document.addEventListener('pointermove', onDragMove);
document.addEventListener('mousemove', onDragMove);

document.addEventListener('pointermove', (e) => {
  if (!popoverDragging || !previewPopover) return;
  const dx = (e.clientX - popoverDragStart.x) / zoomLevel;
  const dy = (e.clientY - popoverDragStart.y) / zoomLevel;
  previewPopover.style.left = (popoverDragStart.left + dx) + 'px';
  previewPopover.style.top = (popoverDragStart.top + dy) + 'px';
});

function endDrag() {
  if (!isDraggingNode) return;
  console.log('[drag] up');
  isDraggingNode = false;
  if (activeBlueprintNode) {
    activeBlueprintNode.classList.remove('bp-selected');
  }
  document.body.style.userSelect = '';
  if (dragOverlay) dragOverlay.style.display = 'none';
}

document.addEventListener('pointerup', endDrag);
document.addEventListener('mouseup', endDrag);
document.addEventListener('pointercancel', endDrag);
window.addEventListener('blur', endDrag);

document.addEventListener('pointerup', () => {
  popoverDragging = false;
  if (previewPopover) {
    const left = parseFloat(previewPopover.style.left || '0');
    const top = parseFloat(previewPopover.style.top || '0');
    popoverLastPos = { left: Number.isNaN(left) ? 0 : left, top: Number.isNaN(top) ? 0 : top };
  }
});

function ensureDragOverlay() {
  if (dragOverlay) return;
  dragOverlay = document.createElement('div');
  dragOverlay.className = 'drag-overlay';
  dragOverlay.style.display = 'none';
  document.body.appendChild(dragOverlay);
  dragOverlay.addEventListener('pointermove', onDragMove);
  dragOverlay.addEventListener('mousemove', onDragMove);
  dragOverlay.addEventListener('pointerup', endDrag);
  dragOverlay.addEventListener('mouseup', endDrag);
}

document.addEventListener('mousedown', (e) => {
  const target = e.target;
  const cls = target && target.className ? target.className.toString() : '';
  console.log('[debug] mousedown', { cls, tag: target?.tagName });
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (pendingPin) {
      const prev = scene.querySelector(`[data-pin-id="${pendingPin}"]`);
      if (prev) prev.classList.remove('pin-selected');
      pendingPin = null;
      return;
    }
    if (lastPinConnection) {
      const idx = pinConnections.lastIndexOf(lastPinConnection);
      if (idx >= 0) {
        pinConnections.splice(idx, 1);
        lastPinConnection = null;
        drawEdges();
      }
      return;
    }
  }
  if (e.key !== 'Delete' && e.key !== 'Backspace') return;
  deleteActiveBlueprintNode();
});

function deleteActiveBlueprintNode() {
  if (!activeBlueprintNode) return;
  if (previewVisible) closePreviewPopover();
  const id = activeBlueprintNode.dataset.nodeId;
  if (id) {
    currentBlueprintNodes = currentBlueprintNodes.filter(n => String(n.id || n.name) !== String(id));
  }
  activeBlueprintNode.remove();
  activeBlueprintNode = null;
  drawEdges();
}

canvas.addEventListener('dblclick', (e) => {
  if (e.target.closest('.bp-popover')) return;
  const pad = lastCenterPad;
  canvas.scrollLeft = pad / 2;
  canvas.scrollTop = pad / 2;
  updateGridPosition();
});

function recenterInfinite() {
  if (!scene) return;
  const maxX = canvas.scrollWidth - canvas.clientWidth;
  const maxY = canvas.scrollHeight - canvas.clientHeight;
  if (maxX <= 0 || maxY <= 0) return;
  const midX = maxX / 2;
  const midY = maxY / 2;
  const nearX = canvas.scrollLeft < infiniteMargin || canvas.scrollLeft > maxX - infiniteMargin;
  const nearY = canvas.scrollTop < infiniteMargin || canvas.scrollTop > maxY - infiniteMargin;
  if (!nearX && !nearY) return;

  const dx = midX - canvas.scrollLeft;
  const dy = midY - canvas.scrollTop;

  const moveEls = scene.querySelectorAll('.node, .group-box, .group-label, .bp-node, .bp-title, .bp-popover');
  moveEls.forEach((el) => {
    const left = parseFloat(el.style.left || '0');
    const top = parseFloat(el.style.top || '0');
    if (!Number.isNaN(left)) el.style.left = (left + dx) + 'px';
    if (!Number.isNaN(top)) el.style.top = (top + dy) + 'px';
  });

  canvas.scrollLeft = midX;
  canvas.scrollTop = midY;
  updateGridPosition();
  drawEdges();
}

function updateSceneBaseSize() {
  if (!scene) return;
  const w = scene.offsetWidth || canvas.clientWidth || 2000;
  const h = scene.offsetHeight || canvas.clientHeight || 1200;
  baseSceneWidth = Math.max(w / zoomLevel, minSceneBaseSize);
  baseSceneHeight = Math.max(h / zoomLevel, minSceneBaseSize);
  applyZoom(zoomLevel);
}

function applyZoom(nextZoom, centerX = null, centerY = null) {
  if (!scene) return;
  const prevZoom = zoomLevel;
  zoomLevel = Math.max(0.3, Math.min(2.5, nextZoom));
  scene.style.transformOrigin = '0 0';
  scene.style.transform = `scale(${zoomLevel})`;
  const w = (baseSceneWidth || scene.offsetWidth || 2000) * zoomLevel;
  const h = (baseSceneHeight || scene.offsetHeight || 1200) * zoomLevel;
  scene.style.width = w + 'px';
  scene.style.height = h + 'px';
  canvas.style.setProperty('--grid-scale', zoomLevel.toFixed(3));

  if (centerX !== null && centerY !== null && prevZoom !== zoomLevel) {
    const rect = canvas.getBoundingClientRect();
    const cx = centerX - rect.left;
    const cy = centerY - rect.top;
    const contentX = (canvas.scrollLeft + cx) / prevZoom;
    const contentY = (canvas.scrollTop + cy) / prevZoom;
    canvas.scrollLeft = contentX * zoomLevel - cx;
    canvas.scrollTop = contentY * zoomLevel - cy;
  }
  updateGridPosition();
  drawEdges();
  persistCanvasState();
}

function persistCanvasState() {
  try {
    const state = {
      zoom: zoomLevel,
      scrollLeft: canvas.scrollLeft,
      scrollTop: canvas.scrollTop
    };
    localStorage.setItem(canvasStateKey, JSON.stringify(state));
  } catch {}
}

function restoreCanvasState() {
  try {
    const raw = localStorage.getItem(canvasStateKey);
    if (!raw) return;
    const state = JSON.parse(raw);
    if (state && typeof state.zoom === 'number') zoomLevel = state.zoom;
    if (state && typeof state.scrollLeft === 'number') canvas.scrollLeft = state.scrollLeft;
    if (state && typeof state.scrollTop === 'number') canvas.scrollTop = state.scrollTop;
  } catch {}
}

function tryDeleteEdgeAt(clientX, clientY) {
  if (!scene) return false;
  const rect = scene.getBoundingClientRect();
  const px = clientX - rect.left;
  const py = clientY - rect.top;
  let bestIdx = -1;
  let bestDist = 9999;
  pinConnections.forEach((c, idx) => {
    const a = scene.querySelector(`[data-pin-id="${c.from}"]`);
    const b = scene.querySelector(`[data-pin-id="${c.to}"]`);
    if (!a || !b) return;
    const ra = a.getBoundingClientRect();
    const rb = b.getBoundingClientRect();
    const x1 = ra.left - rect.left + ra.width / 2;
    const y1 = ra.top - rect.top + ra.height / 2;
    const x2 = rb.left - rect.left + rb.width / 2;
    const y2 = rb.top - rect.top + rb.height / 2;
    const dist = pointToSegmentDistance(px, py, x1, y1, x2, y2);
    if (dist < bestDist) {
      bestDist = dist;
      bestIdx = idx;
    }
  });
  if (bestIdx >= 0 && bestDist <= 10) {
    pinConnections.splice(bestIdx, 1);
    drawEdges();
    return true;
  }
  return false;
}

function pointToSegmentDistance(px, py, x1, y1, x2, y2) {
  const vx = x2 - x1;
  const vy = y2 - y1;
  const wx = px - x1;
  const wy = py - y1;
  const c1 = vx * wx + vy * wy;
  if (c1 <= 0) return Math.hypot(px - x1, py - y1);
  const c2 = vx * vx + vy * vy;
  if (c2 <= c1) return Math.hypot(px - x2, py - y2);
  const t = c1 / c2;
  const projX = x1 + t * vx;
  const projY = y1 + t * vy;
  return Math.hypot(px - projX, py - projY);
}

function updatePreviewCrop(node) {
  if (!previewImg) return;
  const maxSize = 320;
  if (!lastBlueprintRootBBox) {
    previewTransform = { scale: 1, offsetX: 0, offsetY: 0, viewW: maxSize, viewH: maxSize };
    previewImg.style.width = maxSize + 'px';
    previewImg.style.height = maxSize + 'px';
    previewImg.style.transform = 'translate(0px, 0px)';
    if (previewImg.parentElement) {
      previewImg.parentElement.style.width = maxSize + 'px';
      previewImg.parentElement.style.height = maxSize + 'px';
    }
    return;
  }
  const [rx, ry, rw, rh] = lastBlueprintRootBBox;
  const rootAspect = rw / (rh || 1);
  let viewW = maxSize;
  let viewH = maxSize;
  if (rootAspect >= 1) {
    viewH = Math.round(maxSize / rootAspect);
  } else {
    viewW = Math.round(maxSize * rootAspect);
  }

  if (previewImg.parentElement) {
    previewImg.parentElement.style.width = viewW + 'px';
    previewImg.parentElement.style.height = viewH + 'px';
  }

  let scale = Math.min(viewW / (rw || 1), viewH / (rh || 1));
  let offsetX = 0;
  let offsetY = 0;

  if (node && node.bbox) {
    const [nx, ny, nw, nh] = node.bbox;
    scale = Math.min(viewW / (nw || 1), viewH / (nh || 1));
    offsetX = - (nx - rx) * scale;
    offsetY = - (ny - ry) * scale;
  }

  const imgW = rw * scale;
  const imgH = rh * scale;
  previewTransform = { scale, offsetX, offsetY, viewW, viewH };
  previewImg.style.width = imgW + 'px';
  previewImg.style.height = imgH + 'px';
  previewImg.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
}
