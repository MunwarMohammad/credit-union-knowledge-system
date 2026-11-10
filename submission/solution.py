"""Offline temporal knowledge system. Entry point for the participant harness."""

import calendar
import re
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlsplit

from contract import Answer, Conflict, Source
from search import ParagraphIndex
from evidence import Evidence, plain, published
from rates import Row, PCT, choose, extract, family_for, key, model_years


def terms(s):
    ignore = set(
        "a an the for in is on what how do does i my you can to of it me your dupaco much cost fee at are we with and".split()
    )
    return {
        w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in ignore
    }


def extra_rows(page, sid):
    path = urlsplit(page.url).path.rstrip("/")
    source = lambda line: Source(page.url, sid, line)
    if path == "/personal/credit-cards":
        card = ""
        for line in page.markdown.splitlines():
            h = re.fullmatch(r"#+\s+(Platinum Visa|Rewards Visa)\s*", line, re.I)
            if h:
                card = h[1]
            if card and "carry a balance" in line and PCT.search(line):
                yield Row(
                    "card",
                    card,
                    "",
                    {"APR": "–".join(PCT.findall(line))},
                    source(line),
                    (3, page.fetched_at),
                )
                card = ""
    for m in re.finditer(
        r"(?im)^([^\n|]{0,45}?)(\d+)[- ]month (.{0,35}?certificate) (APY|dividend rate)[: ]+(\d+(?:\.\d+)?%)",
        page.markdown,
    ):
        rank = 3 if "/rates/" in path else 1
        yield Row(
            "certificate",
            f"{m[2]} Month {m[3]}".strip(),
            "",
            {m[4].upper(): m[5]},
            source(m[0]),
            (rank, page.fetched_at),
        )
    if "/newsroom/" in path:
        m = re.search(r"\b(\d+) branch office locations\b", page.markdown)
        if m and published(page):
            yield Row(
                "organization",
                "Branch office locations",
                "",
                {"count": m[1]},
                source(m[0]),
                (2, published(page)),
            )


def equivalent(a, b):
    def precision(value):
        return re.sub(r"\d+(?:\.\d+)?", lambda m: str(float(m[0])), value)

    return precision(a) == precision(b)


class Edition:
    def __init__(self, snapshot):
        self.paragraphs = ParagraphIndex(snapshot)
        self.evidence = Evidence(snapshot)
        self.rows = {}
        self.claims = defaultdict(list)
        self.faq = []
        self.fees = []
        for p in snapshot.pages:
            for row in (
                *extract(p, snapshot.snapshot_id, Source),
                *extra_rows(p, snapshot.snapshot_id),
            ):
                k = key(row)
                if k not in self.rows or self.rows[k].rank < row.rank:
                    self.rows[k] = row
                for metric, value in row.fields.items():
                    if metric in ("APY", "APR", "rate", "dividend rate", "count"):
                        self.claims[k + (metric,)].append((value, row))
            path = urlsplit(p.url).path.lower()
            if "/newsroom/" in path or "/blog/" in path:
                continue
            for m in re.finditer(
                r"(?m)^#{2,6} ([^#\n]{6,160}\?)\s*\n\s*([^\n#!|][^\n]{12,650})(?=\n|$)",
                p.markdown,
            ):
                self.faq.append(
                    (
                        terms(plain(m[1])),
                        plain(m[2]),
                        Source(p.url, snapshot.snapshot_id, m[0]),
                    )
                )
            for m in re.finditer(
                r"(?m)^- \[([^\]\n]{5,160}\?)\]\([^\n)]+\)\s*\n\s*([^\n#!|\[-][^\n]{12,1000})(?=\n|$)",
                p.markdown,
            ):
                self.faq.append(
                    (
                        terms(m[1]),
                        plain(m[2]),
                        Source(p.url, snapshot.snapshot_id, m[0]),
                    )
                )
            if "fee" in path:
                for line in p.markdown.splitlines():
                    if "$" in line and len(line) < 180 and not line.startswith("|"):
                        self.fees.append(
                            (
                                terms(line.split("$")[0]),
                                plain(line),
                                Source(p.url, snapshot.snapshot_id, line),
                            )
                        )
        self.notes = {}
        self.overlaps = {}
        # Compare only model years that both tables explicitly cover.
        autos = [
            r for r in self.rows.values() if r.family == "auto loan" and r.rank[0] == 3
        ]
        for official in autos:
            low, high = model_years(official.label)
            for candidates in self.claims.values():
                for value, other in candidates:
                    if (
                        other.family != "auto loan"
                        or other.tier != official.tier
                        or other.rank[0] >= 3
                    ):
                        continue
                    start, end = model_years(other.label)
                    start, end = max(start, low), min(end, high)
                    apr = official.fields.get("APR")
                    if (
                        start <= end
                        and apr
                        and value != apr
                        and key(official) != key(other)
                    ):
                        years = f"{start}–{end}" if start != end else str(start)
                        reason = "The auto-loan product table covers this model year and term. The secondary table quotes a different APR."
                        topic = f"Auto loan APR, {years} model year, {official.tier}"
                        self.overlaps[topic, value, apr] = Conflict(
                            topic,
                            [value, apr],
                            [other.source, official.source],
                            apr,
                            reason,
                        )
                        self.notes[key(official)] = reason

        self.disputed_facts = {}
        self.disputes = list(self.overlaps.values())
        for fact, claims in sorted(self.claims.items()):
            winner = self.rows[fact[:3]]
            value = winner.fields.get(fact[3])
            if value is None or winner.rank[0] < 2:
                continue
            alternatives = {}
            for other_value, other in claims:
                if other.source.url == winner.source.url or other.rank >= winner.rank:
                    continue
                if equivalent(other_value, value):
                    continue
                alternatives.setdefault(other_value, other.source)
            if alternatives:
                topic = " ".join(filter(None, fact))
                self.disputed_facts[topic] = fact
                reason = (
                    "Latest dated organizational statement."
                    if fact[0] == "organization"
                    else "The product disclosure outranks secondary pages in this crawl."
                )
                self.notes[fact[:3]] = reason
                self.disputes.append(
                    Conflict(
                        topic,
                        [*alternatives, value],
                        [*alternatives.values(), winner.source],
                        value,
                        reason,
                    )
                )

    def lookup(self, q):
        query = terms(q)
        pool = self.fees if re.search(r"fee|charge|cost|replacement", q) else self.faq
        scored = []
        for words, text, source in pool:
            overlap = len(query & words)
            if (
                overlap >= 2
                and overlap >= len(query) * 0.65
                and overlap >= len(words) * 0.55
            ):
                scored.append((overlap / len(query | words), text, source))
        if scored:
            scored.sort(key=lambda x: -x[0])
            if (
                len(scored) == 1
                or scored[0][0] > scored[1][0]
                or scored[0][1] == scored[1][1]
            ):
                return Answer(scored[0][1], [scored[0][2]])


def cutoff(question):
    m = re.search(r"\b(?:as of|back in|in|during|on)\s+(\d{4}-\d\d-\d\d)\b", question)
    if m:
        return m[1]
    m = re.search(
        r"\b(?:as of|back in|in|during|on)\s+([a-z]+) (?:(\d{1,2}),? )?(\d{4})",
        question,
    )
    if m:
        for fmt in ("%B", "%b"):
            try:
                month = datetime.strptime(m[1], fmt).month
                day = int(m[2]) if m[2] else calendar.monthrange(int(m[3]), month)[1]
                return datetime(int(m[3]), month, day).date().isoformat()
            except ValueError:
                continue


class System:
    def __init__(self):
        self.history = {}

    def ingest(self, snapshot):
        """Build a complete edition without carrying deleted pages forward."""
        self.history[snapshot.taken_on] = Edition(snapshot)

    def answer(self, question, as_of=None):
        q = normalize_question(question)
        date = as_of or cutoff(q)
        editions = [day for day in self.history if date is None or day <= date]
        if not editions:
            return Answer(
                "I don't know. There is no snapshot for that date or earlier.",
                confident=False,
            )
        selected = max(editions)
        for day in sorted(editions, reverse=True):
            answer = self._answer_in(self.history[day], q)
            if answer.sources:
                if day != selected:
                    answer.text = f"Last seen on {day}: {answer.text}"
                    note = f"The {selected} crawl does not verify this answer. The cited evidence is from {day}."
                    answer.conflict_note = " ".join(filter(None, [note, answer.conflict_note]))
                return answer
        return answer

    def _answer_in(self, ed, q):
        early = ed.evidence.answer(q)
        if early:
            return early
        unknown = Answer(
            "I don't know. I couldn't verify that detail in the selected snapshot.",
            confident=False,
        )
        family = family_for(q)
        if family and (
            re.search(
                r"rate|interest|apr|apy|yield|earn|pay|dividend|minimum|how much|special",
                q,
            )
            or family == "certificate"
            or re.search(r"\d+[- ]*year", q)
            or family == "card"
            and "offer" in q
        ):
            rows = choose(ed.rows.values(), q, family)
            return render_rates(rows, q, family, ed.notes) if rows else unknown
        if re.search(r"\b(rate|apy|apr|hours|yield)\b", q):
            return unknown
        return ed.lookup(q) or ed.paragraphs.lookup(q) or unknown

    def conflicts(self):
        """Report competing sources still present in the latest full crawl."""
        if not self.history:
            return []
        dates = sorted(self.history, reverse=True)
        latest = self.history[dates[0]]
        result = []
        for conflict in latest.disputes:
            fact = latest.disputed_facts.get(conflict.topic)
            earlier_sources = []
            pending = set(conflict.values[:-1])
            for day in dates[1:] if fact else ():
                old = self.history[day].rows.get(fact[:3])
                if not old or old.rank[0] < 2:
                    continue
                value = old.fields.get(fact[3], "")
                matches = {v for v in pending if equivalent(v, value)}
                if matches:
                    earlier_sources.append(old.source)
                    pending -= matches
                if not pending:
                    break
            if earlier_sources:
                conflict = Conflict(
                    conflict.topic, conflict.values, [*conflict.sources, *earlier_sources],
                    conflict.resolution,
                    conflict.reason + " Earlier disclosures also quote the competing value.",
                )
            result.append(conflict)
        return result


def normalize_question(question):
    q = question.lower().replace("–", "-").replace("’", "'")
    for pattern, replacement in [
        (r"\bmortage\b", "mortgage"),
        (r"\bcerts?\b", "certificate"),
        (r"\bmos?\b", "month"),
        (r"\byrs?\b", "year"),
    ]:
        q = re.sub(pattern, replacement, q)
    for word, n in {
        "six": 6,
        "ten": 10,
        "twelve": 12,
        "seventeen": 17,
        "thirty": 30,
        "sixty": 60,
    }.items():
        q = re.sub(r"\b" + word + r"(?=[ -](?:month|year))", str(n), q)
    if re.fullmatch(r"\s*\d+[- ]*year[ ?]*", q):
        q += " mortgage"
    return q


def render_rates(rows, q, family, notes):
    """Keep the original labels beside the figures and cite each selected row."""
    lines, sources = [], []
    for r in rows:
        fields = [
            f"{value} {metric}"
            if metric in ("APR", "APY", "rate", "dividend rate")
            else f"{metric} {value}"
            for metric, value in r.fields.items()
        ]
        lines.append(
            " ".join(filter(None, [r.label, r.tier])) + " — " + ", ".join(fields)
        )
        sources.append(r.source)
    percent = re.search(r"(\d+\.\d+)%", q)
    if family == "deposit" and percent and re.search("any|does|do |is there", q):
        matches = [
            r
            for r in rows
            if r.fields.get("APY") and float(r.fields["APY"][:-1]) == float(percent[1])
        ]
        lines.insert(
            0,
            "Yes, within the listed tiers."
            if matches
            else "No. None of the listed tiers below pays that APY.",
        )
    note = next((notes[key(r)] for r in rows if key(r) in notes), None)
    return Answer("\n".join(lines), sources, conflict_note=note)


def build():
    return System()
