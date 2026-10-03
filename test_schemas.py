import json
import unittest
from pathlib import Path
from coal.checkpoint import Checkpoint
from coal.receipts import build_receipt
from _common import ident, SHA, mini_validate

S = Path(__file__).resolve().parent.parent / "schemas"


def load(n):
    return json.loads((S / f"{n}.schema.json").read_text())


class T(unittest.TestCase):
    def test_all_parse(self):
        for p in S.glob("*.schema.json"):
            s = json.loads(p.read_text())
            self.assertEqual(s["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(s["type"], "object")
        self.assertEqual(len(list(S.glob("*.schema.json"))), 4)

    def test_instances(self):
        self.assertEqual(mini_validate(load("reservation-request"),
                                       {"identity": ident().to_dict(), "target_sha": SHA}), [])
        self.assertNotEqual(mini_validate(load("reservation-request"),
                                          {"identity": ident().to_dict(), "target_sha": "x"}), [])
        r = build_receipt(operation="read", native_ref=ident().ref_name, observed_at="t", http_status=200, body=b"{}")
        self.assertEqual(mini_validate(load("reservation-receipt"), r.to_dict()), [])
        self.assertEqual(mini_validate(load("checkpoint"), Checkpoint("E", 1, "a" * 64).to_dict()), [])
        self.assertNotEqual(mini_validate(load("checkpoint"), {"epoch": "E", "frontier": -1, "digest": "a" * 64}), [])
        rb = {"status": "PRESENT_MATCH", "reason": "r", "observed_sha": SHA,
              "causal_authorship_proven": False, "receipt": None}
        self.assertEqual(mini_validate(load("reservation-readback"), rb), [])
        rb["causal_authorship_proven"] = True
        self.assertNotEqual(mini_validate(load("reservation-readback"), rb), [])
