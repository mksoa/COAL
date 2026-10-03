import hashlib
import unittest

from coal.admission import AdmissionDecision, reserve_with_admission
from coal.carrier import (
    CARRIER_PATH, CarrierMismatch, FrozenGLOWBinding, NativeCarrierObservation,
    plan_carrier, verify_native_carrier,
)
from coal.identity import AttemptIdentity
from coal.models import ReserveOutcome
from coal.reservation import ReservationRequest
from coal.synthetic import SyntheticGitHub


def setup():
    binding = FrozenGLOWBinding(
        source_commit="a" * 40, source_tree="b" * 40,
        source_successor_sha256="c" * 64, operation_id="NEXT001-OP1",
        operation_binding_sha256="d" * 64,
    )
    identity = AttemptIdentity(
        repository="mksoa/COAL", subject="NEXT-001", epoch="E1",
        operation_id=binding.operation_id, source_binding=binding.digest,
    )
    plan = plan_carrier(identity, binding, "e" * 40)
    obs = NativeCarrierObservation("f" * 40, plan.tree_sha, (plan.coal_parent,),
                                   plan.expected_tree_entries, plan.content)
    return plan, obs


class SharedAdmission:
    def __init__(self, mode="FIRST_CONSUMED"):
        self.seen = set()
        self.calls = 0
        self.mode = mode

    def consume_once(self, digest, sha):
        self.calls += 1
        if self.mode == "throw":
            raise TimeoutError()
        if (digest, sha) in self.seen:
            return AdmissionDecision("ALREADY_CONSUMED", digest, sha)
        # Synthetic shared state only; NOT an external CAS demonstration.
        self.seen.add((digest, sha))
        return AdmissionDecision(self.mode, digest, sha, "synthetic-receipt",
                                 hashlib.sha256(b"synthetic-ACK").hexdigest())


class TestCarrier(unittest.TestCase):
    def test_exact_local_carrier_and_external_binding(self):
        p, o = setup()
        self.assertEqual(verify_native_carrier(p, o), "f" * 40)
        self.assertEqual(p.expected_tree_entries[0][0], CARRIER_PATH)
        self.assertIn(b'"source_commit":"', p.content)
        self.assertIn(b'"operation_id":"NEXT001-OP1"', p.content)
        self.assertEqual(p.content.count(b'"external_binding"'), 1)

    def test_cross_repository_commit_rejected(self):
        p, o = setup()
        with self.assertRaises(CarrierMismatch):
            plan_carrier(AttemptIdentity("mshigueoka/GLOW", "NEXT-001", "E1",
                                         p.binding.operation_id, p.binding.digest),
                         p.binding, p.coal_parent)

    def test_binding_operation_or_digest_mismatch(self):
        p, _ = setup()
        with self.assertRaises(CarrierMismatch):
            plan_carrier(AttemptIdentity("mksoa/COAL", "NEXT-001", "E1",
                                         "WRONG", p.binding.digest), p.binding, p.coal_parent)
        with self.assertRaises(CarrierMismatch):
            plan_carrier(AttemptIdentity("mksoa/COAL", "NEXT-001", "E1",
                                         p.binding.operation_id, "not-bound"), p.binding, p.coal_parent)

    def test_native_commit_tree_parent_blob_mismatch(self):
        p, o = setup()
        variations = (
            NativeCarrierObservation(o.commit_sha, "0" * 40, o.parents, o.tree_entries, o.original_blob),
            NativeCarrierObservation(o.commit_sha, o.tree_sha, ("0" * 40,), o.tree_entries, o.original_blob),
            NativeCarrierObservation(o.commit_sha, o.tree_sha, o.parents, (), o.original_blob),
            NativeCarrierObservation(o.commit_sha, o.tree_sha, o.parents, o.tree_entries, b"forged"),
        )
        for bad in variations:
            with self.subTest(bad=bad):
                with self.assertRaises(CarrierMismatch):
                    verify_native_carrier(p, bad)

    def test_glow_sha_cannot_be_ref_target(self):
        p, o = setup()
        a = SharedAdmission()
        net = SyntheticGitHub(repository="mksoa/COAL")
        with self.assertRaises(CarrierMismatch):
            reserve_with_admission(p, o, ReservationRequest(p.identity, p.binding.source_commit), net, a)
        self.assertEqual((a.calls, net.create_calls), (0, 0))


class TestAdmission(unittest.TestCase):
    def test_exact_first_only_shared_port_two_process_objects(self):
        p, o = setup()
        a = SharedAdmission()
        net = SyntheticGitHub(repository="mksoa/COAL")
        r1 = reserve_with_admission(p, o, ReservationRequest(p.identity, o.commit_sha), net, a)
        r2 = reserve_with_admission(p, o, ReservationRequest(p.identity, o.commit_sha), net, a)
        self.assertEqual(r1.disposition, "ATTEMPTED_CREATED")
        self.assertEqual(r1.reservation.outcome, ReserveOutcome.CREATED)
        self.assertEqual(r2.disposition, "ALREADY_CONSUMED_STOP")
        self.assertEqual((a.calls, net.create_calls), (2, 1))
        self.assertEqual(net.refs[p.identity.ref_name], o.commit_sha)
        self.assertFalse(r1.custody_qualified)

    def test_same_request_and_unknown_never_retry(self):
        p, o = setup()
        a = SharedAdmission(mode="throw")
        net = SyntheticGitHub(repository="mksoa/COAL")
        req = ReservationRequest(p.identity, o.commit_sha)
        self.assertEqual(reserve_with_admission(p, o, req, net, a).disposition,
                         "ADMISSION_UNKNOWN_READ_ONLY")
        self.assertEqual(reserve_with_admission(p, o, req, net, a).disposition,
                         "REQUEST_ALREADY_CONSUMED_NO_RETRY")
        self.assertEqual((a.calls, net.create_calls), (1, 0))

    def test_consumed_admission_rejected_without_post(self):
        p, o = setup()
        a = SharedAdmission(mode="UNKNOWN")
        net = SyntheticGitHub(repository="mksoa/COAL")
        self.assertEqual(reserve_with_admission(p, o, ReservationRequest(p.identity, o.commit_sha),
                                                net, a).disposition, "ADMISSION_UNKNOWN_READ_ONLY")
        self.assertEqual(net.create_calls, 0)

    def test_divergent_and_unverified_admission_no_post(self):
        p, o = setup()
        net = SyntheticGitHub(repository="mksoa/COAL")
        class Bad:
            def __init__(self, decision): self.decision = decision
            def consume_once(self, digest, sha): return self.decision
        cases = (
            AdmissionDecision("FIRST_CONSUMED", "a" * 64, o.commit_sha, "r", "b" * 64),
            AdmissionDecision("FIRST_CONSUMED", p.identity.digest, o.commit_sha, "", "b" * 64),
            AdmissionDecision("FIRST_CONSUMED", p.identity.digest, o.commit_sha, "r", "bad"),
        )
        for decision in cases:
            r = reserve_with_admission(p, o, ReservationRequest(p.identity, o.commit_sha),
                                       net, Bad(decision))
            self.assertIsNone(r.reservation)
        self.assertEqual(net.create_calls, 0)

    def test_lost_post_ack_consumes_admission(self):
        p, o = setup()
        a = SharedAdmission()
        net = SyntheticGitHub(repository="mksoa/COAL", create_fault="timeout_after")
        r = reserve_with_admission(p, o, ReservationRequest(p.identity, o.commit_sha), net, a)
        self.assertEqual(r.disposition, "ATTEMPTED_UNKNOWN")
        self.assertEqual(net.create_calls, 1)
        again = reserve_with_admission(p, o, ReservationRequest(p.identity, o.commit_sha), net, a)
        self.assertEqual(again.disposition, "ALREADY_CONSUMED_STOP")
        self.assertEqual(net.create_calls, 1)
