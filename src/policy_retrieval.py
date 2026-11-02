"""Small RAG retriever over the approved synthetic policy (TF-IDF over sections).

Retrieved text is DATA for the agent, never instructions. Passages that contain
instruction-like text aimed at an AI are dropped and reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import POLICY_DIR

MIN_SIMILARITY = 0.08
INJECTION_PATTERNS = re.compile(
    r"ignore (all|any|previous|prior) (instructions|rules)|disregard (the|your) (system|instructions)|"
    r"you are now|system prompt|as an ai (you|model) must", re.I)
SECTION_RE = re.compile(r"^## (SP-\d+\.\d+) (.+)$", re.M)
# Agents often search with detector rule names; expand them into policy vocabulary.
QUERY_EXPANSION = {
    "off_hours_login": "after-hours off-hours working hours shift sign-in",
    "new_system": "unfamiliar systems not used before business need",
    "failed_login_burst": "repeated failed sign-in attempts password guessing",
    "failures_then_success": "burst of failures followed by a successful login",
    "unusual_privileged_action": "privileged actions administrator privileged role escalated review",
    "new_location": "new unfamiliar location label remote access VPN",
}


def normalize_query(query: str) -> str:
    q = query
    for rule, words in QUERY_EXPANSION.items():
        q = re.sub(rf"\b{rule}\b", f"{rule} {words}", q)
    return q.replace("_", " ")


@dataclass
class Passage:
    section_id: str
    title: str
    text: str
    source: str

    @property
    def citation(self) -> str:
        return f"{self.source}#{self.section_id}"


class PolicyIndex:
    def __init__(self, policy_dir: Path | str = POLICY_DIR):
        self.passages: list[Passage] = []
        self.rejected: list[str] = []
        for path in sorted(Path(policy_dir).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            heads = list(SECTION_RE.finditer(text))
            for i, h in enumerate(heads):
                end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
                body = " ".join(text[h.end():end].split())
                p = Passage(h.group(1), h.group(2).strip(), body, path.name)
                if INJECTION_PATTERNS.search(body):
                    self.rejected.append(p.citation)
                    continue
                self.passages.append(p)
        if not self.passages:
            raise RuntimeError(f"No policy sections found in {policy_dir}")
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([f"{p.title} {p.text}" for p in self.passages])

    @property
    def citations(self) -> set[str]:
        return {p.citation for p in self.passages}

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not query or not query.strip():
            return []
        sims = cosine_similarity(self.vectorizer.transform([normalize_query(query)]), self.matrix)[0]
        ranked = sims.argsort()[::-1][:k]
        return [{"citation": self.passages[i].citation, "section_id": self.passages[i].section_id,
                 "title": self.passages[i].title, "text": self.passages[i].text, "score": round(float(sims[i]), 3)}
                for i in ranked if sims[i] >= MIN_SIMILARITY]
