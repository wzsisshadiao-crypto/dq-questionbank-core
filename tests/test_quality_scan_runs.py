from __future__ import annotations

import json
import unittest

from dq_questionbank import RULESET_VERSION
from dq_questionbank.quality_scan_runs import (
    LeaseHeldError,
    ScanLease,
    ScanRunError,
    ScanRunState,
    checkpoint,
    pending_items,
    resume_run,
    start_run,
    summarize,
)

# Leases tick on a monotonic counter, never wall time (issue #95).
LEASE = ScanLease(lease_id="lease-1", owner="worker-a", expires_at=100)
FRESH_LEASE = ScanLease(lease_id="lease-2", owner="worker-b", expires_at=500)


class StartRunTests(unittest.TestCase):
    def test_start_run_deduplicates_ids_preserving_order(self):
        run = start_run(["q-3", "q-1", "q-3", "q-2", "q-1"], LEASE)

        self.assertEqual(("q-3", "q-1", "q-2"), run.question_ids)
        self.assertEqual((), run.completed)
        self.assertEqual((), run.failures)
        self.assertEqual(LEASE, run.lease)

    def test_run_id_is_deterministic_from_content(self):
        first = start_run(["q-1", "q-2"], None)
        second = start_run(["q-1", "q-2"], None)

        self.assertEqual(first.run_id, second.run_id)
        self.assertTrue(first.run_id.startswith("scan-"))

    def test_run_id_tracks_order_and_ignores_duplicates(self):
        ordered = start_run(["q-1", "q-2"], None)
        reordered = start_run(["q-2", "q-1"], None)
        duplicated = start_run(["q-1", "q-2", "q-1"], None)

        self.assertNotEqual(ordered.run_id, reordered.run_id)
        self.assertEqual(ordered.run_id, duplicated.run_id)

    def test_explicit_run_id_is_kept(self):
        run = start_run(["q-1"], LEASE, run_id="scan-manual")

        self.assertEqual("scan-manual", run.run_id)

    def test_invalid_question_ids_are_rejected(self):
        for bad in ("", None, 7):
            with self.assertRaises(ValueError):
                start_run([bad], LEASE)


class ScanLeaseTests(unittest.TestCase):
    def test_expiry_boundary_is_exactly_now_tick_ge_expires_at(self):
        lease = ScanLease("lease-1", "worker-a", 10)

        self.assertFalse(lease.is_expired(9))
        self.assertTrue(lease.is_expired(10))
        self.assertTrue(lease.is_expired(11))


class PendingItemsTests(unittest.TestCase):
    def test_pending_items_keep_run_order_and_exclude_completed(self):
        run = start_run(["q-1", "q-2", "q-3", "q-4"], LEASE)
        run = checkpoint(run, "q-3")

        self.assertEqual(("q-1", "q-2", "q-4"), pending_items(run))

    def test_pending_items_are_empty_once_coverage_is_complete(self):
        run = start_run(["q-1"], LEASE)
        run = checkpoint(run, "q-1")

        self.assertEqual((), pending_items(run))



class CheckpointTests(unittest.TestCase):
    def test_checkpoint_appends_completion_and_rule_failures(self):
        run = start_run(["q-1", "q-2"], LEASE)
        run = checkpoint(run, "q-1", failed_rules=("latex-mismatched-delimiters",))

        self.assertEqual(("q-1",), run.completed)
        self.assertEqual(1, len(run.failures))
        failure = run.failures[0]
        self.assertEqual("q-1", failure["question_id"])
        self.assertEqual("latex-mismatched-delimiters", failure["rule_id"])
        self.assertTrue(failure["error"])

    def test_checkpoint_deduplicates_repeated_rule_ids(self):
        run = start_run(["q-1"], LEASE)
        run = checkpoint(
            run,
            "q-1",
            failed_rules=(
                "latex-mismatched-delimiters",
                "latex-mismatched-delimiters",
            ),
        )

        self.assertEqual(1, len(run.failures))

    def test_checkpoint_rejects_duplicate_completion(self):
        run = checkpoint(start_run(["q-1"], LEASE), "q-1")

        with self.assertRaises(ValueError):
            checkpoint(run, "q-1")

    def test_checkpoint_rejects_unknown_question(self):
        run = start_run(["q-1"], LEASE)

        with self.assertRaises(ValueError):
            checkpoint(run, "q-9")

    def test_checkpoint_rejects_invalid_rule_ids(self):
        run = start_run(["q-1"], LEASE)

        for bad in ("", 7, None):
            with self.assertRaises(ValueError):
                checkpoint(run, "q-1", failed_rules=(bad,))

    def test_checkpoint_never_mutates_the_original_state(self):
        run = start_run(["q-1", "q-2"], LEASE)

        updated = checkpoint(run, "q-1")

        self.assertEqual((), run.completed)
        self.assertEqual(("q-1",), updated.completed)


class ResumeLeaseTests(unittest.TestCase):
    def test_resume_replaces_an_absent_lease(self):
        run = start_run(["q-1"], None)

        resumed = resume_run(run, now_tick=0, lease=LEASE)

        self.assertEqual(LEASE, resumed.lease)

    def test_resume_refreshes_an_expired_lease(self):
        run = start_run(["q-1"], LEASE)

        resumed = resume_run(run, now_tick=150, lease=FRESH_LEASE)

        self.assertEqual(FRESH_LEASE, resumed.lease)

    def test_lease_boundary_one_tick_before_expiry_still_holds(self):
        run = start_run(["q-1"], LEASE)  # expires_at == 100

        with self.assertRaises(LeaseHeldError):
            resume_run(run, now_tick=99, lease=FRESH_LEASE)

    def test_lease_boundary_at_the_exact_expiry_tick_refreshes(self):
        run = start_run(["q-1"], LEASE)  # expires_at == 100

        resumed = resume_run(run, now_tick=100, lease=FRESH_LEASE)

        self.assertEqual(FRESH_LEASE, resumed.lease)

    def test_unexpired_lease_held_by_another_owner_raises(self):
        run = start_run(["q-1"], LEASE)

        with self.assertRaises(LeaseHeldError) as raised:
            resume_run(run, now_tick=50, lease=FRESH_LEASE)

        self.assertIn("worker-a", str(raised.exception))

    def test_lease_held_error_is_a_module_runtime_error(self):
        self.assertTrue(issubclass(LeaseHeldError, ScanRunError))
        self.assertTrue(issubclass(ScanRunError, RuntimeError))

    def test_unexpired_lease_renews_for_the_same_owner(self):
        renewed = ScanLease(lease_id="lease-1b", owner="worker-a", expires_at=200)
        run = start_run(["q-1"], LEASE)

        resumed = resume_run(run, now_tick=50, lease=renewed)

        self.assertEqual(renewed, resumed.lease)

    def test_resume_keeps_progress_untouched(self):
        run = checkpoint(start_run(["q-1", "q-2"], LEASE), "q-1")

        resumed = resume_run(run, now_tick=150, lease=FRESH_LEASE)

        self.assertEqual(("q-1",), resumed.completed)
        self.assertEqual(("q-1", "q-2"), resumed.question_ids)
        self.assertEqual(run.failures, resumed.failures)
        self.assertEqual(run.run_id, resumed.run_id)



class SummarizeTests(unittest.TestCase):
    def test_summary_of_an_empty_run_is_vacuously_complete(self):
        summary = summarize(start_run([], None))

        self.assertEqual(0, summary["total"])
        self.assertEqual(0, summary["completed"])
        self.assertEqual(0, summary["pending"])
        self.assertTrue(summary["coverage_complete"])
        self.assertEqual({}, summary["failures_by_rule"])
        self.assertEqual(RULESET_VERSION, summary["ruleset"])

    def test_summary_counts_partial_coverage_and_failures(self):
        run = start_run(["q-1", "q-2", "q-3"], LEASE)
        run = checkpoint(run, "q-1", failed_rules=("latex-mismatched-delimiters",))
        run = checkpoint(run, "q-3")

        summary = summarize(run)

        self.assertEqual(run.run_id, summary["run_id"])
        self.assertEqual(3, summary["total"])
        self.assertEqual(2, summary["completed"])
        self.assertEqual(1, summary["pending"])
        self.assertFalse(summary["coverage_complete"])
        self.assertEqual(
            {"latex-mismatched-delimiters": 1}, summary["failures_by_rule"]
        )
        self.assertEqual("quality/1", summary["ruleset"])


class SerializationTests(unittest.TestCase):
    def test_lease_round_trips_through_json(self):
        restored = ScanLease.from_dict(json.loads(json.dumps(LEASE.to_dict())))

        self.assertEqual(LEASE, restored)

    def test_lease_rejects_unknown_fields(self):
        payload = LEASE.to_dict()
        payload["ttl"] = 5

        with self.assertRaises(ValueError):
            ScanLease.from_dict(payload)

    def test_run_state_round_trips_with_a_lease(self):
        run = start_run(["q-1", "q-2"], LEASE)
        run = checkpoint(run, "q-1", failed_rules=("latex-bare-function-names",))

        restored = ScanRunState.from_dict(json.loads(json.dumps(run.to_dict())))

        self.assertEqual(run, restored)
        self.assertEqual(LEASE, restored.lease)

    def test_run_state_round_trips_without_a_lease(self):
        run = start_run(["q-1"], None)

        restored = ScanRunState.from_dict(json.loads(json.dumps(run.to_dict())))

        self.assertEqual(run, restored)
        self.assertIsNone(restored.lease)

    def test_run_state_rejects_unknown_fields(self):
        payload = start_run(["q-1"], LEASE).to_dict()
        payload["worker"] = "worker-a"

        with self.assertRaises(ValueError):
            ScanRunState.from_dict(payload)

    def test_failure_entries_reject_unknown_fields(self):
        run = checkpoint(
            start_run(["q-1"], LEASE),
            "q-1",
            failed_rules=("latex-mismatched-delimiters",),
        )
        payload = run.to_dict()
        payload["failures"][0]["severity"] = "error"

        with self.assertRaises(ValueError):
            ScanRunState.from_dict(payload)

    def test_failure_entries_reject_missing_fields(self):
        run = checkpoint(
            start_run(["q-1"], LEASE),
            "q-1",
            failed_rules=("latex-mismatched-delimiters",),
        )
        payload = run.to_dict()
        del payload["failures"][0]["error"]

        with self.assertRaises(ValueError):
            ScanRunState.from_dict(payload)

    def test_completed_outside_the_run_fail_closed(self):
        payload = start_run(["q-1"], LEASE).to_dict()
        payload["completed"] = ["q-1", "q-2"]

        with self.assertRaises(ValueError):
            ScanRunState.from_dict(payload)

    def test_duplicate_completed_entries_fail_closed(self):
        payload = start_run(["q-1"], LEASE).to_dict()
        payload["completed"] = ["q-1", "q-1"]

        with self.assertRaises(ValueError):
            ScanRunState.from_dict(payload)



class CrashSimulationTests(unittest.TestCase):
    """Issue #95: an interrupted scan resumes exactly where it stopped."""

    def test_interrupted_run_resumes_exactly_once(self):
        question_ids = ("q-1", "q-2", "q-3", "q-4", "q-5")
        run = start_run(question_ids, LEASE)

        # Two items are scanned before the interruption; q-1 carries findings.
        run = checkpoint(
            run,
            "q-1",
            failed_rules=(
                "latex-mismatched-delimiters",
                "latex-bare-function-names",
            ),
        )
        run = checkpoint(run, "q-2")
        self.assertFalse(summarize(run)["coverage_complete"])

        # The process dies: the state survives only as persisted JSON, and
        # the in-memory object is dropped.
        persisted = json.loads(json.dumps(run.to_dict()))
        del run

        # A new worker takes over once the old lease has expired.
        resumed = resume_run(
            ScanRunState.from_dict(persisted), now_tick=100, lease=FRESH_LEASE
        )
        self.assertEqual(("q-3", "q-4", "q-5"), pending_items(resumed))
        self.assertFalse(summarize(resumed)["coverage_complete"])

        # The rescan covers only the pending items, never the done ones.
        final = checkpoint(resumed, "q-3")
        self.assertFalse(summarize(final)["coverage_complete"])
        final = checkpoint(final, "q-4", failed_rules=("latex-mismatched-delimiters",))
        self.assertFalse(summarize(final)["coverage_complete"])
        final = checkpoint(final, "q-5")
        self.assertTrue(summarize(final)["coverage_complete"])

        # Exactly-once: no id appears twice in completed and none is skipped.
        completed = final.completed
        self.assertEqual(len(set(completed)), len(completed))
        self.assertEqual(set(question_ids), set(completed))

        # Completion order is preserved across the interruption.
        self.assertEqual(question_ids, completed)

        summary = summarize(final)
        self.assertEqual(5, summary["total"])
        self.assertEqual(5, summary["completed"])
        self.assertEqual(0, summary["pending"])
        self.assertEqual(
            {"latex-mismatched-delimiters": 2, "latex-bare-function-names": 1},
            summary["failures_by_rule"],
        )
        self.assertEqual(RULESET_VERSION, summary["ruleset"])

        # A replayed checkpoint after recovery still fails closed.
        with self.assertRaises(ValueError):
            checkpoint(final, "q-2")


if __name__ == "__main__":
    unittest.main()
