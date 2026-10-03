import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from coal import cli
from coal.github_adapter import CreateNotActivated, GitHubCreateAdapter, GitHubReadAdapter, urllib_http
from coal.models import ReadStatus as R, TransportError
from coal.reconciliation import read_exact_attempt
from _common import ident, SHA

ROOT = Path(__file__).resolve().parent.parent


class Rec:
    def __init__(self, status=200, body=b"{}", exc=None):
        self.calls, self.status, self.body, self.exc = [], status, body, exc
    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, dict(headers), body))
        if self.exc: raise self.exc
        return self.status, {"X-GitHub-Request-Id": "RID1"}, self.body


class T(unittest.TestCase):
    def test_read_get_only_and_url(self):
        h = Rec(404)
        r = read_exact_attempt(ident(), GitHubReadAdapter("owner/repo", token="tok", http=h), expected_sha=SHA)
        self.assertEqual(r.status, R.ABSENT_OBSERVED)
        m, url, hdr, body = h.calls[0]
        self.assertEqual(m, "GET")
        self.assertEqual(url, "https://api.github.com/repos/owner/repo/git/ref/heads/coal/attempts/" + ident().digest)
        self.assertIsNone(body)
        self.assertEqual(r.receipt.request_id, "RID1")
        self.assertNotIn("tok", json.dumps(r.receipt.to_dict()))
        self.assertNotIn("Authorization", json.dumps(r.receipt.to_dict()))

    def test_read_failure_maps_to_unknown(self):
        a = GitHubReadAdapter("owner/repo", http=Rec(exc=TransportError("x")))
        self.assertEqual(read_exact_attempt(ident(), a, expected_sha=SHA).status, R.UNKNOWN)

    def test_read_rejects_foreign_namespace(self):
        with self.assertRaises(ValueError):
            GitHubReadAdapter("owner/repo", http=Rec()).get_ref("refs/heads/main")

    def test_create_adapter_not_activatable_by_default(self):
        for kw in (dict(transport=None, token_provider=None),
                   dict(transport=urllib_http, token_provider=lambda: "t"),
                   dict(transport=Rec(), token_provider=None)):
            with self.assertRaises(CreateNotActivated):
                GitHubCreateAdapter("owner/repo", **kw)

    def test_create_adapter_scope_with_injected_fakes(self):
        h = Rec(201)
        a = GitHubCreateAdapter("owner/repo", transport=h, token_provider=lambda: "t")
        a.create_ref(ident().ref_name, SHA)
        m, url, _, body = h.calls[0]
        self.assertEqual((m, url), ("POST", "https://api.github.com/repos/owner/repo/git/refs"))
        self.assertEqual(json.loads(body), {"ref": ident().ref_name, "sha": SHA})
        with self.assertRaises(ValueError):
            a.create_ref("refs/heads/main", SHA)
        self.assertEqual(len(h.calls), 1)

    def test_cli_has_no_live_force_or_create(self):
        p = cli.build_parser()
        subs = next(a for a in p._actions if a.dest == "cmd").choices
        self.assertEqual(set(subs), {"validate", "inspect", "simulate", "readback"})
        text = " ".join(h for s in subs.values() for h in s.format_help().split())
        for w in ("--live", "--force", "--create", "--execute"):
            self.assertNotIn(w, text)
        src = (ROOT / "src/coal/cli.py").read_text()
        self.assertNotIn("GitHubCreateAdapter", src)
        self.assertNotIn("NEXT-001", src)

    def test_cli_simulate_and_inspect(self):
        for sc in cli.SCENARIOS:
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cli.main(["simulate", "--scenario", sc]), 0)
            o = json.loads(buf.getvalue())
            self.assertTrue(o["synthetic"]); self.assertLessEqual(o["create_calls"], 1)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["inspect", "--repository", "o/r", "--subject", "s", "--epoch", "e",
                      "--operation-id", "x", "--source-binding", "b"])
        self.assertIn("refs/heads/coal/attempts/", buf.getvalue())

    def test_cli_validate_schemas(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(cli.main(["validate", "--schemas", str(ROOT / "schemas")]), 0)

    def test_ci_workflow_is_read_only(self):
        t = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("contents: read", t)
        self.assertIn("cancel-in-progress: true", t)
        for bad in ("workflow_dispatch", "secrets.", "pull_request", "git push", "curl", "POST"):
            self.assertNotIn(bad, t)
        # Exact source inventory after the separately reviewed, GET-only custodian addition.
        workflows = {item.name for item in (ROOT / ".github/workflows").glob("*.yml")}
        self.assertEqual(workflows, {"ci.yml", "coal-custodian-jwt-verify-v1.yml"})
        custodian = (ROOT / ".github/workflows/coal-custodian-jwt-verify-v1.yml").read_text()
        for required in (
            "workflow_dispatch:", "contents: read", "environment: coal-custodian-verify",
            "persist-credentials: false", "github.run_attempt == 1",
            "github.ref_protected == true", "github.actor == 'mksoa'",
        ):
            self.assertIn(required, custodian)
        for forbidden in ("pull_request:", "pull_request_target:", "push:"):
            self.assertNotIn(forbidden, custodian)
