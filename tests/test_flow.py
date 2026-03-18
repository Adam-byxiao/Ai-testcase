import pytest
from httpx import AsyncClient, ASGITransport
from main_api import app, agent
from database import engine, Base, get_db
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import os
import json
import asyncio
from unittest.mock import patch

# Setup test DB
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_testcase.db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

import pytest_asyncio

@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(autouse=True)
async def prepare_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Also dispose engine and close redis to prevent hanging
    await test_engine.dispose()
    
    # Close Redis client from main_api
    from main_api import redis_client
    await redis_client.aclose()

@pytest.mark.asyncio
@patch.object(agent, 'run')
async def test_auth_and_flow(mock_agent_run):
    mock_agent_run.return_value = '''
    [
        {
            "title": "Login",
            "description": "User can login",
            "priority": "High",
            "status": "Draft",
            "assignee": "Unassigned"
        }
    ]
    '''
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register User
        res = await ac.post("/api/auth/register", json={"username": "testuser", "password": "testpassword", "role": "admin"})
        assert res.status_code == 200

        # 2. Login User
        res = await ac.post("/api/auth/login", data={"username": "testuser", "password": "testpassword"})
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Upload Design (Mock file)
        files = {'file': ('design.json', b'{"type": "figma"}', 'application/json')}
        res = await ac.post("/api/design/upload", files=files, headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        req_id = items[0]["id"]
        
        # 4. Generate Test Cases
        mock_agent_run.return_value = f'''
        [
            {{
                "requirement_id": "{req_id}",
                "scenario": "Valid Login",
                "preconditions": "User is on login page",
                "steps": "1. Enter user\\n2. Click login",
                "expected_result": "Success",
                "priority": "High",
                "script_bound": false
            }}
        ]
        '''
        res = await ac.post(f"/api/testcases/generate?requirement_ids={req_id}", json=[req_id], headers=headers)
        assert res.status_code == 200
        test_cases = res.json()["test_cases"]
        assert len(test_cases) == 1
        tc_id = test_cases[0]["id"]

        # 5. Coverage Stats
        res = await ac.get("/api/stats/coverage", headers=headers)
        assert res.status_code == 200
        assert res.json()["total_requirements"] == 1
        assert res.json()["covered_requirements"] == 1

        # 6. Update Requirement (Trigger Event / State Change)
        res = await ac.put(f"/api/requirements/{req_id}", json={"title": "Login Updated"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["requirement"]["version"] == 2
        
        # 7. Verify TestCase Status Changed to "Needs Review"
        res = await ac.get("/api/testcases/export", headers=headers)
        assert res.status_code == 200
        assert b"Needs Review" in res.content

        # 8. Generate PRD Markdown
        res = await ac.post("/api/prd/generate-markdown", json=[req_id], headers=headers)
        assert res.status_code == 200
        assert b"# Product Requirements Document" in res.content

        # 9. Test Invalid Login
        res = await ac.post("/api/auth/login", data={"username": "testuser", "password": "wrongpassword"})
        assert res.status_code == 400

        # 10. Test Invalid File Upload
        files = {'file': ('design.txt', b'not json', 'text/plain')}
        res = await ac.post("/api/design/upload", files=files, headers=headers)
        assert res.status_code == 400
