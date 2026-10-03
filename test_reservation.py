import unittest
from coal.models import ReserveOutcome as O
from coal.reservation import ReservationRequest, ReservationResult, reserve_exact_attempt
from coal.synthetic import SyntheticGitHub
from coal.receipts import verify_receipt
from _common import ident, SHA


def run(net, **kw):
    return reserve_exact_attempt(ReservationRequest(ident(), SHA), net, **kw)


class T(unittest.TestCase):
    def test_first_reservation(self):
        net = SyntheticGitHub()
        r = run(net)
        self.assertEqual(r.outcome, O.CREATED)
        self.assertEqual((net.create_calls, net.get_calls), (1, 0))  # one create, no pre-check
        self.assertEqual(net.refs[ident().ref_name], SHA)
        self.assertTrue(verify_receipt(r.receipt)[0])
        self.assertEqual(r.receipt.http_status, 201)

    def test_existing_not_overwritten(self):
        net = SyntheticGitHub()
        net.refs[ident().ref_name] = "b" * 40
        r = run(net)
        self.assertEqual(r.outcome, O.ALREADY_EXISTS)
        self.assertEqual(net.refs[ident().ref_name], "b" * 40)
        self.assertEqual(net.create_calls, 1)

    def test_201_divergent_body(self):
        self.assertEqual(run(SyntheticGitHub(create_fault="divergent_201")).outcome, O.CONFLICT)

    def test_422_without_exists_is_rejected(self):
        self.assertEqual(run(SyntheticGitHub(create_fault="validation_422")).outcome, O.REJECTED)

    def test_422_exists_is_not_ownership(self):
        net = SyntheticGitHub(); net.refs[ident().ref_name] = SHA
        r = run(net)
        self.assertEqual(r.outcome, O.ALREADY_EXISTS)
        self.assertFalse(ReservationResult.ownership_established)

    def test_403_rejected(self):
        r = run(SyntheticGitHub(create_fault="forbidden"))
        self.assertEqual((r.outcome, r.receipt.http_status), (O.REJECTED, 403))

    def test_500_unknown(self):
        self.assertEqual(run(SyntheticGitHub(create_fault="server_500")).outcome, O.UNKNOWN)

    def test_timeout_before_is_unknown_and_not_retried(self):
        net = SyntheticGitHub(create_fault="timeout_before")
        req = ReservationRequest(ident(), SHA)
        self.assertEqual(reserve_exact_attempt(req, net).outcome, O.UNKNOWN)
        self.assertEqual(net.create_calls, 1)
        again = reserve_exact_attempt(req, net)  # retry attempt on same request
        self.assertEqual(again.outcome, O.REJECTED)
        self.assertEqual(net.create_calls, 1)

    def test_ack_lost_unknown_though_ref_exists(self):
        net = SyntheticGitHub(create_fault="timeout_after")
        r = run(net)
        self.assertEqual(r.outcome, O.UNKNOWN)
        self.assertIn(ident().ref_name, net.refs)
        self.assertEqual(net.create_calls, 1)

    def test_malformed_response_unknown(self):
        class Bad:
            def create_ref(self, ref, sha): return "ok"
        self.assertEqual(run(Bad()).outcome, O.UNKNOWN)

    def test_never_claims_authority(self):
        for flag in ("ownership_established", "h0_m0_issued", "credential_qualified"):
            self.assertFalse(getattr(ReservationResult, flag))

    def test_repository_mismatch_makes_no_call(self):
        net = SyntheticGitHub(repository="other/repo")
        self.assertEqual(run(net).outcome, O.REJECTED)
        self.assertEqual(net.create_calls, 0)

    def test_request_has_no_authority_boolean_and_validates(self):
        with self.assertRaises(ValueError):
            ReservationRequest(ident(), "xyz")
        with self.assertRaises(TypeError):
            reserve_exact_attempt(ReservationRequest(ident(), SHA), object())
