import os
from typing import Optional, List, Dict
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends, Request
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
from proxy_manager import metrics
import json
import uuid

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
        """
        response_text = agent.run(prompt)
        
        if response_text.startswith("```json"):
            response_text = response_text[7:-3].strip()
        elif response_text.startswith("```"):
            response_text = response_text[3:-3].strip()
            
        prd_items = json.loads(response_text)
        
        # Save to DB
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
            
            # Audit log
            await log_audit(
                db, current_user.id, "CREATE", "Requirement", req.id, 
                None, {"title": req.title}, request.client.host
            )
            
        return {"items": saved_items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

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
    requirement_ids: List[str],
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

if __name__ == "__main__":
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
