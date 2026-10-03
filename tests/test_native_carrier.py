import base64
import json
import unittest

from coal.carrier import CarrierMismatch, FrozenGLOWBinding, ORIGINAL_PREACT, plan_carrier
from coal.identity import AttemptIdentity
from coal.native_carrier import (
    CarrierObjectRequest, GitHubCarrierObjectRead, GitHubCarrierObjectWrite,
    prepare_native_carrier_once, OPERATIONS,
)
from coal.github_adapter import CreateNotActivated, urllib_http


def case():
    op = "GLOW-V2-T03-NEXT001:BRANCH:001"
    b = FrozenGLOWBinding(source_commit="a"*40, source_tree="b"*40,
                          source_successor_sha256="c"*64, operation_id=op,
                          operation_binding_sha256="d"*64)
    i = AttemptIdentity(repository="mksoa/COAL", subject="NEXT-001", epoch=ORIGINAL_PREACT,
                        operation_id=op, source_binding=b.digest)
    return plan_carrier(i, b, "e"*40)


class NativeFake:
    def __init__(self, plan, *, bad_ack=None, bad_read=None):
        self.p = plan
        self.posts = []
        self.reads = []
        self.bad_ack = bad_ack
        self.bad_read = bad_read
        self.commit_sha = "f"*40

    def write(self, method, url, headers, body, timeout):
        kind = url.rsplit("/", 1)[-1]
        self.posts.append(kind)
        assert method == "POST" and "Authorization" in headers
        d = json.loads(body)
        if kind == "blobs":
            assert d == {"content": base64.b64encode(self.p.content).decode("ascii"),
                         "encoding": "base64"}
            sha = self.p.blob_sha
        elif kind == "trees":
            assert d == {"tree": [{"path":"reservation.json", "mode":"100644",
                                   "type":"blob", "sha":self.p.blob_sha}]}
            sha = self.p.tree_sha
        else:
            assert kind == "commits" and d["tree"] == self.p.tree_sha
            assert d["parents"] == [self.p.coal_parent]
            assert d["message"].endswith(self.p.identity.digest)
            sha = self.commit_sha
        if self.bad_ack == kind:
            return 500, {"X-GitHub-Request-Id": "r1"}, b'{"message":"ambiguous"}'
        return 201, {"X-GitHub-Request-Id": "r1"}, json.dumps({"sha":sha}).encode()

    def read(self, method, url, headers, body, timeout):
        kind, sha = url.rsplit("/", 2)[-2:]
        self.reads.append(kind)
        assert method == "GET" and body is None
        if self.bad_read == kind:
            return 404, {}, b'{"message":"Not Found"}'
        if kind == "blobs":
            d = {"sha":sha, "content":base64.b64encode(self.p.content).decode("ascii"),
                 "encoding":"base64", "size":len(self.p.content)}
        elif kind == "trees":
            d = {"sha":sha, "truncated":False,
                 "tree":[{"path":"reservation.json","mode":"100644",
                          "type":"blob","sha":self.p.blob_sha}]}
        else:
            assert kind == "commits"
            d = {"sha":sha, "message":"COAL NEXT-001 carrier v1: "+self.p.identity.digest,
                 "tree":{"sha":self.p.tree_sha}, "parents":[{"sha":self.p.coal_parent}]}
        if kind == "blobs" and self.bad_read == "wrapped_base64":
            v = d["content"]; d["content"] = "\n".join(v[j:j+60] for j in range(0,len(v),60))
        if kind == "trees" and self.bad_read == "tree_divergent":
            d["tree"][0]["mode"] = "100755"
        if kind == "commits" and self.bad_read == "commit_divergent":
            d["parents"] = [{"sha":"0"*40}]
        return 200, {"X-GitHub-Request-Id":"r2"}, json.dumps(d).encode()


def ports(fake):
    return (GitHubCarrierObjectWrite(transport=fake.write, token_provider=lambda:"synthetic-token"),
            GitHubCarrierObjectRead(http=fake.read))


class TestNativeCarrier(unittest.TestCase):
    def test_six_original_operation_names(self):
        self.assertEqual(len(OPERATIONS), 6)
        self.assertIn("GLOW-V2-T03-NEXT001:OPEN_PR:001", OPERATIONS)

    def test_first_native_shapes_and_original_receipts(self):
        p=case(); net=NativeFake(p); w,r=ports(net)
        result=prepare_native_carrier_once(CarrierObjectRequest(p),w,r)
        self.assertEqual(result.status, "NATIVE_OBJECT_SHAPE_VERIFIED_NOT_CUSTODY")
        self.assertEqual(result.commit_sha, "f"*40)
        self.assertEqual(net.posts, ["blobs","trees","commits"])
        self.assertEqual(net.reads, ["blobs","trees","commits"])
        self.assertEqual([x.http_status for x in result.post_receipts], [201]*3)
        self.assertEqual([x.http_status for x in result.read_receipts], [200]*3)
        self.assertTrue(all(x.body_b64 is not None for x in result.post_receipts))
        self.assertFalse(result.custody_qualified)
        self.assertFalse(result.attempt_reserved)

    def test_wrapped_base64_and_timestamp(self):
        import re
        p=case(); net=NativeFake(p,bad_read="wrapped_base64"); w,r=ports(net)
        result=prepare_native_carrier_once(CarrierObjectRequest(p),w,r)
        self.assertEqual(result.status, "NATIVE_OBJECT_SHAPE_VERIFIED_NOT_CUSTODY")
        self.assertTrue(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", x.observed_at)
                            for x in result.post_receipts + result.read_receipts))

    def test_read_drift_fail_closed(self):
        for fault in ("tree_divergent", "commit_divergent"):
            with self.subTest(fault=fault):
                p=case(); net=NativeFake(p,bad_read=fault); w,r=ports(net)
                result=prepare_native_carrier_once(CarrierObjectRequest(p),w,r)
                self.assertEqual(result.status, "NATIVE_SHAPE_DIVERGENT_STOP")
                self.assertIsNone(result.commit_sha)
                self.assertEqual(len(net.posts),3)

    def test_same_request_never_reposts(self):
        p=case(); net=NativeFake(p); w,r=ports(net); req=CarrierObjectRequest(p)
        self.assertIsNotNone(prepare_native_carrier_once(req,w,r).commit_sha)
        self.assertEqual(prepare_native_carrier_once(req,w,r).status,
                         "REQUEST_ALREADY_CONSUMED_NO_RETRY")
        self.assertEqual(len(net.posts),3)

    def test_ambiguous_ack_stops_before_followon(self):
        for bad,expected in (("blobs",["blobs"]),("trees",["blobs","trees"]),
                             ("commits",["blobs","trees","commits"])):
            p=case(); net=NativeFake(p,bad_ack=bad); w,r=ports(net)
            result=prepare_native_carrier_once(CarrierObjectRequest(p),w,r)
            self.assertEqual(result.status,"POST_"+bad.upper()+"_UNKNOWN_STOP")
            self.assertEqual(net.posts,expected)
            self.assertEqual(net.reads,[])
            self.assertEqual(result.commit_sha,None)

    def test_read_failure_never_claims_verified(self):
        p=case(); net=NativeFake(p,bad_read="trees"); w,r=ports(net)
        result=prepare_native_carrier_once(CarrierObjectRequest(p),w,r)
        self.assertEqual(result.status,"READ_TREES_UNKNOWN_STOP")
        self.assertIsNone(result.commit_sha)
        self.assertEqual(len(net.posts),3)

    def test_externally_supplied_writer_only(self):
        with self.assertRaises(CreateNotActivated):
            GitHubCarrierObjectWrite(transport=urllib_http,token_provider=lambda:"x")
        with self.assertRaises(CreateNotActivated):
            GitHubCarrierObjectWrite(transport=None,token_provider=lambda:"x")
        with self.assertRaises(CarrierMismatch):
            GitHubCarrierObjectRead(repository="mshigueoka/GLOW")

    def test_alternate_subject_or_epoch_stops_before_any_post(self):
        from dataclasses import replace
        p=case()
        for drift in ({"subject":"OTHER"}, {"epoch":"REPINNED"}):
            with self.subTest(drift=drift):
                bad_id=replace(p.identity,**drift)
                bad_plan=plan_carrier(bad_id,p.binding,p.coal_parent)
                net=NativeFake(bad_plan);w,r=ports(net)
                with self.assertRaises(CarrierMismatch):
                    prepare_native_carrier_once(CarrierObjectRequest(bad_plan),w,r)
                self.assertEqual(net.posts,[])

    def test_unknown_operation_fails_before_post(self):
        p=case()
        from dataclasses import replace
        bad=replace(p.binding, operation_id="OTHER")
        bad_id=replace(p.identity, operation_id="OTHER",source_binding=bad.digest)
        plan=plan_carrier(bad_id,bad,p.coal_parent)
        net=NativeFake(plan);w,r=ports(net)
        with self.assertRaises(CarrierMismatch):
            prepare_native_carrier_once(CarrierObjectRequest(plan),w,r)
        self.assertEqual(net.posts,[])
