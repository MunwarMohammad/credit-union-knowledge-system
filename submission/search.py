"""Conservative extractive BM25 retrieval for service questions."""

import math
import re
from collections import Counter, defaultdict

from contract import Answer, Source
from evidence import plain

STOP = set(
    "a an and are as at be can do does for from how i in is it me my of on or the their to what which with you your dupaco".split()
)


def tokens(text):
    return [
        w.rstrip("s") for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP
    ]


class ParagraphIndex:
    def __init__(self, snapshot):
        self.docs = []
        self.postings = defaultdict(list)
        seen = set()
        for page in snapshot.pages:
            if re.search(r"/(?:newsroom|blog|calculators|hubfs)/", page.url):
                continue
            for paragraph in re.split(r"\n\s*\n", page.markdown):
                raw = paragraph.strip()
                if not 30 <= len(raw) <= 900 or raw.startswith(("#", "|", "![", "[")):
                    continue
                passage = plain(raw)
                if passage in seen or "?" in passage or "%" in passage:
                    continue
                seen.add(passage)
                counts = Counter(tokens(passage))
                idx = len(self.docs)
                self.docs.append(
                    (
                        passage,
                        Source(page.url, snapshot.snapshot_id, raw),
                        sum(counts.values()),
                    )
                )
                for word, count in counts.items():
                    self.postings[word].append((idx, count))
        self.avg = sum(d[2] for d in self.docs) / max(1, len(self.docs)) or 1

    def lookup(self, question):
        words = set(tokens(question))
        if len(words) < 2 or any(w not in self.postings for w in words):
            return None
        score, hits = Counter(), Counter()
        total_idf = 0
        for word in sorted(words):
            postings = self.postings[word]
            idf = math.log1p(
                (len(self.docs) - len(postings) + 0.5) / (len(postings) + 0.5)
            )
            total_idf += idf
            for idx, tf in postings:
                length = self.docs[idx][2]
                score[idx] += (
                    idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / self.avg))
                )
                hits[idx] += 1
        ranked = sorted((s, i) for i, s in score.items() if hits[i] == len(words))
        if not ranked:
            return None
        best, idx = ranked[-1]
        if best < 0.65 * total_idf or len(ranked) > 1 and best < ranked[-2][0] * 1.12:
            return None
        passage, source, _ = self.docs[idx]
        return Answer(passage, [source])
