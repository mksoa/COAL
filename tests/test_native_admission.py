import json
import unittest

from coal.admission import reserve_with_admission
from coal.carrier import CarrierMismatch, FrozenGLOWBinding, ORIGINAL_PREACT, NativeCarrierObservation, plan_carrier
from coal.github_adapter import CreateNotActivated, urllib_http
from coal.identity import AttemptIdentity
from coal.models import ReserveOutcome
from coal.native_admission import NativeOperationAdmission, original_operation_admission_ref
from coal.reservation import ReservationRequest
from coal.synthetic import SyntheticGitHub


def plan():
    op="GLOW-V2-T03-NEXT001:BRANCH:001"
    binding=FrozenGLOWBinding(source_commit="a"*40,source_tree="b"*40,
                              source_successor_sha256="c"*64,operation_id=op,
                              operation_binding_sha256="d"*64)
    identity=AttemptIdentity("mksoa/COAL","NEXT-001",ORIGINAL_PREACT,op,binding.digest)
    p=plan_carrier(identity,binding,"e"*40)
    observation=NativeCarrierObservation("f"*40,p.tree_sha,(p.coal_parent,),
                                          p.expected_tree_entries,p.content)
    return p,observation


class NativeNet:
    def __init__(self, *, post_status=201, read_status=200, mismatch=False, lose_ack=False):
        self.refs={}
        self.calls=[]
        self.post_status=post_status
        self.read_status=read_status
        self.mismatch=mismatch
        self.lose_ack=lose_ack
    def body(self,ref,sha):
        return json.dumps({"ref":ref,"object":{"type":"commit","sha":sha}}).encode()
    def post(self,method,url,headers,body,timeout):
        self.calls.append(method)
        assert method=="POST" and url.endswith("/git/refs") and "Authorization" in headers
        d=json.loads(body); ref=d["ref"];sha=d["sha"]
        if self.lose_ack:
            self.refs[ref]=sha
            raise TimeoutError()
        if self.post_status!=201:return self.post_status,{"X-GitHub-Request-Id":"p1"},b'{"message":"ambiguous"}'
        if ref in self.refs:return 422,{"X-GitHub-Request-Id":"p2"},b'{"message":"Reference already exists"}'
        self.refs[ref]=sha
        return 201,{"X-GitHub-Request-Id":"p3"},self.body(ref,"0"*40 if self.mismatch else sha)
    def read(self,method,url,headers,body,timeout):
        self.calls.append(method)
        assert method=="GET" and body is None and "/git/ref/heads/coal/admissions/" in url
        ref="refs/"+url.split("/git/ref/",1)[-1]
        if self.read_status!=200:return self.read_status,{"X-GitHub-Request-Id":"g1"},b'{"message":"not found"}'
        return 200,{"X-GitHub-Request-Id":"g2"},self.body(ref,self.refs.get(ref,"0"*40))


def port(p,o,net):
    return NativeOperationAdmission(p,o,transport=net.post,token_provider=lambda:"fake-secret-header-only",
                                    read_http=net.read)


class TestOriginalOperationAdmission(unittest.TestCase):
    def test_first_ack_and_separate_get_then_original_attempt(self):
        p,o=plan();net=NativeNet();admit=port(p,o,net)
        target=SyntheticGitHub(repository="mksoa/COAL")
        r=reserve_with_admission(p,o,ReservationRequest(p.identity,o.commit_sha),target,admit)
        self.assertEqual(r.disposition,"ATTEMPTED_CREATED")
        self.assertEqual(r.reservation.outcome,ReserveOutcome.CREATED)
        self.assertEqual(net.calls,["POST","GET"])
        self.assertEqual(target.create_calls,1)
        self.assertEqual(admit.original_create_receipt.http_status,201)
        self.assertEqual(admit.readback_receipt.http_status,200)
        self.assertEqual(r.admission.receipt_id,admit.original_create_receipt.receipt_digest)
        self.assertEqual(r.admission.original_body_sha256,admit.original_create_receipt.body_sha256)
        self.assertNotIn("fake-secret-header-only",json.dumps(admit.original_create_receipt.to_dict()))
        self.assertFalse(admit.custody_qualified)

    def test_two_port_instances_share_fixed_operation_ref_not_source_digest(self):
        p,o=plan();net=NativeNet()
        first=port(p,o,net)
        self.assertEqual(first.consume_once(p.identity.digest,o.commit_sha).status,"FIRST_CONSUMED")
        from dataclasses import replace
        b=replace(p.binding, source_successor_sha256="1"*64)
        i=replace(p.identity,source_binding=b.digest)
        q=plan_carrier(i,b,p.coal_parent)
        obs=NativeCarrierObservation(o.commit_sha,q.tree_sha,(q.coal_parent,),
                                     q.expected_tree_entries,q.content)
        second=port(q,obs,net)
        self.assertNotEqual(first.identity_digest,second.identity_digest)
        self.assertEqual(first.admission_ref,second.admission_ref)
        self.assertEqual(second.consume_once(i.digest,o.commit_sha).status,"UNKNOWN")
        self.assertEqual(net.calls,["POST","GET","POST"])
        self.assertIsNone(second.readback_receipt)

    def test_201_divergent_no_read_or_original_effect(self):
        p,o=plan();net=NativeNet(mismatch=True);a=port(p,o,net)
        target=SyntheticGitHub(repository="mksoa/COAL")
        r=reserve_with_admission(p,o,ReservationRequest(p.identity,o.commit_sha),target,a)
        self.assertEqual(r.disposition,"ADMISSION_UNKNOWN_READ_ONLY")
        self.assertEqual(net.calls,["POST"])
        self.assertEqual(target.create_calls,0)

    def test_read_failure_burns_one_attempt(self):
        p,o=plan();net=NativeNet(read_status=404);a=port(p,o,net)
        self.assertEqual(a.consume_once(p.identity.digest,o.commit_sha).status,"UNKNOWN")
        self.assertEqual(a.consume_once(p.identity.digest,o.commit_sha).status,"ALREADY_CONSUMED")
        self.assertEqual(net.calls,["POST","GET"])

    def test_ack_lost_cannot_retry_even_if_ref_exists(self):
        p,o=plan();net=NativeNet(lose_ack=True);a=port(p,o,net)
        self.assertEqual(a.consume_once(p.identity.digest,o.commit_sha).status,"UNKNOWN")
        self.assertEqual(a.consume_once(p.identity.digest,o.commit_sha).status,"ALREADY_CONSUMED")
        self.assertEqual(net.calls,["POST"])
        self.assertIn(a.admission_ref,net.refs)

    def test_422_and_403_are_not_first_causal_proof(self):
        for status in (422,403):
            with self.subTest(status=status):
                p,o=plan();net=NativeNet(post_status=status);a=port(p,o,net)
                self.assertEqual(a.consume_once(p.identity.digest,o.commit_sha).status,"UNKNOWN")
                self.assertEqual(net.calls,["POST"])

    def test_wrong_identity_rejected_without_consuming_slot(self):
        p,o=plan();net=NativeNet();a=port(p,o,net)
        self.assertEqual(a.consume_once("0"*64,o.commit_sha).status,"REJECTED")
        self.assertEqual(net.calls,[])
        self.assertEqual(a.consume_once(p.identity.digest,o.commit_sha).status,"FIRST_CONSUMED")

    def test_constructor_requires_external_writer_and_original_scope(self):
        p,o=plan();net=NativeNet()
        with self.assertRaises(CreateNotActivated):
            NativeOperationAdmission(p,o,transport=urllib_http,token_provider=lambda:"x",read_http=net.read)
        with self.assertRaises(CreateNotActivated):
            NativeOperationAdmission(p,o,transport=net.post,token_provider=lambda:"x",read_http=None)
        with self.assertRaises(CarrierMismatch):
            original_operation_admission_ref("GLOW-V2-T03-NEXT001:OTHER:001")
