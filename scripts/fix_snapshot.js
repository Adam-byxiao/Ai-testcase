const fs = require('fs');
const path = 'D:/work/Repository/Ai-testcase/blueprint_flow/output/blueprint_snapshots/default/_all_test3_1774426419.json';
const data = JSON.parse(fs.readFileSync(path, 'utf8'));
const nodes = data.nodes || [];
const edges = data.edges || [];
const idMap = new Map();
const newNodes = [];
const isDecision = (name) => {
  if (!name) return false;
  const n = String(name).toLowerCase();
  return n.includes('?') || n.includes(' if ') || n.includes('是否') || n.includes('判断') || n.includes('判定');
};
const isPoly = (p) => {
  if (!p) return false;
  const t = String(p.type || '').toUpperCase();
  if (t === 'POLYGON') return true;
  return String(p.name || '').toLowerCase().includes('polygon');
};
for (const n of nodes) {
  const nid = n.id;
  if (!nid) { newNodes.push(n); continue; }
  const name = n.name || '';
  const pins = (n.sections || []).flatMap(s => s.pins || []);
  const question = pins.find(p => isDecision(p.name));
  if (/^\s*(group|frame)\s*\d+/i.test(name) && question) {
    const baseId = `decision-${nid}`;
    const poly = pins.find(isPoly);
    const qname = question.name || name;
    newNodes.push({
      id: baseId,
      name: qname,
      type: 'DECISION',
      bbox: n.bbox,
      x: n.x,
      y: n.y,
      sections: [{
        title: 'MAIN',
        pins: [
          poly ? { ...poly, id: `${baseId}-poly`, name: 'Polygon', side: 'left', depth: 0 } : null,
          { id: `${baseId}-q`, name: qname, side: 'left', depth: 0 },
          { id: `${baseId}-in`, name: 'IN', side: 'left', depth: 0, virtual: true },
          { id: `${baseId}-yes`, name: 'YES', side: 'right', depth: 0, virtual: true },
          { id: `${baseId}-no`, name: 'NO', side: 'right', depth: 0, virtual: true }
        ].filter(Boolean)
      }]
    });
    idMap.set(String(nid), baseId);
  } else {
    newNodes.push(n);
  }
}
const mapSide = (val, suffix) => {
  if (!val) return val;
  const v = String(val);
  let m = null;
  if (v.startsWith('node-')) {
    const raw = v.slice(5);
    if (idMap.has(raw)) m = idMap.get(raw);
  } else if (idMap.has(v)) {
    m = idMap.get(v);
  }
  if (m) return `${m}-${suffix}`;
  return val;
};
const newEdges = edges.map(e => ({ ...e, from: mapSide(e.from, 'yes'), to: mapSide(e.to, 'in') }));
const finalNodes = newNodes.filter(n => !idMap.has(String(n.id)));
data.nodes = finalNodes;
data.edges = newEdges;
fs.writeFileSync(path, JSON.stringify(data, null, 2), 'utf8');
console.log('fixed', path);
