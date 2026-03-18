import os
import time
import logging
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logger = logging.getLogger("ProxyManager")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class ProxyMetrics:
    def __init__(self):
        self.total_requests = 0
        self.proxy_success = 0
        self.proxy_failures = 0
        self.direct_success = 0
        self.direct_failures = 0
        self.switch_count = 0
        self.total_latency_ms = 0.0

    def to_dict(self):
        return {
            "total_requests": self.total_requests,
            "proxy_success": self.proxy_success,
            "proxy_failures": self.proxy_failures,
            "direct_success": self.direct_success,
            "direct_failures": self.direct_failures,
            "switch_count": self.switch_count,
            "total_latency_ms": self.total_latency_ms
        }

metrics = ProxyMetrics()

def record_switch_event(source_ip: str, target_domain: str, reason: str, latency: float):
    metrics.switch_count += 1
    logger.warning(
        f"[Proxy Switch] Source: {source_ip} | Target: {target_domain} | "
        f"Reason: {reason} | Latency: {latency:.2f}ms"
    )

class RedundantProxyTransport(httpx.BaseTransport):
    def __init__(self, mode: str = "auto_fallback", proxy_url: Optional[str] = None):
        self.mode = mode
        self.proxy_url = proxy_url
        
        self.direct_transport = httpx.HTTPTransport()
        if self.proxy_url:
            self.proxy_transport = httpx.HTTPTransport(proxy=self.proxy_url)
        else:
            self.proxy_transport = self.direct_transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        start_time = time.time()
        metrics.total_requests += 1
        target_domain = request.url.host

        if self.mode == "direct_only" or not self.proxy_url:
            return self._execute_direct(request, start_time)
            
        if self.mode == "proxy_only":
            return self._execute_proxy(request, start_time)

        # auto_fallback mode
        try:
            return self._execute_proxy(request, start_time)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout) as e:
            latency = (time.time() - start_time) * 1000
            metrics.proxy_failures += 1
            record_switch_event("local", target_domain, str(e), latency)
            # fallback to direct
            return self._execute_direct(request, time.time())

    def _execute_proxy(self, request: httpx.Request, start_time: float) -> httpx.Response:
        try:
            resp = self.proxy_transport.handle_request(request)
            metrics.proxy_success += 1
            metrics.total_latency_ms += (time.time() - start_time) * 1000
            return resp
        except Exception as e:
            raise e

    def _execute_direct(self, request: httpx.Request, start_time: float) -> httpx.Response:
        try:
            resp = self.direct_transport.handle_request(request)
            metrics.direct_success += 1
            metrics.total_latency_ms += (time.time() - start_time) * 1000
            return resp
        except Exception as e:
            metrics.direct_failures += 1
            raise e
            
    def close(self):
        self.direct_transport.close()
        if self.proxy_transport != self.direct_transport:
            self.proxy_transport.close()


class RedundantAsyncProxyTransport(httpx.AsyncBaseTransport):
    def __init__(self, mode: str = "auto_fallback", proxy_url: Optional[str] = None):
        self.mode = mode
        self.proxy_url = proxy_url
        
        self.direct_transport = httpx.AsyncHTTPTransport()
        if self.proxy_url:
            self.proxy_transport = httpx.AsyncHTTPTransport(proxy=self.proxy_url)
        else:
            self.proxy_transport = self.direct_transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        start_time = time.time()
        metrics.total_requests += 1
        target_domain = request.url.host

        if self.mode == "direct_only" or not self.proxy_url:
            return await self._execute_direct(request, start_time)
            
        if self.mode == "proxy_only":
            return await self._execute_proxy(request, start_time)

        # auto_fallback mode
        try:
            return await self._execute_proxy(request, start_time)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout) as e:
            latency = (time.time() - start_time) * 1000
            metrics.proxy_failures += 1
            record_switch_event("local", target_domain, str(e), latency)
            # fallback to direct
            return await self._execute_direct(request, time.time())

    async def _execute_proxy(self, request: httpx.Request, start_time: float) -> httpx.Response:
        try:
            resp = await self.proxy_transport.handle_async_request(request)
            metrics.proxy_success += 1
            metrics.total_latency_ms += (time.time() - start_time) * 1000
            return resp
        except Exception as e:
            raise e

    async def _execute_direct(self, request: httpx.Request, start_time: float) -> httpx.Response:
        try:
            resp = await self.direct_transport.handle_async_request(request)
            metrics.direct_success += 1
            metrics.total_latency_ms += (time.time() - start_time) * 1000
            return resp
        except Exception as e:
            metrics.direct_failures += 1
            raise e
            
    async def aclose(self):
        await self.direct_transport.aclose()
        if self.proxy_transport != self.direct_transport:
            await self.proxy_transport.aclose()

def detect_proxy_environment(proxy_url: str) -> bool:
    """Check proxy availability at startup."""
    if not proxy_url:
        return False
    logger.info(f"Detecting proxy connectivity: {proxy_url}")
    try:
        with httpx.Client(proxy=proxy_url, timeout=3.0) as client:
            client.get("https://api.openai.com", follow_redirects=True)
        logger.info("Proxy is reachable.")
        return True
    except Exception as e:
        logger.warning(f"Proxy is unreachable during startup detection: {e}")
        return False

def get_proxy_client() -> httpx.Client:
    mode = os.getenv("PROXY_MODE", "auto_fallback")
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    
    # Startup check
    if mode == "auto_fallback" and proxy_url:
        is_reachable = detect_proxy_environment(proxy_url)
        if not is_reachable:
            logger.warning("Proxy check failed, but will keep auto_fallback behavior.")

    transport = RedundantProxyTransport(mode=mode, proxy_url=proxy_url)
    return httpx.Client(transport=transport)

def get_async_proxy_client() -> httpx.AsyncClient:
    mode = os.getenv("PROXY_MODE", "auto_fallback")
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    
    transport = RedundantAsyncProxyTransport(mode=mode, proxy_url=proxy_url)
    return httpx.AsyncClient(transport=transport)
