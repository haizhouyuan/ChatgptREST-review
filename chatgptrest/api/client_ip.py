"""Client IP extraction with CIDR-validated proxy trust.

When ``CHATGPTREST_TRUSTED_PROXY_CIDRS`` is configured, uses a
rightmost-trusted-removal algorithm on ``X-Forwarded-For`` to extract the
real client IP, preventing IP spoofing.
"""
from __future__ import annotations

import ipaddress
import os
from functools import lru_cache

from starlette.requests import Request


@lru_cache(maxsize=1)
def _trusted_cidrs() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parse CHATGPTREST_TRUSTED_PROXY_CIDRS (comma-separated CIDRs)."""
    raw = os.environ.get("CHATGPTREST_TRUSTED_PROXY_CIDRS", "").strip()
    if not raw:
        return ()
    nets = []
    for cidr in raw.split(","):
        cidr = cidr.strip()
        if cidr:
            try:
                nets.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                pass  # skip malformed CIDRs
    return tuple(nets)


def _ip_in_trusted(ip_str: str) -> bool:
    """Check if an IP address falls within any trusted CIDR."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_cidrs())


def get_client_ip(request: Request) -> str:
    """Extract real client IP with proper CIDR-validated proxy trust.

    Algorithm (rightmost-trusted removal):
    - Start from direct client IP
    - If direct client IS in trusted CIDRs, walk X-Forwarded-For from RIGHT to LEFT
    - Return the first (rightmost) IP that is NOT in trusted CIDRs
    - This prevents spoofing: attacker can prepend arbitrary IPs, but the
      rightmost non-trusted IP was inserted by a trusted proxy.
    """
    direct = request.client.host if request.client else "0.0.0.0"
    cidrs = _trusted_cidrs()
    if not cidrs:
        return direct  # no proxy config → use direct IP
    if not _ip_in_trusted(direct):
        return direct  # direct client is not a trusted proxy → use as-is

    xff = request.headers.get("x-forwarded-for", "").strip()
    if not xff:
        return direct

    # Walk from right to left, skip trusted proxies, return first untrusted VALID IP
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    for ip_str in reversed(parts):
        try:
            ipaddress.ip_address(ip_str)  # drop malformed tokens
        except ValueError:
            continue
        if not _ip_in_trusted(ip_str):
            return ip_str

    return direct  # all IPs are trusted proxies → use direct
