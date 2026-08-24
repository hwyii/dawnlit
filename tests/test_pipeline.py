import datetime as dt
import dataclasses
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest.mock import patch


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

    def test_arxiv_query_widens_weekend_lookback(self):
        self.assertEqual(radar.effective_lookback_days(self.profile, self.now), 4)
        tuesday = dt.datetime(2026, 6, 30, 12, tzinfo=dt.timezone.utc)
        self.assertEqual(radar.effective_lookback_days(self.profile, tuesday), 1)

    def test_arxiv_rate_limit_uses_extended_backoff(self):
        rate_limit = urllib.error.HTTPError(
            radar.ARXIV_ENDPOINT, 429, "rate limited", {}, None
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self.payload

            payload = b"ok"

        with patch.object(
            radar.urllib.request,
            "urlopen",
            side_effect=[rate_limit, rate_limit, Response()],
        ), patch.object(radar.time, "sleep") as sleep:
            self.assertEqual(radar.fetch_arxiv_page(radar.ARXIV_ENDPOINT), b"ok")

        self.assertEqual([call.args[0] for call in sleep.call_args_list], [30, 60])

    def test_atom_pages_can_be_merged(self):
        merged = radar.merge_atom_pages([self.payload, self.payload])
        self.assertEqual(len(radar.parse_atom(merged)), 12)

    def test_official_virtual_event_parser_extracts_oral_metadata(self):
        payload = b"""
        <div class="event-card" data-event-type="Oral" data-event-id="42">
          <h3 class="event-title"><a href="/virtual/2026/oral/42">Efficient Adversarial Training for LLMs</a></h3>
          <div class="event-speakers">Ada One \xe2\x8b\x85 Bob Two</div>
          <div class="event-abstract"><div class="abstract-text">We reduce robust fine-tuning cost by 40%.</div></div>
        </div>
        """
        papers = radar.parse_conference_event_page(
            payload,
            "https://iclr.cc/virtual/2026/events/oral",
            "ICLR",
            2026,
            "oral",
        )
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].id, "conf:iclr:2026:42")
        self.assertEqual(papers[0].authors, ["Ada One", "Bob Two"])
        self.assertEqual(papers[0].presentation, "Oral")
        self.assertEqual(papers[0].source, "conference")

    def test_event_discovery_accepts_only_requested_presentation_pages(self):
        payload = b"""
        <a href="/virtual/2026/events/oral"><span>Orals</span></a>
        <a href="/virtual/2026/events/spotlights">Spotlight Posters</a>
        <a href="/virtual/2026/events/posters">Posters</a>
        """
        urls = radar.discover_conference_event_urls(
            payload,
            "https://icml.cc/virtual/2026/papers.html",
            {"oral", "spotlight"},
        )
        self.assertEqual(
            urls,
            [
                ("oral", "https://icml.cc/virtual/2026/events/oral"),
                ("spotlight", "https://icml.cc/virtual/2026/events/spotlights"),
            ],
        )

    def test_acl_schedule_parser_does_not_mislabel_posters_as_orals(self):
        payload = (
            "Preamble,,,,,\n"
            "Paper number,Title,Abstract,Authors Names,Presentation mode,Underline/Whova Session Name\n"
            "12-MAIN,Safe LLM Training,We study efficient adversarial training for language models.,Ada One,In-Person,Oral Session A: Safety\n"
            "13-MAIN,Poster LLM Paper,We study data selection for language models.,Bob Two,In-Person,Poster Session A\n"
        ).encode()
        papers = radar.parse_acl_schedule_csv(
            payload,
            "ACL",
            2026,
            "https://2026.aclweb.org/program/",
        )
        self.assertEqual([paper.id for paper in papers], ["conf:acl:2026:12-main"])
        self.assertEqual(papers[0].presentation, "Oral")

    def test_conference_supplements_prefer_newer_year_then_oral(self):
        def candidate(paper_id, year, presentation, score):
            paper = radar.Paper(
                id=paper_id,
                title=f"Unique {paper_id} language model safety",
                abstract="Efficient adversarial training for robust language models.",
                authors=["Example"],
                published=f"{year}-01-01T00:00:00Z",
                updated=f"{year}-01-01T00:00:00Z",
                categories=[f"ICML {year}", presentation],
                primary_category=f"ICML {year}",
                abs_url="https://icml.cc/",
                pdf_url="https://icml.cc/",
                source="conference",
                venue="ICML",
                presentation=presentation,
                conference_year=year,
            )
            return {
                "id": paper_id,
                "title": paper.title,
                "lane": "llm",
                "scores": {"total": score},
                "_tokens": radar.tokenize(paper.text()),
                "_paper": paper,
            }

        chosen = radar.select_conference_supplements(
            [
                candidate("2025-oral", 2025, "Oral", 0.99),
                candidate("2026-spotlight", 2026, "Spotlight", 0.95),
                candidate("2026-oral", 2026, "Oral", 0.94),
            ],
            [],
            2,
            self.profile,
        )
        self.assertEqual([item["id"] for item in chosen], ["2026-oral", "2026-spotlight"])

    def test_title_fingerprint_deduplicates_arxiv_and_conference_versions(self):
        existing = [radar.title_tokens("Efficient Adversarial Training for Large Language Models")]
        self.assertTrue(
            radar.title_is_duplicate(
                "Efficient Adversarial Training for Large-Language Models",
                existing,
            )
        )
        self.assertFalse(
            radar.title_is_duplicate("Loss Landscape Geometry for LLM Alignment", existing)
        )

    def test_scope_gate_rejects_unrelated_vlm(self):
        lane, _, _ = radar.scope_lane(self.papers[4], self.profile)
        self.assertIsNone(lane)
        lane, _, _ = radar.scope_lane(self.papers[5], self.profile)
        self.assertEqual(lane, "transferable")

    def test_scope_gate_rejects_multilingual_and_language_specific_papers(self):
        for paper_id, title, abstract in [
            (
                "2608.00001",
                "Multilingual Safety Alignment for Large Language Models",
                "We align large language models across many languages and evaluate safety.",
            ),
            (
                "2608.00002",
                "Adversarial Robustness in Arabic Language Models",
                "We study robust fine-tuning and attacks for Arabic language models.",
            ),
            (
                "2608.00005",
                "Language-Agnostic Safety Alignment for Large Language Models",
                "We align large language models across linguistic settings.",
            ),
        ]:
            paper = radar.Paper(
                id=paper_id,
                title=title,
                abstract=abstract,
                authors=["Example"],
                published="2026-08-01T00:00:00Z",
                updated="2026-08-01T00:00:00Z",
                categories=["cs.CL"],
                primary_category="cs.CL",
                abs_url=f"https://arxiv.org/abs/{paper_id}",
                pdf_url=f"https://arxiv.org/pdf/{paper_id}",
            )
            lane, _, matches = radar.scope_lane(paper, self.profile)
            self.assertIsNone(lane)
            self.assertTrue(matches)

    def test_scope_gate_does_not_treat_robot_foundation_model_as_llm(self):
        paper = radar.Paper(
            id="2608.00003",
            title="Scaling Behavior Foundation Models for Humanoid Robots",
            abstract=(
                "Behavior foundation models learn whole-body robot control from "
                "large behavioral datasets and generalize across environments."
            ),
            authors=["Example"],
            published="2026-08-01T00:00:00Z",
            updated="2026-08-01T00:00:00Z",
            categories=["cs.RO"],
            primary_category="cs.RO",
            abs_url="https://arxiv.org/abs/2608.00003",
            pdf_url="https://arxiv.org/pdf/2608.00003",
        )
        lane, _, _ = radar.scope_lane(paper, self.profile)
        self.assertIsNone(lane)

    def test_stored_multilingual_paper_is_removed_by_new_guardrails(self):
        item = {
            "id": "2608.00004",
            "title": "Cross-Lingual Safety Alignment for LLMs",
            "abstract": "We evaluate multilingual safety across several languages.",
            "authors": ["Example"],
            "published": "2026-08-01T00:00:00Z",
            "updated": "2026-08-01T00:00:00Z",
            "categories": ["cs.CL"],
            "primary_category": "cs.CL",
            "abs_url": "https://arxiv.org/abs/2608.00004",
            "pdf_url": "https://arxiv.org/pdf/2608.00004",
        }
        self.assertFalse(radar.stored_item_matches_scope(item, self.profile))

    def test_topic_scoring_finds_loss_landscape(self):
        lane, scope_score, _ = radar.scope_lane(self.papers[0], self.profile)
        self.assertEqual(lane, "llm")
        topics = radar.topic_scores(self.papers[0], self.profile, scope_score, [], [])
        self.assertEqual(topics[0]["id"], "llm_loss_landscape")
        self.assertGreater(topics[0]["score"], 0.4)

    def test_topic_scoring_rejects_surface_only_adversarial_match(self):
        paper = radar.Paper(
            id="2607.11444",
            title="UMoE: Unlocking Every Expert in Domain-Specific Training",
            abstract=(
                "Mixture-of-Experts models contain experts that contribute little on a target "
                "domain, and standard supervised fine-tuning leaves that composition unchanged. "
                "We prune low-saliency experts, regrow them through perturbation-based expansion, "
                "and apply standard fine-tuning. The method demonstrates robustness across strong "
                "training regimes without studying adversarial examples or jailbreak attacks."
            ),
            authors=["Example Author"],
            published="2026-07-13T11:52:42Z",
            updated="2026-07-13T11:52:42Z",
            categories=["cs.CL"],
            primary_category="cs.CL",
            abs_url="https://arxiv.org/abs/2607.11444",
            pdf_url="https://arxiv.org/pdf/2607.11444",
        )
        _, scope_score, _ = radar.scope_lane(paper, self.profile)
        topics = radar.topic_scores(paper, self.profile, scope_score, [], [])
        self.assertNotIn("efficient_adversarial_training", {item["id"] for item in topics})

    def test_term_matching_respects_word_boundaries(self):
        self.assertTrue(radar.contains_term("We prove a generalization bound.", "bound"))
        self.assertFalse(radar.contains_term("Boundary-aware context grounding.", "bound"))
        self.assertFalse(radar.contains_term("An MLLM benchmark.", "llm"))

    def test_semantic_scholar_feedback_scores_use_latest_explicit_labels(self):
        feedback = [
            {
                "paper_id": "2505.17646",
                "action": "useful",
                "created_at": "2026-06-27T12:00:00Z",
            },
            {
                "paper_id": "2606.00003",
                "action": "irrelevant",
                "created_at": "2026-06-27T12:01:00Z",
            },
        ]
        response = {
            "recommendedPapers": [
                {"externalIds": {"ArXiv": "2607.12345v2"}},
                {"externalIds": {"DOI": "10.1000/example"}},
            ]
        }
        with patch.object(radar, "request_json", return_value=response) as request:
            scores = radar.semantic_scholar_feedback_scores(feedback)
        self.assertEqual(scores, {"2607.12345": 1.0})
        body = request.call_args.kwargs["body"]
        self.assertEqual(body["positivePaperIds"], ["ArXiv:2505.17646"])
        self.assertEqual(body["negativePaperIds"], ["ArXiv:2606.00003"])

    def test_feedback_uses_action_strength_and_time_decay(self):
        feedback = [
            {
                "paper_id": "recent-irrelevant",
                "action": "irrelevant",
                "title": "Arabic language model adversarial robustness",
                "abstract": "Evaluation of attacks against Arabic language models.",
                "created_at": "2026-06-27T11:00:00Z",
            },
            {
                "paper_id": "old-not-useful",
                "action": "not_useful",
                "title": "Sparse language model circuits",
                "abstract": "An interpretability study of sparse circuits.",
                "created_at": "2025-06-27T12:00:00Z",
            },
        ]
        _, negatives = radar.feedback_corpora(feedback, self.now)
        recent_weight = next(weight for tokens, weight in negatives if "arabic" in tokens)
        old_weight = next(weight for tokens, weight in negatives if "circuits" in tokens)
        self.assertGreater(recent_weight, old_weight)
        candidate = radar.tokenize(
            "Arabic language model adversarial robustness evaluation of attacks"
        )
        self.assertLess(radar.feedback_adjustment(candidate, [], negatives), -0.2)

    def test_topic_feedback_tuning_adjusts_weights_without_compounding(self):
        profile = json.loads(json.dumps(self.profile))
        feedback = []
        for index in range(4):
            feedback.append(
                {
                    "paper_id": f"useful-{index}",
                    "action": "useful",
                    "topics": ["llm_data_selection"],
                    "created_at": self.now.isoformat(),
                }
            )
            feedback.append(
                {
                    "paper_id": f"irrelevant-{index}",
                    "action": "irrelevant",
                    "topics": ["trustworthy_llm"],
                    "created_at": self.now.isoformat(),
                }
            )

        tuned, diagnostics = radar.apply_topic_feedback_tuning(
            profile,
            feedback,
            self.now,
        )
        data_topic = next(
            topic for topic in tuned["topics"] if topic["id"] == "llm_data_selection"
        )
        trust_topic = next(
            topic for topic in tuned["topics"] if topic["id"] == "trustworthy_llm"
        )
        self.assertGreater(data_topic["effective_weight"], data_topic["weight"])
        self.assertLess(trust_topic["effective_weight"], trust_topic["weight"])
        self.assertEqual(data_topic["feedback_stats"]["hit_rate"], 1.0)
        self.assertEqual(trust_topic["feedback_stats"]["hit_rate"], 0.0)
        self.assertEqual(diagnostics["labeled_papers"], 8)
        self.assertEqual(diagnostics["adjusted_topics"], 2)

        tuned_again, _ = radar.apply_topic_feedback_tuning(tuned, feedback, self.now)
        data_again = next(
            topic
            for topic in tuned_again["topics"]
            if topic["id"] == "llm_data_selection"
        )
        self.assertEqual(data_again["weight"], data_topic["weight"])
        self.assertEqual(data_again["effective_weight"], data_topic["effective_weight"])

    def test_topic_feedback_tuning_uses_latest_action_and_honors_minimum_samples(self):
        profile = json.loads(json.dumps(self.profile))
        feedback = [
            {
                "paper_id": "same-paper",
                "action": "useful",
                "topics": ["llm_loss_landscape"],
                "created_at": "2026-06-27T10:00:00Z",
            },
            {
                "paper_id": "same-paper",
                "action": "irrelevant",
                "topics": ["llm_loss_landscape"],
                "created_at": "2026-06-27T11:00:00Z",
            },
            {
                "paper_id": "cancelled-paper",
                "action": "useful",
                "topics": ["llm_loss_landscape"],
                "created_at": "2026-06-27T09:00:00Z",
            },
            {
                "paper_id": "cancelled-paper",
                "action": "unsave",
                "topics": ["llm_loss_landscape"],
                "created_at": "2026-06-27T11:30:00Z",
            },
        ]
        tuned, diagnostics = radar.apply_topic_feedback_tuning(
            profile,
            feedback,
            self.now,
        )
        topic = next(
            item for item in tuned["topics"] if item["id"] == "llm_loss_landscape"
        )
        self.assertEqual(topic["feedback_stats"]["useful"], 0.0)
        self.assertEqual(topic["feedback_stats"]["irrelevant"], 1.0)
        self.assertFalse(topic["feedback_stats"]["active"])
        self.assertEqual(topic["effective_weight"], topic["weight"])
        self.assertEqual(diagnostics["labeled_papers"], 1)

    def test_secondary_topic_feedback_receives_reduced_credit(self):
        profile = json.loads(json.dumps(self.profile))
        feedback = [
            {
                "paper_id": "multi-topic",
                "action": "useful",
                "topics": ["trustworthy_llm", "llm_data_selection"],
                "created_at": self.now.isoformat(),
            }
        ]
        tuned, _ = radar.apply_topic_feedback_tuning(profile, feedback, self.now)
        trust = next(topic for topic in tuned["topics"] if topic["id"] == "trustworthy_llm")
        data = next(topic for topic in tuned["topics"] if topic["id"] == "llm_data_selection")
        self.assertEqual(trust["feedback_stats"]["useful"], 1.0)
        self.assertEqual(data["feedback_stats"]["useful"], 0.5)

    def test_topic_scoring_uses_effective_weight_but_preserves_manual_weight(self):
        profile = json.loads(json.dumps(self.profile))
        lane, scope_score, _ = radar.scope_lane(self.papers[0], profile)
        self.assertEqual(lane, "llm")
        baseline = radar.topic_scores(self.papers[0], profile, scope_score, [], [])
        loss_topic = next(
            topic for topic in profile["topics"] if topic["id"] == "llm_loss_landscape"
        )
        manual_weight = loss_topic["weight"]
        loss_topic["effective_weight"] = manual_weight / 2
        tuned = radar.topic_scores(self.papers[0], profile, scope_score, [], [])
        baseline_loss = next(
            topic for topic in baseline if topic["id"] == "llm_loss_landscape"
        )
        tuned_loss = next(topic for topic in tuned if topic["id"] == "llm_loss_landscape")
        self.assertLess(tuned_loss["score"], baseline_loss["score"])
        self.assertEqual(loss_topic["weight"], manual_weight)

    def test_unsave_cancels_previous_positive_signal(self):
        feedback = [
            {
                "paper_id": "same-paper",
                "action": "useful",
                "title": "Mechanistic interpretability for language models",
                "created_at": "2026-06-27T10:00:00Z",
            },
            {
                "paper_id": "same-paper",
                "action": "unsave",
                "title": "Mechanistic interpretability for language models",
                "created_at": "2026-06-27T11:00:00Z",
            },
        ]
        positives, negatives = radar.feedback_corpora(feedback, self.now)
        self.assertEqual(positives, [])
        self.assertEqual(negatives, [])

    def test_fallback_summary_is_english(self):
        topics = [{"name": "LLM loss landscape"}]
        summary = radar.extractive_summary(self.papers[0], topics)
        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotRegex(serialized, r"[\u3400-\u9fff]")
        self.assertIn("Matches your research profile", summary["why_for_you"])

    def test_profile_separates_interface_and_content_language(self):
        self.assertEqual(self.profile["ui_language"], "en")
        self.assertEqual(self.profile["content_language"], "zh")

    def test_model_summary_parser_requires_grounded_schema(self):
        raw = """```json
        {"takeaway":"Specific contribution","problem":"Specific research problem","method":"Concrete method",
        "evidence":"Grounded evidence","limitations":"Material limitation","why_for_you":"Matched research direction"}
        ```"""
        summary = radar.parse_model_summary(raw, "test/model")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["generated_by"], "test/model")
        self.assertIsNone(radar.parse_model_summary('{"takeaway":"Only one"}', "test"))

    def test_chinese_language_tag_requires_actual_chinese_content(self):
        english = {
            "takeaway": "Specific contribution",
            "problem": "Specific research problem",
            "method": "Concrete technical method",
            "evidence": "Grounded experimental evidence",
            "limitations": "Material evaluation limitation",
            "why_for_you": "Matched research direction",
        }
        self.assertFalse(radar.language_content_matches(english, "zh"))
        self.assertIsNone(
            radar.parse_model_summary(json.dumps(english), "test/model", "zh")
        )
        chinese = {
            key: value
            for key, value in zip(
                english,
                [
                    "论文提出了一个具体且可验证的贡献。",
                    "论文研究大语言模型训练中的核心问题。",
                    "作者采用结构化方法解决这个问题。",
                    "实验结果为论文结论提供直接证据。",
                    "当前实验范围仍然存在明显限制。",
                    "该方法匹配大语言模型训练研究方向。",
                ],
            )
        }
        self.assertTrue(radar.language_content_matches(chinese, "zh"))

    def test_signal_icons_follow_content_and_role(self):
        self.assertEqual(
            radar.choose_signal_icon("A multilingual tokenization benchmark", 0),
            "🌐",
        )
        self.assertEqual(
            radar.choose_signal_icon("The pipeline fine-tunes a verifier", 1),
            "⚙️",
        )
        self.assertEqual(
            radar.choose_signal_icon("However, the gains remain modest", 2),
            "⚠️",
        )

    def test_analysis_prompt_requests_mobile_length_signals(self):
        prompt = radar.analysis_prompt(
            self.papers[0],
            [{"name": "LLM loss landscape"}],
            self.papers[0].abstract,
            "abstract",
        )
        self.assertIn("limited to 12-20 words", prompt)
        self.assertIn("Choose each signal icon by meaning", prompt)

        chinese = radar.analysis_prompt(
            self.papers[0],
            [{"name": "LLM loss landscape"}],
            self.papers[0].abstract,
            "abstract",
            "zh",
        )
        self.assertIn("Simplified Chinese", chinese)
        self.assertIn("20-45 Chinese characters", chinese)

    def test_cloudflare_response_envelopes_are_normalized(self):
        self.assertEqual(
            radar.cloudflare_response_text({"result": {"response": '{"ok":true}'}}),
            '{"ok":true}',
        )

    def test_cloudflare_inference_falls_back_to_direct_api_on_worker_5xx(self):
        worker_error = radar.urllib.error.HTTPError(
            "https://worker.example/api/ai/run", 500, "error", {}, None
        )
        with patch.dict(
            os.environ,
            {
                "RADAR_API_URL": "https://worker.example",
                "RADAR_ADMIN_TOKEN": "admin",
                "CLOUDFLARE_ACCOUNT_ID": "account",
                "CLOUDFLARE_API_TOKEN": "cloudflare",
            },
            clear=False,
        ), patch.object(
            radar,
            "request_json",
            side_effect=[worker_error, {"result": {"response": "ok"}}],
        ) as request:
            result = radar.cloudflare_inference("model", {"messages": []}, 30)
        self.assertEqual(result["result"]["response"], "ok")
        self.assertEqual(request.call_count, 2)
        self.assertIn("api.cloudflare.com", request.call_args_list[1].args[0])
        self.assertEqual(
            radar.cloudflare_response_text(
                {
                    "result": {
                        "choices": [
                            {"message": {"content": '{"ok":true}'}}
                        ]
                    }
                }
            ),
            '{"ok":true}',
        )

    def test_cloudflare_inference_retries_transient_errors(self):
        rate_limit = radar.urllib.error.HTTPError(
            "https://worker.example/api/ai/run", 429, "rate limited", {}, None
        )
        with patch.object(
            radar,
            "cloudflare_inference",
            side_effect=[rate_limit, {"result": {"response": "ok"}}],
        ) as inference, patch.object(radar.time, "sleep") as sleep:
            result = radar.cloudflare_inference_with_retry("model", {}, 30)

        self.assertEqual(result["result"]["response"], "ok")
        self.assertEqual(inference.call_count, 2)
        sleep.assert_called_once_with(20)

    def test_full_analysis_parser_requires_three_signals(self):
        payload = {
            "brief": {
                "takeaway": "Specific contribution",
                "problem": "Specific research problem",
                "method": "Concrete method",
                "evidence": "Grounded evidence",
                "limitations": "Material limitation",
                "why_for_you": "Matched research direction",
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
        self.assertEqual(analysis[1]["schema_version"], radar.ANALYSIS_SCHEMA_VERSION)
        payload["deep_dive"]["signals"].pop()
        self.assertIsNone(
            radar.parse_model_analysis(
                json.dumps(payload), "test/model", "full text"
            )
        )

    def test_full_analysis_rejects_numbers_missing_from_source(self):
        payload = {
            "brief": {
                "takeaway": "The method improves accuracy by 99%.",
                "problem": "The paper studies robust language models.",
                "method": "The authors train a robust classifier.",
                "evidence": "The reported gain is 99%.",
                "limitations": "The available source states limited evaluation.",
                "why_for_you": "This matches adversarial robustness research.",
            },
            "deep_dive": {
                "signals": [
                    {"icon": "A", "text": "The method targets robustness."},
                    {"icon": "B", "text": "Training uses adversarial examples."},
                    {"icon": "C", "text": "Accuracy improves by 99%."},
                ],
                "overview": "The paper proposes and evaluates a robust training method.",
                "methodology": [{"title": "Training", "detail": "Uses adversarial data."}],
                "mechanism": [{"title": "Mechanism", "detail": "Improves invariance."}],
                "experiments": [{"title": "Evaluation", "detail": "Tests robustness."}],
                "findings": [{"title": "Accuracy", "detail": "Reports a 99% gain."}],
                "contributions": ["A robust training method."],
                "limitations": ["Evaluation scope is limited."],
                "open_questions": ["Whether the method transfers."],
            },
        }
        self.assertIsNone(
            radar.parse_model_analysis(
                json.dumps(payload),
                "test/model",
                "full text",
                "The source reports a 12% accuracy gain.",
            )
        )

    def test_full_analysis_allows_empty_unsupported_sections(self):
        payload = {
            "brief": {
                "takeaway": "Specific contribution grounded in the source.",
                "problem": "Specific research problem grounded in the source.",
                "method": "Concrete technical method grounded in the source.",
                "evidence": "Grounded evidence reported by the available source.",
                "limitations": "The source does not state a complete limitation.",
                "why_for_you": "The method matches the selected research direction.",
            },
            "deep_dive": {
                "signals": [
                    {"icon": "A", "text": "The paper makes a specific contribution."},
                    {"icon": "B", "text": "The method uses a concrete pipeline."},
                    {"icon": "C", "text": "The available evidence supports the claim."},
                ],
                "overview": "A grounded overview of the research question and thesis.",
                "methodology": [],
                "mechanism": [],
                "experiments": [],
                "findings": [],
                "contributions": [],
                "limitations": [],
                "open_questions": [],
            },
        }
        self.assertIsNotNone(
            radar.parse_model_analysis(json.dumps(payload), "test/model", "abstract")
        )

    def test_stale_refresh_limit_counts_attempts_not_only_successes(self):
        items = [
            {
                "id": f"paper-{index}",
                "title": f"Paper {index}",
                "abstract": "A grounded language model paper abstract.",
                "published": self.now.isoformat(),
                "updated": self.now.isoformat(),
                "recommended_at": self.now.isoformat(),
                "topics": [{"name": "LLM safety", "matched": ["safety"]}],
                "lane": "llm",
                "scores": {"total": 0.5},
            }
            for index in range(5)
        ]
        pending = {
            "deep_dive": {"schema_version": radar.ANALYSIS_SCHEMA_VERSION},
            "analysis_status": "pending",
        }
        with patch.object(radar, "cloudflare_available", return_value=True), patch.object(
            radar, "serialize_item", return_value=pending
        ) as serialize, patch.dict(
            os.environ,
            {
                "AI_CACHE_REFRESH_LIMIT": "2",
                "AI_CACHE_REFRESH_TIME_BUDGET_SECONDS": "999",
            },
            clear=False,
        ):
            refreshed = radar.refresh_stale_weekly_analyses(
                items, True, self.now, "zh"
            )
        self.assertEqual(refreshed, 0)
        self.assertEqual(serialize.call_count, 2)

    def test_previous_items_are_loaded_by_arxiv_id(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "papers.json"
            output.write_text(
                json.dumps({"papers": [{"id": "2606.12345", "title": "Cached"}]})
            )
            cached = radar.load_previous_items(output)
            self.assertEqual(cached["2606.12345"]["title"], "Cached")

    def test_seen_ids_include_current_history_archive_and_index(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            (data_dir / "archive").mkdir()
            (data_dir / "papers.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-27T12:00:00+00:00",
                        "papers": [{"id": "current"}],
                    }
                )
            )
            (data_dir / "history.json").write_text(
                json.dumps(
                    {
                        "papers": [
                            {
                                "id": "history",
                                "recommended_at": "2026-06-27T12:30:00+00:00",
                            }
                        ]
                    }
                )
            )
            (data_dir / "archive" / "old.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-26T12:00:00+00:00",
                        "papers": [{"id": "archive"}],
                    }
                )
            )
            (data_dir / "seen.json").write_text(
                json.dumps({"paper_ids": ["indexed"]})
            )
            self.assertEqual(
                radar.load_seen_paper_ids(data_dir / "papers.json"),
                {"current", "history", "archive", "indexed"},
            )
            self.assertEqual(
                radar.load_seen_paper_ids(
                    data_dir / "papers.json",
                    dt.date(2026, 6, 27),
                ),
                {"archive", "indexed"},
            )

    def test_unchanged_paper_reuses_valid_deep_dive(self):
        paper = self.papers[0]
        topics = [{"name": "LLM loss landscape", "matched": ["loss landscape"]}]
        deep_dive = {
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
            "generated_by": "test/model",
            "source_scope": "full text",
            "schema_version": radar.ANALYSIS_SCHEMA_VERSION,
            "prompt_version": radar.ANALYSIS_PROMPT_VERSION,
            "language": "en",
        }
        summary = radar.extractive_summary(paper, topics)
        item = {
            "id": paper.id,
            "title": paper.title,
            "abstract": paper.abstract,
            "topics": topics,
            "lane": "llm",
            "_paper": paper,
            "_tokens": set(),
        }
        previous_item = {
            "id": paper.id,
            "title": paper.title,
            "abstract": paper.abstract,
            "updated": paper.updated,
            "summary": summary,
            "deep_dive": deep_dive,
        }
        with patch.object(radar, "cloudflare_analysis") as generate:
            serialized = radar.serialize_item(item, True, previous_item)
        generate.assert_not_called()
        self.assertEqual(serialized["deep_dive"]["overview"], "Overview")
        self.assertEqual(
            serialized["deep_dive"]["schema_version"],
            radar.ANALYSIS_SCHEMA_VERSION,
        )

    def test_content_language_change_translates_cache_without_reanalysis(self):
        paper = self.papers[0]
        topics = [{"name": "LLM safety", "matched": ["llm"]}]
        summary = {
            "takeaway": "Specific contribution",
            "problem": "Specific research problem",
            "method": "Concrete method",
            "evidence": "Grounded evidence",
            "limitations": "Material limitation",
            "why_for_you": "Matched research direction",
            "schema_version": radar.SUMMARY_SCHEMA_VERSION,
            "prompt_version": radar.SUMMARY_PROMPT_VERSION,
            "language": "en",
        }
        deep_dive = {
            "signals": [
                {"icon": "A", "text": "Finding"},
                {"icon": "B", "text": "Method"},
                {"icon": "C", "text": "Evidence"},
            ],
            "overview": "Overview",
            "methodology": [{"title": "Method", "detail": "Detail"}],
            "mechanism": [{"title": "Mechanism", "detail": "Detail"}],
            "experiments": [{"title": "Setup", "detail": "Detail"}],
            "findings": [{"title": "Finding", "detail": "Detail"}],
            "contributions": ["Contribution"],
            "limitations": ["Limitation"],
            "open_questions": ["Question"],
            "schema_version": radar.ANALYSIS_SCHEMA_VERSION,
            "prompt_version": radar.ANALYSIS_PROMPT_VERSION,
            "language": "en",
        }
        translated_summary = {
            **summary,
            "takeaway": "这项工作提出了一个具体且可验证的贡献。",
            "problem": "论文研究大语言模型安全中的具体问题。",
            "method": "作者采用结构化训练方法解决该问题。",
            "evidence": "实验结果为核心结论提供了直接证据。",
            "limitations": "现有证据仍受实验范围限制。",
            "why_for_you": "该方法匹配大语言模型安全研究方向。",
            "language": "zh",
        }
        translated_deep_dive = {
            **deep_dive,
            "signals": [
                {"icon": "A", "text": "论文提出了可验证的安全训练贡献"},
                {"icon": "B", "text": "方法采用结构化训练与评估流程"},
                {"icon": "C", "text": "实验结果支持核心安全结论"},
            ],
            "overview": "论文围绕大语言模型安全问题提出方法，并通过实验验证核心结论。",
            "methodology": [{"title": "训练方法", "detail": "使用结构化流程完成训练与评估。"}],
            "mechanism": [{"title": "作用机制", "detail": "该机制改善模型的安全行为。"}],
            "experiments": [{"title": "实验设计", "detail": "在明确的数据和基线上进行评估。"}],
            "findings": [{"title": "主要发现", "detail": "实验结果支持论文的核心主张。"}],
            "contributions": ["提出可复现的安全训练方法。"],
            "limitations": ["实验覆盖范围仍然有限。"],
            "open_questions": ["该方法能否推广到更大模型？"],
            "language": "zh",
        }
        item = {
            "id": paper.id,
            "title": paper.title,
            "abstract": paper.abstract,
            "topics": topics,
            "lane": "llm",
            "_paper": paper,
            "_tokens": set(),
        }
        previous = {
            "title": paper.title,
            "abstract": paper.abstract,
            "updated": paper.updated,
            "summary": summary,
            "deep_dive": deep_dive,
        }
        with patch.object(
            radar,
            "cloudflare_translate_analysis",
            return_value=(translated_summary, translated_deep_dive),
        ) as translate, patch.object(radar, "cloudflare_analysis") as analyze:
            serialized = radar.serialize_item(item, True, previous, "zh")
        translate.assert_called_once()
        analyze.assert_not_called()
        self.assertEqual(serialized["summary"]["language"], "zh")
        self.assertEqual(serialized["deep_dive"]["language"], "zh")

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

    def test_ai_analysis_crash_falls_back_to_extractive_summary(self):
        paper = self.papers[0]
        topics = [{"name": "LLM safety", "matched": ["llm"], "status": "core"}]
        item = {
            "id": paper.id,
            "title": paper.title,
            "abstract": paper.abstract,
            "topics": topics,
            "lane": "llm",
            "_paper": paper,
            "_tokens": set(),
        }
        with patch.object(
            radar,
            "cloudflare_analysis",
            side_effect=RuntimeError("models timeout"),
        ), patch.object(
            radar,
            "cloudflare_summary",
            side_effect=RuntimeError("fallback timeout"),
        ):
            serialized = radar.serialize_item(item, True)

        self.assertEqual(serialized["summary"]["source"], "abstract")
        self.assertEqual(serialized["summary"]["generated_by"], "extractive")
        self.assertNotIn("deep_dive", serialized)

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

    def test_remote_profile_keeps_repository_guardrails(self):
        remote = json.loads(json.dumps(self.profile))
        remote["scope"].pop("excluded_language_focus", None)
        trustworthy = next(
            topic for topic in remote["topics"] if topic["id"] == "trustworthy_llm"
        )
        trustworthy.pop("required_central_any", None)
        remote["ui_language"] = "zh"
        with patch.dict(
            os.environ,
            {"RADAR_API_URL": "https://worker.example", "RADAR_ADMIN_TOKEN": "token"},
            clear=False,
        ), patch.object(radar, "request_json", return_value=remote):
            profile = radar.load_profile(
                ROOT / "config" / "profile.json",
                ROOT / "config" / "interests.txt",
            )
        self.assertEqual(profile["ui_language"], "zh")
        self.assertIn("arabic", profile["scope"]["excluded_language_focus"])
        self.assertEqual(profile["conference_fallback"]["minimum_daily"], 3)
        self.assertIn("EMNLP", profile["conference_fallback"]["venues"])
        self.assertTrue(profile["feedback_tuning"]["enabled"])
        self.assertEqual(profile["feedback_tuning"]["maximum_weight"], 1.0)
        trustworthy = next(
            topic for topic in profile["topics"] if topic["id"] == "trustworthy_llm"
        )
        self.assertIn("llm safety", trustworthy["required_central_any"])

    def test_simple_interests_reject_invalid_weight(self):
        with tempfile.TemporaryDirectory() as directory:
            interests_path = Path(directory) / "interests.txt"
            interests_path.write_text("Safety @ 2.0 :: alignment\n")
            with self.assertRaises(ValueError):
                radar.parse_interests(interests_path)

    def test_daily_build_uses_unseen_in_scope_conference_fallback(self):
        conference_papers = [
            radar.Paper(
                id="conf:iclr:2026:safety",
                title="Efficient Adversarial Training for Large Language Models",
                abstract=(
                    "We introduce efficient adversarial training and robust fine-tuning "
                    "for large language models with extensive experiments and ablations."
                ),
                authors=["Ada One"],
                published="2026-01-01T00:00:00Z",
                updated="2026-01-01T00:00:00Z",
                categories=["ICLR 2026", "Oral"],
                primary_category="ICLR 2026",
                abs_url="https://iclr.cc/virtual/2026/oral/safety",
                pdf_url="https://iclr.cc/virtual/2026/oral/safety",
                source="conference",
                venue="ICLR",
                presentation="Oral",
                conference_year=2026,
            ),
            radar.Paper(
                id="conf:icml:2026:landscape",
                title="Curvature of the Loss Landscape in LLM Fine-Tuning",
                abstract=(
                    "We characterize loss landscape sharpness, Hessian curvature, and mode "
                    "connectivity during large language model fine-tuning."
                ),
                authors=["Bob Two"],
                published="2026-01-01T00:00:00Z",
                updated="2026-01-01T00:00:00Z",
                categories=["ICML 2026", "Spotlight"],
                primary_category="ICML 2026",
                abs_url="https://icml.cc/virtual/2026/poster/landscape",
                pdf_url="https://icml.cc/virtual/2026/poster/landscape",
                source="conference",
                venue="ICML",
                presentation="Spotlight",
                conference_year=2026,
            ),
            radar.Paper(
                id="conf:acl:2026:data",
                title="Training Data Valuation for Safe LLM Post-Training",
                abstract=(
                    "We present data valuation and data selection for safe large language "
                    "model post-training with quantitative benchmark evaluation."
                ),
                authors=["Carol Three"],
                published="2026-01-01T00:00:00Z",
                updated="2026-01-01T00:00:00Z",
                categories=["ACL 2026", "Oral"],
                primary_category="ACL 2026",
                abs_url="https://2026.aclweb.org/program/",
                pdf_url="https://2026.aclweb.org/program/",
                source="conference",
                venue="ACL",
                presentation="Oral",
                conference_year=2026,
            ),
            radar.Paper(
                id="conf:acl:2026:arabic",
                title="Arabic Safety Alignment for Large Language Models",
                abstract="We study robust Arabic language model alignment.",
                authors=["Excluded Author"],
                published="2026-01-01T00:00:00Z",
                updated="2026-01-01T00:00:00Z",
                categories=["ACL 2026", "Oral"],
                primary_category="ACL 2026",
                abs_url="https://2026.aclweb.org/program/",
                pdf_url="https://2026.aclweb.org/program/",
                source="conference",
                venue="ACL",
                presentation="Oral",
                conference_year=2026,
            ),
        ]
        cache = {
            "schema_version": radar.CONFERENCE_CACHE_SCHEMA_VERSION,
            "updated_at": self.now.isoformat(),
            "source_status": {"ICLR:2026": "ok:1", "ICML:2026": "ok:1", "ACL:2026": "ok:2"},
            "papers": [dataclasses.asdict(paper) for paper in conference_papers],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data" / "papers.json"
            radar.build(
                ROOT / "config" / "profile.json",
                output,
                ROOT / "tests" / "fixtures" / "arxiv_feed.xml",
                self.now,
                use_ai=False,
            )
            with (
                patch.object(radar, "fetch_arxiv", return_value=(self.payload, 6)),
                patch.object(radar, "sync_conference_cache", return_value=cache),
            ):
                feed = radar.build(
                    ROOT / "config" / "profile.json",
                    output,
                    now=self.now + dt.timedelta(days=1),
                    use_ai=False,
                )
            self.assertEqual(len(feed["papers"]), 3)
            self.assertTrue(feed["minimum_daily_met"])
            self.assertEqual(feed["conference_supplement_count"], 3)
            self.assertEqual({item["source"] for item in feed["papers"]}, {"conference"})
            self.assertNotIn("conf:acl:2026:arabic", {item["id"] for item in feed["papers"]})

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
            self.assertEqual(feed["source_lookback_days"], 4)
            self.assertEqual(feed["content_language"], "zh")
            self.assertFalse(feed["source_truncated"])
            self.assertTrue(feed["topic_feedback"]["enabled"])
            self.assertEqual(feed["topic_feedback"]["adjusted_topics"], 0)
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
            self.assertTrue((output.parent / "seen.json").exists())
            self.assertEqual(feed["papers"][0]["summary"]["source"], "abstract")

            second_feed = radar.build(
                ROOT / "config" / "profile.json",
                output,
                ROOT / "tests" / "fixtures" / "arxiv_feed.xml",
                self.now + dt.timedelta(days=1),
                use_ai=False,
            )
            self.assertEqual(second_feed["papers"], [])


if __name__ == "__main__":
    unittest.main()
