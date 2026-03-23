# Blueprint Flow — Updated Implementation Plan (Two-Step)

Date: 2026-03-23
Owner: Codex + User
Status: Draft

## Goal
Build a UE5 Blueprint-style UI that reconstructs Figma structure into nodes and pins, enabling manual wiring. Deliver in two steps:

1) Single large node URL → render as one UE5-style node
2) Higher-level layer URL → render multiple nodes + manual connections

This plan focuses on frontend strategy and module breakdown, grounded in Figma JSON as the source of truth.

---

## Step 1 — Single Node Blueprint (MVP)
### Objective
Render a single Figma node (e.g. Live Note frame) as one UE5-style blueprint node with pins derived from its child layers.

### Inputs
- Figma URL with node-id of a single large node
- Figma JSON for that node (via backend API)

### Output
- One UE5-style node card with:
  - Header (node title)
  - Sections (Fixed/Scroll/Groups)
  - Pins for children (left or right)
  - Optional status tags

### Mapping Rules
- Node = Figma frame/component
- Pin = child layer (TEXT, INSTANCE, VECTOR, etc.)
- Sections = groups based on layer names or semantic tags (Fixed, Scrolls, etc.)

### Layout Rules
- Node position = center
- Pin list = vertical, fixed spacing
- Pin side:
  - default left
  - right side if detected as "action" or "output" (e.g. icons, buttons)

### Visual Style (UE5-like)
- Dark grid background
- Node card: dark panel + inner glow
- Pin: small circle + color (type-based)
- Connection preview line on hover

---

## Step 2 — Multi Node + Manual Wiring
### Objective
Render a group/page with multiple nodes, allow user to manually connect pins.

### Inputs
- Figma URL containing multiple frames/components
- Figma JSON extracted from a parent frame/page

### Output
- Multiple UE5 nodes positioned by bbox
- User can drag nodes, create connections, delete connections
- Connections saved to backend

### Mapping Rules
- Node = top-level frames under selected parent
- Pin = children under each node (filtered)
- Filter noise (e.g. tiny vectors, invisible layers)

### Layout Rules
- Initial node position = scaled from Figma bbox
- Pins = vertical list
- Canvas = pan/zoom

### Interaction Rules
- Click pin → start link
- Click target pin → finish link
- Right-click edge → delete
- Drag node → reposition

---

## Data Models
### Node
- id, title, bbox, pins[], meta

### Pin
- id, label, type, side, node_id

### Edge
- id, from_pin, to_pin

---

## Modules (Frontend)
1) Data loader (fetch nodes/pins)
2) Blueprint canvas (pan/zoom, grid)
3) Node renderer (UE5 node style)
4) Pin renderer (type-based style)
5) Edge renderer (Bezier + highlight)
6) Interaction layer (dragging, connect, delete)

---

## Backend Requirements
- `GET /api/blueprint/nodes?figma_url=`
  - returns nodes + pins
- `POST /api/blueprint/connections`
  - save edges
- `GET /api/blueprint/connections`
  - restore saved edges

---

## Open Questions
- Pin type taxonomy (text/button/icon/etc.)
- Auto-detection of "output" pins
- Grouping rules per project type

---

## Deliverables
- Phase 1: single node render + pins
- Phase 2: multi-node render + manual wiring
- Docs updated with exact mapping rules
