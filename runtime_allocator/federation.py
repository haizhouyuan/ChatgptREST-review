"""P9: Federation & Edge — cross-region and edge inference support.

Provides client for federated inference and edge node registration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EdgeNode:
    """Registered edge inference node."""

    node_id: str
    region: str
    endpoint: str
    model_ids: list[str] = field(default_factory=list)
    latency_p50_ms: int = 2000
    last_heartbeat: Optional[str] = None
    healthy: bool = True


class EdgeRegistry:
    """In-memory registry of edge nodes. Production would use Redis/etcd."""

    def __init__(self):
        self._nodes: dict[str, EdgeNode] = {}

    def register(self, node: EdgeNode):
        self._nodes[node.node_id] = node

    def deregister(self, node_id: str):
        self._nodes.pop(node_id, None)

    def list_nodes(self, region: Optional[str] = None, model_id: Optional[str] = None) -> list[EdgeNode]:
        nodes = list(self._nodes.values())
        if region:
            nodes = [n for n in nodes if n.region == region]
        if model_id:
            nodes = [n for n in nodes if model_id in n.model_ids]
        return [n for n in nodes if n.healthy]

    def get_node(self, node_id: str) -> Optional[EdgeNode]:
        return self._nodes.get(node_id)

    def choose_node(
        self,
        region: Optional[str] = None,
        model_id: Optional[str] = None,
        prefer_low_latency: bool = True,
    ) -> Optional[EdgeNode]:
        """Select the best edge node based on filters and latency.

        Selection order:
        1. Filter by region (if specified)
        2. Filter by model availability (if specified)
        3. Filter healthy nodes
        4. Sort by latency_p50_ms (ascending)
        5. Return the best node
        """
        nodes = self.list_nodes(region=region, model_id=model_id)
        if not nodes:
            return None
        if prefer_low_latency:
            nodes = sorted(nodes, key=lambda n: n.latency_p50_ms)
        return nodes[0]


class FederationClient:
    """HTTP client for cross-region federated inference.

    Forwards task execution requests to remote runtime allocator instances.
    Uses connection pooling and exponential backoff retry.
    """

    def __init__(
        self,
        remote_endpoint: str,
        api_key: str = "",
        timeout: float = 120.0,
        max_retries: int = 3,
        pool_size: int = 10,
    ):
        self.remote_endpoint = remote_endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[object] = None
        self._pool_size = pool_size

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _get_client(self):
        """Lazy-init httpx client with connection pool."""
        if self._client is None:
            import httpx
            limits = httpx.Limits(max_connections=self._pool_size, max_keepalive_connections=self._pool_size)
            self._client = httpx.Client(limits=limits, timeout=self.timeout)
        return self._client

    def close(self):
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _post_with_retry(self, url: str, payload: dict) -> dict:
        """POST with exponential backoff retry."""
        import httpx
        client = self._get_client()
        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = client.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
                return {"status_code": resp.status_code, "data": resp.json() if resp.status_code == 200 else None, "text": resp.text}
            except httpx.TimeoutException as exc:
                last_error = f"timeout:{exc}"
            except httpx.ConnectError as exc:
                last_error = f"connect:{exc}"
            except Exception as exc:
                last_error = str(exc)
            # Exponential backoff: 0.5s, 1s, 2s
            if attempt < self.max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))
        return {"status_code": 0, "data": None, "error": last_error}

    def forward_request(
        self,
        task_class: str,
        messages: list[dict],
        timeout: Optional[float] = None,
    ) -> dict:
        """Forward a task execution request to a remote allocator.

        Returns a dict with status, content, and metadata.
        """
        payload = {
            "task_class": task_class,
            "messages": messages,
        }
        result = self._post_with_retry(
            f"{self.remote_endpoint}/v1/execute",
            payload,
        )
        if result.get("error"):
            return {
                "status": "error",
                "remote_endpoint": self.remote_endpoint,
                "task_class": task_class,
                "content": "",
                "error": result["error"],
            }
        if result["status_code"] == 200:
            data = result["data"] or {}
            return {
                "status": "forwarded",
                "remote_endpoint": self.remote_endpoint,
                "task_class": task_class,
                "content": data.get("content", ""),
                "success": data.get("success", False),
                "provider_id": data.get("provider_id", ""),
                "latency_ms": data.get("latency_ms", 0.0),
            }
        return {
            "status": "error",
            "remote_endpoint": self.remote_endpoint,
            "task_class": task_class,
            "content": "",
            "error": f"HTTP {result['status_code']}",
        }

    def health_check(self) -> dict:
        """Check remote allocator health."""
        try:
            import httpx
            client = self._get_client()
            resp = client.get(
                f"{self.remote_endpoint}/health",
                headers=self._headers(),
                timeout=10.0,
            )
            return {
                "remote_endpoint": self.remote_endpoint,
                "reachable": resp.status_code == 200,
                "status_code": resp.status_code,
                "healthy": resp.json().get("status") == "healthy" if resp.status_code == 200 else False,
            }
        except Exception as exc:
            return {
                "remote_endpoint": self.remote_endpoint,
                "reachable": False,
                "error": str(exc),
            }


# ── Federated runtime wrapper ────────────────────────────────────────────────

@dataclass
class FederatedProvider:
    """Wraps an EdgeNode so it can be used as a Runtime in allocate().

    The provider_id is the edge node's node_id, and the endpoint is the
    node's endpoint. When selected by allocate(), the skill_agent invokes
    the FederationClient instead of a local LLM.
    """

    node: EdgeNode
    privacy_tier: str = "external_cloud"
    quality_tier: str = "standard"
    supports_tools: bool = False
    supports_json: bool = True
    max_context_tokens: int = 128000

    @property
    def provider_id(self) -> str:
        return f"federated:{self.node.node_id}"

    @property
    def model_name(self) -> str:
        return self.node.model_ids[0] if self.node.model_ids else ""

    @property
    def endpoint(self) -> str:
        return self.node.endpoint

    def to_runtime(self):
        """Convert to an allocator_mvp Runtime dataclass."""
        from runtime_allocator.allocator_mvp import Runtime, PrivacyTier, QualityTier
        return Runtime(
            provider_id=self.provider_id,
            model_name=self.model_name,
            endpoint=self.endpoint,
            privacy_tier=PrivacyTier(self.privacy_tier),
            quality_tier=QualityTier(self.quality_tier),
            supports_tools=self.supports_tools,
            supports_json=self.supports_json,
            max_context_tokens=self.max_context_tokens,
        )
