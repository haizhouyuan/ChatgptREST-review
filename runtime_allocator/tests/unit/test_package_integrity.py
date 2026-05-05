"""Test package integrity — imports, policy loads, provider references."""

from __future__ import annotations

import pytest


class TestPackageImportable:
    def test_runtime_allocator_importable(self):
        import runtime_allocator
        from runtime_allocator.skill_agent import execute_with_fallback
        from runtime_allocator.policy_store import load_routing_policy
        from runtime_allocator.schemas import CommerceDecisionOutput

    def test_security_module_importable(self):
        from runtime_allocator.security import safe_slug
        assert safe_slug("hello world") == "hello_world"

    def test_runtime_state_importable(self):
        from runtime_allocator.runtime_state import RuntimeStateStore
        assert RuntimeStateStore is not None


class TestPolicyIntegrity:
    def test_all_policies_load(self):
        from runtime_allocator.policy_store import load_routing_policy
        policies = load_routing_policy()
        assert len(policies) >= 30

    def test_profiles_load(self):
        from runtime_allocator.skill_agent import load_profiles
        profiles = load_profiles()
        assert "runtimes" in profiles
        providers = set(profiles["runtimes"].keys())
        assert len(providers) >= 4

    def test_policy_references_existing_providers(self):
        from runtime_allocator.skill_agent import load_profiles
        from runtime_allocator.policy_store import load_routing_policy

        profiles = load_profiles()
        policies = load_routing_policy()

        providers = set(profiles["runtimes"].keys())
        for task_class, policy in policies.items():
            for pid in policy.primary + policy.fallback:
                assert pid in providers, f"{task_class} references unknown provider {pid}"

    def test_no_unknown_provider_in_policies(self):
        from runtime_allocator.skill_agent import load_profiles
        from runtime_allocator.policy_store import load_routing_policy

        profiles = load_profiles()
        policies = load_routing_policy()
        providers = set(profiles["runtimes"].keys())

        all_referenced = set()
        for policy in policies.values():
            all_referenced.update(policy.primary)
            all_referenced.update(policy.fallback)

        unknown = all_referenced - providers
        assert not unknown, f"Policies reference unknown providers: {unknown}"

    def test_yaml_files_locatable(self):
        from runtime_allocator.policy_store import _resolve_policy_path
        from runtime_allocator.allocator_mvp import _resolve_profiles_yaml

        policy_path = _resolve_policy_path()
        profiles_path = _resolve_profiles_yaml()
        assert policy_path.exists()
        assert profiles_path.exists()
