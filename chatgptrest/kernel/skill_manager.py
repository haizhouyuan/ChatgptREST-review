"""Canonical skill-platform registry, bundles, resolver, and projections."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILL_REGISTRY_PATH = (REPO_ROOT / "ops" / "policies" / "skill_platform_registry_v1.json").resolve()


def resolve_skill_registry_authority_path(raw: str | os.PathLike[str] = "") -> Path:
    candidate = str(raw or "").strip() or os.environ.get("CHATGPTREST_SKILL_REGISTRY_PATH", "").strip()
    if candidate:
        return Path(candidate).expanduser().resolve()
    return DEFAULT_SKILL_REGISTRY_PATH


@dataclass(frozen=True)
class RegistryAuthority:
    registry_id: str
    schema_version: str
    registry_version: str
    owner: str
    source_of_truth: str
    write_authority: tuple[str, ...] = ()
    classification_contract: tuple[str, ...] = ()
    version_policy: str = ""
    projection_policy: str = ""
    authority_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    version: str
    description: str
    classification: str
    maturity: str
    owner: str
    source_of_truth: str
    platform_support: tuple[str, ...] = ()
    bundle_membership: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    telemetry_keys: tuple[str, ...] = ()
    provides_capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports_platform(self, platform: str) -> bool:
        return not self.platform_support or platform in self.platform_support

    def is_runtime_local(self) -> bool:
        return self.source_of_truth.startswith("skills-src/")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BundleManifest:
    bundle_id: str
    version: str
    description: str
    classification: str
    maturity: str
    owner: str
    platform_support: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    provided_capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports_platform(self, platform: str) -> bool:
        return not self.platform_support or platform in self.platform_support

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentBundleProfile:
    agent_id: str
    platform: str = "openclaw"
    default_bundles: tuple[str, ...] = ()
    preferred_model: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskProfile:
    task_type: str
    description: str
    required_capabilities: tuple[str, ...] = ()
    preferred_agents: tuple[str, ...] = ()
    preferred_bundles: tuple[str, ...] = ()
    fallback_bundles: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlatformAdapter:
    platform: str
    projection_mode: str
    bundle_field: str = "bundles"
    skill_field: str = "skills"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UnmetCapability:
    capability_id: str
    reason: str
    required_by_task: str
    candidate_bundles: list[str] = field(default_factory=list)
    candidate_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolutionResult:
    passed: bool
    status: str
    agent_id: str
    task_type: str
    platform: str
    required_capabilities: list[str]
    available_capabilities: list[str]
    available_skills: list[str]
    available_bundles: list[str]
    recommended_skills: list[str] = field(default_factory=list)
    recommended_bundles: list[str] = field(default_factory=list)
    unmet_capabilities: list[UnmetCapability] = field(default_factory=list)
    suggested_agent: str | None = None
    decision_reasons: list[str] = field(default_factory=list)
    fallback_plan: list[dict[str, Any]] = field(default_factory=list)
    registry_authority: dict[str, Any] = field(default_factory=dict)
    identity_status: str = "registered"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["unmet_capabilities"] = [item.to_dict() for item in self.unmet_capabilities]
        return payload


def _as_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in (values or []) if str(value).strip())


class CanonicalRegistry:
    """Loads and serves the canonical skill platform registry authority."""

    def __init__(self, authority_path: str | os.PathLike[str] = "") -> None:
        self._authority_path = resolve_skill_registry_authority_path(authority_path)
        self._load()

    @property
    def authority_path(self) -> Path:
        return self._authority_path

    def _load(self) -> None:
        payload = json.loads(self._authority_path.read_text(encoding="utf-8"))
        authority = payload.get("authority") or {}
        self.authority = RegistryAuthority(
            registry_id=str(authority.get("registry_id") or "chatgptrest-skill-platform"),
            schema_version=str(authority.get("schema_version") or "1.0"),
            registry_version=str(authority.get("registry_version") or "0.0.0"),
            owner=str(authority.get("owner") or "unknown"),
            source_of_truth=str(authority.get("source_of_truth") or self._authority_path),
            write_authority=_as_tuple(authority.get("write_authority")),
            classification_contract=_as_tuple(authority.get("classification_contract")),
            version_policy=str(authority.get("version_policy") or ""),
            projection_policy=str(authority.get("projection_policy") or ""),
            authority_path=str(self._authority_path),
        )
        self.capabilities: dict[str, str] = {
            str(key): str(value)
            for key, value in (payload.get("capabilities") or {}).items()
            if str(key).strip()
        }
        self.skills: dict[str, SkillManifest] = {}
        for raw in list(payload.get("skills") or []):
            manifest = SkillManifest(
                skill_id=str(raw.get("skill_id") or "").strip(),
                version=str(raw.get("version") or "0.0.0"),
                description=str(raw.get("description") or ""),
                classification=str(raw.get("classification") or "canonical"),
                maturity=str(raw.get("maturity") or "experimental"),
                owner=str(raw.get("owner") or "unknown"),
                source_of_truth=str(raw.get("source_of_truth") or ""),
                platform_support=_as_tuple(raw.get("platform_support")),
                bundle_membership=_as_tuple(raw.get("bundle_membership")),
                dependencies=_as_tuple(raw.get("dependencies")),
                failure_modes=_as_tuple(raw.get("failure_modes")),
                telemetry_keys=_as_tuple(raw.get("telemetry_keys")),
                provides_capabilities=_as_tuple(raw.get("provides_capabilities")),
                metadata=dict(raw.get("metadata") or {}),
            )
            if manifest.skill_id:
                self.skills[manifest.skill_id] = manifest
        self.bundles: dict[str, BundleManifest] = {}
        for raw in list(payload.get("bundles") or []):
            bundle = BundleManifest(
                bundle_id=str(raw.get("bundle_id") or "").strip(),
                version=str(raw.get("version") or "0.0.0"),
                description=str(raw.get("description") or ""),
                classification=str(raw.get("classification") or "canonical"),
                maturity=str(raw.get("maturity") or "experimental"),
                owner=str(raw.get("owner") or "unknown"),
                platform_support=_as_tuple(raw.get("platform_support")),
                skill_ids=_as_tuple(raw.get("skill_ids")),
                provided_capabilities=_as_tuple(raw.get("provided_capabilities")),
                dependencies=_as_tuple(raw.get("dependencies")),
                metadata=dict(raw.get("metadata") or {}),
            )
            if bundle.bundle_id:
                self.bundles[bundle.bundle_id] = bundle
        self.agent_profiles: dict[str, AgentBundleProfile] = {}
        for raw in list(payload.get("agent_profiles") or []):
            profile = AgentBundleProfile(
                agent_id=str(raw.get("agent_id") or "").strip(),
                platform=str(raw.get("platform") or "openclaw"),
                default_bundles=_as_tuple(raw.get("default_bundles")),
                preferred_model=str(raw.get("preferred_model") or "auto"),
                metadata=dict(raw.get("metadata") or {}),
            )
            if profile.agent_id:
                self.agent_profiles[profile.agent_id] = profile
        self.task_profiles: dict[str, TaskProfile] = {}
        for task_type, raw in (payload.get("task_profiles") or {}).items():
            profile = TaskProfile(
                task_type=str(task_type),
                description=str((raw or {}).get("description") or ""),
                required_capabilities=_as_tuple((raw or {}).get("required_capabilities")),
                preferred_agents=_as_tuple((raw or {}).get("preferred_agents")),
                preferred_bundles=_as_tuple((raw or {}).get("preferred_bundles")),
                fallback_bundles=_as_tuple((raw or {}).get("fallback_bundles")),
                metadata={key: value for key, value in (raw or {}).items() if key not in {
                    "description",
                    "required_capabilities",
                    "preferred_agents",
                    "preferred_bundles",
                    "fallback_bundles",
                }},
            )
            self.task_profiles[profile.task_type] = profile
        self.platform_adapters: dict[str, PlatformAdapter] = {}
        for platform, raw in (payload.get("platform_adapters") or {}).items():
            adapter = PlatformAdapter(
                platform=str(platform),
                projection_mode=str((raw or {}).get("projection_mode") or "shared_catalog_reference"),
                bundle_field=str((raw or {}).get("bundle_field") or "bundles"),
                skill_field=str((raw or {}).get("skill_field") or "skills"),
                metadata={key: value for key, value in (raw or {}).items() if key not in {
                    "projection_mode",
                    "bundle_field",
                    "skill_field",
                }},
            )
            self.platform_adapters[adapter.platform] = adapter

    def capability_catalog(self) -> dict[str, str]:
        return dict(self.capabilities)

    def task_profile_requirements(self) -> dict[str, list[str]]:
        return {
            task_type: list(profile.required_capabilities)
            for task_type, profile in self.task_profiles.items()
        }

    def get_task_profile(self, task_type: str) -> TaskProfile:
        return self.task_profiles.get(
            task_type,
            TaskProfile(task_type=task_type or "general", description="Fallback task profile", required_capabilities=("document_writing",)),
        )

    def lookup(self, skill_id: str) -> SkillManifest | None:
        return self.skills.get(skill_id)

    def get_bundle(self, bundle_id: str) -> BundleManifest | None:
        return self.bundles.get(bundle_id)

    def get_agent_profile(self, agent_id: str) -> AgentBundleProfile | None:
        return self.agent_profiles.get(agent_id)

    def list_all(self) -> list[SkillManifest]:
        return list(self.skills.values())

    def list_by_bundle(self, bundle_id: str) -> list[SkillManifest]:
        bundle = self.get_bundle(bundle_id)
        if bundle is None:
            return []
        return [self.skills[skill_id] for skill_id in bundle.skill_ids if skill_id in self.skills]

    def bundles_for_capability(self, capability_id: str, *, platform: str = "") -> list[str]:
        matches: list[str] = []
        for bundle_id, bundle in self.bundles.items():
            if platform and not bundle.supports_platform(platform):
                continue
            if capability_id in bundle.provided_capabilities:
                matches.append(bundle_id)
        return matches

    def skills_for_capability(self, capability_id: str, *, platform: str = "") -> list[str]:
        matches: list[str] = []
        for skill_id, manifest in self.skills.items():
            if platform and not manifest.supports_platform(platform):
                continue
            if capability_id in manifest.provides_capabilities:
                matches.append(skill_id)
        return matches

    def available_skill_ids_for_bundles(
        self,
        bundle_ids: Iterable[str],
        *,
        platform: str = "",
        runtime_local_only: bool = False,
    ) -> list[str]:
        skill_ids: list[str] = []
        for bundle_id in bundle_ids:
            bundle = self.get_bundle(bundle_id)
            if bundle is None or (platform and not bundle.supports_platform(platform)):
                continue
            for skill_id in bundle.skill_ids:
                manifest = self.lookup(skill_id)
                if manifest is None or (platform and not manifest.supports_platform(platform)):
                    continue
                if runtime_local_only and not manifest.is_runtime_local():
                    continue
                if skill_id not in skill_ids:
                    skill_ids.append(skill_id)
        return skill_ids

    def available_capabilities_for_bundles(self, bundle_ids: Iterable[str], *, platform: str = "") -> list[str]:
        capabilities: list[str] = []
        for bundle_id in bundle_ids:
            bundle = self.get_bundle(bundle_id)
            if bundle is None or (platform and not bundle.supports_platform(platform)):
                continue
            for capability_id in bundle.provided_capabilities:
                if capability_id not in capabilities:
                    capabilities.append(capability_id)
            for skill_id in bundle.skill_ids:
                manifest = self.lookup(skill_id)
                if manifest is None or (platform and not manifest.supports_platform(platform)):
                    continue
                for capability_id in manifest.provides_capabilities:
                    if capability_id not in capabilities:
                        capabilities.append(capability_id)
        return capabilities

    def find_best_agent_for_task(
        self,
        task_type: str,
        *,
        platform: str = "openclaw",
        exclude_agent: str = "",
    ) -> str | None:
        profile = self.get_task_profile(task_type)
        required = set(profile.required_capabilities)
        candidates = [
            agent
            for agent in self.agent_profiles.values()
            if agent.platform == platform and agent.agent_id != exclude_agent
        ]
        for preferred in profile.preferred_agents:
            for candidate in candidates:
                if candidate.agent_id != preferred:
                    continue
                capabilities = set(self.available_capabilities_for_bundles(candidate.default_bundles, platform=platform))
                if required.issubset(capabilities):
                    return candidate.agent_id
        best_agent: str | None = None
        best_score = -1
        for candidate in candidates:
            capabilities = set(self.available_capabilities_for_bundles(candidate.default_bundles, platform=platform))
            score = len(required.intersection(capabilities))
            if required.issubset(capabilities):
                score += 100
            if score > best_score:
                best_score = score
                best_agent = candidate.agent_id
        return best_agent

    def projection_for_platform(self, platform: str) -> dict[str, Any]:
        adapter = self.platform_adapters.get(platform) or PlatformAdapter(platform=platform, projection_mode="shared_catalog_reference")
        bundles = [bundle.to_dict() for bundle in self.bundles.values() if bundle.supports_platform(platform)]
        skills = [skill.to_dict() for skill in self.skills.values() if skill.supports_platform(platform)]
        agents = [profile.to_dict() for profile in self.agent_profiles.values() if profile.platform == platform]
        return {
            "authority": self.authority.to_dict(),
            "adapter": adapter.to_dict(),
            "bundles": bundles,
            "skills": skills,
            "agents": agents,
        }


class BundleResolver:
    """Bundle-aware capability resolver built on the canonical registry."""

    def __init__(self, registry: CanonicalRegistry):
        self._registry = registry

    def resolve_for_tenant(self, tenant_id: str, authorized_bundles: list[str]) -> list[SkillManifest]:
        resolved: list[SkillManifest] = []
        seen: set[str] = set()
        for bundle_id in authorized_bundles:
            for manifest in self._registry.list_by_bundle(bundle_id):
                if manifest.skill_id in seen:
                    continue
                seen.add(manifest.skill_id)
                resolved.append(manifest)
        logger.info(
            "Resolved %d skills across %d bundles for tenant %s",
            len(resolved),
            len(authorized_bundles),
            tenant_id,
        )
        return resolved

    def validate_dependency_chain(self, skill_name: str) -> bool:
        manifest = self._registry.lookup(skill_name)
        if manifest is None:
            return False
        for dependency in manifest.dependencies:
            if self._registry.lookup(dependency) is None:
                logger.warning("Dependency %s missing for skill %s", dependency, skill_name)
                return False
        return True

    def resolve_for_agent(
        self,
        *,
        agent_id: str,
        task_type: str,
        platform: str = "openclaw",
        available_bundles: Iterable[str] | None = None,
    ) -> ResolutionResult:
        task_profile = self._registry.get_task_profile(task_type)
        required = list(task_profile.required_capabilities)
        registry_authority = self._registry.authority.to_dict()
        agent_profile = self._registry.get_agent_profile(agent_id)
        if agent_profile is None:
            suggested_agent = self._registry.find_best_agent_for_task(task_type, platform=platform)
            unmet = [
                UnmetCapability(
                    capability_id=capability_id,
                    reason="unknown_agent",
                    required_by_task=task_type,
                    candidate_bundles=self._registry.bundles_for_capability(capability_id, platform=platform),
                    candidate_skills=self._registry.skills_for_capability(capability_id, platform=platform),
                )
                for capability_id in required
            ]
            fallback_plan: list[dict[str, Any]] = []
            if suggested_agent:
                fallback_plan.append(
                    {
                        "action": "switch_agent",
                        "agent_id": suggested_agent,
                        "reason": "registered agent with matching bundle coverage",
                    }
                )
            return ResolutionResult(
                passed=False,
                status="unknown_agent",
                agent_id=agent_id,
                task_type=task_type,
                platform=platform,
                required_capabilities=required,
                available_capabilities=[],
                available_skills=[],
                available_bundles=[],
                recommended_skills=sorted({skill for item in unmet for skill in item.candidate_skills}),
                recommended_bundles=sorted({bundle for item in unmet for bundle in item.candidate_bundles}),
                unmet_capabilities=unmet,
                suggested_agent=suggested_agent,
                decision_reasons=[f"agent '{agent_id}' is not registered for platform '{platform}'"],
                fallback_plan=fallback_plan,
                registry_authority=registry_authority,
                identity_status="unknown_agent",
            )

        effective_bundles = list(dict.fromkeys(str(bundle).strip() for bundle in (available_bundles or agent_profile.default_bundles) if str(bundle).strip()))
        available_capabilities = self._registry.available_capabilities_for_bundles(effective_bundles, platform=platform)
        available_skills = self._registry.available_skill_ids_for_bundles(effective_bundles, platform=platform)
        unmet: list[UnmetCapability] = []
        for capability_id in required:
            if capability_id in available_capabilities:
                continue
            unmet.append(
                UnmetCapability(
                    capability_id=capability_id,
                    reason="bundle_missing",
                    required_by_task=task_type,
                    candidate_bundles=self._registry.bundles_for_capability(capability_id, platform=platform),
                    candidate_skills=self._registry.skills_for_capability(capability_id, platform=platform),
                )
            )
        suggested_agent = None
        decision_reasons = [
            f"agent '{agent_id}' bundles={effective_bundles or ['<none>']}",
            f"required capabilities={required}",
            f"available capabilities={available_capabilities}",
        ]
        fallback_plan: list[dict[str, Any]] = []
        recommended_skills = sorted({skill for item in unmet for skill in item.candidate_skills})
        recommended_bundles = sorted(
            {
                bundle_id
                for bundle_id in task_profile.preferred_bundles
                if bundle_id not in effective_bundles
            }.union({bundle for item in unmet for bundle in item.candidate_bundles})
        )
        if unmet:
            suggested_agent = self._registry.find_best_agent_for_task(task_type, platform=platform, exclude_agent=agent_id)
            if suggested_agent:
                fallback_plan.append(
                    {
                        "action": "switch_agent",
                        "agent_id": suggested_agent,
                        "reason": "registered agent has stronger capability coverage for this task profile",
                    }
                )
            for bundle_id in recommended_bundles:
                fallback_plan.append(
                    {
                        "action": "add_bundle",
                        "bundle_id": bundle_id,
                        "reason": "bundle covers missing capabilities",
                    }
                )
            decision_reasons.append(
                "unmet capabilities detected: "
                + ", ".join(sorted(item.capability_id for item in unmet))
            )
            return ResolutionResult(
                passed=False,
                status="unmet_capabilities",
                agent_id=agent_id,
                task_type=task_type,
                platform=platform,
                required_capabilities=required,
                available_capabilities=available_capabilities,
                available_skills=available_skills,
                available_bundles=effective_bundles,
                recommended_skills=recommended_skills,
                recommended_bundles=recommended_bundles,
                unmet_capabilities=unmet,
                suggested_agent=suggested_agent,
                decision_reasons=decision_reasons,
                fallback_plan=fallback_plan,
                registry_authority=registry_authority,
            )
        decision_reasons.append("bundle coverage satisfied all required capabilities")
        return ResolutionResult(
            passed=True,
            status="ready",
            agent_id=agent_id,
            task_type=task_type,
            platform=platform,
            required_capabilities=required,
            available_capabilities=available_capabilities,
            available_skills=available_skills,
            available_bundles=effective_bundles,
            recommended_skills=[],
            recommended_bundles=[],
            unmet_capabilities=[],
            suggested_agent=None,
            decision_reasons=decision_reasons,
            fallback_plan=[],
            registry_authority=registry_authority,
        )


@lru_cache(maxsize=1)
def get_canonical_registry(authority_path: str = "") -> CanonicalRegistry:
    return CanonicalRegistry(authority_path=authority_path)


@lru_cache(maxsize=1)
def get_bundle_resolver(authority_path: str = "") -> BundleResolver:
    return BundleResolver(get_canonical_registry(authority_path=authority_path))
