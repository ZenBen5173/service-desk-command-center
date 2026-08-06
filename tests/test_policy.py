"""
Tests for the policy engine.

Two things must hold for the hackathon requirement, and both are pinned here:
an edit must reach the agent as a workflow input, and every evaluation the
agent reports must be logged without anything being invented locally.
"""

import json

from app.routers.policies import _coerce_parameter
from app.services import policy as policy_service


def _activity(payload) -> dict:
    """Auto's envelope: the real result is a JSON string under `output`."""
    return {"displayData": {}, "output": json.dumps(payload), "error": ""}


class TestBuiltinPolicies:
    def test_ships_at_least_the_three_required_policies(self):
        keys = {p["key"] for p in policy_service.BUILTIN_POLICIES}
        assert {"auto_remediation_gate", "sla_vip_priority", "change_control"} <= keys

    def test_every_parameter_declares_a_default_and_a_type(self):
        for spec in policy_service.BUILTIN_POLICIES:
            for param in spec["parameters"]:
                assert "default" in param, f"{spec['key']}.{param['name']}"
                assert param.get("type") in ("number", "boolean", "string")

    def test_every_parameter_maps_to_an_auto_workflow_input(self):
        # Without this link an edit changes nothing on the agent side, which is
        # the whole point of the requirement.
        for spec in policy_service.BUILTIN_POLICIES:
            for param in spec["parameters"]:
                assert param.get("maps_to_input"), f"{spec['key']}.{param['name']}"

    def test_no_dataset_values_are_baked_into_policies(self):
        # Policies must survive the judged dataset unchanged, so nothing
        # dataset-specific may appear in their text.
        blob = json.dumps(policy_service.BUILTIN_POLICIES).lower()
        for forbidden in ("itsm-", "inc-", "chg-", "kb-"):
            assert forbidden not in blob, f"{forbidden} leaked into a policy"


class TestCoerceParameter:
    def test_number_within_range_is_accepted(self):
        param = {"type": "number", "min": 0, "max": 1, "step": 0.01}
        value, error = _coerce_parameter(param, "0.95")
        assert value == 0.95
        assert error is None

    def test_number_out_of_range_is_rejected_not_clamped(self):
        # Clamping would silently apply a value the operator did not choose.
        param = {"type": "number", "min": 0, "max": 1, "step": 0.01}
        value, error = _coerce_parameter(param, 5)
        assert value is None
        assert "at most 1" in error

    def test_integer_parameters_stay_integers(self):
        param = {"type": "number", "min": 2, "max": 100, "step": 1}
        value, error = _coerce_parameter(param, "5")
        assert value == 5 and isinstance(value, int)
        assert error is None

    def test_boolean_accepts_real_and_stringified_booleans(self):
        param = {"type": "boolean"}
        assert _coerce_parameter(param, True) == (True, None)
        assert _coerce_parameter(param, "false") == (False, None)

    def test_non_numeric_input_is_rejected(self):
        value, error = _coerce_parameter({"type": "number"}, "high")
        assert value is None
        assert error == "expected a number"


class TestOutcomeNormalisation:
    def test_maps_agent_vocabulary_onto_canonical_outcomes(self):
        assert policy_service._normalise_outcome(True) == "pass"
        assert policy_service._normalise_outcome("ALLOW") == "pass"
        assert policy_service._normalise_outcome("denied") == "fail"
        assert policy_service._normalise_outcome("BLOCKED_PENDING_CAB") == "block"
        assert policy_service._normalise_outcome("HUMAN_REVIEW") == "escalate"

    def test_unknown_outcome_is_preserved_not_discarded(self):
        assert policy_service._normalise_outcome("weird_state") == "weird_state"

    def test_missing_outcome_stays_missing(self):
        assert policy_service._normalise_outcome(None) is None


class TestEvaluationExtraction:
    def test_finds_evaluations_nested_in_agent_output(self):
        payload = {"result": {"policy_evaluations": [{"policy_key": "x"}]}}
        found = policy_service._find_eval_collections(payload)
        assert len(found) == 1

    def test_accepts_alternative_collection_names(self):
        for name in ("policy_checks", "verdicts", "evaluations"):
            found = policy_service._find_eval_collections({name: [{"policy": "p"}]})
            assert len(found) == 1, name

    def test_parses_the_json_string_envelope(self):
        parsed = policy_service._parse_output(_activity({"policy_evaluations": []}))
        assert parsed == {"policy_evaluations": []}

    def test_ignores_steps_that_carry_no_json(self):
        assert policy_service._parse_output({"output": "True"}) is None


class TestEffectiveInputs:
    class _Query:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class _Session:
        def __init__(self, rows):
            self._rows = rows

        def query(self, *a, **k):
            return TestEffectiveInputs._Query(self._rows)

    class _Policy:
        def __init__(self, key, parameters, priority=100):
            self.key = key
            self.parameters = parameters
            self.priority = priority
            self.enabled = True

    def test_keys_values_by_the_workflow_input_they_feed(self):
        rows = [
            self._Policy(
                "gate",
                [{"name": "conf", "value": 0.95, "maps_to_input": "min_auto_confidence"}],
            )
        ]
        result = policy_service.effective_inputs(self._Session(rows))
        assert result["inputs"]["min_auto_confidence"] == 0.95
        assert result["provenance"]["min_auto_confidence"] == "gate"

    def test_parameters_without_a_mapping_are_omitted(self):
        rows = [self._Policy("p", [{"name": "note", "value": "hello"}])]
        result = policy_service.effective_inputs(self._Session(rows))
        assert result["inputs"] == {}

    def test_first_policy_wins_a_colliding_input(self):
        # Rows arrive ordered by priority, so the higher-precedence policy is
        # seen first and keeps the input.
        rows = [
            self._Policy("first", [{"name": "a", "value": 1, "maps_to_input": "shared"}]),
            self._Policy("second", [{"name": "b", "value": 2, "maps_to_input": "shared"}]),
        ]
        result = policy_service.effective_inputs(self._Session(rows))
        assert result["inputs"]["shared"] == 1
        assert result["provenance"]["shared"] == "first"
