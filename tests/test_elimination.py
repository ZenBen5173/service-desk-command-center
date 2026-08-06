"""
Tests for the Elimination Backlog extractor.

The Operators that feed this run on Supervity Auto and emit JSON whose exact key
names vary between rebuilds, so these tests pin the behaviour that matters:
parse what the agent actually sends, never invent a value, and rank in a way
that can be defended.
"""

import json

from app.services import elimination


def _activity(payload) -> dict:
    """Mimic Auto's envelope: the real result is a JSON string under `output`."""
    return {"displayData": {}, "output": json.dumps(payload), "error": ""}


class TestParseOutput:
    def test_unwraps_json_string_under_output(self):
        parsed = elimination._parse_output(_activity({"clusters": []}))
        assert parsed == {"clusters": []}

    def test_handles_plain_dict_payload(self):
        parsed = elimination._parse_output({"output": {"clusters": []}})
        assert parsed == {"clusters": []}

    def test_returns_none_for_non_json_step_output(self):
        # Condition steps print Python's `True`, which is not valid JSON, and
        # some steps emit free text. Neither carries class findings, and neither
        # should raise — they just yield nothing to extract.
        assert elimination._parse_output({"output": "True"}) is None
        assert elimination._parse_output({"output": "not json at all"}) is None
        assert elimination._parse_output(None) is None

    def test_reads_json_booleans(self):
        assert elimination._parse_output({"output": "true"}) is True


class TestFindCollections:
    def test_finds_clusters_nested_several_levels_deep(self):
        payload = {"result": {"data": {"clusters": [{"volume": 3}]}}}
        found = elimination._find_class_collections(payload)
        assert len(found) == 1
        assert found[0][0] == "clusters"

    def test_ignores_lists_of_non_objects(self):
        payload = {"clusters": ["ITSM-1", "ITSM-2"]}
        assert elimination._find_class_collections(payload) == []

    def test_accepts_alternative_collection_names(self):
        for name in ("classes", "ticket_classes", "backlog", "groups"):
            found = elimination._find_class_collections({name: [{"volume": 2}]})
            assert len(found) == 1, name


class TestNormalise:
    SOURCE = {"auto_run_id": "run-1", "workflow_name": "wf", "step_name": "step"}

    def test_maps_alias_field_names(self):
        raw = {
            "cluster_key": "printer-offline",
            "symptom": "Printer offline",
            "member_count": 43,
            "breach_count": 11,
            "distinct_reporter_count": 30,
            "classification": "major incident",
        }
        entry = elimination._normalise_class(raw, self.SOURCE)
        assert entry["key"] == "printer-offline"
        assert entry["volume"] == 43
        assert entry["breaches"] == 11
        assert entry["distinct_reporters"] == 30
        # Normalised to the canonical uppercase form used for branching.
        assert entry["classification"] == "MAJOR_INCIDENT"

    def test_derives_volume_from_member_list_when_absent(self):
        raw = {"key": "k", "members": ["A-1", "A-2", "A-3"]}
        entry = elimination._normalise_class(raw, self.SOURCE)
        assert entry["volume"] == 3

    def test_drops_class_that_cannot_be_sized(self):
        # A class with no volume cannot be ranked. Omitting it is correct;
        # inventing a size would put a fabricated number in front of a judge.
        assert elimination._normalise_class({"label": "mystery"}, self.SOURCE) is None

    def test_missing_fields_stay_none_rather_than_zero(self):
        entry = elimination._normalise_class({"key": "k", "volume": 5}, self.SOURCE)
        assert entry["breaches"] is None
        assert entry["avg_csat"] is None
        assert entry["deflection_forecast"] is None
        assert entry["has_kb_article"] is None

    def test_flags_classes_needing_human_approval(self):
        for classification in ("MAJOR_INCIDENT", "REPEAT_FAILURE", "KNOWLEDGE_GAP"):
            entry = elimination._normalise_class(
                {"key": "k", "volume": 5, "classification": classification}, self.SOURCE
            )
            assert entry["needs_approval"] is True

        below = elimination._normalise_class(
            {"key": "k", "volume": 5, "classification": "BELOW_THRESHOLD"}, self.SOURCE
        )
        assert below["needs_approval"] is False


class TestScoring:
    def _entry(self, **overrides):
        base = {
            "volume": 10,
            "breaches": None,
            "poor_csat_count": None,
            "avg_csat": None,
            "handling_hours": None,
        }
        base.update(overrides)
        return base

    def test_breaches_and_poor_csat_both_raise_the_score(self):
        plain = elimination._score(self._entry())
        breached = elimination._score(self._entry(breaches=10))
        unhappy = elimination._score(self._entry(poor_csat_count=10))

        assert breached["impact_score"] > plain["impact_score"]
        assert unhappy["impact_score"] > plain["impact_score"]

    def test_volume_alone_still_ranks(self):
        small = elimination._score(self._entry(volume=5))
        large = elimination._score(self._entry(volume=50))
        assert large["impact_score"] > small["impact_score"]

    def test_missing_inputs_are_reported_not_assumed(self):
        result = elimination._score(self._entry())
        assert set(result["missing_inputs"]) == {"breaches", "csat", "handling_hours"}

    def test_low_average_csat_counts_as_damage_when_no_poor_count(self):
        good = elimination._score(self._entry(avg_csat=5.0))
        bad = elimination._score(self._entry(avg_csat=2.7))
        assert bad["impact_score"] > good["impact_score"]
        assert "csat" not in bad["missing_inputs"]

    def test_breach_rate_cannot_exceed_one(self):
        # Guards against an Operator reporting more breaches than tickets.
        result = elimination._score(self._entry(volume=5, breaches=50))
        assert result["components"]["breach_rate"] == 1.0


class TestBuildBacklog:
    class _FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def join(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return self._rows

    class _FakeSession:
        """Returns activity/run rows for the join, and nothing for other models.

        build_backlog also looks up AgentWorkflow to resolve names Auto omitted,
        so the fake has to tell the two queries apart.
        """

        def __init__(self, rows, workflows=None):
            self._rows = rows
            self._workflows = workflows or []

        def query(self, *args, **kwargs):
            first = args[0] if args else None
            name = getattr(first, "__name__", "")
            if name == "AgentWorkflow":
                return TestBuildBacklog._FakeQuery(self._workflows)
            return TestBuildBacklog._FakeQuery(self._rows)

    class _Activity:
        def __init__(self, outputs, step_name="step", artifact_data=None):
            self.outputs = outputs
            self.step_name = step_name
            # Larger reports arrive as a downloaded JSON file rather than inline.
            self.artifact_data = artifact_data

    class _Run:
        def __init__(self, run_id, name="Major-Incident Correlator Operator"):
            self.auto_run_id = run_id
            self.workflow_name = name
            self.auto_workflow_id = f"wf-{name}"
            self.auto_created_at = None

    def test_reports_no_data_state_with_guidance(self):
        result = elimination.build_backlog(self._FakeSession([]))
        assert result["has_data"] is False
        assert result["classes"] == []
        assert result["warnings"], "an empty backlog must explain itself"

    def test_ranks_classes_by_damage(self):
        payload = {
            "clusters": [
                {"cluster_key": "low", "member_count": 5},
                {"cluster_key": "high", "member_count": 40, "breach_count": 20},
                {"cluster_key": "mid", "member_count": 20},
            ]
        }
        rows = [(self._Activity(_activity(payload)), self._Run("run-1"))]
        result = elimination.build_backlog(self._FakeSession(rows))

        assert result["has_data"] is True
        assert [c["key"] for c in result["classes"]] == ["high", "mid", "low"]
        assert result["totals"]["tickets_in_classes"] == 65

    def test_deflection_only_counts_what_an_operator_forecast(self):
        payload = {
            "clusters": [
                {"cluster_key": "a", "member_count": 20, "deflection_forecast": 18},
                # No forecast: the agent did not commit to preventing these, so
                # neither do we.
                {"cluster_key": "b", "member_count": 30},
            ]
        }
        rows = [(self._Activity(_activity(payload)), self._Run("run-1"))]
        result = elimination.build_backlog(self._FakeSession(rows))

        assert result["totals"]["deflection_forecast"] == 18
        assert result["totals"]["classes_with_forecast"] == 1
        assert result["totals"]["tickets_in_classes"] == 50

    def test_warns_when_classes_exist_but_nothing_is_forecast(self):
        payload = {"clusters": [{"cluster_key": "a", "member_count": 20}]}
        rows = [(self._Activity(_activity(payload)), self._Run("run-1"))]
        result = elimination.build_backlog(self._FakeSession(rows))
        assert any("deflection forecast" in w for w in result["warnings"])

    def test_newest_run_of_a_workflow_supersedes_the_earlier_one(self):
        # Re-running an Operator after a prompt change renames its clusters, so
        # keeping both runs would count the same tickets twice under different
        # labels. Rows arrive newest-first; only the newest run contributes.
        newest = {"clusters": [{"cluster_key": "renamed", "member_count": 40}]}
        older = {"clusters": [{"cluster_key": "original", "member_count": 5}]}
        rows = [
            (self._Activity(_activity(newest)), self._Run("run-new")),
            (self._Activity(_activity(older)), self._Run("run-old")),
        ]
        result = elimination.build_backlog(self._FakeSession(rows))

        assert result["totals"]["classes"] == 1
        assert result["classes"][0]["volume"] == 40
        assert result["superseded_runs"] == ["run-old"]

    def test_only_one_source_is_counted_the_rest_are_reported(self):
        # Operators describe the same tickets from different angles. Summing
        # them counted tickets twice and produced a backlog larger than the
        # dataset, so the widest-coverage set wins and the rest are listed.
        correlator = {"clusters": [{"cluster_key": "a", "member_count": 10}]}
        csat = {"classes": [{"class_key": "b", "ticket_count": 4}]}
        rows = [
            (self._Activity(_activity(correlator)), self._Run("run-1", "Correlator")),
            (self._Activity(_activity(csat)), self._Run("run-2", "CSAT Loop")),
        ]
        result = elimination.build_backlog(self._FakeSession(rows))

        assert result["totals"]["classes"] == 1
        assert result["totals"]["tickets_in_classes"] == 10
        assert len(result["other_sources"]) == 1
        assert result["other_sources"][0]["workflow_name"] == "CSAT Loop"

    def test_a_set_that_proposes_fixes_wins_an_equal_coverage_tie(self):
        # The panel exists to answer "what would make this stop happening", so
        # naming the fix beats merely sizing the problem.
        sized = {"clusters": [{"cluster_key": "a", "member_count": 10}]}
        actionable = {
            "classes": [
                {
                    "class_key": "b",
                    "ticket_count": 10,
                    "proposed_fix": "Deploy self-service password reset",
                }
            ]
        }
        rows = [
            (self._Activity(_activity(sized)), self._Run("run-1", "Sizer")),
            (self._Activity(_activity(actionable)), self._Run("run-2", "Fixer")),
        ]
        result = elimination.build_backlog(self._FakeSession(rows))
        assert result["classes"][0]["key"] == "b"
        assert result["classes"][0]["proposed_fix"]

    def test_reads_a_report_delivered_as_a_downloaded_artifact(self):
        # Auto writes larger reports to a file and leaves only a link inline.
        report = {"clusters": [{"cluster_key": "from-file", "member_count": 12}]}
        rows = [
            (
                self._Activity(
                    {"output": "The public URL of the uploaded file is: ..."},
                    artifact_data={"report.json": report},
                ),
                self._Run("run-1"),
            )
        ]
        result = elimination.build_backlog(self._FakeSession(rows))
        assert result["totals"]["classes"] == 1
        assert result["classes"][0]["key"] == "from-file"

    def test_tracks_which_runs_the_backlog_came_from(self):
        payload = {"clusters": [{"cluster_key": "a", "member_count": 9}]}
        rows = [(self._Activity(_activity(payload)), self._Run("run-42"))]
        result = elimination.build_backlog(self._FakeSession(rows))
        assert result["generated_from_runs"] == ["run-42"]
