"""Synthetic in-memory transport (no network). Used by `coal simulate` and tests."""
from __future__ import annotations

import json
import threading
from typing import Dict, Optional

from .models import TransportResponse, TransportTimeout


def ref_body(ref: str, sha: str) -> bytes:
    return json.dumps({"ref": ref, "object": {"sha": sha, "type": "commit"}}).encode()


class SyntheticGitHub:
    """create_fault: timeout_before | timeout_after | forbidden | validation_422 | divergent_201 | server_500
       get_fault:    timeout | server_500 | bad_json | other_sha | other_ref"""

    def __init__(self, repository: str = "owner/repo", create_fault: Optional[str] = None,
                 get_fault: Optional[str] = None):
        self.repository = repository
        self.refs: Dict[str, str] = {}
        self.create_fault = create_fault
        self.get_fault = get_fault
        self.create_calls = 0
        self.get_calls = 0
        self._lock = threading.Lock()

    def create_ref(self, ref: str, sha: str) -> TransportResponse:
        with self._lock:
            self.create_calls += 1
            f = self.create_fault
            if f == "timeout_before":
                raise TransportTimeout("before")
            if f == "forbidden":
                return TransportResponse(403, b'{"message":"Resource not accessible"}', "syn-1")
            if f == "validation_422":
                return TransportResponse(422, b'{"message":"Validation Failed"}', "syn-2")
            if f == "server_500":
                return TransportResponse(500, b'{"message":"boom"}', "syn-3")
            if ref in self.refs:
                return TransportResponse(422, b'{"message":"Reference already exists"}', "syn-4")
            self.refs[ref] = sha
            if f == "timeout_after":
                raise TransportTimeout("ack lost")
            if f == "divergent_201":
                return TransportResponse(201, ref_body(ref, "0" * 40), "syn-5")
            return TransportResponse(201, ref_body(ref, sha), "syn-6")

    def get_ref(self, ref: str) -> TransportResponse:
        with self._lock:
            self.get_calls += 1
            f = self.get_fault
            if f == "timeout":
                raise TransportTimeout("read")
            if f == "server_500":
                return TransportResponse(500, b"{}")
            if ref not in self.refs:
                return TransportResponse(404, b'{"message":"Not Found"}')
            if f == "bad_json":
                return TransportResponse(200, b"<html>")
            if f == "other_sha":
                return TransportResponse(200, ref_body(ref, "f" * 40))
            if f == "other_ref":
                return TransportResponse(200, ref_body("refs/heads/coal/attempts/other", self.refs[ref]))
            return TransportResponse(200, ref_body(ref, self.refs[ref]))
