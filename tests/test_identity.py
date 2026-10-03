import unittest
from coal.identity import AttemptIdentity, IdentityError, REF_NAMESPACE
from _common import ident


class T(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(ident().digest, ident().digest)
        self.assertEqual(len(ident().digest), 64)
        self.assertEqual(ident().ref_name, REF_NAMESPACE + ident().digest)

    def test_each_field_changes_digest(self):
        base = ident().digest
        for k, v in dict(repository="owner/other", subject="m2", epoch="E2",
                         operation_id="op-2", source_binding="src-2").items():
            self.assertNotEqual(base, ident(**{k: v}).digest, k)

    def test_no_concatenation_ambiguity(self):
        a = ident(subject="a", epoch="bc")
        b = ident(subject="ab", epoch="c")
        self.assertNotEqual(a.digest, b.digest)

    def test_invalid_inputs(self):
        for kw in (dict(subject=""), dict(epoch="a b"), dict(operation_id="x\n"),
                   dict(repository="norepo"), dict(subject="e\u0301"), dict(epoch="x" * 257)):
            with self.assertRaises(IdentityError, msg=str(kw)):
                ident(**kw)
        with self.assertRaises(IdentityError):
            AttemptIdentity.from_dict({"repository": "o/r"})

    def test_roundtrip(self):
        self.assertEqual(AttemptIdentity.from_dict(ident().to_dict()), ident())
