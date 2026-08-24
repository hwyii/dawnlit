#!/usr/bin/env python3
"""Build a personalized, explainable daily research-paper feed.

The default pipeline uses only the Python standard library.  Optional remote
profile/feedback sync and Cloudflare Workers AI summaries are enabled through
environment variables documented in README.md.
"""

from __future__ import annotations

import argparse
import copy
import csv
import dataclasses
import datetime as dt
import html
import io
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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "profile.json"
DEFAULT_INTERESTS = ROOT / "config" / "interests.txt"
DEFAULT_OUTPUT = ROOT / "public" / "data" / "papers.json"
DEFAULT_PROFILE_OUTPUT = ROOT / "public" / "data" / "profile.json"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"
CONFERENCE_CACHE_SCHEMA_VERSION = 1
CONFERENCE_VIRTUAL_HOSTS = {
    "ICLR": "https://iclr.cc",
    "ICML": "https://icml.cc",
    "NeurIPS": "https://neurips.cc",
}
CONFERENCE_FETCH_TIMEOUT_SECONDS = 35
CONFERENCE_MAX_RESPONSE_BYTES = 16_000_000
USER_AGENT = "dawnlit/0.1 (personal research discovery; contact: hwyii.github.io)"
ARXIV_MAX_ATTEMPTS = 6
ARXIV_HTTP_BACKOFF_SECONDS = (30, 60, 120, 240, 300)
ARXIV_NETWORK_BACKOFF_SECONDS = (15, 30, 60, 120, 240)
CLOUDFLARE_RETRY_DELAYS = (20, 60)

ATOM = {"a": "http://www.w3.org/2005/Atom"}
ARXIV = {"arxiv": "http://arxiv.org/schemas/atom"}
OPENSEARCH = {"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}

TOKEN_RE = re.compile(r"[a-z][a-z0-9+\-]{2,}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
ANALYSIS_SCHEMA_VERSION = 6
SUMMARY_SCHEMA_VERSION = 3
ANALYSIS_PROMPT_VERSION = 2
SUMMARY_PROMPT_VERSION = 2

# Language-focused work is outside this radar even when it uses LLM safety,
# robustness, distillation, or data-selection terminology. Match these only in
# the title and opening abstract sentences so incidental benchmark mentions do
# not hide an otherwise relevant paper.
DEFAULT_EXCLUDED_LANGUAGE_FOCUS = (
    "multilingual",
    "multilinguality",
    "multi-lingual",
    "cross-lingual",
    "crosslingual",
    "cross-language",
    "bilingual",
    "code-switching",
    "code switching",
    "machine translation",
    "translation model",
    "translation models",
    "low-resource language",
    "low-resource languages",
    "low-resource nlp",
    "language-specific",
    "language-agnostic",
    "language diversity",
    "linguistic diversity",
    "arabic",
    "chinese",
    "english",
    "bengali",
    "dutch",
    "french",
    "german",
    "hindi",
    "hebrew",
    "indonesian",
    "japanese",
    "korean",
    "italian",
    "persian",
    "polish",
    "portuguese",
    "russian",
    "spanish",
    "swahili",
    "tamil",
    "telugu",
    "thai",
    "turkish",
    "urdu",
    "vietnamese",
)

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
    source: str = "arxiv"
    venue: str = ""
    presentation: str = ""
    conference_year: int | None = None

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


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write generated state atomically so interrupted builds keep the last good file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def request_json(
    url: str,
    token: str | None = None,
    method: str = "GET",
    body: Any = None,
    timeout: int = 45,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def cloudflare_available() -> bool:
    return bool(
        (
            os.getenv("RADAR_API_URL")
            and os.getenv("RADAR_ADMIN_TOKEN")
        )
        or (
            os.getenv("CLOUDFLARE_ACCOUNT_ID")
            and os.getenv("CLOUDFLARE_API_TOKEN")
        )
    )


def cloudflare_inference(
    model: str,
    body: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    """Run Workers AI through the personal Worker, or direct credentials."""
    api_url = os.getenv("RADAR_API_URL", "").rstrip("/")
    admin_token = os.getenv("RADAR_ADMIN_TOKEN")
    if api_url and admin_token:
        try:
            return request_json(
                f"{api_url}/api/ai/run",
                admin_token,
                "POST",
                {"model": model, "input": body},
                timeout=timeout,
            )
        except urllib.error.HTTPError as error:
            if error.code < 500:
                raise
            if not (
                os.getenv("CLOUDFLARE_ACCOUNT_ID")
                and os.getenv("CLOUDFLARE_API_TOKEN")
            ):
                raise
            print(
                f"Worker AI returned HTTP {error.code}; trying direct Cloudflare API.",
                file=sys.stderr,
            )
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        raise RuntimeError("Cloudflare AI credentials are unavailable")
    return request_json(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        api_token,
        "POST",
        body,
        timeout=timeout,
    )


def cloudflare_inference_with_retry(
    model: str,
    body: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    """Retry transient Workers AI failures before degrading generated content."""
    last_error: Exception | None = None
    for attempt in range(len(CLOUDFLARE_RETRY_DELAYS) + 1):
        try:
            return cloudflare_inference(model, body, timeout)
        except urllib.error.HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504}:
                raise
            last_error = error
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            last_error = error
        if attempt == len(CLOUDFLARE_RETRY_DELAYS):
            break
        delay = CLOUDFLARE_RETRY_DELAYS[attempt]
        print(
            f"Cloudflare AI request failed for {model}; retrying in {delay}s: "
            f"{last_error}",
            file=sys.stderr,
        )
        time.sleep(delay)
    assert last_error is not None
    raise last_error


def cloudflare_response_text(response: dict[str, Any]) -> str:
    """Normalize Workers AI REST and binding response envelopes."""
    result = response.get("result", {})
    raw = result.get("response")
    if raw is None:
        raw = (
            (result.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    return json.dumps(raw) if isinstance(raw, dict) else str(raw or "")


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
    local_profile = json.loads(path.read_text(encoding="utf-8"))
    interests = parse_interests(interests_path)
    profile = apply_interests(local_profile, interests)
    api_url = os.getenv("RADAR_API_URL", "").rstrip("/")
    api_token = os.getenv("RADAR_ADMIN_TOKEN")
    if api_url and api_token:
        try:
            remote = request_json(f"{api_url}/api/profile", api_token)
            if isinstance(remote, dict) and remote.get("topics"):
                profile = copy.deepcopy(remote)
                # Repository guardrails and the simple interest list remain
                # authoritative for scheduled builds. Remote preferences still
                # provide UI/content language, ranking, and other settings.
                profile.setdefault("scope", {})["excluded_language_focus"] = list(
                    local_profile.get("scope", {}).get(
                        "excluded_language_focus",
                        DEFAULT_EXCLUDED_LANGUAGE_FOCUS,
                    )
                )
                profile["conference_fallback"] = copy.deepcopy(
                    local_profile.get("conference_fallback", {})
                )
                profile["feedback_tuning"] = copy.deepcopy(
                    local_profile.get("feedback_tuning", {})
                )
                local_topics = {
                    topic.get("id"): topic
                    for topic in local_profile.get("topics", [])
                    if topic.get("id")
                }
                guardrail_fields = {
                    "required_any",
                    "required_central_any",
                    "required_all_groups",
                    "exclude",
                }
                for topic in profile.get("topics", []):
                    local_topic = local_topics.get(topic.get("id"), {})
                    for field in guardrail_fields:
                        if field in local_topic:
                            topic[field] = copy.deepcopy(local_topic[field])
                profile = apply_interests(profile, interests)
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
        result = request_json(f"{api_url}/api/feedback?limit=1000", api_token)
        return result.get("items", []) if isinstance(result, dict) else []
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"Feedback sync unavailable: {error}", file=sys.stderr)
        return []


def effective_lookback_days(profile: dict[str, Any], now: dt.datetime) -> int:
    """Bridge arXiv's quiet weekend with a wider pool of unseen papers."""
    configured = max(1, int(profile["retrieval"].get("lookback_days", 4)))
    if now.weekday() in {5, 6, 0}:
        return max(configured, 4)
    return configured


def build_arxiv_url(
    profile: dict[str, Any],
    now: dt.datetime,
    start: int = 0,
    page_size: int | None = None,
) -> str:
    retrieval = profile["retrieval"]
    category_query = " OR ".join(f"cat:{category}" for category in retrieval["categories"])
    start_date = now - dt.timedelta(days=effective_lookback_days(profile, now))
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
    for attempt in range(ARXIV_MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last_error = error
            if (
                error.code not in {429, 500, 502, 503, 504}
                or attempt == ARXIV_MAX_ATTEMPTS - 1
            ):
                break
            retry_after = error.headers.get("Retry-After")
            delay = (
                max(1, min(int(retry_after), ARXIV_HTTP_BACKOFF_SECONDS[-1]))
                if retry_after and retry_after.isdigit()
                else ARXIV_HTTP_BACKOFF_SECONDS[attempt]
            )
            print(
                f"arXiv returned HTTP {error.code}; retrying in {delay}s",
                file=sys.stderr,
            )
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < ARXIV_MAX_ATTEMPTS - 1:
                delay = ARXIV_NETWORK_BACKOFF_SECONDS[attempt]
                print(
                    f"arXiv request failed; retrying in {delay}s: {error}",
                    file=sys.stderr,
                )
                time.sleep(delay)
    raise RuntimeError(
        f"Unable to fetch arXiv after {ARXIV_MAX_ATTEMPTS} attempts: {last_error}"
    )


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


class ConferenceEventParser(HTMLParser):
    """Parse official virtual-conference event cards without third-party packages."""

    def __init__(self, base_url: str, venue: str, year: int, presentation: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.venue = venue
        self.year = year
        self.presentation = presentation.title()
        self.papers: list[Paper] = []
        self.event: dict[str, Any] | None = None
        self.event_depth = 0
        self.capture_field: str | None = None
        self.capture_depth = 0

    @staticmethod
    def _classes(attrs: dict[str, str | None]) -> set[str]:
        return set((attrs.get("class") or "").split())

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        attrs = dict(attributes)
        classes = self._classes(attrs)
        if self.event is None:
            if tag == "div" and "event-card" in classes:
                event_id = normalize_space(attrs.get("data-event-id"))
                if not event_id:
                    event_id = normalize_space(attrs.get("id")).removeprefix("event-")
                if event_id:
                    self.event = {
                        "event_id": event_id,
                        "title": [],
                        "authors": [],
                        "abstract": [],
                        "href": "",
                    }
                    self.event_depth = 1
            return

        if tag == "div":
            self.event_depth += 1
        if self.capture_field is not None:
            self.capture_depth += 1
        elif tag == "h3" and "event-title" in classes:
            self.capture_field = "title"
            self.capture_depth = 1
        elif tag == "div" and "event-speakers" in classes:
            self.capture_field = "authors"
            self.capture_depth = 1
        elif tag == "div" and "abstract-text" in classes:
            self.capture_field = "abstract"
            self.capture_depth = 1
        if tag == "a" and self.capture_field == "title" and attrs.get("href"):
            self.event["href"] = attrs["href"]

    def handle_data(self, data: str) -> None:
        if self.event is not None and self.capture_field is not None:
            self.event[self.capture_field].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.event is None:
            return
        if self.capture_field is not None:
            self.capture_depth -= 1
            if self.capture_depth == 0:
                self.capture_field = None
        if tag == "div":
            self.event_depth -= 1
            if self.event_depth == 0:
                self._finish_event()

    def _finish_event(self) -> None:
        assert self.event is not None
        title = normalize_space(" ".join(self.event["title"]))
        abstract = normalize_space(" ".join(self.event["abstract"]))
        author_text = normalize_space(" ".join(self.event["authors"]))
        if title and abstract:
            event_id = self.event["event_id"]
            href = urllib.parse.urljoin(self.base_url, self.event["href"])
            authors = [
                normalize_space(author)
                for author in re.split(r"\s*[⋅·]\s*", author_text)
                if normalize_space(author)
            ]
            published = f"{self.year}-01-01T00:00:00Z"
            self.papers.append(
                Paper(
                    id=f"conf:{self.venue.lower()}:{self.year}:{event_id}",
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    published=published,
                    updated=published,
                    categories=[f"{self.venue} {self.year}", self.presentation],
                    primary_category=f"{self.venue} {self.year}",
                    abs_url=href,
                    pdf_url=href,
                    journal_ref=f"{self.venue} {self.year} {self.presentation}",
                    source="conference",
                    venue=self.venue,
                    presentation=self.presentation,
                    conference_year=self.year,
                )
            )
        self.event = None
        self.event_depth = 0
        self.capture_field = None
        self.capture_depth = 0


def parse_conference_event_page(
    payload: bytes,
    base_url: str,
    venue: str,
    year: int,
    presentation: str,
) -> list[Paper]:
    parser = ConferenceEventParser(base_url, venue, year, presentation)
    parser.feed(payload.decode("utf-8", errors="replace"))
    parser.close()
    return parser.papers


def discover_conference_event_urls(
    payload: bytes,
    base_url: str,
    allowed_presentations: set[str],
) -> list[tuple[str, str]]:
    """Find the conference's own Oral/Spotlight navigation targets."""
    source = payload.decode("utf-8", errors="replace")
    discovered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, inner in re.findall(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        label = normalize_space(re.sub(r"<[^>]+>", " ", inner)).lower()
        presentation = ""
        if "oral" in label:
            presentation = "oral"
        elif "spotlight" in label:
            presentation = "spotlight"
        if (
            not presentation
            or presentation not in allowed_presentations
            or "/events/" not in href
        ):
            continue
        url = urllib.parse.urljoin(base_url, html.unescape(href))
        key = f"{presentation}:{url}"
        if key not in seen:
            seen.add(key)
            discovered.append((presentation, url))
    return discovered


def parse_acl_schedule_csv(
    payload: bytes,
    venue: str,
    year: int,
    landing_url: str,
) -> list[Paper]:
    """Parse an ACL-family schedule export, accepting explicit Oral sessions only."""
    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig", errors="replace"))))
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row and normalize_space(row[0]).lower() == "paper number"
        ),
        None,
    )
    if header_index is None:
        raise ValueError("No ACL schedule header found")
    headers = [normalize_space(value).lower() for value in rows[header_index]]
    papers: list[Paper] = []
    for values in rows[header_index + 1 :]:
        row = {
            header: normalize_space(values[index] if index < len(values) else "")
            for index, header in enumerate(headers)
        }
        session_name = row.get("underline/whova session name", "")
        if not session_name.lower().startswith("oral session"):
            continue
        paper_number = row.get("paper number", "")
        title = row.get("title", "")
        abstract = row.get("abstract", "")
        if not paper_number or not title or not abstract:
            continue
        author_text = row.get("authors names", "").rstrip(";")
        authors = [normalize_space(value) for value in author_text.split(",") if value.strip()]
        published = f"{year}-01-01T00:00:00Z"
        stable_number = re.sub(r"[^a-z0-9.-]+", "-", paper_number.lower()).strip("-")
        papers.append(
            Paper(
                id=f"conf:{venue.lower()}:{year}:{stable_number}",
                title=title,
                abstract=abstract,
                authors=authors,
                published=published,
                updated=published,
                categories=[f"{venue} {year}", "Oral"],
                primary_category=f"{venue} {year}",
                abs_url=landing_url,
                pdf_url=landing_url,
                journal_ref=f"{venue} {year} Oral",
                source="conference",
                venue=venue,
                presentation="Oral",
                conference_year=year,
            )
        )
    return papers


def fetch_conference_url(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(
        request,
        timeout=CONFERENCE_FETCH_TIMEOUT_SECONDS,
    ) as response:
        payload = response.read(CONFERENCE_MAX_RESPONSE_BYTES + 1)
        if len(payload) > CONFERENCE_MAX_RESPONSE_BYTES:
            raise ValueError(f"Conference response exceeds size limit: {url}")
        return payload, response.geturl()


def paper_from_dict(item: dict[str, Any]) -> Paper:
    fields = {field.name for field in dataclasses.fields(Paper)}
    values: dict[str, Any] = {
        "id": "",
        "title": "",
        "abstract": "",
        "authors": [],
        "published": "",
        "updated": "",
        "categories": [],
        "primary_category": "",
        "abs_url": "",
        "pdf_url": "",
    }
    values.update({key: value for key, value in item.items() if key in fields})
    return Paper(**values)


def load_conference_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") == CONFERENCE_CACHE_SCHEMA_VERSION:
            return payload
    except (OSError, ValueError, TypeError):
        pass
    return {
        "schema_version": CONFERENCE_CACHE_SCHEMA_VERSION,
        "updated_at": "",
        "profile_updated_at": "",
        "scanned_years": [],
        "source_status": {},
        "papers": [],
    }


def cached_conference_papers(cache: dict[str, Any]) -> list[Paper]:
    papers: list[Paper] = []
    for item in cache.get("papers", []):
        if not isinstance(item, dict):
            continue
        try:
            paper = paper_from_dict(item)
        except (TypeError, ValueError):
            continue
        if paper.source == "conference" and paper.id:
            papers.append(paper)
    return papers


def conference_candidate_matches_profile(paper: Paper, profile: dict[str, Any]) -> bool:
    lane, scope_score, _ = scope_lane(paper, profile)
    if not lane:
        return False
    topics = topic_scores(paper, profile, scope_score, [], [])
    if not topics:
        return False
    relevance = clamp(
        topics[0]["score"] * 0.8
        + min(sum(item["score"] for item in topics[1:3]), 1) * 0.2
    )
    return relevance >= float(profile["ranking"].get("min_relevance", 0.0))


def fetch_conference_year(
    profile: dict[str, Any],
    year: int,
) -> tuple[list[Paper], dict[str, str]]:
    settings = profile.get("conference_fallback", {})
    allowed_venues = set(settings.get("venues", []))
    allowed_presentations = {
        str(value).lower() for value in settings.get("presentation_types", ["oral", "spotlight"])
    }
    papers: list[Paper] = []
    status: dict[str, str] = {}

    for venue, host in CONFERENCE_VIRTUAL_HOSTS.items():
        if venue not in allowed_venues:
            continue
        source_key = f"{venue}:{year}"
        index_url = f"{host}/virtual/{year}/papers.html"
        try:
            index_payload, final_url = fetch_conference_url(index_url)
            event_urls = discover_conference_event_urls(
                index_payload,
                final_url,
                allowed_presentations,
            )
            count = 0
            for presentation, event_url in event_urls:
                event_payload, event_final_url = fetch_conference_url(event_url)
                parsed = parse_conference_event_page(
                    event_payload,
                    event_final_url,
                    venue,
                    year,
                    presentation,
                )
                papers.extend(parsed)
                count += len(parsed)
            status[source_key] = f"ok:{count}"
        except (OSError, ValueError, urllib.error.URLError, TimeoutError) as error:
            status[source_key] = f"unavailable:{type(error).__name__}"
            print(f"Conference source unavailable ({source_key}): {error}", file=sys.stderr)

    for source in settings.get("verified_schedule_csv", []):
        if not isinstance(source, dict):
            continue
        venue = str(source.get("venue", ""))
        source_year = int(source.get("year", 0) or 0)
        if venue not in allowed_venues or source_year != year:
            continue
        source_key = f"{venue}:{year}"
        try:
            payload, _ = fetch_conference_url(str(source["url"]))
            parsed = parse_acl_schedule_csv(
                payload,
                venue,
                year,
                str(source.get("landing_url") or source["url"]),
            )
            papers.extend(parsed)
            status[source_key] = f"ok:{len(parsed)}"
        except (KeyError, OSError, ValueError, urllib.error.URLError, TimeoutError) as error:
            status[source_key] = f"unavailable:{type(error).__name__}"
            print(f"Conference source unavailable ({source_key}): {error}", file=sys.stderr)

    for venue in allowed_venues:
        status.setdefault(f"{venue}:{year}", "awaiting_verified_schedule")

    unique = {paper.id: paper for paper in papers if conference_candidate_matches_profile(paper, profile)}
    return list(unique.values()), status


def sync_conference_cache(
    path: Path,
    profile: dict[str, Any],
    now: dt.datetime,
    seen_ids: set[str],
    reserve_target: int,
) -> dict[str, Any]:
    settings = profile.get("conference_fallback", {})
    cache = load_conference_cache(path)
    cached = {paper.id: paper for paper in cached_conference_papers(cache)}
    configured_start_year = settings.get("start_year", "current")
    start_year = (
        now.year
        if str(configured_start_year).lower() == "current"
        else min(int(configured_start_year), now.year)
    )
    min_year = min(start_year, int(settings.get("min_year", start_year - 4)))
    scanned = {int(year) for year in cache.get("scanned_years", [])}
    profile_changed = cache.get("profile_updated_at") != profile.get("updated_at")
    try:
        cache_age = now - parse_date(cache.get("updated_at", ""))
        stale = cache_age > dt.timedelta(days=int(settings.get("cache_ttl_days", 7)))
    except (TypeError, ValueError):
        stale = True

    currently_available = sum(
        paper.id not in seen_ids
        and conference_candidate_matches_profile(paper, profile)
        for paper in cached.values()
    )
    if not stale and not profile_changed and currently_available >= reserve_target:
        return cache

    years: list[int] = []
    if stale or profile_changed:
        years.append(start_year)
    years.extend(
        year
        for year in range(start_year, min_year - 1, -1)
        if year not in scanned and year not in years
    )
    source_status = dict(cache.get("source_status", {}))
    successful_scan = False
    for year in years:
        fetched, status = fetch_conference_year(profile, year)
        source_status.update(status)
        if any(value.startswith("ok:") for value in status.values()):
            successful_scan = True
            if stale or profile_changed:
                refreshed_venues = {
                    key.rsplit(":", 1)[0]
                    for key, value in status.items()
                    if value.startswith("ok:")
                }
                cached = {
                    paper_id: paper
                    for paper_id, paper in cached.items()
                    if not (
                        paper.conference_year == year
                        and paper.venue in refreshed_venues
                    )
                }
            cached.update({paper.id: paper for paper in fetched})
            scanned.add(year)
        available = sum(
            paper.id not in seen_ids
            and conference_candidate_matches_profile(paper, profile)
            for paper in cached.values()
        )
        if available >= reserve_target:
            break

    if successful_scan or not path.exists():
        cache = {
            "schema_version": CONFERENCE_CACHE_SCHEMA_VERSION,
            "updated_at": now.isoformat(),
            "profile_updated_at": profile.get("updated_at"),
            "scanned_years": sorted(scanned, reverse=True),
            "source_status": source_status,
            "papers": [
                dataclasses.asdict(paper)
                for paper in sorted(
                    cached.values(),
                    key=lambda paper: (
                        paper.conference_year or 0,
                        paper.presentation.lower() == "oral",
                        paper.title.lower(),
                    ),
                    reverse=True,
                )
            ],
        }
        write_json_atomic(path, cache)
    return cache


def scope_lane(paper: Paper, profile: dict[str, Any]) -> tuple[str | None, float, list[str]]:
    scope = profile["scope"]
    title = paper.title.lower()
    text = paper.text().lower()
    abstract_opening = " ".join(split_sentences(paper.abstract)[:2]).lower()
    central_text = f"{title}. {abstract_opening}"
    language_focus_terms = scope.get(
        "excluded_language_focus",
        DEFAULT_EXCLUDED_LANGUAGE_FOCUS,
    )
    language_focus_hits = [
        term for term in language_focus_terms if contains_term(central_text, term)
    ]
    if language_focus_hits:
        return None, 0.0, language_focus_hits[:5]
    excluded = [term for term in scope.get("excluded_concepts", []) if contains_term(text, term)]
    central_excluded = [term for term in excluded if contains_term(central_text, term)]
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
    strong_title_terms = [
        term
        for term in scope.get("required_concepts", [])
        if term not in {"foundation model", "foundation models", "transformer", "transformers"}
    ]
    title_llm_hits = [term for term in strong_title_terms if contains_term(title, term)]
    direct_llm_mentions = len(
        re.findall(
            r"(?<![a-z0-9])(?:llms?|large[- ]language models?)(?![a-z0-9])",
            text,
        )
    )
    central_llm_work = bool(title_llm_hits) or direct_llm_mentions >= 2 or (
        paper.primary_category in {"cs.CL", "cs.LG"} and direct_llm_mentions >= 1
    )

    if central_excluded or (excluded and not strong_llm_hits):
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


FeedbackSignal = tuple[set[str], float]


def feedback_corpora(
    feedback: list[dict[str, Any]],
    now: dt.datetime | None = None,
) -> tuple[list[FeedbackSignal], list[FeedbackSignal]]:
    """Build action-weighted, time-decayed lexical preference signals."""
    positives: list[FeedbackSignal] = []
    negatives: list[FeedbackSignal] = []
    reference_time = now or dt.datetime.now(dt.timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=dt.timezone.utc)
    action_weights = {
        "save": 1.0,
        "useful": 1.0,
        "read": 0.45,
        "more_method": 1.15,
        "more_topic": 1.15,
        "transferable": 0.7,
        "not_useful": -0.65,
        "not_llm": -1.25,
        "irrelevant": -1.25,
    }
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
        strength = action_weights.get(action, 0.0)
        try:
            created_at = parse_date(str(item.get("created_at", "")))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=dt.timezone.utc)
            age_days = max(
                0.0,
                (reference_time - created_at).total_seconds() / 86400,
            )
        except (TypeError, ValueError):
            age_days = 0.0
        decay = 0.5 ** (age_days / 120.0)
        weighted_strength = abs(strength) * decay
        if strength > 0:
            positives.append((tokens, weighted_strength))
        elif strength < 0:
            negatives.append((tokens, weighted_strength))
    return positives, negatives


def feedback_topic_ids(item: dict[str, Any]) -> list[str]:
    raw_topics = item.get("topics", [])
    if isinstance(raw_topics, str):
        try:
            raw_topics = json.loads(raw_topics)
        except ValueError:
            raw_topics = []
    if not isinstance(raw_topics, list):
        return []
    return list(
        dict.fromkeys(
            str(topic_id).strip()
            for topic_id in raw_topics
            if str(topic_id).strip()
        )
    )


def apply_topic_feedback_tuning(
    profile: dict[str, Any],
    feedback: list[dict[str, Any]],
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive bounded topic weights from each paper's latest explicit label.

    Manual ``weight`` remains the stable baseline. The derived
    ``effective_weight`` is rebuilt from scratch on every run, so an unchanged
    feedback set cannot compound adjustments across daily builds.
    """
    result = copy.deepcopy(profile)
    settings = result.get("feedback_tuning", {})
    enabled = bool(settings.get("enabled", False))
    reference_time = now or utc_now()
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=dt.timezone.utc)
    positive_actions = {
        str(action) for action in settings.get("positive_actions", ["useful", "save"])
    }
    negative_actions = {
        str(action) for action in settings.get("negative_actions", ["irrelevant"])
    }
    half_life_days = max(1.0, float(settings.get("half_life_days", 120)))
    minimum_samples = max(
        0.0,
        float(settings.get("minimum_effective_samples", 4)),
    )
    full_confidence_samples = max(
        minimum_samples or 1.0,
        float(settings.get("full_confidence_samples", 12)),
    )
    secondary_credit = clamp(float(settings.get("secondary_topic_credit", 0.5)))
    prior_strength = max(0.0, float(settings.get("prior_strength", 4)))
    target_hit_rate = clamp(float(settings.get("target_hit_rate", 0.5)))
    learning_rate = max(0.0, float(settings.get("learning_rate", 0.8)))
    max_adjustment = max(0.0, float(settings.get("max_adjustment", 0.15)))
    minimum_weight = clamp(float(settings.get("minimum_weight", 0.2)))
    maximum_weight = clamp(float(settings.get("maximum_weight", 1.0)))
    if minimum_weight > maximum_weight:
        minimum_weight, maximum_weight = maximum_weight, minimum_weight

    topic_ids = {
        str(topic.get("id"))
        for topic in result.get("topics", [])
        if topic.get("id")
    }
    accumulated = {
        topic_id: {
            "useful": 0.0,
            "irrelevant": 0.0,
            "effective_useful": 0.0,
            "effective_irrelevant": 0.0,
        }
        for topic_id in topic_ids
    }
    latest_seen: set[str] = set()
    labeled_papers = 0
    ordered = sorted(feedback, key=lambda item: item.get("created_at", ""), reverse=True)
    for item in ordered:
        paper_id = str(item.get("paper_id", "")).strip()
        if not paper_id or paper_id in latest_seen:
            continue
        latest_seen.add(paper_id)
        action = str(item.get("action", ""))
        if action not in positive_actions and action not in negative_actions:
            continue
        matched_topics = [
            topic_id for topic_id in feedback_topic_ids(item) if topic_id in accumulated
        ]
        if not matched_topics:
            continue
        try:
            created_at = parse_date(str(item.get("created_at", "")))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=dt.timezone.utc)
            age_days = max(
                0.0,
                (reference_time - created_at).total_seconds() / 86400,
            )
        except (TypeError, ValueError):
            age_days = 0.0
        decay = 0.5 ** (age_days / half_life_days)
        labeled_papers += 1
        for index, topic_id in enumerate(matched_topics):
            credit = 1.0 if index == 0 else secondary_credit
            label = "useful" if action in positive_actions else "irrelevant"
            accumulated[topic_id][label] += credit
            accumulated[topic_id][f"effective_{label}"] += credit * decay

    topic_diagnostics: list[dict[str, Any]] = []
    adjusted_topics = 0
    for topic in result.get("topics", []):
        topic_id = str(topic.get("id", ""))
        stats = accumulated.get(
            topic_id,
            {
                "useful": 0.0,
                "irrelevant": 0.0,
                "effective_useful": 0.0,
                "effective_irrelevant": 0.0,
            },
        )
        base_weight = clamp(float(topic.get("weight", 0.0)))
        raw_samples = stats["useful"] + stats["irrelevant"]
        effective_samples = stats["effective_useful"] + stats["effective_irrelevant"]
        hit_rate = stats["useful"] / raw_samples if raw_samples else None
        smoothed_hit_rate = (
            (stats["effective_useful"] + prior_strength * target_hit_rate)
            / (effective_samples + prior_strength)
            if effective_samples + prior_strength > 0
            else target_hit_rate
        )
        active = bool(
            enabled
            and topic.get("enabled", True)
            and base_weight > 0
            and effective_samples >= minimum_samples
        )
        confidence = min(1.0, effective_samples / full_confidence_samples)
        adjustment = (
            clamp(
                (smoothed_hit_rate - target_hit_rate) * learning_rate * confidence,
                -max_adjustment,
                max_adjustment,
            )
            if active
            else 0.0
        )
        effective_weight = (
            clamp(base_weight + adjustment, minimum_weight, maximum_weight)
            if active
            else base_weight
        )
        if active and abs(effective_weight - base_weight) >= 0.0005:
            adjusted_topics += 1
        feedback_stats = {
            "useful": round(stats["useful"], 2),
            "irrelevant": round(stats["irrelevant"], 2),
            "samples": round(raw_samples, 2),
            "effective_samples": round(effective_samples, 2),
            "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
            "smoothed_hit_rate": round(smoothed_hit_rate, 4),
            "confidence": round(confidence, 4),
            "base_weight": round(base_weight, 4),
            "effective_weight": round(effective_weight, 4),
            "adjustment": round(effective_weight - base_weight, 4),
            "active": active,
        }
        topic["effective_weight"] = round(effective_weight, 4)
        topic["feedback_stats"] = feedback_stats
        topic_diagnostics.append({"id": topic_id, **feedback_stats})

    diagnostics = {
        "enabled": enabled,
        "generated_at": reference_time.isoformat(),
        "feedback_records": len(feedback),
        "latest_feedback_papers": len(latest_seen),
        "labeled_papers": labeled_papers,
        "adjusted_topics": adjusted_topics,
        "minimum_effective_samples": minimum_samples,
        "topics": topic_diagnostics,
    }
    result["feedback_tuning_state"] = diagnostics
    return result, diagnostics


def feedback_adjustment(
    tokens: set[str],
    positive_feedback: list[FeedbackSignal],
    negative_feedback: list[FeedbackSignal],
) -> float:
    """Return a bounded reranking adjustment from the closest labeled papers."""
    positive = max(
        (jaccard(tokens, item_tokens) * weight for item_tokens, weight in positive_feedback),
        default=0.0,
    )
    negative = max(
        (jaccard(tokens, item_tokens) * weight for item_tokens, weight in negative_feedback),
        default=0.0,
    )
    return clamp(positive * 0.24 - negative * 0.34, -0.45, 0.3)


def semantic_scholar_feedback_scores(
    feedback: list[dict[str, Any]],
) -> dict[str, float]:
    """Get a free semantic recommendation signal from explicit paper feedback."""
    if os.getenv("SEMANTIC_SCHOLAR_RECOMMENDATIONS", "1") == "0":
        return {}
    positives: list[str] = []
    negatives: list[str] = []
    seen: set[str] = set()
    ordered = sorted(
        feedback,
        key=lambda value: value.get("created_at", ""),
        reverse=True,
    )
    for item in ordered:
        paper_id = re.sub(r"v\d+$", "", str(item.get("paper_id", ""))).strip()
        if not paper_id or paper_id in seen:
            continue
        seen.add(paper_id)
        action = item.get("action")
        semantic_id = f"ArXiv:{paper_id}"
        if action in {"save", "read", "more_method", "more_topic", "useful"}:
            positives.append(semantic_id)
        elif action in {"not_llm", "irrelevant", "not_useful"}:
            negatives.append(semantic_id)
    if not positives:
        return {}

    url = (
        "https://api.semanticscholar.org/recommendations/v1/papers/"
        "?limit=500&fields=externalIds"
    )
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    headers = {"x-api-key": api_key} if api_key else None
    try:
        payload = request_json(
            url,
            method="POST",
            body={
                "positivePaperIds": positives[:100],
                "negativePaperIds": negatives[:100],
            },
            timeout=60,
            extra_headers=headers,
        )
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"Semantic Scholar recommendations unavailable: {error}", file=sys.stderr)
        return {}

    recommended = payload.get("recommendedPapers", [])
    total = max(len(recommended), 1)
    scores: dict[str, float] = {}
    for index, item in enumerate(recommended):
        external_ids = item.get("externalIds") or {}
        arxiv_id = re.sub(
            r"v\d+$", "", str(external_ids.get("ArXiv", ""))
        ).strip()
        if arxiv_id:
            scores[arxiv_id] = round(1.0 - index / total, 4)
    return scores


def topic_scores(
    paper: Paper,
    profile: dict[str, Any],
    scope_score: float,
    positive_feedback: list[FeedbackSignal],
    negative_feedback: list[FeedbackSignal],
) -> list[dict[str, Any]]:
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    abstract_opening = " ".join(split_sentences(paper.abstract)[:2]).lower()
    central_text = f"{title}. {abstract_opening}"
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
        required_central = topic.get("required_central_any", [])
        if required_central and not any(
            contains_term(central_text, term) for term in required_central
        ):
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
        matched = list(
            dict.fromkeys(
                term
                for term in [*phrases, *terms]
                if contains_term(paper.text(), term)
            )
        )[:6]
        weighted = normalized * float(
            topic.get("effective_weight", topic.get("weight", 1.0))
        )
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

    feedback_boost = feedback_adjustment(tokens, positive_feedback, negative_feedback)

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
    if paper.source == "conference":
        if paper.presentation.lower() == "oral":
            score += 0.18
            reasons.append("conference oral")
        elif paper.presentation.lower() == "spotlight":
            score += 0.14
            reasons.append("conference spotlight")
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


def payload_generated_date(payload: dict[str, Any]) -> dt.date | None:
    raw_date = payload.get("generated_at")
    if not isinstance(raw_date, str) or not raw_date:
        return None
    try:
        return parse_date(raw_date).date()
    except ValueError:
        return None


def load_seen_paper_ids(
    output_path: Path,
    current_date: dt.date | None = None,
) -> set[str]:
    """Load previously recommended stable paper IDs, including pre-index archives.

    Same-day recommendations are excluded from the returned set so maintenance
    reruns remain idempotent: today's current feed can be regenerated without
    immediately hiding itself. On following days, those IDs remain part of the
    durable seen index and are not recommended again.
    """
    data_dir = output_path.parent
    seen: set[str] = set()
    same_day_seen: set[str] = set()
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
        payload_date = payload_generated_date(payload) if isinstance(payload, dict) else None
        for paper_id in payload.get("paper_ids", []):
            if isinstance(paper_id, str) and paper_id:
                seen.add(paper_id)
        for item in payload.get("papers", []):
            paper_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(paper_id, str) and paper_id:
                seen.add(paper_id)
                recommended_at = item.get("recommended_at") if isinstance(item, dict) else None
                item_date = None
                if isinstance(recommended_at, str) and recommended_at:
                    try:
                        item_date = parse_date(recommended_at).date()
                    except ValueError:
                        item_date = None
                item_date = item_date or payload_date
                if current_date is not None and item_date == current_date:
                    same_day_seen.add(paper_id)
    if current_date is not None:
        seen.difference_update(same_day_seen)
    return seen


def novelty_score(paper: Paper, previous: list[set[str]]) -> float:
    if not previous:
        return 0.55
    tokens = tokenize(paper.text())
    similarity = max((jaccard(tokens, item) for item in previous), default=0.0)
    return clamp(0.95 - similarity * 1.35, 0.2, 0.95)


def freshness_score(paper: Paper, now: dt.datetime) -> float:
    if paper.source == "conference" and paper.conference_year:
        return clamp(1.0 - max(0, now.year - paper.conference_year) * 0.18, 0.25, 1.0)
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
        "language": "en",
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "prompt_version": 0,
    }


def normalize_language(language: str) -> str:
    return "zh" if str(language).lower().startswith("zh") else "en"


def reader_facing_strings(value: Any) -> list[str]:
    """Flatten generated prose while ignoring icons and generation metadata."""
    if isinstance(value, str):
        normalized = normalize_space(value)
        return [normalized] if len(normalized) >= 4 else []
    if isinstance(value, list):
        return [text for item in value for text in reader_facing_strings(item)]
    if isinstance(value, dict):
        ignored = {
            "icon",
            "generated_by",
            "language",
            "prompt_version",
            "schema_version",
            "source",
            "source_scope",
        }
        return [
            text
            for key, item in value.items()
            if key not in ignored
            for text in reader_facing_strings(item)
        ]
    return []


def language_content_matches(value: Any, language: str) -> bool:
    """Verify the actual generated prose instead of trusting its language tag."""
    strings = reader_facing_strings(value)
    if not strings:
        return False
    target = normalize_language(language)
    if target == "zh":
        cjk_counts = [len(re.findall(r"[\u3400-\u9fff]", text)) for text in strings]
        localized = sum(count >= 2 for count in cjk_counts)
        return sum(cjk_counts) >= 12 and localized / len(strings) >= 0.6
    combined = " ".join(strings)
    latin_words = len(re.findall(r"\b[A-Za-z]{2,}\b", combined))
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", combined))
    return latin_words >= 2 and cjk_count <= max(2, latin_words // 5)


def output_language_instruction(language: str) -> str:
    if normalize_language(language) == "zh":
        return (
            "Write all reader-facing prose in concise Simplified Chinese. Preserve "
            "paper titles, model names, dataset names, metric names, and established "
            "technical terms in English when translating them would reduce precision."
        )
    return "Write all reader-facing prose in concise technical English."


def signal_length_instruction(language: str) -> str:
    if normalize_language(language) == "zh":
        return "20-45 Chinese characters"
    return "12-20 words"


def overview_length_instruction(language: str) -> str:
    if normalize_language(language) == "zh":
        return "120-220 Chinese characters"
    return "70-110 words"


def parse_model_summary(
    raw: str,
    generated_by: str,
    language: str = "en",
) -> dict[str, Any] | None:
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
        isinstance(result.get(field), str) and len(result[field].strip()) >= 8
        for field in required
    ):
        return None
    if not language_content_matches({field: result[field] for field in required}, language):
        return None
    result["source"] = "abstract"
    result["generated_by"] = generated_by
    result["language"] = normalize_language(language)
    result["schema_version"] = SUMMARY_SCHEMA_VERSION
    result["prompt_version"] = SUMMARY_PROMPT_VERSION
    return result


def summary_prompt(
    paper: Paper,
    topics: list[dict[str, Any]],
    language: str = "en",
) -> str:
    topic_names = ", ".join(item["name"] for item in topics[:3])
    return f"""You write a morning research brief for an expert LLM researcher.
Use only the supplied title and abstract. Do not invent results, datasets,
baselines, numbers, or limitations. Return only a JSON object with string
fields: takeaway, problem, method, evidence, limitations, why_for_you.

Requirements:
- {output_language_instruction(language)}
- Each field is one concise technical sentence.
- takeaway states the actual contribution, not generic background.
- method says what the authors concretely do.
- evidence reports the evaluation or theorem; say "Not stated in the abstract"
  when details are absent.
- limitations distinguishes an author-stated limitation from missing evidence.
- why_for_you names the matched research problem or method; generic shared words
  such as training, model, robustness, or optimization are not sufficient.

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
    language: str = "en",
) -> str:
    topic_names = ", ".join(item["name"] for item in topics[:3])
    return f"""Analyze this paper for an expert LLM researcher deciding what to read.

Grounding contract:
- Use only the supplied text. Never invent a model, dataset, baseline, metric,
  number, equation, result, or author-stated limitation.
- Preserve concrete names and numeric results exactly when available.
- If a requested fact is absent, write "Not stated in the available source."
- Separate what the authors show from your inference. Do not call arXiv peer review.

Return only valid JSON with this exact shape:
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
      {{"icon": "💡", "text": "paper-specific contribution"}},
      {{"icon": "⚙️", "text": "paper-specific method or mechanism"}},
      {{"icon": "📊", "text": "strongest evidence or material caveat"}}
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

Content priorities:
0. {output_language_instruction(language)}
1. State the actual contribution, then the mechanism or procedure, then the
   strongest evidence and material caveat. Omit generic background.
2. brief fields are one technical sentence each. Only why_for_you may mention
   the reader's interests, and it must name the matched problem or method.
3. signals has exactly three complementary, scannable items in this order:
   contribution, method/mechanism, and strongest evidence/material caveat. Each
   item is limited to {signal_length_instruction(language)}.
   Each item makes one claim, names a paper-specific entity, and preserves the
   most decision-relevant number when one is available. Put supporting detail in
   the deep-dive fields, not in signals.
4. Choose each signal icon by meaning instead of repeating a fixed trio. Useful
   choices include 💡 contribution, 🛡️ safety, 🤖 agents,
   ⚡ efficiency, ⚙️ method, 🔬 mechanism, 🧮 theory, 🗂️ data, 📈 gain,
   📉 degradation, 📊 evaluation, and ⚠️ limitation.
5. overview is {overview_length_instruction(language)}. Use 0-3 focused items in each detailed section.
   Return an empty list when the source does not support that section; never add
   a placeholder item merely to fill the schema.
6. Findings connect claims to experiments, metrics, theorem statements, or
   ablations. Limitations distinguish author-stated limits from missing evidence.

Research interests: {topic_names}
Available source: {source_scope}
Title: {paper.title}
Abstract: {paper.abstract}

Paper text:
{paper_text}
"""


def choose_signal_icon(text: str, role: int) -> str:
    """Assign a stable, content-aware icon instead of trusting prompt examples."""
    lowered = text.lower()
    if role == 0:
        choices = [
            (("multilingual", "cross-lingual", "language", "arabic", "tokenization", "多语言", "跨语言", "分词", "阿拉伯语"), "🌐"),
            (("agent", "tool use", "workflow", "智能体", "工具调用", "工作流"), "🤖"),
            (("efficient", "cost", "latency", "compute", "效率", "成本", "延迟", "计算"), "⚡"),
            (("safety", "attack", "adversarial", "jailbreak", "robust", "安全", "攻击", "对抗", "越狱", "鲁棒"), "🛡️"),
            (("benchmark", "dataset", "corpus", "基准", "数据集", "语料"), "🗂️"),
            (("interpret", "circuit", "representation", "可解释", "回路", "表征"), "🔎"),
        ]
        fallback = "💡"
    elif role == 1:
        choices = [
            (("theorem", "proof", "bound", "equation", "定理", "证明", "界", "方程"), "🧮"),
            (("mechanism", "representation", "latent", "activation", "机制", "表征", "潜在", "激活"), "🔬"),
            (("dataset", "corpus", "curation", "sampling", "数据集", "语料", "采样"), "🗂️"),
            (("retrieval", "search", "index", "检索", "搜索", "索引"), "🔎"),
            (("train", "fine-tun", "pipeline", "framework", "algorithm", "method", "训练", "微调", "流程", "框架", "算法", "方法"), "⚙️"),
        ]
        fallback = "🔧"
    else:
        choices = [
            (("however", "despite", "limit", "caveat", "insufficient", "fail", "remain", "modest", "unimproved", "然而", "尽管", "局限", "不足", "失败", "仍未", "有限"), "⚠️"),
            (("improv", "outperform", "gain", "increase", "restore", "achiev", "提升", "改进", "优于", "增加", "恢复", "达到"), "📈"),
            (("drop", "degrad", "decline", "loss", "worse", "下降", "退化", "损失", "变差"), "📉"),
            (("theorem", "prove", "guarantee", "定理", "证明", "保证"), "✅"),
            (("benchmark", "experiment", "evaluat", "metric", "accuracy", "基准", "实验", "评估", "指标", "准确率"), "📊"),
        ]
        fallback = "📊"
    for needles, icon in choices:
        if any(needle in lowered for needle in needles):
            return icon
    return fallback


def prepare_deep_dive(
    deep_dive: Any,
    generated_by: str,
    source_scope: str,
    language: str = "en",
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
    if not language_content_matches(deep_dive, language):
        return None
    result = copy.deepcopy(deep_dive)
    for role, signal in enumerate(result["signals"]):
        signal["icon"] = choose_signal_icon(signal.get("text", ""), role)
    result["source_scope"] = source_scope
    result["generated_by"] = generated_by
    result["language"] = normalize_language(language)
    result["schema_version"] = ANALYSIS_SCHEMA_VERSION
    result["prompt_version"] = ANALYSIS_PROMPT_VERSION
    return result


def parse_model_analysis(
    raw: str,
    generated_by: str,
    source_scope: str,
    source_text: str = "",
    language: str = "en",
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    payload = json.loads(match.group(0))
    brief = payload.get("brief")
    deep_dive = payload.get("deep_dive")
    if not isinstance(brief, dict) or not isinstance(deep_dive, dict):
        return None
    if source_text:
        output_numbers = set(NUMBER_RE.findall(json.dumps(payload)))
        source_numbers = set(NUMBER_RE.findall(source_text))
        if output_numbers - source_numbers:
            return None
    summary = parse_model_summary(json.dumps(brief), generated_by, language)
    prepared = prepare_deep_dive(deep_dive, generated_by, source_scope, language)
    if summary is None or prepared is None:
        return None
    summary["source"] = source_scope
    return summary, prepared


def cloudflare_summary(
    paper: Paper,
    topics: list[dict[str, Any]],
    language: str = "en",
) -> dict[str, Any] | None:
    if not cloudflare_available():
        return None
    model = os.getenv("CLOUDFLARE_FALLBACK_MODEL") or "@cf/qwen/qwen3-30b-a3b-fp8"
    try:
        response = cloudflare_inference_with_retry(
            model,
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "Ground every claim in the supplied text and return JSON only.",
                    },
                    {"role": "user", "content": summary_prompt(paper, topics, language)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 900,
            },
            timeout=120,
        )
        raw = cloudflare_response_text(response)
        return parse_model_summary(raw, model, language)
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"AI summary failed for {paper.id}: {error}", file=sys.stderr)
        return None


def cloudflare_analysis(
    paper: Paper,
    topics: list[dict[str, Any]],
    language: str = "en",
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not cloudflare_available():
        return None
    primary_model = os.getenv("CLOUDFLARE_MODEL") or "@cf/openai/gpt-oss-120b"
    fallback_model = (
        os.getenv("CLOUDFLARE_FALLBACK_MODEL") or "@cf/qwen/qwen3-30b-a3b-fp8"
    )
    paper_text, source_scope = extract_pdf_text(paper)
    analysis_language = "en"
    for model in dict.fromkeys([primary_model, fallback_model]):
        attempts = 2 if model == primary_model else 1
        for attempt in range(attempts):
            body = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise research analyst. Follow the grounding contract and return JSON only.",
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt(
                            paper,
                            topics,
                            paper_text,
                            source_scope,
                            analysis_language,
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 3200,
            }
            try:
                response = cloudflare_inference_with_retry(
                    model,
                    body,
                    timeout=180,
                )
                raw = cloudflare_response_text(response)
                analysis = parse_model_analysis(
                    raw, model, source_scope, paper_text, analysis_language
                )
                if analysis:
                    if normalize_language(language) == analysis_language:
                        return analysis
                    translated = cloudflare_translate_analysis(
                        analysis[0], analysis[1], language
                    )
                    if translated:
                        return translated
                    print(
                        f"Localization remains pending for {paper.id}; "
                        "keeping the grounded English analysis.",
                        file=sys.stderr,
                    )
                    return analysis
                print(
                    f"{model} returned an invalid analysis schema for {paper.id} "
                    f"(attempt {attempt + 1}/{attempts})",
                    file=sys.stderr,
                )
            except (
                OSError,
                RuntimeError,
                ValueError,
                urllib.error.URLError,
                IndexError,
            ) as error:
                print(f"{model} analysis failed for {paper.id}: {error}", file=sys.stderr)
                break
    return None


def cloudflare_translate_analysis(
    summary: dict[str, Any],
    deep_dive: dict[str, Any],
    language: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Translate a grounded cached analysis without re-reading or re-analyzing the PDF."""
    if not cloudflare_available():
        return None
    brief_fields = {
        "takeaway",
        "problem",
        "method",
        "evidence",
        "limitations",
        "why_for_you",
    }
    deep_fields = {
        "signals",
        "overview",
        "methodology",
        "mechanism",
        "experiments",
        "findings",
        "contributions",
        "limitations",
        "open_questions",
    }
    payload = {
        "brief": {key: summary[key] for key in brief_fields},
        "deep_dive": {key: deep_dive[key] for key in deep_fields},
    }
    source_json = json.dumps(payload, ensure_ascii=False)
    if len(source_json) > 4500:
        return cloudflare_translate_analysis_chunks(
            payload,
            deep_dive.get("source_scope", "cached grounded analysis"),
            language,
        )
    prompt = f"""Translate the reader-facing string values in this JSON analysis.
{output_language_instruction(language)}

Rules:
- Preserve the exact JSON keys, object shape, arrays, and item counts.
- Preserve all numbers, paper-specific claims, model names, dataset names,
  metric names, equations, and technical meaning exactly.
- Do not add, remove, summarize, reinterpret, or strengthen any claim.
- Keep each signal concise and return JSON only.

JSON:
{source_json}
"""
    fallback_model = (
        os.getenv("CLOUDFLARE_FALLBACK_MODEL") or "@cf/qwen/qwen3-30b-a3b-fp8"
    )
    primary_model = os.getenv("CLOUDFLARE_MODEL") or "@cf/openai/gpt-oss-120b"
    for model in dict.fromkeys([primary_model, fallback_model]):
        attempts = 2 if model == primary_model else 1
        for attempt in range(attempts):
            try:
                response = cloudflare_inference_with_retry(
                    model,
                    {
                        "messages": [
                            {
                                "role": "system",
                                "content": "Translate grounded research JSON exactly and return JSON only.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0,
                        "max_tokens": 5000,
                    },
                    timeout=180,
                )
                raw = cloudflare_response_text(response)
                translated = parse_model_analysis(
                    raw,
                    f"{model} translation",
                    deep_dive.get("source_scope", "cached grounded analysis"),
                    source_json,
                    language,
                )
                if translated:
                    return translated
                print(
                    f"{model} returned an invalid translation schema "
                    f"(attempt {attempt + 1}/{attempts})",
                    file=sys.stderr,
                )
            except (
                OSError,
                RuntimeError,
                ValueError,
                urllib.error.URLError,
                IndexError,
            ) as error:
                print(
                    f"{model} cached translation failed "
                    f"(attempt {attempt + 1}/{attempts}): {error}",
                    file=sys.stderr,
                )
    return None


def same_json_shape(source: Any, translated: Any) -> bool:
    if isinstance(source, dict):
        return (
            isinstance(translated, dict)
            and source.keys() == translated.keys()
            and all(same_json_shape(source[key], translated[key]) for key in source)
        )
    if isinstance(source, list):
        return (
            isinstance(translated, list)
            and len(source) == len(translated)
            and all(same_json_shape(left, right) for left, right in zip(source, translated))
        )
    return isinstance(translated, type(source))


def cloudflare_translate_json_chunk(
    payload: dict[str, Any],
    language: str,
) -> tuple[dict[str, Any], str] | None:
    source_json = json.dumps(payload, ensure_ascii=False)
    prompt = f"""Translate every reader-facing string value in this JSON chunk.
{output_language_instruction(language)}
Preserve the exact keys, shape, list lengths, numbers, names, metrics, equations,
icons, and technical meaning. Do not add or remove claims. Return JSON only.

JSON:
{source_json}
"""
    primary_model = os.getenv("CLOUDFLARE_MODEL") or "@cf/openai/gpt-oss-120b"
    fallback_model = (
        os.getenv("CLOUDFLARE_FALLBACK_MODEL") or "@cf/qwen/qwen3-30b-a3b-fp8"
    )
    for model in dict.fromkeys([primary_model, fallback_model]):
        try:
            response = cloudflare_inference_with_retry(
                model,
                {
                    "messages": [
                        {
                            "role": "system",
                            "content": "Translate grounded JSON exactly and return JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "max_tokens": 2500,
                },
                timeout=180,
            )
            raw = cloudflare_response_text(response)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError("Translation chunk has no JSON object")
            translated = json.loads(match.group(0))
            source_numbers = set(NUMBER_RE.findall(source_json))
            output_numbers = set(NUMBER_RE.findall(json.dumps(translated)))
            if not same_json_shape(payload, translated):
                raise ValueError("Translation chunk changed the JSON shape")
            if output_numbers - source_numbers:
                raise ValueError("Translation chunk introduced unsupported numbers")
            if not language_content_matches(translated, language):
                raise ValueError("Translation chunk does not match the target language")
            return translated, model
        except (
            OSError,
            RuntimeError,
            ValueError,
            urllib.error.URLError,
            IndexError,
        ) as error:
            print(f"{model} chunk translation failed: {error}", file=sys.stderr)
    return None


def cloudflare_translate_analysis_chunks(
    payload: dict[str, Any],
    source_scope: str,
    language: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    deep_dive = payload["deep_dive"]
    chunks = [
        {
            "brief": payload["brief"],
            "deep_dive": {
                "signals": deep_dive["signals"],
                "overview": deep_dive["overview"],
            },
        },
        {
            "deep_dive": {
                "methodology": deep_dive["methodology"],
                "mechanism": deep_dive["mechanism"],
            },
        },
        {
            "deep_dive": {
                "experiments": deep_dive["experiments"],
                "findings": deep_dive["findings"],
            },
        },
        {
            "deep_dive": {
                "contributions": deep_dive["contributions"],
                "limitations": deep_dive["limitations"],
                "open_questions": deep_dive["open_questions"],
            },
        },
    ]
    combined: dict[str, Any] = {"brief": {}, "deep_dive": {}}
    models: list[str] = []
    for chunk in chunks:
        if reader_facing_strings(chunk):
            result = cloudflare_translate_json_chunk(chunk, language)
            if not result:
                return None
            translated, model = result
            models.append(model)
        else:
            translated = copy.deepcopy(chunk)
        if "brief" in translated:
            combined["brief"].update(translated["brief"])
        combined["deep_dive"].update(translated.get("deep_dive", {}))
    return parse_model_analysis(
        json.dumps(combined, ensure_ascii=False),
        f"{'+'.join(dict.fromkeys(models)) or 'cached'} chunked translation",
        source_scope,
        json.dumps(payload, ensure_ascii=False),
        language,
    )


def score_papers(
    papers: list[Paper],
    profile: dict[str, Any],
    feedback: list[dict[str, Any]],
    previous: list[set[str]],
    now: dt.datetime,
    semantic_feedback: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    ranking = profile["ranking"]
    positive_feedback, negative_feedback = feedback_corpora(feedback, now)
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
        semantic_affinity = (semantic_feedback or {}).get(paper.id, 0.0)
        lexical_feedback = feedback_adjustment(
            tokenize(paper.text()),
            positive_feedback,
            negative_feedback,
        )
        relevance = clamp(relevance + semantic_affinity * 0.15)
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
                "source": paper.source,
                "venue": paper.venue,
                "presentation": paper.presentation,
                "conference_year": paper.conference_year,
                "lane": lane,
                "scope_matches": scope_matches,
                "topics": topics,
                "scores": {
                    "total": round(total, 4),
                    "relevance": round(relevance, 4),
                    "quality": round(quality, 4),
                    "novelty": round(novelty, 4),
                    "freshness": round(freshness, 4),
                    "feedback_adjustment": round(lexical_feedback, 4),
                    "semantic_feedback": round(semantic_affinity, 4),
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


def load_recommended_title_tokens(output_path: Path) -> list[set[str]]:
    """Load title-only fingerprints to deduplicate arXiv and conference versions."""
    data_dir = output_path.parent
    tokens: list[set[str]] = []
    for path in [output_path, data_dir / "history.json", *sorted((data_dir / "archive").glob("*.json"))]:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for item in payload.get("papers", []):
            if isinstance(item, dict) and item.get("title"):
                fingerprint = title_tokens(str(item["title"]))
                if fingerprint:
                    tokens.append(fingerprint)
    return tokens


def title_tokens(title: str) -> set[str]:
    return tokenize(re.sub(r"[-–—]", " ", title))


def title_is_duplicate(title: str, fingerprints: list[set[str]]) -> bool:
    candidate = title_tokens(title)
    return bool(
        candidate
        and max((jaccard(candidate, existing) for existing in fingerprints), default=0.0)
        >= 0.92
    )


def select_conference_supplements(
    scored: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    needed: int,
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Prefer newer years, then oral/spotlight quality, while preserving diversity."""
    if needed <= 0:
        return []
    transfer_limit = int(profile["scope"].get("transferable_daily_limit", 1))
    transfer_count = sum(item["lane"] == "transferable" for item in selected)
    penalty = float(profile["ranking"].get("diversity_penalty", 0.18))
    chosen: list[dict[str, Any]] = []
    remaining = list(scored)
    seen_titles: list[set[str]] = [title_tokens(item["title"]) for item in selected]
    while remaining and len(chosen) < needed:
        allowed = [
            item
            for item in remaining
            if (
                item["lane"] != "transferable"
                or transfer_count < transfer_limit
            )
            and not title_is_duplicate(item["title"], seen_titles)
        ]
        if not allowed:
            break

        def supplement_key(item: dict[str, Any]) -> tuple[int, float]:
            paper: Paper = item["_paper"]
            diversity = penalty * max(
                (
                    jaccard(item["_tokens"], other["_tokens"])
                    for other in [*selected, *chosen]
                ),
                default=0.0,
            )
            return (
                paper.conference_year or 0,
                item["scores"]["total"]
                - diversity
                + (0.03 if paper.presentation.lower() == "oral" else 0.0),
            )

        best = max(allowed, key=supplement_key)
        chosen.append(best)
        remaining.remove(best)
        seen_titles.append(title_tokens(best["title"]))
        if best["lane"] == "transferable":
            transfer_count += 1
    return chosen


def serialize_item(
    item: dict[str, Any],
    use_ai: bool,
    previous_item: dict[str, Any] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    language = normalize_language(language)
    paper: Paper = item.pop("_paper")
    item.pop("_tokens", None)
    summary = None
    deep_dive = None
    if use_ai:
        unchanged = bool(
            previous_item
            and previous_item.get("title") == paper.title
            and previous_item.get("abstract") == paper.abstract
            and previous_item.get("updated") == paper.updated
        )
        cached_deep_dive = (
            (previous_item or {}).get("deep_dive") if unchanged else None
        )
        cached_summary = (previous_item or {}).get("summary") if unchanged else None
        required_summary = {
            "takeaway",
            "problem",
            "method",
            "evidence",
            "limitations",
            "why_for_you",
        }
        required_deep_dive = {
            "signals",
            "overview",
            "methodology",
            "mechanism",
            "experiments",
            "findings",
            "contributions",
            "limitations",
            "open_questions",
        }
        cache_is_complete = bool(
            isinstance(cached_deep_dive, dict)
            and required_deep_dive.issubset(cached_deep_dive)
            and isinstance(cached_summary, dict)
            and required_summary.issubset(cached_summary)
        )
        cache_language = (
            cached_deep_dive.get("language", "en")
            if isinstance(cached_deep_dive, dict)
            else "en"
        )
        cache_is_localized = bool(
            cache_is_complete
            and language_content_matches(cached_summary, language)
            and language_content_matches(cached_deep_dive, language)
        )
        if cache_is_complete and (
            cache_language != language or not cache_is_localized
        ):
            try:
                translated = cloudflare_translate_analysis(
                    cached_summary,
                    cached_deep_dive,
                    language,
                )
            except Exception as error:
                print(
                    f"Cached translation crashed for {paper.id}; re-analyzing: {error}",
                    file=sys.stderr,
                )
                translated = None
            if (
                translated
                and language_content_matches(translated[0], language)
                and language_content_matches(translated[1], language)
            ):
                summary, deep_dive = translated
        if (
            not deep_dive
            and cached_deep_dive
            and cached_deep_dive.get("schema_version") == ANALYSIS_SCHEMA_VERSION
            and cached_deep_dive.get("prompt_version") == ANALYSIS_PROMPT_VERSION
            and cached_deep_dive.get("language", "en") == language
            and language_content_matches(cached_deep_dive, language)
        ):
            deep_dive = prepare_deep_dive(
                cached_deep_dive,
                cached_deep_dive.get("generated_by", "cached analysis"),
                cached_deep_dive.get("source_scope", "available source"),
                language,
            )
        if deep_dive:
            if isinstance(cached_summary, dict):
                if required_summary.issubset(cached_summary) and all(
                    isinstance(cached_summary.get(field), str)
                    for field in required_summary
                ):
                    if (
                        cached_summary.get("schema_version") == SUMMARY_SCHEMA_VERSION
                        and cached_summary.get("prompt_version")
                        == SUMMARY_PROMPT_VERSION
                        and cached_summary.get("language", "en") == language
                        and language_content_matches(cached_summary, language)
                    ):
                        if summary is None:
                            summary = copy.deepcopy(cached_summary)
        else:
            try:
                analysis = cloudflare_analysis(paper, item["topics"], language)
            except Exception as error:
                print(
                    f"Cloudflare analysis crashed for {paper.id}; falling back: {error}",
                    file=sys.stderr,
                )
                analysis = None
            if analysis:
                summary, deep_dive = analysis
            else:
                try:
                    summary = cloudflare_summary(paper, item["topics"], language)
                except Exception as error:
                    print(
                        f"Cloudflare summary crashed for {paper.id}; falling back to extractive summary: {error}",
                        file=sys.stderr,
                    )
    item["summary"] = summary or extractive_summary(paper, item["topics"])
    if deep_dive:
        item["deep_dive"] = deep_dive
    item["analysis_status"] = (
        "complete"
        if deep_dive
        and language_content_matches(item["summary"], language)
        and language_content_matches(deep_dive, language)
        else "pending"
    )
    item["recommendation_reason"] = {
        "topic": item["topics"][0]["name"],
        "matched": item["topics"][0]["matched"][:4],
        "lane": item["lane"],
    }
    return item


def stored_item_matches_scope(item: dict[str, Any], profile: dict[str, Any]) -> bool:
    """Reapply hard scope guardrails when carrying history into a new build."""
    if not isinstance(item, dict) or not item.get("id"):
        return False
    paper = paper_from_dict(item)
    lane, _, _ = scope_lane(paper, profile)
    return lane is not None


def refresh_stale_weekly_analyses(
    history_items: list[dict[str, Any]],
    use_ai: bool,
    now: dt.datetime,
    language: str = "en",
) -> int:
    """Gradually replace stale cached briefs without creating an API cost spike."""
    if (
        not use_ai
        or not cloudflare_available()
    ):
        return 0
    week_start = now - dt.timedelta(days=7)
    candidates = sorted(
        (
            item
            for item in history_items
            if parse_date(item.get("recommended_at", item.get("published", "")))
            >= week_start
        ),
        key=lambda item: item.get("scores", {}).get("total", 0),
        reverse=True,
    )
    target_language = normalize_language(language)
    limit = max(0, int(os.getenv("AI_CACHE_REFRESH_LIMIT", "3")))
    time_budget = max(
        0,
        int(os.getenv("AI_CACHE_REFRESH_TIME_BUDGET_SECONDS", "420")),
    )
    started_at = time.monotonic()
    attempted = 0
    refreshed = 0
    for item in candidates:
        if attempted >= limit or time.monotonic() - started_at >= time_budget:
            break
        if (
            item.get("deep_dive", {}).get("schema_version")
            == ANALYSIS_SCHEMA_VERSION
            and item.get("deep_dive", {}).get("language", "en")
            == target_language
            and item.get("deep_dive", {}).get("prompt_version")
            == ANALYSIS_PROMPT_VERSION
            and language_content_matches(item.get("deep_dive", {}), target_language)
            and item.get("summary", {}).get("schema_version")
            == SUMMARY_SCHEMA_VERSION
            and item.get("summary", {}).get("language", "en")
            == target_language
            and item.get("summary", {}).get("prompt_version")
            == SUMMARY_PROMPT_VERSION
            and language_content_matches(item.get("summary", {}), target_language)
        ):
            continue
        attempted += 1
        paper = paper_from_dict(item)
        working = copy.deepcopy(item)
        working.pop("summary", None)
        working.pop("deep_dive", None)
        recommended_at = working.pop("recommended_at", None)
        working["_paper"] = paper
        working["_tokens"] = tokenize(paper.text())
        result = serialize_item(working, True, item, language)
        if result.get("deep_dive", {}).get("schema_version") != ANALYSIS_SCHEMA_VERSION:
            continue
        if recommended_at:
            result["recommended_at"] = recommended_at
        item.clear()
        item.update(result)
        if result.get("analysis_status") == "complete":
            refreshed += 1
    if attempted:
        print(
            f"Attempted {attempted} stale weekly AI analyses; "
            f"completed {refreshed}.",
            file=sys.stderr,
        )
    return refreshed


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
            paper = paper_from_dict(item)
            item["summary"] = extractive_summary(paper, item.get("topics", []))
            rewritten += 1
        write_json_atomic(path, payload)

    public_profile = dict(profile)
    public_profile.pop("owner", None)
    write_json_atomic(data_dir / "profile.json", public_profile)
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
    profile, topic_feedback = apply_topic_feedback_tuning(
        profile,
        feedback,
        now,
    )
    semantic_feedback = semantic_scholar_feedback_scores(feedback)
    if atom_fixture:
        payload = atom_fixture.read_bytes()
        query_total = atom_total_results(payload)
    else:
        payload, query_total = fetch_arxiv(profile, now)
    papers = parse_atom(payload)
    previous = load_previous_papers(output_path)
    previous_items = load_previous_items(output_path)
    seen_ids = load_seen_paper_ids(output_path, now.date())
    unseen_papers = [paper for paper in papers if paper.id not in seen_ids]
    scored = score_papers(
        unseen_papers,
        profile,
        feedback,
        previous,
        now,
        semantic_feedback,
    )
    selected = diversify(scored, profile)
    conference_settings = profile.get("conference_fallback", {})
    minimum_daily = max(0, int(conference_settings.get("minimum_daily", 0)))
    conference_cache: dict[str, Any] = {}
    conference_eligible_count = 0
    if (
        not atom_fixture
        and conference_settings.get("enabled", True)
        and len(selected) < minimum_daily
    ):
        conference_cache_path = output_path.parent / "conference_pool.json"
        conference_cache = sync_conference_cache(
            conference_cache_path,
            profile,
            now,
            seen_ids,
            max(
                minimum_daily - len(selected),
                int(conference_settings.get("reserve_target", 24)),
            ),
        )
        allowed_venues = set(conference_settings.get("venues", []))
        allowed_presentations = {
            str(value).lower()
            for value in conference_settings.get("presentation_types", ["oral", "spotlight"])
        }
        historical_titles = load_recommended_title_tokens(output_path)
        historical_titles.extend(title_tokens(item["title"]) for item in selected)
        conference_papers = [
            paper
            for paper in cached_conference_papers(conference_cache)
            if paper.id not in seen_ids
            and paper.venue in allowed_venues
            and paper.presentation.lower() in allowed_presentations
            and not title_is_duplicate(paper.title, historical_titles)
        ]
        conference_scored = score_papers(
            conference_papers,
            profile,
            feedback,
            previous,
            now,
        )
        conference_eligible_count = len(conference_scored)
        selected.extend(
            select_conference_supplements(
                conference_scored,
                selected,
                minimum_daily - len(selected),
                profile,
            )
        )
    conference_supplement_count = sum(
        item["_paper"].source == "conference" for item in selected
    )
    serialized = [
        serialize_item(
            item,
            use_ai,
            previous_items.get(item["id"]),
            profile.get("content_language", profile.get("language", "en")),
        )
        for item in selected
    ]
    feed = {
        "schema_version": 1,
        "demo": bool(atom_fixture),
        "generated_at": now.isoformat(),
        "profile_updated_at": profile.get("updated_at"),
        "content_language": normalize_language(
            profile.get("content_language", profile.get("language", "en"))
        ),
        "source_count": len(papers),
        "source_total": query_total,
        "source_lookback_days": effective_lookback_days(profile, now),
        "source_truncated": query_total > len(papers),
        "unseen_source_count": len(unseen_papers),
        "previously_recommended_count": len(seen_ids),
        "eligible_count": len(scored),
        "feedback_count": len(feedback),
        "topic_feedback": topic_feedback,
        "semantic_feedback_count": len(semantic_feedback),
        "minimum_daily_target": minimum_daily,
        "minimum_daily_met": len(serialized) >= minimum_daily,
        "conference_supplement_count": conference_supplement_count,
        "conference_eligible_count": conference_eligible_count,
        "conference_pool_updated_at": conference_cache.get("updated_at"),
        "conference_source_status": conference_cache.get("source_status", {}),
        "papers": serialized,
    }
    write_json_atomic(output_path, feed)

    seen_ids.update(item["id"] for item in serialized)
    seen_path = output_path.parent / "seen.json"
    write_json_atomic(
        seen_path,
        {
            "updated_at": now.isoformat(),
            "paper_ids": sorted(seen_ids),
        },
    )

    history_path = output_path.parent / "history.json"
    if reset_history:
        old_history = []
    else:
        try:
            old_history = json.loads(history_path.read_text(encoding="utf-8")).get("papers", [])
        except (OSError, ValueError):
            old_history = []
    old_history = [
        item for item in old_history if stored_item_matches_scope(item, profile)
    ]
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
    refresh_stale_weekly_analyses(
        history_items,
        use_ai,
        now,
        profile.get("content_language", profile.get("language", "en")),
    )
    history = {"generated_at": now.isoformat(), "papers": history_items}
    write_json_atomic(history_path, history)

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
    write_json_atomic(output_path.parent / "weekly.json", weekly)

    public_profile = dict(profile)
    public_profile.pop("owner", None)
    profile_output = output_path.parent / "profile.json"
    write_json_atomic(profile_output, public_profile)

    archive_dir = output_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{now.date().isoformat()}.json"
    write_json_atomic(archive_path, feed)
    return feed


def translate_existing_ai_content(
    profile_path: Path,
    output_path: Path,
    interests_path: Path | None = DEFAULT_INTERESTS,
) -> tuple[int, int]:
    """Translate the current feed caches without fetching arXiv or re-analyzing PDFs."""
    profile = load_profile(profile_path, interests_path)
    language = normalize_language(
        profile.get("content_language", profile.get("language", "en"))
    )
    data_dir = output_path.parent
    paths = [output_path, data_dir / "weekly.json", data_dir / "history.json"]
    payloads: dict[Path, dict[str, Any]] = {}
    for path in paths:
        if path.exists():
            payloads[path] = json.loads(path.read_text(encoding="utf-8"))

    weekly_items = payloads.get(data_dir / "weekly.json", {}).get("papers", [])
    translated_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    pending = 0
    for item in weekly_items:
        paper_id = item.get("id")
        summary = item.get("summary")
        deep_dive = item.get("deep_dive")
        if not paper_id or not isinstance(summary, dict) or not isinstance(deep_dive, dict):
            continue
        if (
            summary.get("language", "en") == language
            and deep_dive.get("language", "en") == language
            and language_content_matches(summary, language)
            and language_content_matches(deep_dive, language)
        ):
            continue
        translated = cloudflare_translate_analysis(summary, deep_dive, language)
        if translated:
            translated_by_id[paper_id] = translated
        else:
            pending += 1

    if translated_by_id:
        for path, payload in payloads.items():
            changed = False
            for item in payload.get("papers", []):
                translated = translated_by_id.get(item.get("id"))
                if not translated:
                    continue
                item["summary"], item["deep_dive"] = copy.deepcopy(translated)
                item["analysis_status"] = "complete"
                changed = True
            if changed:
                write_json_atomic(path, payload)

    public_profile = dict(profile)
    public_profile.pop("owner", None)
    write_json_atomic(data_dir / "profile.json", public_profile)
    return len(translated_by_id), pending


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
    parser.add_argument(
        "--translate-existing",
        action="store_true",
        help="Translate current AI briefs and Deep Dives without fetching arXiv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.rewrite_existing:
        count = rewrite_existing(args.profile, args.output, args.interests)
        print(f"Rewrote {count} existing paper summaries.")
        return 0
    if args.translate_existing:
        translated, pending = translate_existing_ai_content(
            args.profile,
            args.output,
            args.interests,
        )
        print(f"Translated {translated} cached papers; {pending} remain pending.")
        return 0 if pending == 0 else 1
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
    if os.getenv("AI_REQUIRED") == "1" and feed["papers"]:
        incomplete = [
            item["id"]
            for item in feed["papers"]
            if item.get("analysis_status") != "complete"
        ]
        if incomplete:
            print(
                "AI_REQUIRED is enabled, but localized Deep Dive content is "
                f"missing for: {', '.join(incomplete)}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
