import os
from typing import Optional, List, Dict
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from sqlalchemy.sql import func

# Local imports
from agent_app import FigmaAgent
from figma_mcp import parse_figma_file, parse_figma_file_detailed, get_figma_file_name, fetch_figma_api_json
from figma_image_exporter import export_figma_image
from vision_parser import parse_ui_from_image, parse_flowchart_from_image, parse_flowchart_from_image_bytes, parse_flow_banners_from_image, parse_flow_banner_groups_from_image
from flowchart_nodes import extract_flow_nodes_scoped
from flowchart_edges import detect_flowchart_edges_cv
from flowchart_validate import validate_flowchart_with_cv, detect_shapes_cv
from flowchart_align import align_flowchart_with_llm
from flowchart_edges_fallback import generate_edges_fallback
from flowchart_aggregate import aggregate_flow_nodes
from image_utils import download_image
from opencv_circles import detect_circular_screens, crop_by_bbox
from circle_verify import verify_screen_crop
from upload_utils import save_upload_to_temp
from flowchart_semantic import parse_flow_nodes_semantic
from flowchart_cv import build_flowchart_from_cv
from figma_layer.figma_layer_links import extract_layer_links_from_file_json
from figma_layer.flowchart_from_links import build_flowchart_from_links, build_flowchart_with_visual_order
from figma_layer.flow_banner_grouping import group_flow_by_banners
from figma_layer.node_matcher import match_visual_to_json_nodes, match_visual_to_json_nodes_llm
from prompts import get_prd_flow_banner_prompt, get_prd_default_prompt
from semantic_fuser import fuse_ui_contexts
from semantic_metrics import compute_semantic_metrics
from proxy_manager import metrics
import json
import uuid
from datetime import datetime

# DB & Auth
from database import get_db
from models import Requirement, TestCase, User, generate_uuid
from auth import get_current_user, RoleChecker, create_access_token, get_password_hash, verify_password
from audit import log_audit

load_dotenv()

app = FastAPI(
    title="Ai-Testcase Backend API",
    description="API for Design -> PRD -> Test Case pipeline",
    version="1.0.0"
)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agent
agent = FigmaAgent(model_name="gpt-4o")

# --- Models ---
class PRDItem(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    status: str
    assignee: str

class TestCaseItem(BaseModel):
    id: str
    scenario: str
    preconditions: str
    steps: str
    expected_result: str
    priority: str
    script_bound: bool = False

class FigmaDesignRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

class FigmaCompareResponse(BaseModel):
    json_only: list
    merged: list
    added_by_vision: list

class FlowchartRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

class FlowchartNodeRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

class FlowchartValidateRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

class FlowchartLayerRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

class FigmaImageUrlRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

class FlowchartCircleRequest(BaseModel):
    file_key: str
    node_id: Optional[str] = None

def _clean_llm_json_response(response_text: str) -> str:
    if response_text.startswith("```json"):
        return response_text[7:-3].strip()
    if response_text.startswith("```"):
        return response_text[3:-3].strip()
    return response_text.strip()

def _extract_json_array(text: str) -> Optional[str]:
    if not text:
        return None
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1]

def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return "".join(ch for ch in text.lower() if ch.isalnum() or '\u4e00' <= ch <= '\u9fff')

def _bigrams(text: str) -> set:
    if len(text) <= 1:
        return set([text]) if text else set()
    return {text[i:i+2] for i in range(len(text) - 1)}

def _similarity(a: str, b: str) -> float:
    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    a_set = _bigrams(a_norm)
    b_set = _bigrams(b_norm)
    if not a_set or not b_set:
        return 0.0
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    return inter / union if union else 0.0

async def _save_prd_items(
    prd_items: list,
    db: AsyncSession,
    current_user: User,
    request: Request
):
    saved_items = []
    for item in prd_items:
        req = Requirement(
            title=item.get("title", "Untitled"),
            description=item.get("description", ""),
            priority=item.get("priority", "Medium"),
            status=item.get("status", "Draft"),
            assignee=item.get("assignee", "Unassigned")
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        saved_items.append(req)

        await log_audit(
            db, current_user.id, "CREATE", "Requirement", req.id,
            None, {"title": req.title}, request.client.host
        )
    return saved_items

# --- Auth Endpoints ---

@app.post("/api/auth/register", tags=["Auth"])
async def register(user_data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == user_data["username"]))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = get_password_hash(user_data["password"])
    new_user = User(username=user_data["username"], hashed_password=hashed_pwd, role=user_data.get("role", "pm"))
    db.add(new_user)
    await db.commit()
    return {"msg": "User registered successfully"}

@app.post("/api/auth/login", tags=["Auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Endpoints ---

@app.get("/metrics", tags=["System"])
async def get_metrics():
    """Get redundant proxy metrics for monitoring."""
    return metrics.to_dict()

@app.post("/api/design/upload", tags=["Design"])
async def upload_design(
    request: Request,
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Upload a Figma JSON file and generate structured PRD items."""
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files are supported.")
        
    content = await file.read()
    temp_file_path = f"temp_{uuid.uuid4().hex}.json"
    with open(temp_file_path, "wb") as f:
        f.write(content)
        
    try:
        # Prompt to get structured JSON
        prompt = f"""
        Please analyze the Figma design file at '{os.path.abspath(temp_file_path)}'.
        Extract the core features and UI interactions, and generate structured PRD items in JSON format.
        Return ONLY a JSON array of objects with the following keys:
        - "title" (string)
        - "description" (string)
        - "priority" (string, High/Medium/Low)
        - "status" (string, Draft)
        - "assignee" (string, Unassigned)
        Ensure the output is valid JSON without any markdown formatting.
        IMPORTANT: All content (title, description, etc.) MUST be in Simplified Chinese (简体中文).
        """
        response_text = agent.run(prompt)
        try:
            preview = (response_text or "")[:2000]
            print(f"[LLM Raw Output][Figma] len={len(response_text or '')} preview=\\n{preview}")
        except Exception:
            pass
        response_text = _clean_llm_json_response(response_text)
        try:
            prd_items = json.loads(response_text)
        except Exception:
            extracted = _extract_json_array(response_text)
            if not extracted:
                raise HTTPException(status_code=502, detail="Model did not return valid JSON.")
            prd_items = json.loads(extracted)
        saved_items = await _save_prd_items(prd_items, db, current_user, request)
        return {"items": saved_items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/api/design/figma", tags=["Design"])
async def upload_design_from_figma(
    payload: FigmaDesignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Fetch a Figma file via MCP tool and generate structured PRD items."""
    import time
    t_start = time.time()
    try:
        t_parse_start = time.time()
        figma_context = parse_figma_file(payload.file_key, payload.node_id)
        print(f"[Timing][Figma] json_basic={time.time()-t_parse_start:.2f}s")
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)

        file_name = ""
        try:
            file_name = get_figma_file_name(payload.file_key)
        except Exception:
            file_name = ""

        layer_links = []
        layer_arrow_nodes = []
        layer_name_nodes = []
        layer_flowchart = None
        flow_banners = []
        flow_banner_groups = []
        try:
            raw_json = fetch_figma_api_json(payload.file_key, payload.node_id)
            layer_result = extract_layer_links_from_file_json(raw_json)
            layer_links = layer_result.get("links", [])
            layer_arrow_nodes = layer_result.get("arrow_nodes", [])
            layer_name_nodes = layer_result.get("name_nodes", [])
            layer_flowchart = build_flowchart_from_links(layer_links)
        except Exception as e:
            print(f"[Figma] layer_links_failed: {e}")

        image_url = ""
        used_node_id = payload.node_id
        visual_context = ""
        merged_context = figma_context
        metrics = None
        enable_vision = os.getenv("ENABLE_FIGMA_VISION", "true").lower() in ("1", "true", "yes")

        if enable_vision:
            try:
                print("[Timing][Figma] vision_pipeline_start")
                t0 = time.time()
                figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
                t1 = time.time()
                image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
                t2 = time.time()
                visual_context = parse_ui_from_image(image_url)
                t3 = time.time()
                enable_flow_banner = os.getenv("ENABLE_FLOW_BANNER_VISION", "true").lower() in ("1", "true", "yes")
                if enable_flow_banner:
                    try:
                        group_result = parse_flow_banner_groups_from_image(image_url) or {}
                        flow_banner_groups = group_result.get("groups", [])
                        flow_banners = [
                            {"label": g.get("feature_label"), "bbox": g.get("banner_bbox")}
                            for g in flow_banner_groups if g.get("feature_label")
                        ]
                    except Exception as e:
                        print(f"[FlowBanner] vision_failed: {e}")
                        flow_banners = []
                        flow_banner_groups = []
                visual_payload = json.dumps({
                    "node_id": used_node_id,
                    "image_url": image_url,
                    "visual_context": visual_context
                }, ensure_ascii=False)
                merged_context = fuse_ui_contexts(figma_context, visual_payload)
                t4 = time.time()
                metrics = compute_semantic_metrics(figma_context, visual_context)
                t5 = time.time()
                if flow_banners and not flow_banner_groups:
                    img_path = download_image(image_url)
                    flowchart_vision = {}
                    try:
                        flowchart_vision = parse_flowchart_from_image(image_url)
                    except Exception as e:
                        print(f"[FlowBanner] flowchart_vision_failed: {e}")
                    flow_banner_groups = group_flow_by_banners(
                        flow_banners,
                        layer_name_nodes,
                        layer_links,
                        layer_arrow_nodes,
                        img_path,
                        fallback_edges=(flowchart_vision or {}).get("edges", [])
                    )
                print(f"[Timing][Figma] json_detailed={t1-t0:.2f}s image_export={t2-t1:.2f}s vision_parse={t3-t2:.2f}s fusion={t4-t3:.2f}s metrics={t5-t4:.2f}s")
            except Exception as e:
                import traceback
                print(f"[Timing][Figma] vision_pipeline_failed: {e}")
                traceback.print_exc()
                merged_context = figma_context
                metrics = None

        max_chars = int(os.getenv("PROMPT_MAX_CHARS", "50000"))
        merged_context = _truncate_text(merged_context, max_chars)
        def _safe_prd_default(ctx: str) -> str:
            return f"""
            请基于以下设计上下文生成 PRD 条目，输出必须为严格 JSON 数组。
            每个对象包含：title, description, priority(High/Medium/Low), status(Draft), assignee(Unassigned), steps(可选)。
            必须使用简体中文，不要输出任何多余文本或 Markdown。

            设计上下文：
            {ctx}
            """

        prd_flow_prompt = get_prd_flow_banner_prompt()
        prd_default_prompt = get_prd_default_prompt()
        if flow_banner_groups and "{flow_banner_groups}" in prd_flow_prompt:
            fb_context = json.dumps(flow_banner_groups, ensure_ascii=False)
            prompt = prd_flow_prompt.format(
                flow_banner_groups=fb_context,
                figma_context=merged_context
            )
        elif "{figma_context}" in prd_default_prompt:
            prompt = prd_default_prompt.format(figma_context=merged_context)
        else:
            prompt = _safe_prd_default(merged_context)

        t_prompt_start = time.time()
        response_text = agent.run(prompt)
        t_prompt_end = time.time()
        print(f"[Timing][Figma] agent_run={t_prompt_end-t_prompt_start:.2f}s total={time.time()-t_start:.2f}s")
        try:
            preview = (response_text or "")[:2000]
            print(f"[LLM Raw Output][Figma] len={len(response_text or '')} preview=\\n{preview}")
        except Exception:
            pass
        response_text = _clean_llm_json_response(response_text)
        try:
            prd_items = json.loads(response_text)
        except Exception:
            extracted = _extract_json_array(response_text)
            if not extracted:
                raise HTTPException(status_code=502, detail="Model did not return valid JSON.")
            prd_items = json.loads(extracted)
        saved_items = await _save_prd_items(prd_items, db, current_user, request)
        response_payload = {
            "items": saved_items,
            "figma": {
                "file_key": payload.file_key,
                "file_name": file_name,
                "node_id": used_node_id,
                "image_url": image_url
            },
            "metrics": metrics,
            "layer_links": layer_links,
            "layer_arrow_nodes": layer_arrow_nodes,
            "layer_name_nodes": layer_name_nodes,
            "layer_flowchart": layer_flowchart,
            "flow_banners": flow_banners,
            "flow_banner_groups": flow_banner_groups
        }
        try:
            if flow_banner_groups and layer_name_nodes:
                # build node mapping for each group
                group_mappings = []
                use_llm_map = os.getenv("ENABLE_NODE_MAPPING_LLM", "false").lower() in ("1", "true", "yes")
                group_flowcharts = []
                for g in flow_banner_groups:
                    visual_nodes = g.get("nodes", []) if isinstance(g, dict) else []
                    # use nodes within group bbox scope if provided
                    json_nodes = []
                    group_bbox = g.get("banner_bbox") or None
                    if group_bbox and g.get("node_bboxes"):
                        for name, bbox in g.get("node_bboxes", {}).items():
                            json_nodes.append({"name": name, "bbox": bbox})
                    if not json_nodes:
                        json_nodes = layer_name_nodes
                    mapping_result = None
                    mapping_source = "heuristic"
                    mapping_error = None
                    if use_llm_map:
                        try:
                            mapping_result = match_visual_to_json_nodes_llm(visual_nodes, json_nodes)
                            mapping_source = "llm"
                        except Exception as e:
                            mapping_error = str(e)
                            print(f"[FlowBanner] node_mapping_llm_failed: {e}")
                    if not mapping_result:
                        mapping_result = match_visual_to_json_nodes(visual_nodes, json_nodes)
                    group_mappings.append({
                        "feature_label": g.get("feature_label"),
                        "mappings": mapping_result.get("mappings", []),
                        "source": mapping_source,
                        "error": mapping_error
                    })
                    # combine json edges with visual order
                    group_flowcharts.append({
                        "feature_label": g.get("feature_label"),
                        "flowchart": build_flowchart_with_visual_order(
                            visual_nodes,
                            layer_links,
                            g.get("edges", [])
                        )
                    })
                response_payload["node_mappings"] = group_mappings
                response_payload["flow_banner_flowcharts"] = group_flowcharts
            report_dir = os.path.join(os.getcwd(), "output", "flow_banner_reports")
            os.makedirs(report_dir, exist_ok=True)
            report = {
                "ts": datetime.now().isoformat(),
                "file_key": payload.file_key,
                "node_id": used_node_id,
                "flow_banner_groups": flow_banner_groups,
                "node_mappings": response_payload.get("node_mappings", []),
                "flow_banner_flowcharts": response_payload.get("flow_banner_flowcharts", []),
            }
            report_name = f"flow_banner_{payload.file_key}_{(used_node_id or 'all').replace(':','-')}_{int(datetime.now().timestamp())}.json"
            report_path = os.path.join(report_dir, report_name)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            response_payload["flow_banner_report"] = report_path
        except Exception as e:
            print(f"[FlowBanner] node_mapping_failed: {e}")

        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/figma-flowchart-validate", tags=["Design"])
async def validate_flowchart_from_figma(
    payload: FlowchartValidateRequest,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Validate flowchart nodes/edges using OpenCV only (no LLM)."""
    try:
        figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)

        node_payload = extract_flow_nodes_scoped(figma_context, payload.node_id)
        nodes = node_payload.get("aggregated_nodes") or node_payload.get("containers") or []
        frame_bbox = node_payload.get("frame_bbox")
        if not frame_bbox:
            raise HTTPException(status_code=400, detail="Frame bbox not found for validation.")

        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        img_path = download_image(image_url)
        report = validate_flowchart_with_cv(img_path, nodes, frame_bbox)

        return {
            "validation": report,
            "figma": {
                "file_key": payload.file_key,
                "node_id": used_node_id,
                "image_url": image_url
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/figma-flowchart-layer1", tags=["Design"])
async def flowchart_layer1_opencv(
    payload: FlowchartLayerRequest,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Layer 1: OpenCV structural detection (nodes/edges)."""
    try:
        figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)
        node_payload = extract_flow_nodes_scoped(figma_context, payload.node_id)
        nodes = node_payload.get("aggregated_nodes") or node_payload.get("containers") or []
        frame_bbox = node_payload.get("frame_bbox")
        if not frame_bbox:
            raise HTTPException(status_code=400, detail="Frame bbox not found.")

        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        img_path = download_image(image_url)
        edges = detect_flowchart_edges_cv(img_path, nodes, frame_bbox)

        return {
            "cv": {"nodes": nodes, "edges": edges},
            "figma": {"file_key": payload.file_key, "node_id": used_node_id, "image_url": image_url}
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/figma-flowchart-layer2", tags=["Design"])
async def flowchart_layer2_semantic(
    payload: FlowchartLayerRequest,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Layer 2: LLM semantic nodes (JSON + vision)."""
    try:
        figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)

        node_payload = extract_flow_nodes_scoped(figma_context, payload.node_id)
        json_context = json.dumps(node_payload, ensure_ascii=False)

        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        visual_context = parse_ui_from_image(image_url)
        visual_payload = json.dumps({
            "image_url": image_url,
            "visual_context": visual_context
        }, ensure_ascii=False)

        result = parse_flow_nodes_semantic(json_context, visual_payload)
        return {
            "semantic": result,
            "figma": {"file_key": payload.file_key, "node_id": used_node_id, "image_url": image_url}
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/figma-flowchart-layer3", tags=["Design"])
async def flowchart_layer3_align(
    payload: FlowchartLayerRequest,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Layer 3: LLM alignment using CV + semantic + image."""
    try:
        # layer1
        figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)
        node_payload = extract_flow_nodes_scoped(figma_context, payload.node_id)
        nodes = node_payload.get("aggregated_nodes") or node_payload.get("containers") or []
        frame_bbox = node_payload.get("frame_bbox")
        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        img_path = download_image(image_url)
        edges = detect_flowchart_edges_cv(img_path, nodes, frame_bbox) if frame_bbox else []
        cv_struct = {"nodes": nodes, "edges": edges}

        # layer2
        json_context = json.dumps(node_payload, ensure_ascii=False)
        visual_context = parse_ui_from_image(image_url)
        visual_payload = json.dumps({
            "image_url": image_url,
            "visual_context": visual_context
        }, ensure_ascii=False)
        semantic = parse_flow_nodes_semantic(json_context, visual_payload)

        # align
        aligned = align_flowchart_with_llm(image_url, cv_struct, semantic)
        return {
            "aligned": aligned,
            "cv": cv_struct,
            "semantic": semantic,
            "figma": {"file_key": payload.file_key, "node_id": used_node_id, "image_url": image_url}
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/design/figma-image-url", tags=["Design"])
async def get_figma_image_url(
    file_key: str,
    node_id: Optional[str] = None,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Get Figma image URL (backend only calls Figma API, frontend downloads image)."""
    try:
        image_url, used_node_id = export_figma_image(file_key, node_id=node_id)
        return {"image_url": image_url, "node_id": used_node_id, "file_key": file_key}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/flowchart/circle-detect", tags=["Design"])
async def flowchart_circle_detect(
    payload: FlowchartCircleRequest,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Detect circular device screens with OpenCV and verify via multimodal LLM."""
    try:
        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        img_path = download_image(image_url)
        circles = detect_circular_screens(img_path)
        verified = []
        for c in circles:
            crop_bytes = crop_by_bbox(img_path, c["bbox"])
            result = verify_screen_crop(crop_bytes)
            if result.get("is_screen"):
                verified.append({**c, **result})
        return {
            "circles": circles,
            "verified": verified,
            "figma": {"file_key": payload.file_key, "node_id": used_node_id, "image_url": image_url}
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/flowchart/circle-detect-upload", tags=["Design"])
async def flowchart_circle_detect_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Detect circular device screens from uploaded image, then verify via LLM."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required.")
    content = await file.read()
    ext = os.path.splitext(file.filename)[-1].lower()
    temp_path = save_upload_to_temp(content, suffix=ext or ".png")
    try:
        circles = detect_circular_screens(temp_path)
        verified = []
        for c in circles:
            try:
                crop_bytes = crop_by_bbox(temp_path, c["bbox"])
            except Exception as e:
                print(f"[Flowchart][circle] skip empty/invalid crop: bbox={c.get('bbox')} err={e}")
                continue
            result = verify_screen_crop(crop_bytes)
            if result.get("is_screen"):
                verified.append({**c, **result})
        return {"circles": circles, "verified": verified}
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

@app.post("/api/design/flowchart/upload-image", tags=["Design"])
async def flowchart_from_uploaded_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Run flowchart detection using uploaded image (no backend image fetch)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required.")

    content = await file.read()
    ext = os.path.splitext(file.filename)[-1].lower()
    mime = "image/png"
    if ext in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    temp_path = save_upload_to_temp(content, suffix=ext or '.png')
    try:
        # Layer1: OpenCV shape detection
        shapes = detect_shapes_cv(temp_path)
        # Layer2: Vision semantic on image only
        semantic = parse_flowchart_from_image_bytes(content, image_mime=mime)
        return {
            "cv": {"shapes": shapes, "shape_count": len(shapes)},
            "semantic": semantic
        }
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

@app.post("/api/design/figma-compare", tags=["Design"])
async def compare_design_from_figma(
    payload: FigmaDesignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Compare JSON-only vs merged (vision+json) PRD results without saving to DB."""
    try:
        figma_context = parse_figma_file(payload.file_key, payload.node_id)
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)

        enable_vision = os.getenv("ENABLE_FIGMA_VISION", "true").lower() in ("1", "true", "yes")
        merged_context = figma_context
        image_url = ""
        used_node_id = payload.node_id
        visual_context = ""
        metrics = None
        layer_links = []
        layer_arrow_nodes = []
        layer_flowchart = None
        flow_banners = []
        flow_banner_groups = []
        try:
            raw_json = fetch_figma_api_json(payload.file_key, payload.node_id)
            layer_result = extract_layer_links_from_file_json(raw_json)
            layer_links = layer_result.get("links", [])
            layer_arrow_nodes = layer_result.get("arrow_nodes", [])
            layer_flowchart = build_flowchart_from_links(layer_links)
        except Exception as e:
            print(f"[Figma] layer_links_failed: {e}")

        if enable_vision:
            try:
                figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
                image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
                visual_context = parse_ui_from_image(image_url)
                enable_flow_banner = os.getenv("ENABLE_FLOW_BANNER_VISION", "true").lower() in ("1", "true", "yes")
                if enable_flow_banner:
                    try:
                        flow_banners = (parse_flow_banners_from_image(image_url) or {}).get("banners", [])
                    except Exception as e:
                        print(f"[FlowBanner] vision_failed: {e}")
                        flow_banners = []
                visual_payload = json.dumps({
                    "node_id": used_node_id,
                    "image_url": image_url,
                    "visual_context": visual_context
                }, ensure_ascii=False)
                merged_context = fuse_ui_contexts(figma_context, visual_payload)
                metrics = compute_semantic_metrics(figma_context, visual_context)
                if flow_banners:
                    node_payload = extract_flow_nodes_scoped(figma_context, used_node_id)
                    img_path = download_image(image_url)
                    flow_banner_groups = group_flow_by_banners(
                        flow_banners,
                        node_payload.get("containers", []),
                        layer_links,
                        img_path
                    )
            except Exception:
                merged_context = figma_context
                metrics = None

        max_chars = int(os.getenv("PROMPT_MAX_CHARS", "50000"))
        json_only_context = _truncate_text(figma_context, max_chars)
        merged_context_trim = _truncate_text(merged_context, max_chars)

        base_prompt = """
        Please analyze the following Figma design context.
        Extract the core features and UI interactions, and generate structured PRD items in JSON format.
        Return ONLY a JSON array of objects with the following keys:
        - "title" (string)
        - "description" (string)
        - "priority" (string, High/Medium/Low)
        - "status" (string, Draft)
        - "assignee" (string, Unassigned)
        Ensure the output is valid JSON without any markdown formatting.
        IMPORTANT: All content MUST be in Simplified Chinese.
        """

        json_only_prompt = f"""
{base_prompt}

Figma Context (JSON Only):
{json_only_context}
"""
        merged_prompt = f"""
{base_prompt}

Figma Context (Merged):
{merged_context_trim}
"""

        json_only_text = agent.run(json_only_prompt)
        merged_text = agent.run(merged_prompt)

        json_only_text = _clean_llm_json_response(json_only_text)
        merged_text = _clean_llm_json_response(merged_text)

        try:
            json_only_items = json.loads(json_only_text)
        except Exception:
            extracted = _extract_json_array(json_only_text)
            if not extracted:
                raise HTTPException(status_code=502, detail="Model did not return valid JSON (json_only).")
            json_only_items = json.loads(extracted)

        try:
            merged_items = json.loads(merged_text)
        except Exception:
            extracted = _extract_json_array(merged_text)
            if not extracted:
                raise HTTPException(status_code=502, detail="Model did not return valid JSON (merged).")
            merged_items = json.loads(extracted)

        sim_threshold = float(os.getenv("COMPARE_SIM_THRESHOLD", "0.55"))
        vision_threshold = float(os.getenv("VISION_TEXT_THRESHOLD", "0.35"))
        vision_text = ""
        try:
            if isinstance(visual_context, dict):
                labels = [c.get("label", "") for c in visual_context.get("components", []) if isinstance(c, dict)]
                vision_text = " ".join([visual_context.get("summary", "")] + labels)
        except Exception:
            vision_text = ""

        def best_json_match(item: dict):
            title = item.get("title", "")
            desc = item.get("description", "")
            best = 0.0
            for j in json_only_items:
                if not isinstance(j, dict):
                    continue
                j_title = j.get("title", "")
                j_desc = j.get("description", "")
                score = max(_similarity(title, j_title), _similarity(desc, j_desc))
                if score > best:
                    best = score
            return best

        annotated_merged = []
        for item in merged_items:
            if not isinstance(item, dict):
                continue
            json_score = best_json_match(item)
            vision_score = max(_similarity(item.get("title", ""), vision_text), _similarity(item.get("description", ""), vision_text))
            from_json = json_score >= sim_threshold
            from_vision = vision_score >= vision_threshold
            if from_json and from_vision:
                source = "Both"
            elif from_json:
                source = "JSON"
            else:
                source = "Vision"
            annotated = {**item, "source": source, "json_similarity": round(json_score, 3), "vision_similarity": round(vision_score, 3)}
            annotated_merged.append(annotated)

        added_by_vision = [item for item in annotated_merged if item.get("source") == "Vision"]

        return {
            "json_only": json_only_items,
            "merged": annotated_merged,
            "added_by_vision": added_by_vision,
            "figma": {
                "file_key": payload.file_key,
                "node_id": used_node_id,
                "image_url": image_url
            },
            "metrics": metrics,
            "layer_links": layer_links,
            "layer_arrow_nodes": layer_arrow_nodes,
            "layer_flowchart": layer_flowchart,
            "flow_banners": flow_banners,
            "flow_banner_groups": flow_banner_groups
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/figma-flowchart", tags=["Design"])
async def parse_flowchart_from_figma(
    payload: FlowchartRequest,
    request: Request,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Parse a Figma flowchart via visual model and return nodes/edges."""
    try:
        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        flowchart_vision = parse_flowchart_from_image(image_url)
        flowchart_cv = None
        use_cv = os.getenv("ENABLE_FLOWCHART_CV", "true").lower() in ("1", "true", "yes")
        if use_cv:
            try:
                flowchart_cv = build_flowchart_from_cv(image_url)
            except Exception:
                flowchart_cv = None

        flowchart = flowchart_cv if flowchart_cv and flowchart_cv.get("nodes") else flowchart_vision
        return {
            "flowchart": flowchart,
            "flowchart_vision": flowchart_vision,
            "flowchart_cv": flowchart_cv,
            "figma": {
                "file_key": payload.file_key,
                "node_id": used_node_id,
                "image_url": image_url
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/design/figma-flowchart-nodes", tags=["Design"])
async def parse_flowchart_nodes_from_figma(
    payload: FlowchartNodeRequest,
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Parse flowchart nodes (semantic) using JSON structure + visual context."""
    try:
        figma_context = parse_figma_file_detailed(payload.file_key, payload.node_id)
        if figma_context.startswith("Error"):
            raise HTTPException(status_code=400, detail=figma_context)

        # Reduce JSON to flow-relevant nodes
        node_payload = extract_flow_nodes_scoped(figma_context, payload.node_id)
        include_regex = os.getenv("FLOW_NODE_INCLUDE_REGEX", "Start|Join|Joining|Record|Recording|Initiat|Init|Meeting")
        ignore_regex = os.getenv("FLOW_NODE_IGNORE_REGEX", "Background|BG|Stroke|Mask|Shadow|Glow|Note|Info|Prompt")
        aggregated_nodes = aggregate_flow_nodes(
            node_payload.get("containers", []),
            node_payload.get("texts", []),
            include_regex,
            ignore_regex
        )
        node_payload["aggregated_nodes"] = aggregated_nodes
        json_context = json.dumps(node_payload, ensure_ascii=False)

        image_url, used_node_id = export_figma_image(payload.file_key, node_id=payload.node_id)
        visual_context = {}
        enable_flow_vision = os.getenv("ENABLE_FLOWCHART_VISION", "true").lower() in ("1", "true", "yes")
        if enable_flow_vision:
            try:
                visual_context = parse_ui_from_image(image_url)
            except Exception as e:
                print(f"[Flowchart] vision_parse_failed: {e}")
                visual_context = {}
        visual_payload = json.dumps({
            "image_url": image_url,
            "visual_context": visual_context
        }, ensure_ascii=False)

        result = parse_flow_nodes_semantic(json_context, visual_payload)
        # OpenCV edge detection (optional)
        edges = []
        use_cv = os.getenv("ENABLE_FLOWCHART_CV", "true").lower() in ("1", "true", "yes")
        if use_cv and node_payload.get("frame_bbox") and result.get("nodes"):
            try:
                img_path = download_image(image_url)
                edges = detect_flowchart_edges_cv(img_path, result.get("nodes", []), node_payload.get("frame_bbox"))
            except Exception:
                edges = []
        if not edges:
            edges = generate_edges_fallback(result.get("nodes", []))
        return {
            "nodes": result.get("nodes", []),
            "edges": edges,
            "figma": {
                "file_key": payload.file_key,
                "node_id": used_node_id,
                "image_url": image_url
            },
            "raw": {
                "json_context": node_payload,
                "visual_context": visual_context
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/requirements", tags=["PRD"])
async def get_requirements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer", "qa"]))
):
    """Get all requirements."""
    result = await db.execute(select(Requirement).order_by(Requirement.created_at.desc()))
    items = result.scalars().all()
    return items

@app.delete("/api/requirements/clear", tags=["PRD"])
async def clear_requirements(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Clear all requirements and related test cases."""
    await db.execute(delete(TestCase))
    await db.execute(delete(Requirement))
    await db.commit()

    await log_audit(
        db, current_user.id, "DELETE", "TestCase", "*",
        None, {"cleared": True}, request.client.host
    )
    await log_audit(
        db, current_user.id, "DELETE", "Requirement", "*",
        None, {"cleared": True}, request.client.host
    )

    return {"msg": "Requirements and test cases cleared"}

@app.post("/api/prd/generate-markdown", tags=["PRD"])
async def generate_prd_markdown(
    requirement_ids: List[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "designer"]))
):
    """Generate a standard Markdown PRD document from a list of PRD items."""
    result = await db.execute(select(Requirement).filter(Requirement.id.in_(requirement_ids)))
    items = result.scalars().all()
    
    md_content = "# Product Requirements Document\n\n"
    for item in items:
        md_content += f"## {item.id}: {item.title}\n"
        md_content += f"- **Priority:** {item.priority}\n"
        md_content += f"- **Status:** {item.status}\n"
        md_content += f"- **Assignee:** {item.assignee}\n"
        md_content += f"\n**Description:**\n{item.description}\n\n"
        md_content += "---\n"
    return {"markdown": md_content}

@app.post("/api/testcases/generate", tags=["Test Cases"])
async def generate_test_cases(
    request: Request,
    requirement_ids: List[str] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "qa"]))
):
    """Generate test cases based on the provided Requirement IDs."""
    # Load requirements
    result = await db.execute(select(Requirement).filter(Requirement.id.in_(requirement_ids)))
    requirements = result.scalars().all()
    if not requirements:
        raise HTTPException(status_code=404, detail="No requirements found")
        
    items_json = json.dumps([
        {"id": req.id, "title": req.title, "description": req.description}
        for req in requirements
    ], ensure_ascii=False)
    
    prompt = f"""
    Based on the following PRD items in JSON format, generate a comprehensive set of test cases.
    Return ONLY a JSON array of objects with the following keys:
    - "requirement_id" (string, MUST exactly match one of the input PRD ids)
    - "scenario" (string)
    - "preconditions" (string)
    - "steps" (string)
    - "expected_result" (string)
    - "priority" (string, High/Medium/Low)
    - "script_bound" (boolean, false)
    Ensure the output is valid JSON without any markdown formatting.
    IMPORTANT: All content (scenario, preconditions, steps, expected_result, etc.) MUST be in Simplified Chinese (简体中文).
    
    PRD Items:
    {items_json}
    """
    
    try:
        response_text = agent.run(prompt)
        
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()
            
        test_cases_data = json.loads(response_text)
        
        saved_cases = []
        for tc_data in test_cases_data:
            tc = TestCase(
                requirement_id=tc_data.get("requirement_id"),
                scenario=tc_data.get("scenario", ""),
                preconditions=tc_data.get("preconditions", ""),
                steps=tc_data.get("steps", ""),
                expected_result=tc_data.get("expected_result", ""),
                priority=tc_data.get("priority", "Medium"),
                script_bound=tc_data.get("script_bound", False),
                status="Draft"
            )
            db.add(tc)
            await db.commit()
            await db.refresh(tc)
            saved_cases.append(tc)
            
            # Audit log
            await log_audit(
                db, current_user.id, "CREATE", "TestCase", tc.id, 
                None, {"scenario": tc.scenario}, request.client.host
            )
            
        return {"test_cases": saved_cases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/requirements/{req_id}", tags=["PRD"])
async def update_requirement(
    req_id: str,
    req_data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm"]))
):
    """Update a requirement and notify associated test cases."""
    result = await db.execute(select(Requirement).filter(Requirement.id == req_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
        
    # Create before snapshot
    before = {
        "title": req.title,
        "description": req.description,
        "priority": req.priority,
        "status": req.status,
        "assignee": req.assignee,
        "version": req.version
    }
    
    # Update fields
    for key, value in req_data.items():
        if hasattr(req, key) and key not in ["id", "created_at", "updated_at"]:
            setattr(req, key, value)
            
    req.version += 1
    
    # Notify TestCases (mark them as Needs Review)
    await db.execute(
        update(TestCase)
        .where(TestCase.requirement_id == req_id)
        .values(status="Needs Review", updated_at=func.now())
    )
    
    await db.commit()
    await db.refresh(req)
    
    # Create after snapshot
    after = {
        "title": req.title,
        "description": req.description,
        "priority": req.priority,
        "status": req.status,
        "assignee": req.assignee,
        "version": req.version
    }
    
    # Audit log
    await log_audit(
        db, current_user.id, "UPDATE", "Requirement", req.id, 
        before, after, request.client.host
    )
    
    return {"msg": "Requirement updated", "requirement": req}

@app.delete("/api/requirements/{req_id}", tags=["PRD"])
async def delete_requirement(
    req_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm"]))
):
    """Delete a requirement and related test cases."""
    result = await db.execute(select(Requirement).filter(Requirement.id == req_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    before = {
        "id": req.id,
        "title": req.title,
        "description": req.description,
        "priority": req.priority,
        "status": req.status,
        "assignee": req.assignee,
        "version": req.version
    }

    await db.execute(delete(TestCase).where(TestCase.requirement_id == req_id))
    await db.execute(delete(Requirement).where(Requirement.id == req_id))
    await db.commit()

    await log_audit(
        db, current_user.id, "DELETE", "Requirement", req_id,
        before, None, request.client.host
    )

    return {"msg": "Requirement deleted"}

import redis.asyncio as redis_async
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

# Setup redis
redis_client = redis_async.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)

@app.get("/api/stats/coverage", tags=["Stats"])
async def get_coverage_stats(db: AsyncSession = Depends(get_db)):
    """Get requirement coverage statistics with Redis caching (fallback if Redis unavailable)."""
    try:
        cached_stats = await redis_client.get("req_coverage_stats")
        if cached_stats:
            return json.loads(cached_stats)
    except Exception:
        pass # Fallback to computing if redis is down
        
    # Calculate coverage
    total_reqs_result = await db.execute(select(func.count(Requirement.id)))
    total_reqs = total_reqs_result.scalar() or 0
    
    if total_reqs == 0:
        stats = {"total_requirements": 0, "covered_requirements": 0, "coverage_rate": "0%"}
    else:
        covered_reqs_result = await db.execute(
            select(func.count(func.distinct(TestCase.requirement_id)))
        )
        covered_reqs = covered_reqs_result.scalar() or 0
        
        coverage_rate = f"{(covered_reqs / total_reqs) * 100:.2f}%"
        
        stats = {
            "total_requirements": total_reqs,
            "covered_requirements": covered_reqs,
            "coverage_rate": coverage_rate
        }
    
    try:
        # Cache for 60 seconds
        await redis_client.setex("req_coverage_stats", 60, json.dumps(stats))
    except Exception:
        pass # Ignore redis errors
        
    return stats

@app.get("/api/testcases/export", tags=["Integration"])
async def export_testcases(db: AsyncSession = Depends(get_db)):
    """Export all test cases to CSV format."""
    result = await db.execute(select(TestCase))
    cases = result.scalars().all()
    
    f = StringIO()
    writer = csv.writer(f)
    writer.writerow(["ID", "Requirement ID", "Scenario", "Preconditions", "Steps", "Expected Result", "Priority", "Status", "Version"])
    
    for c in cases:
        writer.writerow([c.id, c.requirement_id, c.scenario, c.preconditions, c.steps, c.expected_result, c.priority, c.status, c.version])
        
    f.seek(0)
    return StreamingResponse(f, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=testcases.csv"})

@app.get("/api/testcases", tags=["Test Cases"])
async def get_testcases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "qa", "designer"]))
):
    """Get all test cases."""
    result = await db.execute(select(TestCase).order_by(TestCase.created_at.desc()))
    cases = result.scalars().all()
    return cases

@app.put("/api/testcases/{tc_id}", tags=["Test Cases"])
async def update_testcase(
    tc_id: str,
    tc_data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "qa"]))
):
    """Update a test case."""
    result = await db.execute(select(TestCase).filter(TestCase.id == tc_id))
    tc = result.scalars().first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    before = {
        "scenario": tc.scenario,
        "preconditions": tc.preconditions,
        "steps": tc.steps,
        "expected_result": tc.expected_result,
        "priority": tc.priority,
        "script_bound": tc.script_bound,
        "status": tc.status,
        "version": tc.version
    }

    for key, value in tc_data.items():
        if hasattr(tc, key) and key not in ["id", "created_at", "updated_at", "requirement_id"]:
            setattr(tc, key, value)

    tc.version += 1
    await db.commit()
    await db.refresh(tc)

    after = {
        "scenario": tc.scenario,
        "preconditions": tc.preconditions,
        "steps": tc.steps,
        "expected_result": tc.expected_result,
        "priority": tc.priority,
        "script_bound": tc.script_bound,
        "status": tc.status,
        "version": tc.version
    }

    await log_audit(
        db, current_user.id, "UPDATE", "TestCase", tc.id,
        before, after, request.client.host
    )

    return {"msg": "Test case updated", "testcase": tc}

@app.delete("/api/testcases/{tc_id}", tags=["Test Cases"])
async def delete_testcase(
    tc_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "qa"]))
):
    """Delete a test case."""
    result = await db.execute(select(TestCase).filter(TestCase.id == tc_id))
    tc = result.scalars().first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    before = {
        "scenario": tc.scenario,
        "preconditions": tc.preconditions,
        "steps": tc.steps,
        "expected_result": tc.expected_result,
        "priority": tc.priority,
        "script_bound": tc.script_bound,
        "status": tc.status,
        "version": tc.version
    }

    await db.execute(delete(TestCase).where(TestCase.id == tc_id))
    await db.commit()

    await log_audit(
        db, current_user.id, "DELETE", "TestCase", tc_id,
        before, None, request.client.host
    )

    return {"msg": "Test case deleted"}

@app.delete("/api/testcases/clear", tags=["Test Cases"])
async def clear_testcases(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "pm", "qa"]))
):
    """Clear all test cases."""
    await db.execute(delete(TestCase))
    await db.commit()

    await log_audit(
        db, current_user.id, "DELETE", "TestCase", "*",
        None, {"cleared": True}, request.client.host
    )

    return {"msg": "Test cases cleared"}

if __name__ == "__main__":
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
