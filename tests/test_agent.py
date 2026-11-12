import tempfile
import unittest
from pathlib import Path

from tt_trends import agent, analysis


def raw(name, rank, vv=1000, posts=10, ind=23000000000, curve=(0, 50, 100), followers=5000):
    return {
        "hashtagName": name, "rankIndex": str(rank), "vv": str(vv), "publishCnt": str(posts),
        "industryIDs": [ind],
        "popularityCurve": [{"timestamp": str(1794268800 + i), "value": v} for i, v in enumerate(curve)],
        "topCreators": [{"handleName": "c1", "followedCnt": str(followers)}],
    }


def latest_fixture():
    data = {"DE": {
        "7": {"items": analysis.merge_lists({"all": [raw("hot", 1, vv=9_000_000, posts=100)],
                                              "14": [raw("glow", 1, ind=14000000000)]})},
        "30": {"items": analysis.merge_lists({"all": [raw("hot", 2, curve=(100, 50, 20))]})},
        "90": {"items": analysis.merge_lists({"all": [raw("hot", 3)]})},
    }}
    for p in data["DE"].values():
        p["dataUntil"] = 1794268800
    return {
        "generatedAt": "2026-11-12T13:49:00+00:00",
        "countries": {"DE": "Deutschland"},
        "data": data,
        "global": {"7": [], "30": []},
    }


class AgentTest(unittest.TestCase):
    def test_compact(self):
        self.assertEqual(agent.compact(26_332_488), "26.3M")
        self.assertEqual(agent.compact(1_000), "1K")
        self.assertEqual(agent.compact(950), "950")
        self.assertEqual(agent.compact(421_405_325), "421M")
        self.assertEqual(agent.compact(None), "-")

    def test_digits(self):
        self.assertEqual(agent.digits([0, 50, 100]), "059")
        self.assertEqual(agent.digits([]), "-")

    def test_rows(self):
        rows = {r["tag"]: r for r in agent.build_rows("DE", latest_fixture())}
        hot = rows["hot"]
        self.assertEqual(hot["top"], "7:1|30:2|90:3")
        self.assertEqual(hot["m7"], "R")
        self.assertEqual(hot["m30"], "F")
        self.assertIn("E", hot["fl"])
        self.assertEqual(rows["glow"]["ind"], "beauty")
        self.assertIn("X", rows["glow"]["fl"])
        self.assertTrue(0 <= hot["s"] <= 100)

    def test_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent.write_agent_files(latest_fixture(), Path(tmp))
            lines = (Path(tmp) / "agent" / "DE.tsv").read_text().splitlines()
            self.assertTrue(lines[0].startswith("#ttr1 country=DE"))
            self.assertEqual(lines[1].split("\t"), agent.COLUMNS)
            self.assertEqual(len(lines[2].split("\t")), len(agent.COLUMNS))
            self.assertIn("agent/<CC>.tsv", (Path(tmp) / "llms.txt").read_text())


if __name__ == "__main__":
    unittest.main()
