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

function initScene() {
  if (!scene) {
    scene = document.createElement('div');
    scene.className = 'scene';
    edgesSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    edgesSvg.setAttribute('id', 'edgesSvg');
    scene.appendChild(edgesSvg);
    canvas.appendChild(scene);
  }
}

function setStatus(msg) {
  status.textContent = msg;
}

function clearCanvas() {
  if (scene) {
    scene.querySelectorAll('.node, .group-box, .group-label, .bp-node, .bp-title, .bp-image').forEach((n) => n.remove());
  }
  connections = [];
  selected = null;
  drawEdges();
}

function drawEdges() {
  if (!scene || !edgesSvg) return;
  const rect = scene.getBoundingClientRect();
  edgesSvg.setAttribute('width', rect.width);
  edgesSvg.setAttribute('height', rect.height);
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
  drawEdges();
}

const loadBtn = document.getElementById('loadBtn');
const blueprintBtn = document.getElementById('blueprintBtn');
const saveBtn = document.getElementById('saveBtn');
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
  const data = await res.json();
  lastData = data;
  lastBlueprint = data;
  initScene();
  renderBlueprintNode(data);
  setStatus(`blueprint: ${data.node?.name || 'node'}`);
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

window.addEventListener('resize', drawEdges);

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
}

const depthSlider = document.getElementById('layerDepth');
const depthVal = document.getElementById('layerDepthVal');
const applyDepth = document.getElementById('applyDepth');
const layerList = document.getElementById('layerList');

depthSlider.oninput = () => {
  depthVal.textContent = depthSlider.value;
};

applyDepth.onclick = () => {
  if (!lastData) return;
  const maxDepth = parseInt(depthSlider.value, 10);
  const filterNodes = (list) => (list || []).filter(n => typeof n.depth === 'number' ? n.depth <= maxDepth : true);
  if (blueprintMode && lastBlueprint) {
    renderBlueprintNode(lastBlueprint, maxDepth);
    renderLayerListBlueprint(lastBlueprint, maxDepth);
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
  const sections = data.sections || [];
  scene.classList.add('blueprint-scene');
  scene.style.width = '100%';
  scene.style.height = '100%';

  const title = document.createElement('div');
  title.className = 'bp-title';
  title.textContent = node.name || 'Blueprint Node';
  title.onclick = (e) => togglePreviewPopover(data, e);
  scene.appendChild(title);

  const card = document.createElement('div');
  card.className = 'bp-node';
  card.style.left = '140px';
  card.style.top = '120px';
  card.style.width = '360px';
  scene.appendChild(card);

  const header = document.createElement('div');
  header.className = 'bp-header';
  header.textContent = node.name || 'Node';
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

      pin.onmouseenter = () => {
        showPreviewBBox(p, node);
        pin.classList.add('hover');
      };
      pin.onmouseleave = () => {
        pin.classList.remove('hover');
      };
      pin.onclick = (e) => {
        openPreviewPopoverAt(data, e);
        showPreviewBBox(p, node);
      };

      previewPins.push({ pin, data: p });
    });

    card.appendChild(secWrap);
  });
  drawEdges();
}

function renderLayerListBlueprint(data, maxDepth = null) {
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
  } else {
    closePreviewPopover();
  }
}

function openPreviewPopoverAt(data, evt) {
  if (!data?.figma?.image_url) return;
  ensurePreviewPopover();
  previewImg.src = data.figma.image_url;
  previewPopover.style.display = 'block';
  previewVisible = true;
  placePopoverFixed();
}

function closePreviewPopover() {
  if (!previewPopover) return;
  previewPopover.style.display = 'none';
  previewVisible = false;
  if (previewBox) previewBox.style.display = 'none';
}

function showPreviewBBox(p, node) {
  if (!previewPopover || previewPopover.style.display !== 'block') return;
  if (!previewImg || !previewBox || !p.bbox || !node.bbox) return;
  const [nx, ny, nw, nh] = node.bbox;
  const [bx, by, bw, bh] = p.bbox;
  const relX = (bx - nx) / (nw || 1);
  const relY = (by - ny) / (nh || 1);
  const relW = (bw) / (nw || 1);
  const relH = (bh) / (nh || 1);
  const imgRect = previewImg.getBoundingClientRect();
  const scaleX = imgRect.width;
  const scaleY = imgRect.height;
  previewBox.style.display = 'block';
  previewBox.style.left = (relX * scaleX) + 'px';
  previewBox.style.top = (relY * scaleY) + 'px';
  previewBox.style.width = (relW * scaleX) + 'px';
  previewBox.style.height = (relH * scaleY) + 'px';
}

function handlePreviewClick(e) {
  if (!previewImg || !previewBox || !lastBlueprint?.node?.bbox) return;
  const rect = previewImg.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const [nx, ny, nw, nh] = lastBlueprint.node.bbox;
  const absX = nx + (x / rect.width) * nw;
  const absY = ny + (y / rect.height) * nh;
  const found = previewPins.find(p => {
    const b = p.data.bbox;
    if (!b) return false;
    return absX >= b[0] && absX <= b[0] + b[2] && absY >= b[1] && absY <= b[1] + b[3];
  });
  previewPins.forEach(p => p.pin.classList.remove('active'));
  if (found) {
    found.pin.classList.add('active');
    showPreviewBBox(found.data, lastBlueprint.node);
    found.pin.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function placePopoverFixed() {
  if (!previewPopover || !scene) return;
  const sceneRect = scene.getBoundingClientRect();
  const popRect = previewPopover.getBoundingClientRect();
  const padding = 16;
  const x = Math.max(padding, sceneRect.width - popRect.width - padding);
  const y = padding + 40;
  previewPopover.style.left = x + 'px';
  previewPopover.style.top = y + 'px';
}
