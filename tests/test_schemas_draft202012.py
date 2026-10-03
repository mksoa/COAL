"""Full Draft 2020-12 validation in addition to the bundled bounded mini-validator."""
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
from coal.checkpoint import Checkpoint
from coal.receipts import build_receipt
from _common import ident, SHA

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

class T(unittest.TestCase):
    def test_schema_metaschema(self):
        for p in sorted(SCHEMA_DIR.glob("*.schema.json")):
            with self.subTest(name=p.name):
                Draft202012Validator.check_schema(json.loads(p.read_text()))

    def test_sample_instances_full_validator(self):
        examples = {
            "reservation-request": (
                {"identity": ident().to_dict(), "target_sha": SHA},
                {"identity": ident().to_dict(), "target_sha": "not_a_sha"},
            ),
            "reservation-receipt": (
                build_receipt(operation="read", native_ref=ident().ref_name,
                              observed_at="synthetic", http_status=200, body=b"{}").to_dict(),
                {"operation": "read", "native_ref": "invalid"},
            ),
            "reservation-readback": (
                {"status":"PRESENT_MATCH", "reason":"synthetic", "observed_sha":SHA,
                 "causal_authorship_proven":False,"receipt":None},
                {"status":"PRESENT_MATCH", "reason":"synthetic", "observed_sha":SHA,
                 "causal_authorship_proven":True,"receipt":None},
            ),
            "checkpoint": (
                Checkpoint("E", 1, "a" * 64).to_dict(),
                {"epoch":"E", "frontier":-1, "digest":"a" * 64},
            ),
        }
        for name, (valid, invalid) in examples.items():
            with self.subTest(schema=name):
                validator = Draft202012Validator(json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text()))
                self.assertTrue(validator.is_valid(valid))
                self.assertFalse(validator.is_valid(invalid))
