import unittest
from coal.models import ReadStatus as R
from coal.reconciliation import ReadbackResult, read_exact_attempt
from coal.reservation import ReservationRequest, reserve_exact_attempt
from coal.synthetic import SyntheticGitHub
from _common import ident, SHA


def rb(net, sha=SHA):
    return read_exact_attempt(ident(), net, expected_sha=sha)


class T(unittest.TestCase):
    def test_absent(self):
        r = rb(SyntheticGitHub())
        self.assertEqual(r.status, R.ABSENT_OBSERVED)
        self.assertFalse(ReadbackResult.absence_is_future_guarantee)

    def test_match(self):
        net = SyntheticGitHub(); net.refs[ident().ref_name] = SHA
        r = rb(net)
        self.assertEqual((r.status, r.observed_sha), (R.PRESENT_MATCH, SHA))

    def test_sha_mismatch(self):
        net = SyntheticGitHub(); net.refs[ident().ref_name] = "c" * 40
        r = rb(net)
        self.assertEqual((r.status, r.reason, r.observed_sha), (R.DIVERGENT, "sha_mismatch", "c" * 40))

    def test_other_sha_and_other_ref_served(self):
        for f, reason in (("other_sha", "sha_mismatch"), ("other_ref", "ref_name_mismatch")):
            net = SyntheticGitHub(get_fault=f); net.refs[ident().ref_name] = SHA
            r = rb(net)
            self.assertEqual((r.status, r.reason), (R.DIVERGENT, reason))

    def test_read_failures_unknown(self):
        for f in ("timeout", "server_500", "bad_json"):
            net = SyntheticGitHub(get_fault=f); net.refs[ident().ref_name] = SHA
            self.assertEqual(rb(net).status, R.UNKNOWN, f)

    def test_reconcile_after_ack_lost_does_not_prove_authorship(self):
        net = SyntheticGitHub(create_fault="timeout_after")
        reserve_exact_attempt(ReservationRequest(ident(), SHA), net)
        r = rb(net)
        self.assertEqual(r.status, R.PRESENT_MATCH)
        self.assertFalse(ReadbackResult.causal_authorship_proven)
        self.assertEqual(net.create_calls, 1)

    def test_reconcile_after_timeout_before_is_absent(self):
        net = SyntheticGitHub(create_fault="timeout_before")
        reserve_exact_attempt(ReservationRequest(ident(), SHA), net)
        self.assertEqual(rb(net).status, R.ABSENT_OBSERVED)

    def test_invalid_expected_sha(self):
        with self.assertRaises(ValueError):
            rb(SyntheticGitHub(), "bad")
