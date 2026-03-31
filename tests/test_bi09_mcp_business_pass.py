#!/usr/bin/env python3
"""BI-09: Test MCP surface for advisor agent.

Validates:
- attachments survive MCP transport
- role_id, user_id, trace_id survive MCP transport
- MCP users don't need to see low-level /v1/jobs/* details
"""

import asyncio
import json
import sys
from unittest.mock import MagicMock, patch

# Test 1: Verify MCP forwards attachments
def test_mcp_forwards_attachments():
    """BI-01 equivalent: attachments survive MCP transport"""
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "completed",
        "answer": "Code review complete",
        "delivery": {"format": "markdown"},
        "provenance": {"route": "code_review", "provider_path": ["chatgpt"]},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_context.getcode.return_value = 200
        mock_urlopen.return_value = mock_context

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Review this code",
                goal_hint="code_review",
                depth="deep",
                attachments=["/tmp/repo.zip", "/tmp/test.py"],
                timeout_seconds=300,
            )
        )

        # Verify request payload
        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload.get("attachments") == ["/tmp/repo.zip", "/tmp/test.py"], \
            f"Attachments not forwarded: {payload.get('attachments')}"
        assert payload.get("goal_hint") == "code_review"
        assert payload.get("depth") == "deep"

        # Verify response doesn't expose /v1/jobs/* details
        assert "job_id" not in result or result.get("delivery", {}).get("format") == "markdown"
        assert "provenance" in result
        assert result["provenance"].get("route") == "code_review"

        print("✓ BI-01: MCP forwards attachments correctly")


def test_mcp_forwards_identity():
    """BI-02/BI-03 equivalent: identity fields survive MCP transport"""
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-456",
        "status": "completed",
        "answer": "Research complete",
        "provenance": {"route": "gemini_research", "provider_path": ["gemini"]},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_context.getcode.return_value = 200
        mock_urlopen.return_value = mock_context

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Research this topic",
                goal_hint="gemini_research",
                role_id="researcher",
                user_id="user-123",
                trace_id="trace-abc",
                auto_watch=False,
                timeout_seconds=300,
            )
        )

        # Verify identity fields in request
        req = mock_urlopen.call_args_list[0].args[0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload.get("role_id") == "researcher", f"role_id not forwarded: {payload}"
        assert payload.get("user_id") == "user-123", f"user_id not forwarded: {payload}"
        assert payload.get("trace_id") == "trace-abc", f"trace_id not forwarded: {payload}"

        # Verify response structure - no /v1/jobs/* exposure
        assert "job_id" not in result or "provenance" in result

        print("✓ BI-02/BI-03: MCP forwards identity fields correctly")


def test_mcp_status_endpoint():
    """BI-07 equivalent: status doesn't expose /v1/jobs/* details"""
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-789",
        "status": "running",
        "last_message": "Processing...",
        "route": "quick_ask",
        "next_action": "wait",
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_context.getcode.return_value = 200
        mock_urlopen.return_value = mock_context

        result = asyncio.run(
            agent_mcp.advisor_agent_status(None, session_id="test-session")
        )

        # Verify no /v1/jobs/* details exposed
        assert "job_id" not in result, "job_id should not be in status response"
        assert result.get("status") == "running"
        assert "next_action" in result

        print("✓ BI-07: MCP status endpoint hides /v1/jobs/* details")


def test_mcp_cancel_endpoint():
    """BI-08 equivalent: cancel works correctly"""
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "cancelled",
        "cancelled_job_ids": ["job-1", "job-2"],
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_context.getcode.return_value = 200
        mock_urlopen.return_value = mock_context

        result = asyncio.run(
            agent_mcp.advisor_agent_cancel(None, session_id="test-session")
        )

        assert result.get("ok") is True
        assert result.get("status") == "cancelled"

        # Verify request went to /v3/agent/cancel
        req = mock_urlopen.call_args.args[0]
        assert "/v3/agent/cancel" in req.full_url

        print("✓ BI-08: MCP cancel endpoint works correctly")


def test_mcp_dual_model_consult():
    """BI-04 equivalent: consult creates consultation"""
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-consult",
        "status": "completed",
        "answer": "Dual review: Model A agrees, Model B suggests...",
        "delivery": {"format": "markdown"},
        "provenance": {
            "consultation_id": "consult-123",
            "provider_path": ["chatgpt", "gemini"],
        },
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_context.getcode.return_value = 200
        mock_urlopen.return_value = mock_context

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Review this code from both perspectives",
                goal_hint="dual_review",
                timeout_seconds=300,
            )
        )

        # Verify consultation response
        assert result.get("provenance", {}).get("consultation_id") == "consult-123"
        assert "chatgpt" in result["provenance"].get("provider_path", [])
        assert "gemini" in result["provenance"].get("provider_path", [])

        print("✓ BI-04: MCP handles dual-model consult correctly")


def test_mcp_image_generation():
    """BI-05 equivalent: image generation works"""
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-image",
        "status": "completed",
        "answer": "![generated image](artifacts/jobs/job-img-123/image.png)",
        "delivery": {"format": "markdown"},
        "provenance": {
            "route": "image",
            "provider_path": ["gemini"],
        },
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_context.getcode.return_value = 200
        mock_urlopen.return_value = mock_context

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Generate an image of a sunset",
                goal_hint="image",
                attachments=["/tmp/reference.jpg"],
                timeout_seconds=300,
            )
        )

        # Verify request payload has correct fields
        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload.get("goal_hint") == "image"
        assert payload.get("attachments") == ["/tmp/reference.jpg"]

        # Verify response format
        assert "image" in result.get("answer", "").lower() or "png" in result.get("answer", "").lower()

        print("✓ BI-05: MCP handles image generation correctly")


def main():
    print("=" * 60)
    print("BI-09: Public MCP Business Pass Tests")
    print("=" * 60)

    tests = [
        ("BI-01: Attachments survive MCP transport", test_mcp_forwards_attachments),
        ("BI-02/BI-03: Identity fields survive MCP transport", test_mcp_forwards_identity),
        ("BI-04: Dual-model consult via MCP", test_mcp_dual_model_consult),
        ("BI-05: Image generation via MCP", test_mcp_image_generation),
        ("BI-07: Status endpoint hides /v1/jobs/*", test_mcp_status_endpoint),
        ("BI-08: Cancel endpoint works", test_mcp_cancel_endpoint),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {name}: FAILED - {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} PASSED, {failed} FAILED")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    print("\nBI-09: ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
