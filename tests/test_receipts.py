import dataclasses
import unittest
from coal.receipts import Receipt, ReceiptError, body_bytes, build_receipt, verify_receipt

REF = "refs/heads/coal/attempts/" + "1" * 64


def mk(body=b'{"a":1}', **kw):
    return build_receipt(operation="create", native_ref=REF, observed_at="2026-01-01T00:00:00Z",
                         http_status=201, body=body, request_id="rid", **kw)


class T(unittest.TestCase):
    def test_preserves_original_and_verifies(self):
        r = mk()
        self.assertEqual(body_bytes(r), b'{"a":1}')
        self.assertEqual((r.request_id, r.http_status), ("rid", 201))
        self.assertEqual(verify_receipt(r), (True, "ok"))
        self.assertEqual(verify_receipt(Receipt.from_dict(r.to_dict()))[0], True)

    def test_corrupt_body(self):
        r = dataclasses.replace(mk(), body_b64="e30=")
        self.assertFalse(verify_receipt(r)[0])

    def test_corrupt_status(self):
        self.assertEqual(verify_receipt(dataclasses.replace(mk(), http_status=200))[1],
                         "receipt_digest_mismatch")

    def test_sha_mismatch_with_recomputed_digest(self):
        r = mk()
        forged = build_receipt(operation="create", native_ref=REF, observed_at=r.observed_at,
                               http_status=201, body=b"x", request_id="rid")
        bad = dataclasses.replace(forged, body_sha256=r.body_sha256)
        d = bad.to_dict(); d["receipt_digest"] = ""
        from coal.receipts import _digest
        bad = Receipt.from_dict({**d, "receipt_digest": _digest(d)})
        self.assertEqual(verify_receipt(bad), (False, "body_sha256_mismatch"))

    def test_secret_bodies_withheld(self):
        for b in (b"token ghp_" + b"A" * 30, b"Authorization: Bearer x", b"-----BEGIN PRIVATE KEY-----"):
            r = mk(body=b)
            self.assertTrue(r.body_withheld)
            self.assertIsNone(r.body_b64)
            self.assertNotIn("ghp_", repr(r.to_dict()))
            self.assertTrue(verify_receipt(r)[0])

    def test_no_credential_fields(self):
        keys = " ".join(mk().to_dict()).lower()
        for w in ("token", "authorization", "password", "secret", "key"):
            self.assertNotIn(w, keys)

    def test_extra_field_rejected(self):
        d = mk().to_dict(); d["authorization"] = "x"
        with self.assertRaises(ReceiptError):
            Receipt.from_dict(d)
