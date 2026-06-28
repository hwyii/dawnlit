import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_radar", ROOT / "scripts" / "build_radar.py")
radar = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = radar
SPEC.loader.exec_module(radar)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads((ROOT / "config" / "profile.json").read_text())
        cls.payload = (ROOT / "tests" / "fixtures" / "arxiv_feed.xml").read_bytes()
        cls.papers = radar.parse_atom(cls.payload)
        cls.now = dt.datetime(2026, 6, 27, 12, tzinfo=dt.timezone.utc)

    def test_atom_parser_removes_version(self):
        self.assertEqual(len(self.papers), 6)
        self.assertEqual(self.papers[0].id, "2505.17646")
        self.assertEqual(self.papers[0].primary_category, "cs.LG")
        self.assertEqual(len(self.papers[0].authors), 2)

    def test_scope_gate_rejects_unrelated_vlm(self):
        lane, _, _ = radar.scope_lane(self.papers[4], self.profile)
        self.assertIsNone(lane)
        lane, _, _ = radar.scope_lane(self.papers[5], self.profile)
        self.assertEqual(lane, "transferable")

    def test_topic_scoring_finds_loss_landscape(self):
        lane, scope_score, _ = radar.scope_lane(self.papers[0], self.profile)
        self.assertEqual(lane, "llm")
        topics = radar.topic_scores(self.papers[0], self.profile, scope_score, [], [])
        self.assertEqual(topics[0]["id"], "llm_loss_landscape")
        self.assertGreater(topics[0]["score"], 0.4)

    def test_term_matching_respects_word_boundaries(self):
        self.assertTrue(radar.contains_term("We prove a generalization bound.", "bound"))
        self.assertFalse(radar.contains_term("Boundary-aware context grounding.", "bound"))
        self.assertFalse(radar.contains_term("An MLLM benchmark.", "llm"))

    def test_fallback_summary_is_english(self):
        topics = [{"name": "LLM loss landscape"}]
        summary = radar.extractive_summary(self.papers[0], topics)
        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotRegex(serialized, r"[\u3400-\u9fff]")
        self.assertIn("Matches your research profile", summary["why_for_you"])

    def test_simple_interests_retain_advanced_rules_and_add_topics(self):
        with tempfile.TemporaryDirectory() as directory:
            interests_path = Path(directory) / "interests.txt"
            interests_path.write_text(
                "# editable\n"
                "LLM loss landscape @ 0.9 :: spectral geometry\n"
                "Mechanistic interpretability :: sparse autoencoders, circuits\n"
            )
            interests = radar.parse_interests(interests_path)
            profile = radar.apply_interests(self.profile, interests)
            self.assertEqual(len(profile["topics"]), 2)
            self.assertEqual(profile["topics"][0]["id"], "llm_loss_landscape")
            self.assertEqual(profile["topics"][0]["weight"], 0.9)
            self.assertIn("spectral geometry", profile["topics"][0]["phrases"])
            self.assertEqual(
                profile["topics"][1]["id"], "mechanistic_interpretability"
            )
            self.assertIn("sparse autoencoders", profile["topics"][1]["phrases"])

    def test_simple_interests_reject_invalid_weight(self):
        with tempfile.TemporaryDirectory() as directory:
            interests_path = Path(directory) / "interests.txt"
            interests_path.write_text("Safety @ 2.0 :: alignment\n")
            with self.assertRaises(ValueError):
                radar.parse_interests(interests_path)

    def test_end_to_end_fixture_build(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data" / "papers.json"
            feed = radar.build(
                ROOT / "config" / "profile.json",
                output,
                ROOT / "tests" / "fixtures" / "arxiv_feed.xml",
                self.now,
                use_ai=False,
            )
            self.assertEqual(feed["source_count"], 6)
            self.assertGreaterEqual(feed["eligible_count"], 5)
            self.assertEqual(len(feed["papers"]), 5)
            self.assertNotIn("2606.00004", {item["id"] for item in feed["papers"]})
            self.assertLessEqual(
                sum(item["lane"] == "transferable" for item in feed["papers"]),
                1,
            )
            self.assertTrue((output.parent / "profile.json").exists())
            self.assertTrue((output.parent / "archive" / "2026-06-27.json").exists())
            self.assertTrue((output.parent / "history.json").exists())
            self.assertTrue((output.parent / "weekly.json").exists())
            self.assertEqual(feed["papers"][0]["summary"]["source"], "abstract")


if __name__ == "__main__":
    unittest.main()
