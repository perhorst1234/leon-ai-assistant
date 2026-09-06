"""Focused scheduler/brief regressions; does not replace missing store/HTTP tests."""

import unittest
from unittest.mock import Mock, patch

from leon_control_plane.night_queue import NightQueueScheduler, build_night_queue_actions
from leon_control_plane.risk_policy import evaluate_action_policy


ACTION_ID = "apply_controlled_self_improvement"


class NightQueueEvidenceTests(unittest.TestCase):
    def setUp(self):
        # Persistence is the sole test double: real policy, router and brief code run.
        self.store = Mock(spec=[
            "start_night_queue_run", "get_state", "retrieve_memory",
            "complete_night_queue_run", "record_controlled_self_improvement",
        ])
        self.store.start_night_queue_run.return_value = "night-evidence-test"
        self.store.get_state.return_value = {"tasks": [], "phases": []}
        self.store.retrieve_memory.return_value = {}
        self.scheduler = NightQueueScheduler(self.store)

    def action(self):
        return next(item for item in build_night_queue_actions() if item["id"] == ACTION_ID)

    def assert_no_improvement(self, brief):
        self.store.record_controlled_self_improvement.assert_not_called()
        completed = self.store.complete_night_queue_run.call_args.kwargs
        self.assertEqual(completed["changes"], [])
        self.assertEqual(brief["completed_improvements"], [])
        self.assertTrue(brief["partial_failure_disclosure"]["visible_to_user"])
        self.assertTrue(brief["partial_failure_disclosure"]["has_partial_failure"])
        for result in completed["action_results"]:
            if result["action_id"] == ACTION_ID:
                self.assertNotEqual(result["status"], "succeeded")
                self.assertNotIn("test_results", result)
        return completed

    def test_action_metadata_does_not_invent_evidence(self):
        action = self.action()
        self.assertFalse(action["policy_metadata"]["tests_passed"])
        self.assertFalse(action["policy_metadata"]["diff_limited"])
        policy = evaluate_action_policy(
            action_type=action["action_type"],
            requested_scope=action["requested_scope"],
            metadata=action["policy_metadata"],
        )
        self.assertEqual(policy["risk_class"], "R3")
        self.assertEqual(policy["decision"], "needs_review")
        self.assertFalse(policy["execution_allowed"])

    def test_default_queue_reports_review_not_success(self):
        brief = self.scheduler.run_once(requested_actions=[ACTION_ID])
        completed = self.assert_no_improvement(brief)
        self.assertEqual(completed["status"], "failed")
        self.assertEqual(completed["action_results"][0]["status"], "blocked_by_policy")
        self.assertEqual(len(brief["proposals"]), 1)
        self.assertFalse(brief["proposals"][0]["execution_allowed"])

    def test_allowing_r3_or_all_classes_does_not_manufacture_success(self):
        for allowed in (["R3"], ["R1", "R2", "R3", "R4", "R5"]):
            with self.subTest(allowed=allowed):
                brief = self.scheduler.run_once(
                    requested_actions=[ACTION_ID], allowed_risk_classes=allowed,
                )
                completed = self.assert_no_improvement(brief)
                result = completed["action_results"][0]
                self.assertEqual(result["status"], "blocked_by_policy")
                self.assertEqual(result["policy"]["decision"], "needs_review")
                self.assertEqual(len(brief["proposals"]), 1)

    def test_direct_execution_cannot_record_fake_patch_or_tests(self):
        with self.assertRaisesRegex(NotImplementedError, "no tests were run"):
            self.scheduler._execute_action(
                self.action(), run_id="direct", state={}, indexed_sources=[],
            )
        self.store.record_controlled_self_improvement.assert_not_called()

    def test_forged_metadata_cannot_revive_synthetic_execution(self):
        action = self.action()
        action["policy_metadata"].update(tests_passed=True, diff_limited=True)
        with patch("leon_control_plane.night_queue.build_night_queue_actions", return_value=[action]):
            brief = self.scheduler.run_once(allowed_risk_classes=["R3"])
        completed = self.assert_no_improvement(brief)
        self.assertEqual(completed["status"], "failed")
        self.assertEqual(completed["action_results"][0]["status"], "failed")
        self.assertIn("no tests were run", completed["failures"][0]["reason"])

    def test_read_only_indexing_still_succeeds(self):
        brief = self.scheduler.run_once(requested_actions=["index_new_sources"])
        completed = self.store.complete_night_queue_run.call_args.kwargs
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["action_results"][0]["status"], "succeeded")
        self.assertTrue(completed["sources"])
        self.assertEqual(brief["completed_improvements"], [])
        self.store.record_controlled_self_improvement.assert_not_called()

    def test_mixed_run_preserves_success_and_discloses_blocked_action(self):
        brief = self.scheduler.run_once(
            requested_actions=["index_new_sources", ACTION_ID],
            allowed_risk_classes=["R1", "R3"],
        )
        completed = self.assert_no_improvement(brief)
        self.assertEqual(completed["status"], "completed_with_attention")
        statuses = {result["action_id"]: result["status"] for result in completed["action_results"]}
        self.assertEqual(statuses["index_new_sources"], "succeeded")
        self.assertEqual(statuses[ACTION_ID], "blocked_by_policy")
        self.assertEqual(len(brief["proposals"]), 1)


if __name__ == "__main__":
    unittest.main()
