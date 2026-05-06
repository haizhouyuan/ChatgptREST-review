from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "chatgpt_wrapper_v1.py"
    spec = importlib.util.spec_from_file_location("chatgpt_wrapper_v1", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompt_refine_adds_structure() -> None:
    mod = _load_module()
    out = mod.prompt_refine("帮我看看这个系统怎么改")
    assert "原始问题" in out
    assert "目标定义" in out
    assert "子问题拆解" in out


def test_prompt_refine_empty_input_returns_template() -> None:
    mod = _load_module()
    out = mod.prompt_refine("")
    assert "背景" in out
    assert "目标" in out
    assert "约束" in out


def test_prompt_refine_injects_context() -> None:
    mod = _load_module()
    out = mod.prompt_refine(
        "请给出修复方案",
        {
            "project": "chatgptrest",
            "goal": "修复 wait 卡死",
        },
    )
    assert "已知上下文" in out
    assert "- project: chatgptrest" in out
    assert "- goal: 修复 wait 卡死" in out


def test_question_gap_check_detects_missing_context() -> None:
    mod = _load_module()
    asks = mod.question_gap_check("这个问题尽快处理", {})
    assert len(asks) >= 3
    assert any("截止时间" in item for item in asks)
    assert any("对象不明确" in item for item in asks)


def test_question_gap_check_returns_empty_when_context_complete() -> None:
    mod = _load_module()
    ctx = {
        "project": "homeagent",
        "goal": "修复播报中断",
        "constraints": "不改核心架构",
        "environment": "python3.11",
        "acceptance": "pytest + 日志指标",
        "reference": "ops/chatgpt_agent_shell_v0.py",
        "deadline": "2026-02-28T12:00:00Z",
    }
    asks = mod.question_gap_check("修复语音中断", ctx)
    assert asks == []


def test_question_gap_check_matches_case_insensitive_english_reference() -> None:
    mod = _load_module()
    asks = mod.question_gap_check("THIS HAS THE SAME ISSUE", {"project": "demo"})
    assert any("对象不明确" in item for item in asks)


def test_channel_strategy_prefers_deep_research_for_research_queries() -> None:
    mod = _load_module()
    route = mod.channel_strategy("请调研最近一年的竞品与政策变化并给出来源引用")
    assert route == mod.ROUTE_DEEP_RESEARCH


def test_channel_strategy_prefers_multi_stage_when_strategy_and_research_both_present() -> None:
    mod = _load_module()
    route = mod.channel_strategy("先做架构方案，再做最新资料调研并汇总")
    assert route == mod.ROUTE_PRO_THEN_DR_THEN_PRO


def test_channel_strategy_prefers_crosscheck_route() -> None:
    mod = _load_module()
    route = mod.channel_strategy("需要双重验证和多模型交叉验证")
    assert route == mod.ROUTE_PRO_GEMINI_CROSSCHECK


def test_channel_strategy_negated_research_routes_to_chatgpt_pro() -> None:
    mod = _load_module()
    route = mod.channel_strategy("请给出一个 CLI 发布流程优化建议，不需要联网调研")
    assert route == mod.ROUTE_CHATGPT_PRO


def test_channel_strategy_trace_contains_reason_and_keywords() -> None:
    mod = _load_module()
    trace = mod.channel_strategy_trace("先做架构方案，再做最新资料调研并汇总")
    assert trace["route"] == mod.ROUTE_PRO_THEN_DR_THEN_PRO
    assert trace["reason"] == "matched_research_and_strategy_keywords"
    assert trace["flags"]["has_research"] is True
    assert trace["flags"]["has_strategy"] is True
    assert "调研" in trace["matched_keywords"]["research"]


def test_channel_strategy_trace_crosscheck_overrides_other_signals() -> None:
    mod = _load_module()
    trace = mod.channel_strategy_trace("请做多模型交叉验证并调研最新竞品")
    assert trace["route"] == mod.ROUTE_PRO_GEMINI_CROSSCHECK
    assert trace["flags"]["has_crosscheck"] is True
    assert "多模型" in trace["matched_keywords"]["crosscheck"]


def test_channel_strategy_trace_marks_negated_research() -> None:
    mod = _load_module()
    trace = mod.channel_strategy_trace("这个方案不需要联网调研，直接给出落地步骤")
    assert trace["route"] == mod.ROUTE_CHATGPT_PRO
    assert trace["reason"] == "matched_research_keywords_negated"
    assert trace["flags"]["has_research"] is False
    assert trace["flags"]["has_research_negation"] is True
    assert "调研" in trace["matched_keywords"]["research"]
    assert "zh_no_online_research" in trace["matched_keywords"]["research_negation"]


def test_answer_contract_parses_structured_markdown() -> None:
    mod = _load_module()
    raw = """
结论:
- 建议先修复会话幂等。
证据:
- 近24h出现重复提交。
不确定:
- 线上负载峰值未知。
下一步:
- 增加幂等监控。
来源:
- https://example.com/report
""".strip()
    contract = mod.answer_contract(raw)
    assert "建议先修复" in contract["conclusion"]
    assert any("重复提交" in item for item in contract["evidence"])
    assert any("负载峰值" in item for item in contract["uncertainty"])
    assert any("幂等监控" in item for item in contract["next_steps"])
    assert contract["source_refs"] == ["https://example.com/report"]


def test_answer_contract_fallback_from_plain_text() -> None:
    mod = _load_module()
    raw = "建议先验证幂等键。因为日志显示 12% 请求重试。可能存在隐藏竞态。"
    contract = mod.answer_contract(raw)
    assert contract["conclusion"]
    assert isinstance(contract["evidence"], list)
    assert isinstance(contract["uncertainty"], list)
    assert isinstance(contract["next_steps"], list)
    assert isinstance(contract["source_refs"], list)


def test_answer_contract_handles_numbered_bold_heading_and_strips_url_punctuation() -> None:
    mod = _load_module()
    raw = """
**1. 结论**:
- 可上线。
**2. 来源**:
- https://example.com/doc.
""".strip()
    contract = mod.answer_contract(raw)
    assert "可上线" in contract["conclusion"]
    assert contract["source_refs"] == ["https://example.com/doc"]


def test_answer_contract_ignores_fake_heading_inside_code_fence() -> None:
    mod = _load_module()
    raw = """
```markdown
## 结论
这是假结论
```
## 结论
- 这是真结论
## 来源
- https://example.com/real
""".strip()
    contract = mod.answer_contract(raw)
    assert "这是真结论" in contract["conclusion"]
    assert "这是假结论" not in contract["conclusion"]
    assert contract["source_refs"] == ["https://example.com/real"]


def test_answer_contract_supports_synonym_markdown_headings() -> None:
    mod = _load_module()
    raw = """
### 总结
- 可灰度发布
### 建议步骤
- 先加监控
### References
- https://example.com/a
""".strip()
    contract = mod.answer_contract(raw)
    assert "可灰度发布" in contract["conclusion"]
    assert any("先加监控" in item for item in contract["next_steps"])
    assert contract["source_refs"] == ["https://example.com/a"]


class _FakeV0Agent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def ask(self, *, question: str, force: bool = False) -> dict[str, object]:
        self.calls.append({"question": question, "force": force})
        return {
            "ok": True,
            "status": "completed",
            "job_id": "job-123",
            "conversation_url": "https://chatgpt.com/c/demo",
            "answer": "结论: 可执行\n证据: 日志已验证\n下一步: 上线灰度",
        }


class _FakeState:
    def __init__(self, conversation_url: str = "") -> None:
        self.conversation_url = conversation_url


class _SelfHealV0Agent:
    def __init__(self, first_error: str, conversation_url: str = "") -> None:
        self.first_error = first_error
        self.calls: list[dict[str, object]] = []
        self.state = _FakeState(conversation_url=conversation_url)

    def _save_state(self) -> None:
        return None

    def get_status(self) -> dict[str, str]:
        return {"conversation_url": self.state.conversation_url}

    def ask(self, *, question: str, force: bool = False) -> dict[str, object]:
        self.calls.append({"question": question, "force": force})
        if len(self.calls) == 1:
            return {"ok": False, "status": "error", "error": self.first_error}
        return {
            "ok": True,
            "status": "completed",
            "job_id": "job-self-heal",
            "conversation_url": self.state.conversation_url or "https://chatgpt.com/c/recovered",
            "answer": "结论: 自修复后成功",
        }


class _ForcePassV0Agent:
    def __init__(self) -> None:
        self.calls = 0

    def ask(self, *, question: str, force: bool = False) -> dict[str, object]:
        self.calls += 1
        return {"ok": True, "status": "completed", "job_id": "job-force", "answer": question}


class _DictStateSelfHealV0Agent:
    def __init__(self) -> None:
        self.state: dict[str, str] = {}
        self.calls = 0

    def get_status(self) -> dict[str, str]:
        return {"conversation_url": "https://gemini.google.com/app/recovered"}

    def _save_state(self) -> None:
        return None

    def ask(self, *, question: str, force: bool = False) -> dict[str, object]:
        self.calls += 1
        if self.calls == 1:
            return {"ok": False, "status": "error", "error": "requires input.conversation_url"}
        return {
            "ok": True,
            "status": "completed",
            "job_id": "job-dict-state",
            "conversation_url": self.state.get("conversation_url") or "",
            "answer": "结论: recovered",
        }


class _NoneStateSelfHealV0Agent:
    def __init__(self) -> None:
        self.state = None
        self.calls = 0

    def get_status(self) -> dict[str, str]:
        return {}

    def ask(self, *, question: str, force: bool = False) -> dict[str, object]:
        self.calls += 1
        return {"ok": False, "status": "error", "error": "requires input.conversation_url"}


class _NoChangeStateV0Agent:
    def __init__(self) -> None:
        self.state = {"conversation_url": "https://gemini.google.com/app/same"}
        self.save_calls = 0

    def get_status(self) -> dict[str, str]:
        return {"conversation_url": "https://gemini.google.com/app/same"}

    def _save_state(self) -> None:
        self.save_calls += 1

    def ask(self, *, question: str, force: bool = False) -> dict[str, object]:
        return {"ok": False, "status": "error", "error": "requires input.conversation_url"}


def test_wrapper_v1_compat_executes_v0_agent() -> None:
    mod = _load_module()
    wrapper = mod.ChatGPTWrapperV1(_FakeV0Agent())
    ctx = {
        "project": "chatgptrest",
        "goal": "设计路由策略",
        "constraints": "最小侵入",
        "environment": "python",
        "acceptance": "有测试",
    }
    out = wrapper.advise(raw_question="请给出渠道策略", context=ctx, execute=True)
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert out["job_id"] == "job-123"
    assert out["conversation_url"].startswith("https://")
    assert out["answer_contract"]["conclusion"]


def test_wrapper_v1_returns_needs_context_without_execution() -> None:
    mod = _load_module()
    fake = _FakeV0Agent()
    wrapper = mod.ChatGPTWrapperV1(fake)
    out = wrapper.advise(raw_question="这个事情尽快处理", context={}, execute=True)
    assert out["ok"] is False
    assert out["status"] == "needs_context"
    assert len(out["followups"]) > 0
    assert fake.calls == []


def test_wrapper_v1_force_bypasses_gap_check_and_executes() -> None:
    mod = _load_module()
    fake = _ForcePassV0Agent()
    wrapper = mod.ChatGPTWrapperV1(fake)
    out = wrapper.advise(raw_question="这个事情尽快处理", context={}, execute=True, force=True)
    assert out["ok"] is True
    assert out["status"] == "completed"
    assert fake.calls == 1
    assert "assumptions" in out
    assert "已识别待确认信息" in str(out["v0_result"]["answer"])


def test_wrapper_v1_from_v0_compat_constructor(tmp_path: Path) -> None:
    mod = _load_module()
    wrapper = mod.ChatGPTWrapperV1.from_v0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="wrapper-v1-compat",
        dry_run=True,
    )
    out = wrapper.advise(
        raw_question="给出升级建议",
        context={
            "project": "chatgptrest",
            "goal": "升级wrapper",
            "constraints": "最小侵入",
            "environment": "python3.11",
            "acceptance": "pytest",
        },
        execute=False,
    )
    assert out["ok"] is True
    assert out["status"] == "planned"


def test_load_v0_class_is_idempotent() -> None:
    mod = _load_module()
    cls1 = mod._load_v0_class()
    cls2 = mod._load_v0_class()
    assert cls1 is cls2


def test_load_v0_class_recovers_from_partial_cached_module(monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.setitem(sys.modules, "chatgpt_agent_shell_v0", types.SimpleNamespace())
    cls = mod._load_v0_class()
    assert cls.__name__ == "ChatGPTAgentV0"


def test_wrapper_v1_self_heal_retries_for_missing_idempotency_key() -> None:
    mod = _load_module()
    wrapper = mod.ChatGPTWrapperV1(_SelfHealV0Agent("missing header Idempotency-Key"))
    out = wrapper.advise(
        raw_question="制定修复方案",
        context={
            "project": "chatgptrest",
            "goal": "防止重复提交",
            "constraints": "最小侵入",
            "environment": "python3.11",
            "acceptance": "单测通过",
        },
        execute=True,
    )
    assert out["ok"] is True
    assert "self_heal_actions" in out
    assert "retry_with_fresh_request_context" in out["self_heal_actions"]


def test_wrapper_v1_self_heal_recovers_conversation_url() -> None:
    mod = _load_module()
    fake = _SelfHealV0Agent(
        "gemini_web.ask params.phase=wait requires input.conversation_url",
        conversation_url="https://gemini.google.com/app/abc123xyz",
    )
    wrapper = mod.ChatGPTWrapperV1(fake)
    out = wrapper.advise(
        raw_question="继续等待并汇总结果",
        context={
            "project": "chatgptrest",
            "goal": "等待完成",
            "constraints": "不重发问题",
            "environment": "python3.11",
            "acceptance": "拿到最终结论",
        },
        execute=True,
    )
    assert out["ok"] is True
    assert "recover_conversation_url_from_session" in out.get("self_heal_actions", [])
    assert out["conversation_url"] == "https://gemini.google.com/app/abc123xyz"


def test_wrapper_v1_self_heal_supports_dict_state() -> None:
    mod = _load_module()
    fake = _DictStateSelfHealV0Agent()
    wrapper = mod.ChatGPTWrapperV1(fake)
    out = wrapper.advise(
        raw_question="继续等待并汇总结果",
        context={
            "project": "chatgptrest",
            "goal": "等待完成",
            "constraints": "不重发问题",
            "environment": "python3.11",
            "acceptance": "拿到最终结论",
        },
        execute=True,
    )
    assert out["ok"] is True
    assert "recover_conversation_url_from_session" in out.get("self_heal_actions", [])
    assert fake.state.get("conversation_url") == "https://gemini.google.com/app/recovered"


def test_wrapper_v1_self_heal_none_state_does_not_false_positive_retry() -> None:
    mod = _load_module()
    fake = _NoneStateSelfHealV0Agent()
    wrapper = mod.ChatGPTWrapperV1(fake)
    out = wrapper.advise(
        raw_question="继续等待并汇总结果",
        context={
            "project": "chatgptrest",
            "goal": "等待完成",
            "constraints": "不重发问题",
            "environment": "python3.11",
            "acceptance": "拿到最终结论",
        },
        execute=True,
    )
    assert out["ok"] is False
    assert out["status"] == "error"
    assert "self_heal_actions" not in out
    assert fake.calls == 1


def test_wrapper_v1_self_heal_does_not_save_when_conversation_url_unchanged() -> None:
    mod = _load_module()
    fake = _NoChangeStateV0Agent()
    wrapper = mod.ChatGPTWrapperV1(fake)
    out = wrapper.advise(
        raw_question="继续等待并汇总结果",
        context={
            "project": "chatgptrest",
            "goal": "等待完成",
            "constraints": "不重发问题",
            "environment": "python3.11",
            "acceptance": "拿到最终结论",
        },
        execute=True,
    )
    assert out["ok"] is False
    assert out["status"] == "error"
    assert fake.save_calls == 0


def test_wrapper_v1_main_passes_client_repair_args_to_v0(tmp_path: Path) -> None:
    mod = _load_module()
    seen: dict[str, object] = {}

    class _DummyV0:
        def __init__(self, **kwargs):  # noqa: ANN003
            seen.update(kwargs)

    mod._load_v0_class = lambda: _DummyV0  # type: ignore[method-assign]

    rc = mod.main(
        [
            "--question",
            "请给出策略",
            "--context-json",
            '{"project":"p","goal":"g","constraints":"c","environment":"e","acceptance":"a"}',
            "--state-root",
            str(tmp_path),
            "--client-name",
            "advisor-shell",
            "--request-id-prefix",
            "advisor req @@@",
            "--no-auto-client-name-repair",
            "--client-name-repair-allowlist",
            "chatgptrest-mcp,chatgpt_wrapper_v1",
            "--persist-client-name-repair",
        ]
    )
    assert rc == 0
    assert seen["client_name"] == "advisor-shell"
    assert seen["request_id_prefix"] == "advisor req @@@"
    assert seen["auto_client_name_repair"] is False
    assert seen["client_name_repair_allowlist"] == ["chatgptrest-mcp", "chatgpt_wrapper_v1"]
    assert seen["persist_client_name_repair"] is True


def test_wrapper_v1_main_rejects_conflicting_auto_repair_flags(tmp_path: Path) -> None:
    mod = _load_module()
    rc = mod.main(
        [
            "--question",
            "请给出策略",
            "--context-json",
            '{"project":"p","goal":"g","constraints":"c","environment":"e","acceptance":"a"}',
            "--state-root",
            str(tmp_path),
            "--auto-client-name-repair",
            "--no-auto-client-name-repair",
        ]
    )
    assert rc == 2
