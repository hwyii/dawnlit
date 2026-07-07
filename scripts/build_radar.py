#!/usr/bin/env python3
"""Build a personalized, explainable daily arXiv paper feed.

The default pipeline uses only the Python standard library.  Optional remote
profile/feedback sync and Cloudflare Workers AI summaries are enabled through
environment variables documented in README.md.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import datetime as dt
import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "profile.json"
DEFAULT_INTERESTS = ROOT / "config" / "interests.txt"
DEFAULT_OUTPUT = ROOT / "public" / "data" / "papers.json"
DEFAULT_PROFILE_OUTPUT = ROOT / "public" / "data" / "profile.json"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"
USER_AGENT = "dawnlit/0.1 (personal research discovery; contact: hwyii.github.io)"

ATOM = {"a": "http://www.w3.org/2005/Atom"}
ARXIV = {"arxiv": "http://arxiv.org/schemas/atom"}
OPENSEARCH = {"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}

TOKEN_RE = re.compile(r"[a-z][a-z0-9+\-]{2,}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
ANALYSIS_SCHEMA_VERSION = 2

STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "among",
    "approach",
    "based",
    "been",
    "being",
    "between",
    "both",
    "from",
    "have",
    "into",
    "large",
    "language",
    "model",
    "models",
    "more",
    "most",
    "paper",
    "results",
    "show",
    "that",
    "their",
    "these",
    "this",
    "through",
    "using",
    "with",
}


@dataclasses.dataclass
class Paper:
    id: str
    title: str
    abstract: str
    authors: list[str]
    published: str
    updated: str
    categories: list[str]
    primary_category: str
    abs_url: str
    pdf_url: str
    comment: str = ""
    journal_ref: str = ""

    def text(self) -> str:
        return f"{self.title}. {self.abstract}".strip()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def parse_date(value: str) -> dt.datetime:
    if not value:
        return utc_now()
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(text.lower())
        if token not in STOPWORDS and not token.isdigit()
    }


def contains_term(text: str, term: str) -> bool:
    text = text.lower()
    term = term.lower().strip()
    if not term:
        return False
    if re.fullmatch(r"[a-z0-9]+", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def phrase_hits(text: str, phrases: Iterable[str]) -> float:
    lowered = text.lower()
    total = 0.0
    for phrase in phrases:
        phrase = phrase.lower().strip()
        if not phrase:
            continue
        if re.fullmatch(r"[a-z0-9]+", phrase):
            count = len(
                re.findall(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", lowered)
            )
        else:
            count = lowered.count(phrase)
        if count:
            total += min(count, 3) * (1.0 + min(len(phrase.split()), 4) * 0.35)
    return total


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def request_json(
    url: str,
    token: str | None = None,
    method: str = "GET",
    body: Any = None,
    timeout: int = 45,
) -> Any:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def interest_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_interests(path: Path | None) -> list[dict[str, Any]]:
    """Parse the small, human-editable interest file.

    Each non-comment line is:
        Topic name @ optional-weight :: optional, comma-separated, keywords
    """
    if path is None or not path.exists():
        return []
    interests: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name_part, separator, keyword_part = line.partition("::")
        topic_name, weight_separator, raw_weight = name_part.rpartition("@")
        if weight_separator:
            topic_name = topic_name.strip()
            try:
                weight = float(raw_weight.strip())
            except ValueError as error:
                raise ValueError(f"Invalid interest weight: {raw_line}") from error
            if not 0 <= weight <= 1:
                raise ValueError(f"Interest weight must be between 0 and 1: {raw_line}")
        else:
            topic_name = name_part.strip()
            weight = None
        if not topic_name:
            raise ValueError(f"Invalid interest line: {raw_line}")
        keywords = (
            [item.strip() for item in keyword_part.split(",") if item.strip()]
            if separator
            else []
        )
        interests.append(
            {
                "name": topic_name,
                "weight": weight,
                "keywords": keywords,
            }
        )
    return interests


def apply_interests(
    profile: dict[str, Any], interests: list[dict[str, Any]]
) -> dict[str, Any]:
    """Overlay a simple interest list while retaining advanced topic rules."""
    if not interests:
        return profile
    result = copy.deepcopy(profile)
    existing = {
        interest_key(topic.get("id", "")): topic for topic in result.get("topics", [])
    }
    existing.update(
        {
            interest_key(topic.get("name", "")): topic
            for topic in result.get("topics", [])
        }
    )
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, interest in enumerate(interests):
        key = interest_key(interest["name"])
        topic = copy.deepcopy(existing.get(key))
        if topic is None:
            topic = {
                "id": key or f"interest_{index + 1}",
                "name": interest["name"],
                "description": interest["name"],
                "weight": 0.8,
                "status": "emerging",
                "enabled": True,
                "phrases": [interest["name"]],
                "terms": sorted(tokenize(interest["name"])),
                "exclude": [],
            }
        topic["enabled"] = True
        if interest["weight"] is not None:
            topic["weight"] = interest["weight"]
        if interest["keywords"]:
            topic["phrases"] = list(
                dict.fromkeys([*(topic.get("phrases") or []), *interest["keywords"]])
            )
            topic["terms"] = list(
                dict.fromkeys(
                    [
                        *(topic.get("terms") or []),
                        *sorted(tokenize(" ".join(interest["keywords"]))),
                    ]
                )
            )
        topic_id = topic["id"]
        if topic_id in used_ids:
            topic_id = f"{topic_id}_{index + 1}"
            topic["id"] = topic_id
        used_ids.add(topic_id)
        selected.append(topic)
    result["topics"] = selected
    return result


def load_profile(
    path: Path, interests_path: Path | None = DEFAULT_INTERESTS
) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    profile = apply_interests(profile, parse_interests(interests_path))
    api_url = os.getenv("RADAR_API_URL", "").rstrip("/")
    api_token = os.getenv("RADAR_ADMIN_TOKEN")
    if api_url and api_token:
        try:
            remote = request_json(f"{api_url}/api/profile", api_token)
            if isinstance(remote, dict) and remote.get("topics"):
                profile = remote
                print("Loaded profile from RADAR_API_URL", file=sys.stderr)
        except (OSError, ValueError, urllib.error.URLError) as error:
            print(f"Profile sync unavailable; using local profile: {error}", file=sys.stderr)
    return profile


def load_feedback() -> list[dict[str, Any]]:
    api_url = os.getenv("RADAR_API_URL", "").rstrip("/")
    api_token = os.getenv("RADAR_ADMIN_TOKEN")
    if not api_url or not api_token:
        return []
    try:
        result = request_json(f"{api_url}/api/feedback?limit=500", api_token)
        return result.get("items", []) if isinstance(result, dict) else []
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"Feedback sync unavailable: {error}", file=sys.stderr)
        return []


def build_arxiv_url(
    profile: dict[str, Any],
    now: dt.datetime,
    start: int = 0,
    page_size: int | None = None,
) -> str:
    retrieval = profile["retrieval"]
    category_query = " OR ".join(f"cat:{category}" for category in retrieval["categories"])
    start_date = now - dt.timedelta(days=int(retrieval.get("lookback_days", 4)))
    date_query = (
        f"submittedDate:[{start_date.strftime('%Y%m%d%H%M')} TO "
        f"{now.strftime('%Y%m%d%H%M')}]"
    )
    query = f"({category_query}) AND {date_query}"
    parameters = {
        "search_query": query,
        "start": start,
        "max_results": page_size or int(retrieval.get("page_size", 250)),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_ENDPOINT}?{urllib.parse.urlencode(parameters)}"


def fetch_arxiv_page(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                break
            retry_after = error.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 15 * (
                attempt + 1
            )
            print(
                f"arXiv returned HTTP {error.code}; retrying in {delay}s",
                file=sys.stderr,
            )
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < 3:
                time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch arXiv after 4 attempts: {last_error}")


def atom_total_results(payload: bytes) -> int:
    root = ET.fromstring(payload)
    value = root.findtext("opensearch:totalResults", namespaces=OPENSEARCH)
    return int(value or len(root.findall("a:entry", ATOM)))


def merge_atom_pages(pages: list[bytes]) -> bytes:
    if not pages:
        raise ValueError("No arXiv pages to merge")
    root = ET.fromstring(pages[0])
    for payload in pages[1:]:
        page_root = ET.fromstring(payload)
        for entry in page_root.findall("a:entry", ATOM):
            root.append(entry)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def fetch_arxiv(profile: dict[str, Any], now: dt.datetime) -> tuple[bytes, int]:
    retrieval = profile["retrieval"]
    page_size = max(1, min(int(retrieval.get("page_size", 250)), 500))
    result_limit = max(page_size, int(retrieval.get("max_results", 2000)))
    pages = [
        fetch_arxiv_page(
            build_arxiv_url(profile, now, start=0, page_size=page_size)
        )
    ]
    total_results = atom_total_results(pages[0])
    fetched = len(ET.fromstring(pages[0]).findall("a:entry", ATOM))
    target = min(total_results, result_limit)
    while fetched < target:
        time.sleep(3)
        requested = min(page_size, target - fetched)
        page = fetch_arxiv_page(
            build_arxiv_url(profile, now, start=fetched, page_size=requested)
        )
        page_count = len(ET.fromstring(page).findall("a:entry", ATOM))
        if page_count == 0:
            break
        pages.append(page)
        fetched += page_count
    return merge_atom_pages(pages), total_results


def parse_atom(payload: bytes) -> list[Paper]:
    root = ET.fromstring(payload)
    papers: list[Paper] = []
    for entry in root.findall("a:entry", ATOM):
        raw_id = normalize_space(entry.findtext("a:id", namespaces=ATOM))
        arxiv_id = raw_id.rsplit("/", 1)[-1]
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        links = {
            link.attrib.get("title") or link.attrib.get("rel"): link.attrib.get("href", "")
            for link in entry.findall("a:link", ATOM)
        }
        category_nodes = entry.findall("a:category", ATOM)
        primary = entry.find("arxiv:primary_category", ARXIV)
        primary_category = primary.attrib.get("term", "") if primary is not None else ""
        papers.append(
            Paper(
                id=arxiv_id,
                title=normalize_space(entry.findtext("a:title", namespaces=ATOM)),
                abstract=normalize_space(entry.findtext("a:summary", namespaces=ATOM)),
                authors=[
                    normalize_space(author.findtext("a:name", namespaces=ATOM))
                    for author in entry.findall("a:author", ATOM)
                ],
                published=normalize_space(entry.findtext("a:published", namespaces=ATOM)),
                updated=normalize_space(entry.findtext("a:updated", namespaces=ATOM)),
                categories=[node.attrib.get("term", "") for node in category_nodes],
                primary_category=primary_category,
                abs_url=links.get("alternate") or f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=links.get("pdf") or f"https://arxiv.org/pdf/{arxiv_id}",
                comment=normalize_space(entry.findtext("arxiv:comment", namespaces=ARXIV)),
                journal_ref=normalize_space(entry.findtext("arxiv:journal_ref", namespaces=ARXIV)),
            )
        )
    return papers


def scope_lane(paper: Paper, profile: dict[str, Any]) -> tuple[str | None, float, list[str]]:
    scope = profile["scope"]
    title = paper.title.lower()
    text = paper.text().lower()
    excluded = [term for term in scope.get("excluded_concepts", []) if contains_term(text, term)]
    modality_hits = [
        term for term in scope.get("non_llm_modalities", []) if contains_term(text, term)
    ]
    llm_hits = [term for term in scope.get("required_concepts", []) if contains_term(text, term)]
    transfer_hits = [
        term for term in scope.get("transferable_concepts", []) if contains_term(text, term)
    ]
    strong_llm_hits = [
        term
        for term in llm_hits
        if term.startswith("large language")
        or term in {"llm", "llms", "foundation model", "foundation models", "instruction tuning"}
    ]
    title_llm_hits = [
        term for term in scope.get("required_concepts", []) if contains_term(title, term)
    ]
    direct_llm_mentions = len(
        re.findall(
            r"(?<![a-z0-9])(?:llms?|large[- ]language models?|foundation models?)(?![a-z0-9])",
            text,
        )
    )
    central_llm_work = bool(title_llm_hits) or direct_llm_mentions >= 2 or (
        paper.primary_category in {"cs.CL", "cs.LG"} and direct_llm_mentions >= 1
    )

    if excluded and not strong_llm_hits:
        return None, 0.0, excluded
    if modality_hits:
        title_transfer_hits = [
            term for term in scope.get("transferable_concepts", []) if contains_term(title, term)
        ]
        is_survey = "survey" in title or "review" in title
        if scope.get("allow_transferable") and title_transfer_hits and not is_survey:
            return "transferable", clamp(0.4 + 0.1 * len(title_transfer_hits)), title_transfer_hits[:5]
        return None, 0.0, modality_hits
    if llm_hits and central_llm_work:
        title_bonus = sum(1 for term in llm_hits if term in title)
        return "llm", clamp(0.55 + 0.08 * len(llm_hits) + 0.08 * title_bonus), llm_hits[:5]
    if scope.get("allow_transferable") and transfer_hits:
        return "transferable", clamp(0.38 + 0.1 * len(transfer_hits)), transfer_hits[:5]
    return None, 0.0, []


def feedback_corpora(feedback: list[dict[str, Any]]) -> tuple[list[set[str]], list[set[str]]]:
    positives: list[set[str]] = []
    negatives: list[set[str]] = []
    seen_papers: set[str] = set()
    ordered = sorted(feedback, key=lambda item: item.get("created_at", ""), reverse=True)
    for item in ordered:
        paper_id = item.get("paper_id", "")
        if paper_id and paper_id in seen_papers:
            continue
        if paper_id:
            seen_papers.add(paper_id)
        action = item.get("action")
        if action == "unsave":
            continue
        text = f"{item.get('title', '')} {item.get('abstract', '')}"
        tokens = tokenize(text)
        if not tokens:
            continue
        if action in {"save", "read", "more_method", "more_topic", "transferable"}:
            positives.append(tokens)
        elif action in {"not_llm", "irrelevant"}:
            negatives.append(tokens)
    return positives, negatives


def topic_scores(
    paper: Paper,
    profile: dict[str, Any],
    scope_score: float,
    positive_feedback: list[set[str]],
    negative_feedback: list[set[str]],
) -> list[dict[str, Any]]:
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    tokens = tokenize(paper.text())
    scored: list[dict[str, Any]] = []
    for topic in profile["topics"]:
        if not topic.get("enabled", True) or float(topic.get("weight", 0)) <= 0:
            continue
        excluded = [
            term for term in topic.get("exclude", []) if contains_term(paper.text(), term)
        ]
        if excluded:
            continue
        required_any = topic.get("required_any", [])
        if required_any and not any(contains_term(paper.text(), term) for term in required_any):
            continue
        required_groups = topic.get("required_all_groups", [])
        if required_groups and not all(
            any(contains_term(paper.text(), term) for term in group)
            for group in required_groups
        ):
            continue
        phrases = topic.get("phrases", [])
        terms = topic.get("terms", [])
        title_hits = phrase_hits(title, [*phrases, *terms])
        abstract_hits = phrase_hits(abstract, [*phrases, *terms])
        description_overlap = jaccard(tokens, tokenize(topic.get("description", "")))
        raw = title_hits * 1.8 + abstract_hits * 0.65 + description_overlap * 4.0
        normalized = 1.0 - math.exp(-raw / 5.5)
        matched = [
            term
            for term in [*phrases, *terms]
            if contains_term(paper.text(), term)
        ][:6]
        weighted = normalized * float(topic.get("weight", 1.0))
        if weighted > 0.04 and (matched or description_overlap >= 0.18):
            scored.append(
                {
                    "id": topic["id"],
                    "name": topic["name"],
                    "status": topic.get("status", "watch"),
                    "score": round(clamp(weighted), 4),
                    "matched": matched,
                }
            )

    feedback_boost = 0.0
    if positive_feedback:
        feedback_boost += max(jaccard(tokens, item) for item in positive_feedback) * 0.2
    if negative_feedback:
        feedback_boost -= max(jaccard(tokens, item) for item in negative_feedback) * 0.25

    for topic in scored:
        topic["score"] = round(clamp(topic["score"] * scope_score + feedback_boost), 4)
    return sorted(scored, key=lambda item: item["score"], reverse=True)


def quality_score(paper: Paper) -> tuple[float, list[str]]:
    text = paper.text().lower()
    signals: list[tuple[str, float, str]] = [
        ("code", 0.14, "code available"),
        ("github.com", 0.16, "GitHub link"),
        ("ablation", 0.1, "ablation study"),
        ("baseline", 0.07, "baseline comparison"),
        ("benchmark", 0.07, "benchmark evaluation"),
        ("experiment", 0.06, "experiments"),
        ("theorem", 0.1, "theoretical result"),
        ("we prove", 0.1, "proof"),
        ("bound", 0.06, "formal bound"),
        ("dataset", 0.04, "dataset evidence"),
        ("open-source", 0.08, "open source"),
        ("reproduc", 0.08, "reproducibility"),
    ]
    score = 0.28
    reasons: list[str] = []
    for needle, weight, label in signals:
        if needle in text:
            score += weight
            reasons.append(label)
    if NUMBER_RE.search(paper.abstract):
        score += 0.08
        reasons.append("quantitative results")
    if len(paper.abstract.split()) >= 120:
        score += 0.05
    if paper.journal_ref:
        score += 0.06
        reasons.append("publication metadata")
    return clamp(score), reasons[:5]


def load_previous_papers(output_path: Path) -> list[set[str]]:
    if not output_path.exists():
        return []
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        return [tokenize(item.get("title", "") + " " + item.get("abstract", "")) for item in data.get("papers", [])]
    except (OSError, ValueError):
        return []


def load_previous_items(output_path: Path) -> dict[str, dict[str, Any]]:
    if not output_path.exists():
        return {}
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        return {
            item["id"]: item
            for item in data.get("papers", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
    except (OSError, ValueError):
        return {}


def load_seen_paper_ids(output_path: Path) -> set[str]:
    """Load every previously recommended arXiv ID, including pre-index archives."""
    data_dir = output_path.parent
    seen: set[str] = set()
    paths = [
        data_dir / "seen.json",
        output_path,
        data_dir / "history.json",
        *sorted((data_dir / "archive").glob("*.json")),
    ]
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for paper_id in payload.get("paper_ids", []):
            if isinstance(paper_id, str) and paper_id:
                seen.add(paper_id)
        for item in payload.get("papers", []):
            paper_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(paper_id, str) and paper_id:
                seen.add(paper_id)
    return seen


def novelty_score(paper: Paper, previous: list[set[str]]) -> float:
    if not previous:
        return 0.55
    tokens = tokenize(paper.text())
    similarity = max((jaccard(tokens, item) for item in previous), default=0.0)
    return clamp(0.95 - similarity * 1.35, 0.2, 0.95)


def freshness_score(paper: Paper, now: dt.datetime) -> float:
    age_days = max(0.0, (now - parse_date(paper.published)).total_seconds() / 86400)
    return clamp(1.0 - age_days / 7.0, 0.2, 1.0)


def split_sentences(text: str) -> list[str]:
    return [normalize_space(sentence) for sentence in SENTENCE_RE.split(text) if normalize_space(sentence)]


def select_sentence(sentences: list[str], needles: Iterable[str], fallback: int) -> str:
    lowered_needles = tuple(item.lower() for item in needles)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(needle in lowered for needle in lowered_needles):
            return sentence
    if not sentences:
        return ""
    return sentences[min(fallback, len(sentences) - 1)]


def extractive_summary(paper: Paper, topics: list[dict[str, Any]]) -> dict[str, Any]:
    sentences = split_sentences(paper.abstract)
    takeaway = select_sentence(
        sentences,
        [
            "we propose",
            "we introduce",
            "we present",
            "we develop",
            "we find",
            "we show",
            "we demonstrate",
        ],
        0,
    )
    method = select_sentence(
        sentences,
        ["we propose", "we introduce", "we develop", "our method", "framework", "algorithm"],
        1,
    )
    evidence = select_sentence(
        sentences[1:] or sentences,
        ["experiment", "outperform", "improve", "achieve", "demonstrate", "theorem", "prove"],
        1,
    )
    matched_topics = ", ".join(topic["name"] for topic in topics[:2])
    return {
        "takeaway": takeaway,
        "problem": sentences[0] if sentences else "",
        "method": method,
        "evidence": evidence,
        "limitations": "The abstract does not state complete limitations; verify the experimental setup, baselines, and scope before relying on the result.",
        "why_for_you": f"Matches your research profile: {matched_topics}." if matched_topics else "Retained as an exploration paper.",
        "source": "abstract",
        "generated_by": "extractive",
    }


def parse_model_summary(raw: str, generated_by: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    result = json.loads(match.group(0))
    required = {
        "takeaway",
        "problem",
        "method",
        "evidence",
        "limitations",
        "why_for_you",
    }
    if not required.issubset(result) or not all(
        isinstance(result.get(field), str) for field in required
    ):
        return None
    result["source"] = "abstract"
    result["generated_by"] = generated_by
    return result


def summary_prompt(paper: Paper, topics: list[dict[str, Any]]) -> str:
    topic_names = ", ".join(item["name"] for item in topics[:3])
    return f"""You write a morning research brief for an expert LLM researcher.
Use only the supplied title and abstract. Do not invent results, datasets,
baselines, numbers, or limitations. Return only a JSON object with string
fields: takeaway, problem, method, evidence, limitations, why_for_you.

Requirements:
- Each field is one concise technical sentence.
- takeaway states the actual contribution, not generic background.
- method says what the authors concretely do.
- evidence reports the evaluation or theorem; say "Not stated in the abstract"
  when details are absent.
- limitations distinguishes an author-stated limitation from missing evidence.
- why_for_you connects specifically to the supplied research interests.

Research interests: {topic_names}
Title: {paper.title}
Abstract: {paper.abstract}
"""


def condense_paper_text(text: str, max_chars: int = 18000) -> str:
    """Keep high-signal paper regions within hosted-model request limits."""
    if len(text) <= max_chars:
        return text
    lowered = text.lower()
    chunks: list[str] = [text[:5000]]
    used_positions = [0]
    headings = [
        "method",
        "approach",
        "algorithm",
        "experimental setup",
        "experiments",
        "evaluation",
        "results",
        "ablation",
        "mechanistic analysis",
        "limitations",
        "conclusion",
    ]
    for heading in headings:
        position = lowered.find(heading)
        if position < 0 or any(abs(position - used) < 2200 for used in used_positions):
            continue
        chunks.append(f"\n[{heading.upper()} REGION]\n{text[position : position + 2800]}")
        used_positions.append(position)
        if sum(len(chunk) for chunk in chunks) >= max_chars - 4000:
            break
    chunks.append(f"\n[ENDING REGION]\n{text[-3500:]}")
    return "\n".join(chunks)[:max_chars]


def extract_pdf_text(paper: Paper, max_chars: int = 18000) -> tuple[str, str]:
    """Download and extract selected-paper text, falling back to its abstract."""
    request = urllib.request.Request(paper.pdf_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read(25_000_001)
        if len(payload) > 25_000_000:
            raise ValueError("PDF exceeds the 25 MB analysis limit")
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "paper.pdf"
            text_path = Path(directory) / "paper.txt"
            pdf_path.write_bytes(payload)
            subprocess.run(
                [
                    "pdftotext",
                    "-f",
                    "1",
                    "-l",
                    "30",
                    "-nopgbrk",
                    str(pdf_path),
                    str(text_path),
                ],
                check=True,
                capture_output=True,
                timeout=90,
            )
            text = text_path.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) < 1500:
            raise ValueError("Extracted PDF text is too short")
        text = condense_paper_text(text, max_chars)
        return text, "selected full-text regions (up to 30 pages)"
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
        urllib.error.URLError,
    ) as error:
        print(f"Full-text extraction failed for {paper.id}: {error}", file=sys.stderr)
        return paper.abstract, "abstract"


def analysis_prompt(
    paper: Paper,
    topics: list[dict[str, Any]],
    paper_text: str,
    source_scope: str,
) -> str:
    topic_names = ", ".join(item["name"] for item in topics[:3])
    return f"""Analyze a research paper for an expert LLM researcher.
Use only the supplied paper text. Never invent models, datasets, baselines,
numbers, equations, findings, or limitations. Write in concise technical English.
Return only valid JSON matching this exact shape:
{{
  "brief": {{
    "takeaway": "one sentence",
    "problem": "one sentence",
    "method": "one sentence",
    "evidence": "one sentence",
    "limitations": "one sentence",
    "why_for_you": "one sentence"
  }},
  "deep_dive": {{
    "signals": [
      {{"icon": "🧠", "text": "specific finding"}},
      {{"icon": "🛡️", "text": "specific method"}},
      {{"icon": "📉", "text": "specific mechanism or evidence"}}
    ],
    "overview": "detailed synthesis",
    "methodology": [
      {{"title": "method component", "detail": "technical explanation"}}
    ],
    "mechanism": [
      {{"title": "mechanism or theory", "detail": "technical explanation"}}
    ],
    "experiments": [
      {{"title": "experimental component", "detail": "models, data, baselines, and metrics"}}
    ],
    "findings": [
      {{"title": "finding", "detail": "grounded result"}}
    ],
    "contributions": ["contribution"],
    "limitations": ["stated limitation or clearly labeled missing evidence"],
    "open_questions": ["important unresolved research question"]
  }}
}}

Requirements:
- Do not write generic statements such as "the paper studies" or "this is
  relevant to trustworthy AI" when a named method, mechanism, model, dataset,
  metric, baseline, or quantitative result is available.
- signals must contain exactly three complementary items of 25-45 words each.
  Every signal must include at least one paper-specific technical entity or
  concrete result.
- overview must be 140-220 words and explain the research question, thesis,
  approach, and strongest evidence as a connected argument.
- Use 3-5 methodology items of 50-90 words each. Explain purpose, procedure,
  inputs/outputs, training objective, and implementation choices when present.
- Use 1-4 mechanism items of 45-90 words each. Preserve equations and causal or
  geometric claims only when present; otherwise state that no mechanism is given.
- Use 2-5 experiment items of 45-85 words each. Name concrete models, datasets,
  baselines, metrics, evaluation protocol, and ablations when present.
- Use 3-6 findings of 40-80 words each and connect each claim to its evidence,
  including exact numerical results when available.
- Use 3-5 contributions, 2-4 limitations, and 2-4 open questions. Each item
  should be specific enough to guide a research discussion.
- If evidence is unavailable in the supplied text, say so explicitly.
- Do not treat arXiv publication as peer review.

Research interests: {topic_names}
Available source: {source_scope}
Title: {paper.title}
Abstract: {paper.abstract}

Paper text:
{paper_text}
"""


def prepare_deep_dive(
    deep_dive: Any,
    generated_by: str,
    source_scope: str,
) -> dict[str, Any] | None:
    if not isinstance(deep_dive, dict) or not isinstance(
        deep_dive.get("overview"), str
    ):
        return None
    required_lists = {
        "signals",
        "methodology",
        "mechanism",
        "experiments",
        "findings",
        "contributions",
        "limitations",
        "open_questions",
    }
    if (
        not all(isinstance(deep_dive.get(field), list) for field in required_lists)
        or len(deep_dive["signals"]) != 3
    ):
        return None
    for field in {"signals", "methodology", "mechanism", "experiments", "findings"}:
        if not all(
            isinstance(item, dict)
            and all(isinstance(value, str) for value in item.values())
            for item in deep_dive[field]
        ):
            return None
    if not all(
        isinstance(item, str)
        for field in {"contributions", "limitations", "open_questions"}
        for item in deep_dive[field]
    ):
        return None
    result = copy.deepcopy(deep_dive)
    result["source_scope"] = source_scope
    result["generated_by"] = generated_by
    result["schema_version"] = ANALYSIS_SCHEMA_VERSION
    return result


def parse_model_analysis(
    raw: str,
    generated_by: str,
    source_scope: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    payload = json.loads(match.group(0))
    brief = payload.get("brief")
    deep_dive = payload.get("deep_dive")
    if not isinstance(brief, dict) or not isinstance(deep_dive, dict):
        return None
    summary = parse_model_summary(json.dumps(brief), generated_by)
    prepared = prepare_deep_dive(deep_dive, generated_by, source_scope)
    if summary is None or prepared is None:
        return None
    return summary, prepared


def cloudflare_summary(paper: Paper, topics: list[dict[str, Any]]) -> dict[str, Any] | None:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        return None
    model = os.getenv("CLOUDFLARE_MODEL") or "@cf/meta/llama-3.2-3b-instruct"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    try:
        response = request_json(
            url,
            api_token,
            "POST",
            {"prompt": summary_prompt(paper, topics), "max_tokens": 700},
        )
        raw = response.get("result", {}).get("response", "")
        return parse_model_summary(raw, model)
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"AI summary failed for {paper.id}: {error}", file=sys.stderr)
        return None


def github_chat(token: str, body: dict[str, Any]) -> dict[str, Any]:
    url = "https://models.github.ai/inference/chat/completions"
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return request_json(url, token, "POST", body, timeout=180)
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(6 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == 2:
                raise
            time.sleep(12 * (attempt + 1))
    raise RuntimeError(f"GitHub Models request failed: {last_error}")


def github_analysis(
    paper: Paper,
    topics: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None
    primary_model = os.getenv("GITHUB_MODEL") or "openai/gpt-4.1-mini"
    fallback_model = os.getenv("GITHUB_FALLBACK_MODEL") or "openai/gpt-4o-mini"
    paper_text, source_scope = extract_pdf_text(paper)
    for model in dict.fromkeys([primary_model, fallback_model]):
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise research analyst. Ground every claim in the supplied text and return JSON only.",
                },
                {
                    "role": "user",
                    "content": analysis_prompt(
                        paper,
                        topics,
                        paper_text,
                        source_scope,
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
        }
        try:
            response = github_chat(token, body)
            raw = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            analysis = parse_model_analysis(raw, model, source_scope)
            if not analysis:
                print(
                    f"{model} returned an invalid analysis schema for {paper.id}",
                    file=sys.stderr,
                )
                continue
            return analysis
        except (
            OSError,
            RuntimeError,
            ValueError,
            urllib.error.URLError,
            IndexError,
        ) as error:
            print(f"{model} analysis failed for {paper.id}: {error}", file=sys.stderr)
    return None


def score_papers(
    papers: list[Paper],
    profile: dict[str, Any],
    feedback: list[dict[str, Any]],
    previous: list[set[str]],
    now: dt.datetime,
) -> list[dict[str, Any]]:
    ranking = profile["ranking"]
    positive_feedback, negative_feedback = feedback_corpora(feedback)
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for paper in papers:
        if paper.id in seen_ids:
            continue
        seen_ids.add(paper.id)
        lane, scope_score, scope_matches = scope_lane(paper, profile)
        if not lane:
            continue
        topics = topic_scores(paper, profile, scope_score, positive_feedback, negative_feedback)
        if not topics:
            continue
        relevance = clamp(topics[0]["score"] * 0.8 + min(sum(item["score"] for item in topics[1:3]), 1) * 0.2)
        quality, quality_reasons = quality_score(paper)
        novelty = novelty_score(paper, previous)
        freshness = freshness_score(paper, now)
        total = (
            relevance * float(ranking["relevance_weight"])
            + quality * float(ranking["quality_weight"])
            + novelty * float(ranking["novelty_weight"])
            + freshness * float(ranking["freshness_weight"])
        )
        if relevance < float(ranking.get("min_relevance", 0.0)):
            continue
        results.append(
            {
                "id": paper.id,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "published": paper.published,
                "updated": paper.updated,
                "categories": paper.categories,
                "primary_category": paper.primary_category,
                "abs_url": paper.abs_url,
                "pdf_url": paper.pdf_url,
                "comment": paper.comment,
                "journal_ref": paper.journal_ref,
                "lane": lane,
                "scope_matches": scope_matches,
                "topics": topics,
                "scores": {
                    "total": round(total, 4),
                    "relevance": round(relevance, 4),
                    "quality": round(quality, 4),
                    "novelty": round(novelty, 4),
                    "freshness": round(freshness, 4),
                },
                "quality_signals": quality_reasons,
                "_tokens": tokenize(paper.text()),
                "_paper": paper,
            }
        )
    return sorted(results, key=lambda item: item["scores"]["total"], reverse=True)


def diversify(scored: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    target = int(profile.get("feed_size", 6))
    transfer_limit = int(profile["scope"].get("transferable_daily_limit", 1))
    penalty = float(profile["ranking"].get("diversity_penalty", 0.18))
    selected: list[dict[str, Any]] = []
    remaining = list(scored)

    while remaining and len(selected) < target:
        allowed = [
            item
            for item in remaining
            if item["lane"] != "transferable"
            or sum(chosen["lane"] == "transferable" for chosen in selected) < transfer_limit
        ]
        if not allowed:
            break
        best = max(
            allowed,
            key=lambda item: item["scores"]["total"]
            - penalty
            * max((jaccard(item["_tokens"], chosen["_tokens"]) for chosen in selected), default=0.0),
        )
        selected.append(best)
        remaining.remove(best)

    # Guarantee a small emerging/watch lane when a relevant candidate exists.
    if selected:
        has_non_core = any(
            item["topics"][0]["status"] in {"emerging", "watch"} for item in selected
        )
        candidate = next(
            (
                item
                for item in scored
                if item not in selected
                and item["topics"][0]["status"] in {"emerging", "watch"}
                and item["scores"]["relevance"] >= 0.18
            ),
            None,
        )
        if not has_non_core and candidate:
            selected[-1] = candidate
    return selected


def serialize_item(
    item: dict[str, Any],
    use_ai: bool,
    previous_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paper: Paper = item.pop("_paper")
    item.pop("_tokens", None)
    summary = None
    deep_dive = None
    if use_ai:
        unchanged = bool(
            previous_item
            and previous_item.get("title") == paper.title
            and previous_item.get("abstract") == paper.abstract
        )
        cached_deep_dive = (
            (previous_item or {}).get("deep_dive") if unchanged else None
        )
        if cached_deep_dive:
            deep_dive = prepare_deep_dive(
                cached_deep_dive,
                cached_deep_dive.get("generated_by", "cached analysis"),
                cached_deep_dive.get("source_scope", "available source"),
            )
        if deep_dive:
            cached_summary = (previous_item or {}).get("summary")
            if isinstance(cached_summary, dict):
                required_summary = {
                    "takeaway",
                    "problem",
                    "method",
                    "evidence",
                    "limitations",
                    "why_for_you",
                }
                if required_summary.issubset(cached_summary) and all(
                    isinstance(cached_summary.get(field), str)
                    for field in required_summary
                ):
                    summary = copy.deepcopy(cached_summary)
        else:
            try:
                analysis = github_analysis(paper, item["topics"])
            except Exception as error:
                print(
                    f"AI analysis crashed for {paper.id}; falling back to extractive summary: {error}",
                    file=sys.stderr,
                )
                analysis = None
            if analysis:
                summary, deep_dive = analysis
            else:
                try:
                    summary = cloudflare_summary(paper, item["topics"])
                except Exception as error:
                    print(
                        f"Cloudflare summary crashed for {paper.id}; falling back to extractive summary: {error}",
                        file=sys.stderr,
                    )
    item["summary"] = summary or extractive_summary(paper, item["topics"])
    if deep_dive:
        item["deep_dive"] = deep_dive
    item["recommendation_reason"] = {
        "topic": item["topics"][0]["name"],
        "matched": item["topics"][0]["matched"][:4],
        "lane": item["lane"],
    }
    return item


def rewrite_existing(
    profile_path: Path,
    output_path: Path,
    interests_path: Path | None = DEFAULT_INTERESTS,
) -> int:
    """Refresh generated summaries/profile without fetching new papers."""
    profile = load_profile(profile_path, interests_path)
    data_dir = output_path.parent
    paths = [
        data_dir / "papers.json",
        data_dir / "weekly.json",
        data_dir / "history.json",
        *sorted((data_dir / "archive").glob("*.json")),
    ]
    rewritten = 0
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("papers", []):
            paper = Paper(
                id=item.get("id", ""),
                title=item.get("title", ""),
                abstract=item.get("abstract", ""),
                authors=item.get("authors", []),
                published=item.get("published", ""),
                updated=item.get("updated", ""),
                categories=item.get("categories", []),
                primary_category=item.get("primary_category", ""),
                abs_url=item.get("abs_url", ""),
                pdf_url=item.get("pdf_url", ""),
                comment=item.get("comment", ""),
                journal_ref=item.get("journal_ref", ""),
            )
            item["summary"] = extractive_summary(paper, item.get("topics", []))
            rewritten += 1
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    public_profile = dict(profile)
    public_profile.pop("owner", None)
    (data_dir / "profile.json").write_text(
        json.dumps(public_profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return rewritten


def build(
    profile_path: Path,
    output_path: Path,
    atom_fixture: Path | None = None,
    now: dt.datetime | None = None,
    use_ai: bool = True,
    reset_history: bool = False,
    interests_path: Path | None = DEFAULT_INTERESTS,
) -> dict[str, Any]:
    now = now or utc_now()
    profile = load_profile(profile_path, interests_path)
    feedback = load_feedback()
    if atom_fixture:
        payload = atom_fixture.read_bytes()
        query_total = atom_total_results(payload)
    else:
        payload, query_total = fetch_arxiv(profile, now)
    papers = parse_atom(payload)
    previous = load_previous_papers(output_path)
    previous_items = load_previous_items(output_path)
    seen_ids = load_seen_paper_ids(output_path)
    unseen_papers = [paper for paper in papers if paper.id not in seen_ids]
    scored = score_papers(unseen_papers, profile, feedback, previous, now)
    selected = diversify(scored, profile)
    serialized = [
        serialize_item(
            item,
            use_ai,
            previous_items.get(item["id"]),
        )
        for item in selected
    ]
    feed = {
        "schema_version": 1,
        "demo": bool(atom_fixture),
        "generated_at": now.isoformat(),
        "profile_updated_at": profile.get("updated_at"),
        "source_count": len(papers),
        "source_total": query_total,
        "source_truncated": query_total > len(papers),
        "unseen_source_count": len(unseen_papers),
        "previously_recommended_count": len(seen_ids),
        "eligible_count": len(scored),
        "feedback_count": len(feedback),
        "papers": serialized,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    seen_ids.update(item["id"] for item in serialized)
    seen_path = output_path.parent / "seen.json"
    seen_path.write_text(
        json.dumps(
            {
                "updated_at": now.isoformat(),
                "paper_ids": sorted(seen_ids),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    history_path = output_path.parent / "history.json"
    if reset_history:
        old_history = []
    else:
        try:
            old_history = json.loads(history_path.read_text(encoding="utf-8")).get("papers", [])
        except (OSError, ValueError):
            old_history = []
    merged_history: dict[str, dict[str, Any]] = {
        item["id"]: item for item in old_history if item.get("id")
    }
    for item in serialized:
        history_item = dict(item)
        history_item["recommended_at"] = now.isoformat()
        merged_history[item["id"]] = history_item
    history_items = sorted(
        merged_history.values(),
        key=lambda item: item.get("recommended_at", item.get("published", "")),
        reverse=True,
    )[:100]
    history = {"generated_at": now.isoformat(), "papers": history_items}
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    week_start = now - dt.timedelta(days=7)
    weekly_items = [
        item
        for item in history_items
        if parse_date(item.get("recommended_at", item.get("published", ""))) >= week_start
    ]
    weekly_items.sort(key=lambda item: item.get("scores", {}).get("total", 0), reverse=True)
    weekly = {
        "generated_at": now.isoformat(),
        "papers": weekly_items[: int(profile.get("weekly_size", 12))],
    }
    (output_path.parent / "weekly.json").write_text(
        json.dumps(weekly, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    public_profile = dict(profile)
    public_profile.pop("owner", None)
    profile_output = output_path.parent / "profile.json"
    profile_output.write_text(
        json.dumps(public_profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    archive_dir = output_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{now.date().isoformat()}.json"
    archive_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return feed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--interests",
        type=Path,
        default=DEFAULT_INTERESTS,
        help="Simple one-topic-per-line interest file",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture", type=Path, help="Use a local Atom file instead of the network")
    parser.add_argument("--now", help="Override current time with an ISO-8601 value")
    parser.add_argument("--no-ai", action="store_true", help="Always use extractive summaries")
    parser.add_argument(
        "--reset-history",
        action="store_true",
        help="Start weekly/history data from this run",
    )
    parser.add_argument(
        "--rewrite-existing",
        action="store_true",
        help="Refresh existing generated summaries/profile without fetching arXiv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.rewrite_existing:
        count = rewrite_existing(args.profile, args.output, args.interests)
        print(f"Rewrote {count} existing paper summaries.")
        return 0
    now = parse_date(args.now) if args.now else None
    feed = build(
        args.profile,
        args.output,
        args.fixture,
        now,
        use_ai=not args.no_ai,
        reset_history=args.reset_history,
        interests_path=args.interests,
    )
    print(
        f"Generated {len(feed['papers'])} recommendations "
        f"from {feed['source_count']} source papers "
        f"({feed['unseen_source_count']} unseen, "
        f"{feed['eligible_count']} eligible, "
        f"{feed['previously_recommended_count']} previously recommended)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
