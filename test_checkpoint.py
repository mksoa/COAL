import unittest
from coal.checkpoint import CheckpointVerdict, verify_frontier

A, B = "a" * 64, "b" * 64


def cp(f, d=A, e="E1"):
    return {"epoch": e, "frontier": f, "digest": d}


class T(unittest.TestCase):
    def test_advance(self):
        self.assertEqual(verify_frontier(cp(1), cp(2, B)).reason, "FRONTIER_ADVANCED")

    def test_idempotent(self):
        self.assertTrue(verify_frontier(cp(1), cp(1)).ok)

    def test_rollback(self):
        v = verify_frontier(cp(5), cp(4))
        self.assertEqual((v.ok, v.reason), (False, "FRONTIER_REGRESSION"))

    def test_same_frontier_conflict(self):
        self.assertEqual(verify_frontier(cp(5), cp(5, B)).reason, "SAME_FRONTIER_DIGEST_CONFLICT")

    def test_epoch_change(self):
        self.assertEqual(verify_frontier(cp(5), cp(6, B, "E2")).reason, "EPOCH_MISMATCH")

    def test_structural(self):
        bad = [{}, cp(True), cp(-1), cp(1.0), cp(1, "xyz"), cp(1, A.upper()), {**cp(1), "x": 1},
               cp(1, e=""), "str", None]
        for b in bad:
            v = verify_frontier(cp(1), b)
            self.assertFalse(v.ok, b)
            self.assertTrue(v.reason.startswith("STRUCTURAL_INVALID"), b)
        self.assertFalse(verify_frontier(None, cp(1)).ok)

    def test_no_witness_claim(self):
        self.assertFalse(CheckpointVerdict.witness_installed)
        self.assertFalse(CheckpointVerdict.w038_qualified)
