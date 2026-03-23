import './style.css';

const app = document.getElementById('app');

app.innerHTML = `
  <div class="toolbar">
    <input id="backend" value="http://127.0.0.1:8000" placeholder="Backend URL" />
    <input id="figmaUrl" placeholder="Figma URL (可选，优先解析)" />
    <input id="fileKey" placeholder="Figma file key" />
    <input id="nodeId" placeholder="node id (可选)" />
    <input id="scale" value="0.18" style="width:70px" />
    <button id="loadBtn">加载节点</button>
    <button id="blueprintBtn" class="secondary">蓝图节点</button>
    <button id="saveBtn" class="secondary">保存连线</button>
    <button id="undoEdgeBtn" class="secondary">撤销连线</button>
    <button id="layoutBtn" class="secondary">布局: 还原</button>
    <div class="status" id="status">idle</div>
  </div>
  <div class="workspace">
    <div class="canvas" id="canvas"></div>
    <div class="sidebar">
      <div class="side-title">Layer 深度</div>
      <div class="side-hint">仅用于调试显示层级密度</div>
      <div class="side-row">
        <label>Max Depth</label>
        <input id="layerDepth" type="range" min="1" max="6" value="2" />
        <span id="layerDepthVal">2</span>
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
let infiniteEnabled = true;
let recenterPending = false;
const infiniteMargin = 200;
let lastCenterPad = 600;
let activeBlueprintNode = null;
let isDraggingNode = false;
let dragStart = { x: 0, y: 0, left: 0, top: 0 };
let dragDebugCount = 0;
let dragOverlay = null;

function updateGridPosition() {
  const x = -canvas.scrollLeft;
  const y = -canvas.scrollTop;
  canvas.style.setProperty('--grid-x', x + 'px');
  canvas.style.setProperty('--grid-y', y + 'px');
}
let previewTransform = { scale: 1, offsetX: 0, offsetY: 0, viewW: 280, viewH: 280 };

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
    baseSceneWidth = scene.offsetWidth || canvas.clientWidth || 2000;
    baseSceneHeight = scene.offsetHeight || canvas.clientHeight || 1200;
  }
  applyZoom(zoomLevel);
  updateGridPosition();
}

function setStatus(msg) {
  status.textContent = msg;
}

function clearCanvas() {
  if (scene) {
    scene.querySelectorAll('.node, .group-box, .group-label, .bp-node, .bp-title, .bp-image').forEach((n) => {
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
const layoutBtn = document.getElementById('layoutBtn');

loadBtn.onclick = async () => {
  const backend = document.getElementById('backend').value.trim();
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
  const backend = document.getElementById('backend').value.trim();
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
  initScene();
  renderBlueprintNode(data);
  setStatus(`blueprint: ${data.node?.name || 'node'}`);
};

layerBlueprintBtn.onclick = async () => {
  try {
    const backend = document.getElementById('backend').value.trim();
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
  const backend = document.getElementById('backend').value.trim();
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
  if (infiniteEnabled && !recenterPending) {
    recenterPending = true;
    requestAnimationFrame(() => {
      recenterPending = false;
      recenterInfinite();
    });
  }
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
  if (!e.ctrlKey) return;
  e.preventDefault();
  const delta = e.deltaY > 0 ? -0.1 : 0.1;
  applyZoom(zoomLevel + delta, e.clientX, e.clientY);
}, { passive: false });

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
  lastBlueprintNode = node;
  lastBlueprintRootBBox = node.bbox || null;
  const sections = data.sections || [];
  scene.classList.add('blueprint-scene');
  const pad = 600;
  lastCenterPad = pad;
  scene.style.width = (canvas.clientWidth + pad * 2) + 'px';
  scene.style.height = (canvas.clientHeight + pad * 2) + 'px';

  const title = document.createElement('div');
  title.className = 'bp-title';
  title.textContent = node.name || 'Blueprint Node';
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
  header.textContent = node.name || 'Node';
  const headerPin = document.createElement('span');
  headerPin.className = 'bp-header-pin';
  headerPin.setAttribute('data-pin-id', `node-${node.id || node.name || 'node'}`);
  header.appendChild(headerPin);
  attachPinHandlers(headerPin);
  card.appendChild(header);

  previewPins = [];

  sections.forEach((sec) => {
    const secWrap = document.createElement('div');
    secWrap.className = 'bp-section';
    const label = document.createElement('div');
    label.className = 'bp-section-title';
    label.textContent = sec.title;
    secWrap.appendChild(label);

    const pins = (sec.pins || []).filter(p => {
      if (maxDepth === null || maxDepth === undefined) return true;
      return typeof p.depth === 'number' ? p.depth <= maxDepth : true;
    });
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
      text.textContent = `${p.name} (L${p.depth ?? '?'})`;
      pin.appendChild(text);
      secWrap.appendChild(pin);
      attachPinHandlers(pin);

      pin.onmouseenter = () => {
        showPreviewBBox(p, node);
        pin.classList.add('hover');
      };
      pin.onmouseleave = () => {
        pin.classList.remove('hover');
      };
      pin.addEventListener('click', (e) => {
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
  const nodesData = data.nodes || [];
  lastBlueprintRootBBox = data?.figma?.root_bbox || null;
  previewPins = [];
  if (!nodesData.length) return;
  const pad = 600;
  lastCenterPad = pad;
  const columns = Math.max(2, Math.min(4, Math.ceil(nodesData.length / 2)));
  const cardW = 320;
  const gap = 40;
  const startX = pad + 80;
  const startY = pad + 120;
  nodesData.forEach((n, i) => {
    const col = i % columns;
    const row = Math.floor(i / columns);
    const x = startX + col * (cardW + gap);
    const y = startY + row * 420;
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
  header.textContent = node.name || 'Node';
  const headerPin = document.createElement('span');
  headerPin.className = 'bp-header-pin';
  headerPin.setAttribute('data-pin-id', `node-${node.id || node.name || 'node'}`);
  header.appendChild(headerPin);
  attachPinHandlers(headerPin);
  card.appendChild(header);

  sections.forEach((sec) => {
    const secWrap = document.createElement('div');
    secWrap.className = 'bp-section';
    const label = document.createElement('div');
    label.className = 'bp-section-title';
    label.textContent = sec.title;
    secWrap.appendChild(label);

    const pins = (sec.pins || []).filter(p => {
      if (maxDepth === null || maxDepth === undefined) return true;
      return typeof p.depth === 'number' ? p.depth <= maxDepth : true;
    });

    pins.forEach((p) => {
      const pin = document.createElement('div');
      pin.className = 'bp-pin ' + (p.side === 'right' ? 'right' : 'left');
      pin.setAttribute('data-pin-id', p.id);
      const circle = document.createElement('span');
      circle.className = 'bp-pin-circle';
      pin.appendChild(circle);
      const text = document.createElement('span');
      text.className = 'bp-pin-text';
      text.textContent = `${p.name} (L${p.depth ?? '?'})`;
      pin.appendChild(text);
      secWrap.appendChild(pin);
      attachPinHandlers(pin);

      pin.onmouseenter = () => {
        showPreviewBBox(p, node);
        pin.classList.add('hover');
      };
      pin.onmouseleave = () => {
        pin.classList.remove('hover');
      };
      pin.addEventListener('click', (e) => {
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
  const x = Math.max(padding, sceneRect.width - popRect.width - padding);
  let y = padding + 40;
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
  baseSceneWidth = w / zoomLevel;
  baseSceneHeight = h / zoomLevel;
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
