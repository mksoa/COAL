import threading
import unittest
from collections import Counter
from coal.models import ReserveOutcome as O
from coal.reservation import ReservationRequest, reserve_exact_attempt
from coal.synthetic import SyntheticGitHub
from _common import ident, SHA


def fan(n, fn):
    out, ts = [], []
    barrier = threading.Barrier(n)
    def w(i):
        barrier.wait(); out.append(fn(i))
    for i in range(n):
        ts.append(threading.Thread(target=w, args=(i,)))
    [t.start() for t in ts]; [t.join() for t in ts]
    return out


class T(unittest.TestCase):
    def test_identical_identity_one_winner(self):
        net = SyntheticGitHub()
        res = fan(16, lambda i: reserve_exact_attempt(ReservationRequest(ident(), SHA), net))
        c = Counter(r.outcome for r in res)
        self.assertEqual(c[O.CREATED], 1)
        self.assertEqual(c[O.ALREADY_EXISTS], 15)
        self.assertEqual(len(net.refs), 1)

    def test_different_identities_all_created(self):
        net = SyntheticGitHub()
        res = fan(8, lambda i: reserve_exact_attempt(
            ReservationRequest(ident(operation_id=f"op-{i}"), SHA), net))
        self.assertEqual({r.outcome for r in res}, {O.CREATED})
        self.assertEqual(len(net.refs), 8)

    def test_same_request_object_single_native_create(self):
        net = SyntheticGitHub()
        req = ReservationRequest(ident(), SHA)
        res = fan(8, lambda i: reserve_exact_attempt(req, net))
        self.assertEqual(net.create_calls, 1)
        self.assertEqual(Counter(r.outcome for r in res)[O.CREATED], 1)
