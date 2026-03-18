import pytest
import httpx
import respx
import os
import time
from proxy_manager import (
    RedundantProxyTransport, RedundantAsyncProxyTransport, metrics,
    get_proxy_client, get_async_proxy_client, detect_proxy_environment
)

@pytest.fixture(autouse=True)
def reset_metrics():
    metrics.total_requests = 0
    metrics.proxy_success = 0
    metrics.proxy_failures = 0
    metrics.direct_success = 0
    metrics.direct_failures = 0
    metrics.switch_count = 0
    metrics.total_latency_ms = 0.0

def test_metrics_to_dict():
    d = metrics.to_dict()
    assert isinstance(d, dict)
    assert "total_requests" in d

@respx.mock
def test_proxy_normal_success():
    respx.get("https://api.openai.com/").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    transport = RedundantProxyTransport(mode="auto_fallback", proxy_url="http://127.0.0.1:8888")
    client = httpx.Client(transport=transport)
    resp = client.get("https://api.openai.com/")
    assert resp.status_code == 200
    assert metrics.proxy_success == 1
    assert metrics.switch_count == 0
    client.close()

@respx.mock
def test_proxy_failure_fallback_direct():
    route = respx.get("https://api.openai.com/")
    route.side_effect = [httpx.ConnectError("Proxy unreachable"), httpx.Response(200, json={"status": "direct_ok"})]
    transport = RedundantProxyTransport(mode="auto_fallback", proxy_url="http://127.0.0.1:8888")
    client = httpx.Client(transport=transport)
    resp = client.get("https://api.openai.com/")
    assert resp.status_code == 200
    assert metrics.proxy_failures == 1
    assert metrics.switch_count == 1
    assert metrics.direct_success == 1

@respx.mock
def test_proxy_intermittent_jitter():
    route = respx.get("https://api.openai.com/")
    route.side_effect = [httpx.TimeoutException("Read timeout"), httpx.Response(200, json={"status": "recovered"})]
    transport = RedundantProxyTransport(mode="auto_fallback", proxy_url="http://127.0.0.1:8888")
    client = httpx.Client(transport=transport)
    resp = client.get("https://api.openai.com/")
    assert resp.status_code == 200
    assert metrics.proxy_failures == 1
    assert metrics.switch_count == 1

@respx.mock
def test_forced_direct():
    respx.get("https://api.openai.com/").mock(return_value=httpx.Response(200, json={"status": "forced_direct"}))
    transport = RedundantProxyTransport(mode="direct_only", proxy_url="http://127.0.0.1:8888")
    client = httpx.Client(transport=transport)
    resp = client.get("https://api.openai.com/")
    assert resp.status_code == 200
    assert metrics.direct_success == 1

@respx.mock
def test_forced_proxy_success():
    respx.get("https://api.openai.com/").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    transport = RedundantProxyTransport(mode="proxy_only", proxy_url="http://127.0.0.1:8888")
    client = httpx.Client(transport=transport)
    resp = client.get("https://api.openai.com/")
    assert resp.status_code == 200

@respx.mock
def test_forced_proxy_failure():
    route = respx.get("https://api.openai.com/")
    route.side_effect = httpx.ConnectError("Proxy down")
    transport = RedundantProxyTransport(mode="proxy_only", proxy_url="http://127.0.0.1:8888")
    client = httpx.Client(transport=transport)
    with pytest.raises(httpx.ConnectError):
        client.get("https://api.openai.com/")
    assert metrics.switch_count == 0

@respx.mock
def test_direct_failure():
    route = respx.get("https://api.openai.com/")
    route.side_effect = httpx.ConnectError("Direct down")
    transport = RedundantProxyTransport(mode="direct_only", proxy_url=None)
    client = httpx.Client(transport=transport)
    with pytest.raises(httpx.ConnectError):
        client.get("https://api.openai.com/")
    assert metrics.direct_failures == 1

@pytest.mark.asyncio
@respx.mock
async def test_async_proxy_normal_success():
    respx.get("https://api.openai.com/").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    transport = RedundantAsyncProxyTransport(mode="auto_fallback", proxy_url="http://127.0.0.1:8888")
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://api.openai.com/")
    assert resp.status_code == 200
    assert metrics.proxy_success == 1
    await transport.aclose()

@pytest.mark.asyncio
@respx.mock
async def test_async_proxy_failure_fallback_direct():
    route = respx.get("https://api.openai.com/")
    route.side_effect = [httpx.ConnectError("Proxy unreachable"), httpx.Response(200, json={"status": "direct_ok"})]
    transport = RedundantAsyncProxyTransport(mode="auto_fallback", proxy_url="http://127.0.0.1:8888")
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://api.openai.com/")
    assert resp.status_code == 200
    assert metrics.proxy_failures == 1

@pytest.mark.asyncio
@respx.mock
async def test_async_forced_direct():
    respx.get("https://api.openai.com/").mock(return_value=httpx.Response(200, json={"status": "forced_direct"}))
    transport = RedundantAsyncProxyTransport(mode="direct_only", proxy_url="http://127.0.0.1:8888")
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://api.openai.com/")
    assert resp.status_code == 200

@pytest.mark.asyncio
@respx.mock
async def test_async_forced_proxy_success():
    respx.get("https://api.openai.com/").mock(return_value=httpx.Response(200, json={"status": "ok"}))
    transport = RedundantAsyncProxyTransport(mode="proxy_only", proxy_url="http://127.0.0.1:8888")
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://api.openai.com/")
    assert resp.status_code == 200

@pytest.mark.asyncio
@respx.mock
async def test_async_forced_proxy_failure():
    route = respx.get("https://api.openai.com/")
    route.side_effect = httpx.ConnectError("Proxy down")
    transport = RedundantAsyncProxyTransport(mode="proxy_only", proxy_url="http://127.0.0.1:8888")
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("https://api.openai.com/")

@pytest.mark.asyncio
@respx.mock
async def test_async_direct_failure():
    route = respx.get("https://api.openai.com/")
    route.side_effect = httpx.ConnectError("Direct down")
    transport = RedundantAsyncProxyTransport(mode="direct_only", proxy_url=None)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("https://api.openai.com/")
    assert metrics.direct_failures == 1

def test_detect_proxy_environment(monkeypatch):
    assert detect_proxy_environment(None) == False
    
    # Mock httpx.Client.get
    class MockClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs): pass
        
    monkeypatch.setattr(httpx, "Client", MockClient)
    assert detect_proxy_environment("http://127.0.0.1:8888") == True
    
    class MockClientFail:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs): raise httpx.ConnectError("fail")
        def close(self): pass
        def close(self): pass
        
    monkeypatch.setattr(httpx, "Client", MockClientFail)
    assert detect_proxy_environment("http://127.0.0.1:8888") == False

def test_get_proxy_client(monkeypatch):
    monkeypatch.setenv("PROXY_MODE", "direct_only")
    client = get_proxy_client()
    assert isinstance(client, httpx.Client)
    client.close()

def test_get_proxy_client_auto_fallback(monkeypatch):
    monkeypatch.setenv("PROXY_MODE", "auto_fallback")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:8888")
    
    class MockClientFail2:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kwargs): raise httpx.ConnectError("fail")
        def close(self): pass
        
    monkeypatch.setattr(httpx, "Client", MockClientFail2)
    client = get_proxy_client()
    assert isinstance(client, httpx.Client)
    client.close()

def test_get_async_proxy_client(monkeypatch):
    monkeypatch.setenv("PROXY_MODE", "proxy_only")
    client = get_async_proxy_client()
    assert isinstance(client, httpx.AsyncClient)
