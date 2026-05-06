"""Tests for team lifecycle events (signals.py + cc_native.py emission)."""

import pytest
from chatgptrest.evomap.signals import Signal, SignalType, SignalDomain


class TestTeamSignalTypes:
    """Verify team signal type constants are registered."""

    def test_team_run_created(self):
        assert SignalType.TEAM_RUN_CREATED == "team.run.created"

    def test_team_run_completed(self):
        assert SignalType.TEAM_RUN_COMPLETED == "team.run.completed"

    def test_team_run_failed(self):
        assert SignalType.TEAM_RUN_FAILED == "team.run.failed"

    def test_team_role_completed(self):
        assert SignalType.TEAM_ROLE_COMPLETED == "team.role.completed"

    def test_team_role_failed(self):
        assert SignalType.TEAM_ROLE_FAILED == "team.role.failed"

    def test_team_output_accepted(self):
        assert SignalType.TEAM_OUTPUT_ACCEPTED == "team.output.accepted"

    def test_team_output_rejected(self):
        assert SignalType.TEAM_OUTPUT_REJECTED == "team.output.rejected"

    def test_team_domain(self):
        assert SignalDomain.TEAM == "team"


class TestTeamSignalDomainMapping:
    """Verify Signal.from_trace_event maps team.* → domain 'team'."""

    def test_team_event_domain(self):
        class FakeEvent:
            event_id = "evt_1"
            trace_id = "tr_1"
            event_type = "team.run.created"
            source = "cc_native"
            timestamp = "2026-01-01T00:00:00"
            data = {"team_id": "abc"}

        sig = Signal.from_trace_event(FakeEvent())
        assert sig.domain == "team"
        assert sig.signal_type == "team.run.created"
        assert sig.data["team_id"] == "abc"

    def test_team_role_domain(self):
        class FakeEvent:
            event_id = "evt_2"
            trace_id = "tr_2"
            event_type = "team.role.completed"
            source = "cc_native"
            timestamp = "2026-01-01T00:00:00"
            data = {}

        sig = Signal.from_trace_event(FakeEvent())
        assert sig.domain == "team"
