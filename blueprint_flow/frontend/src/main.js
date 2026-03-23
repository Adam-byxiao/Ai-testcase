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
    <button id="saveBtn" class="secondary">保存连线</button>
    <button id="layoutBtn" class="secondary">布局: 还原</button>
    <div class="status" id="status">idle</div>
  </div>
  <div class="canvas" id="canvas"></div>
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
    scene.querySelectorAll('.node, .group-box, .group-label').forEach((n) => n.remove());
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
const saveBtn = document.getElementById('saveBtn');
const layoutBtn = document.getElementById('layoutBtn');

loadBtn.onclick = async () => {
  const backend = document.getElementById('backend').value.trim();
  const figmaUrl = document.getElementById('figmaUrl').value.trim();
  const fileKey = document.getElementById('fileKey').value.trim();
  const nodeId = document.getElementById('nodeId').value.trim();
  if (!figmaUrl && !fileKey) return alert('请输入 Figma URL 或 file key');
  setStatus('loading...');
  const url = new URL(backend + '/api/blueprint/nodes');
  url.searchParams.set('file_key', figmaUrl || fileKey);
  if (nodeId) url.searchParams.set('node_id', nodeId);
  const res = await fetch(url);
  const data = await res.json();
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
