"""Unit tests for the Workflow Engine state models.

Tests pure merge functions and WorkflowState node tracking logic.
"""

import importlib.util
import os
import sys

import pytest

# Load the state module from src/workflow-engine/models/state.py
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/workflow-engine")
sys.path.insert(0, _service_dir)
_spec = importlib.util.spec_from_file_location(
    "workflow_state",
    os.path.join(_service_dir, "models", "state.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["workflow_state"] = _mod
_spec.loader.exec_module(_mod)

merge_messages = _mod.merge_messages
merge_dicts = _mod.merge_dicts
last_value = _mod.last_value
WorkflowState = _mod.WorkflowState
NodeState = _mod.NodeState


# ============================================================================
# merge_messages
# ============================================================================


class TestMergeMessages:
    def test_both_non_empty(self):
        """Should concatenate two non-empty lists."""
        left = [{"role": "user", "content": "a"}]
        right = [{"role": "assistant", "content": "b"}]
        result = merge_messages(left, right)
        assert result == [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]

    def test_left_empty(self):
        """Should return right when left is empty."""
        right = [{"role": "user", "content": "hello"}]
        result = merge_messages([], right)
        assert result == right

    def test_right_empty(self):
        """Should return left when right is empty."""
        left = [{"role": "user", "content": "hello"}]
        result = merge_messages(left, [])
        assert result == left

    def test_both_empty(self):
        """Should return empty list when both are empty."""
        result = merge_messages([], [])
        assert result == []

    def test_left_none(self):
        """Should return right or empty list when left is None."""
        result = merge_messages(None, [{"role": "user", "content": "x"}])
        assert result == [{"role": "user", "content": "x"}]

    def test_both_none(self):
        """Should return empty list when both are None."""
        result = merge_messages(None, None)
        assert result == []


# ============================================================================
# merge_dicts
# ============================================================================


class TestMergeDicts:
    def test_both_non_empty(self):
        """Should merge dicts with right taking precedence."""
        left = {"a": 1, "b": 2}
        right = {"b": 3, "c": 4}
        result = merge_dicts(left, right)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_left_empty(self):
        """Should return right when left is empty."""
        result = merge_dicts({}, {"key": "value"})
        assert result == {"key": "value"}

    def test_right_empty(self):
        """Should return left when right is empty."""
        result = merge_dicts({"key": "value"}, {})
        assert result == {"key": "value"}

    def test_left_none(self):
        """Should return right when left is None."""
        result = merge_dicts(None, {"x": 1})
        assert result == {"x": 1}

    def test_both_none(self):
        """Should return empty dict when both are None."""
        result = merge_dicts(None, None)
        assert result == {}


# ============================================================================
# last_value
# ============================================================================


class TestLastValue:
    def test_both_non_none(self):
        """Should return right when both are non-None."""
        assert last_value("old", "new") == "new"

    def test_right_none(self):
        """Should return left when right is None."""
        assert last_value("old", None) == "old"

    def test_left_none_right_non_none(self):
        """Should return right when left is None and right is not."""
        assert last_value(None, "new") == "new"


# ============================================================================
# WorkflowState.update_node_state
# ============================================================================


class TestUpdateNodeState:
    def test_creates_new_node_state(self):
        """Should create a NodeState entry for a new node."""
        state = WorkflowState()
        state.update_node_state("research", "running")
        assert "research" in state.node_states
        assert isinstance(state.node_states["research"], NodeState)
        assert state.node_states["research"].status == "running"
        assert state.node_states["research"].started_at is not None

    def test_updates_status(self):
        """Should update status on an existing node."""
        state = WorkflowState()
        state.update_node_state("research", "running")
        state.update_node_state("research", "completed")
        assert state.node_states["research"].status == "completed"

    def test_adds_tokens_to_totals(self):
        """Should accumulate tokens in both node and workflow totals."""
        state = WorkflowState()
        state.update_node_state("llm_call", "running", tokens=100, cost=0.01)
        state.update_node_state("llm_call", "completed", tokens=200, cost=0.02)
        assert state.node_states["llm_call"].tokens_used == 300
        assert state.node_states["llm_call"].cost == pytest.approx(0.03)
        assert state.total_tokens == 300
        assert state.total_cost == pytest.approx(0.03)

    def test_sets_completed_at_on_completion(self):
        """Should set completed_at when status is completed."""
        state = WorkflowState()
        state.update_node_state("step1", "running")
        assert state.node_states["step1"].completed_at is None
        state.update_node_state("step1", "completed")
        assert state.node_states["step1"].completed_at is not None

    def test_sets_completed_at_on_failure(self):
        """Should set completed_at when status is failed."""
        state = WorkflowState()
        state.update_node_state("step1", "running")
        state.update_node_state("step1", "failed", error="timeout")
        assert state.node_states["step1"].completed_at is not None
        assert state.node_states["step1"].error == "timeout"

    def test_preserves_other_nodes(self):
        """Should not affect unrelated nodes when updating one."""
        state = WorkflowState()
        state.update_node_state("node_a", "completed", tokens=50)
        state.update_node_state("node_b", "running", tokens=10)
        assert state.node_states["node_a"].status == "completed"
        assert state.node_states["node_a"].tokens_used == 50
        assert state.node_states["node_b"].status == "running"

    def test_sets_output(self):
        """Should store output dict on the node."""
        state = WorkflowState()
        state.update_node_state("step1", "completed", output={"result": "ok"})
        assert state.node_states["step1"].output == {"result": "ok"}

    def test_returns_self(self):
        """Should return the WorkflowState instance for chaining."""
        state = WorkflowState()
        result = state.update_node_state("step1", "running")
        assert result is state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
