"""P9: Federation & Edge — cross-region and edge inference support.

Provides client for federated inference and edge node registration.
"""

from __future__ import annotations

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


class FederationClient:
    """HTTP client for cross-region federated inference.

    Forwards task execution requests to remote runtime allocator instances.
    """

    def __init__(self, remote_endpoint: str, api_key: str = ""):
        self.remote_endpoint = remote_endpoint.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def forward_request(
        self,
        task_class: str,
        messages: list[dict],
        timeout: float = 120.0,
    ) -> dict:
        """Forward a task execution request to a remote allocator.

        Returns a dict with status, content, and metadata.
        """
        try:
            import httpx
            payload = {
                "task_class": task_class,
                "messages": messages,
            }
            resp = httpx.post(
                f"{self.remote_endpoint}/v1/execute",
                json=payload,
                headers=self._headers(),
                timeout=timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
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
                "error": f"HTTP {resp.status_code}",
            }
        except Exception as exc:
            return {
                "status": "error",
                "remote_endpoint": self.remote_endpoint,
                "task_class": task_class,
                "content": "",
                "error": str(exc),
            }

    def health_check(self) -> dict:
        """Check remote allocator health."""
        try:
            import httpx
            resp = httpx.get(
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
