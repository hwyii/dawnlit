import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
import urllib.parse
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

    def test_arxiv_query_supports_pagination(self):
        url = radar.build_arxiv_url(self.profile, self.now, start=250, page_size=100)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["start"], ["250"])
        self.assertEqual(query["max_results"], ["100"])

    def test_atom_pages_can_be_merged(self):
        merged = radar.merge_atom_pages([self.payload, self.payload])
        self.assertEqual(len(radar.parse_atom(merged)), 12)

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

    def test_model_summary_parser_requires_grounded_schema(self):
        raw = """```json
        {"takeaway":"Contribution","problem":"Problem","method":"Method",
        "evidence":"Evidence","limitations":"Limit","why_for_you":"Reason"}
        ```"""
        summary = radar.parse_model_summary(raw, "test/model")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["generated_by"], "test/model")
        self.assertIsNone(radar.parse_model_summary('{"takeaway":"Only one"}', "test"))

    def test_full_analysis_parser_requires_three_signals(self):
        payload = {
            "brief": {
                "takeaway": "Contribution",
                "problem": "Problem",
                "method": "Method",
                "evidence": "Evidence",
                "limitations": "Limit",
                "why_for_you": "Reason",
            },
            "deep_dive": {
                "signals": [
                    {"icon": "1", "text": "Finding"},
                    {"icon": "2", "text": "Method"},
                    {"icon": "3", "text": "Evidence"},
                ],
                "overview": "Overview",
                "methodology": [{"title": "Method", "detail": "Detail"}],
                "mechanism": [{"title": "Mechanism", "detail": "Detail"}],
                "experiments": [{"title": "Setup", "detail": "Detail"}],
                "findings": [{"title": "Finding", "detail": "Detail"}],
                "contributions": ["Contribution"],
                "limitations": ["Limitation"],
                "open_questions": ["Question"],
            },
        }
        analysis = radar.parse_model_analysis(
            json.dumps(payload), "test/model", "full text"
        )
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis[1]["source_scope"], "full text")
        payload["deep_dive"]["signals"].pop()
        self.assertIsNone(
            radar.parse_model_analysis(
                json.dumps(payload), "test/model", "full text"
            )
        )

    def test_full_text_condensing_keeps_key_regions(self):
        text = (
            "Introduction " + "a" * 6000
            + " Method "
            + "b" * 6000
            + " Experimental Setup "
            + "c" * 6000
            + " Results "
            + "d" * 6000
            + " Conclusion "
            + "e" * 6000
        )
        condensed = radar.condense_paper_text(text, max_chars=18000)
        self.assertLessEqual(len(condensed), 18000)
        self.assertIn("Introduction", condensed)
        self.assertIn("METHOD REGION", condensed)
        self.assertIn("ENDING REGION", condensed)

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
            self.assertEqual(feed["source_total"], 6)
            self.assertFalse(feed["source_truncated"])
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
