import unittest
from datetime import datetime, timedelta, timezone

from tt_trends import analysis


def raw(name, rank, vv=1000, posts=10, industries=(23000000000,), curve=(0, 50, 100)):
    return {
        "hashtagName": name,
        "rankIndex": str(rank),
        "vv": str(vv),
        "publishCnt": str(posts),
        "industryIDs": list(industries),
        "popularityCurve": [{"timestamp": str(i), "value": v} for i, v in enumerate(curve)],
        "topCreators": [{"handleName": "creator", "nickname": "C", "followedCnt": "42"}],
    }


class MomentumTest(unittest.TestCase):
    def test_rising(self):
        self.assertEqual(analysis.momentum([0, 5, 10, 30, 60, 85, 100])[0], "rising")

    def test_fading(self):
        self.assertEqual(analysis.momentum([100, 72, 48, 30, 14, 5, 0])[0], "fading")

    def test_peak(self):
        self.assertEqual(analysis.momentum([0, 20, 30, 56, 100, 93, 60])[0], "peak")

    def test_short_curve(self):
        self.assertEqual(analysis.momentum([50]), ("steady", 0))


class MergeTest(unittest.TestCase):
    def test_dedupes_and_keeps_ranks(self):
        lists = {
            "all": [raw("a", 1, vv=500), raw("b", 2)],
            "23": [raw("a", 1, vv=600), raw("c", 2)],
            "25": [raw("d", 1, industries=(25000000000,))],
        }
        items = analysis.merge_lists(lists)
        by_name = {i["name"]: i for i in items}
        self.assertEqual(set(by_name), {"a", "b", "c", "d"})
        self.assertEqual(by_name["a"]["ranks"], {"all": 1, "23": 1})
        self.assertEqual(by_name["a"]["views"], 600)
        self.assertEqual(by_name["d"]["industries"], ["25"])
        self.assertEqual(items[0]["name"], "a")  # overall rank first

    def test_global_trends(self):
        data = {
            "DE": {"7": {"items": analysis.merge_lists({"all": [raw("x", 1), raw("y", 2)]})}},
            "US": {"7": {"items": analysis.merge_lists({"all": [raw("x", 1)]})}},
        }
        result = analysis.global_trends(data, "7")
        self.assertEqual([g["name"] for g in result], ["x"])
        self.assertEqual(result[0]["countries"], ["DE", "US"])


class HistoryTest(unittest.TestCase):
    def test_new_flag_and_delta(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        history: dict = {}

        def snapshot(names_views):
            items = analysis.merge_lists({"all": [raw(n, i + 1, vv=v) for i, (n, v) in enumerate(names_views)]})
            return {"DE": {"7": {"items": items}}}

        d1 = snapshot([("a", 100)])
        analysis.update_history(history, d1, t0)
        self.assertFalse(d1["DE"]["7"]["items"][0]["isNew"])  # first run: nothing is "new"

        d2 = snapshot([("a", 250), ("b", 50)])
        analysis.update_history(history, d2, t0 + timedelta(days=2))
        by_name = {i["name"]: i for i in d2["DE"]["7"]["items"]}
        self.assertFalse(by_name["a"]["isNew"])
        self.assertEqual(by_name["a"]["viewsDelta"], 150)
        self.assertTrue(by_name["b"]["isNew"])
        self.assertIsNone(by_name["b"]["viewsDelta"])

    def test_prunes_old_entries(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        history: dict = {}
        items = analysis.merge_lists({"all": [raw("old", 1)]})
        analysis.update_history(history, {"DE": {"7": {"items": items}}}, t0)
        items = analysis.merge_lists({"all": [raw("fresh", 1)]})
        analysis.update_history(history, {"DE": {"7": {"items": items}}}, t0 + timedelta(days=40))
        self.assertEqual(list(history["entries"]["DE|7"]), ["fresh"])


if __name__ == "__main__":
    unittest.main()
