"""Offline temporal knowledge system. Entry point for the participant harness."""
import calendar
import re
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlsplit

from contract import Answer, Conflict, Source
from evidence import Evidence, plain, published
from rates import Row, PCT, choose, extract, family_for, key, model_years


def terms(s):
    ignore = set("a an the for in is on what how do does i my you can to of it me your dupaco much cost fee at are we with and".split())
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in ignore}


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
                yield Row("card", card, "", {"APR": "–".join(PCT.findall(line))}, source(line), (3, page.fetched_at))
                card = ""
    for m in re.finditer(r"(?im)^([^\n|]{0,45}?)(\d+)[- ]month (.{0,35}?certificate) (APY|dividend rate)[: ]+(\d+(?:\.\d+)?%)", page.markdown):
        rank = 3 if "/rates/" in path else 1
        yield Row("certificate", f"{m[2]} Month {m[3]}".strip(), "", {m[4].upper(): m[5]}, source(m[0]), (rank, page.fetched_at))
    if "/newsroom/" in path:
        m = re.search(r"\b(\d+) branch office locations\b", page.markdown)
        if m and published(page):
            yield Row("organization", "Branch office locations", "", {"count": m[1]}, source(m[0]), (2, published(page)))


class Edition:
    def __init__(self, snapshot):
        self.evidence = Evidence(snapshot)
        self.rows = {}
        self.claims = defaultdict(list)
        self.faq = []
        self.fees = []
        for p in snapshot.pages:
            for row in (*extract(p, snapshot.snapshot_id, Source), *extra_rows(p, snapshot.snapshot_id)):
                k = key(row)
                if k not in self.rows or self.rows[k].rank < row.rank:
                    self.rows[k] = row
                for metric, value in row.fields.items():
                    if metric in ("APY", "APR", "rate", "dividend rate", "count"):
                        self.claims[k + (metric,)].append((value, row))
            path = urlsplit(p.url).path.lower()
            if "/newsroom/" in path or "/blog/" in path:
                continue
            for m in re.finditer(r"(?m)^#{2,6} ([^#\n]{6,160}\?)\s*\n\s*([^\n#!|][^\n]{12,650})(?=\n|$)", p.markdown):
                self.faq.append((terms(plain(m[1])), plain(m[2]), Source(p.url, snapshot.snapshot_id, m[0])))
            for m in re.finditer(r"(?m)^- \[([^\]\n]{5,160}\?)\]\([^\n)]+\)\s*\n\s*([^\n#!|\[-][^\n]{12,1000})(?=\n|$)", p.markdown):
                self.faq.append((terms(m[1]), plain(m[2]), Source(p.url, snapshot.snapshot_id, m[0])))
            if "fee" in path:
                for line in p.markdown.splitlines():
                    if "$" in line and len(line) < 180 and not line.startswith("|"):
                        self.fees.append((terms(line.split("$")[0]), plain(line), Source(p.url, snapshot.snapshot_id, line)))
        self.notes = {}
        self.overlaps = {}
        # Compare only model years that both tables explicitly cover.
        autos = [r for r in self.rows.values() if r.family == "auto loan" and r.rank[0] == 3]
        for official in autos:
            low, high = model_years(official.label)
            for candidates in self.claims.values():
                for value, other in candidates:
                    if other.family != "auto loan" or other.tier != official.tier or other.rank[0] >= 3:
                        continue
                    start, end = model_years(other.label)
                    start, end = max(start, low), min(end, high)
                    apr = official.fields.get("APR")
                    if start <= end and apr and value != apr and key(official) != key(other):
                        years = f"{start}–{end}" if start != end else str(start)
                        reason = "The auto-loan product table covers this model year and term. The secondary table quotes a different APR."
                        topic = f"Auto loan APR, {years} model year, {official.tier}"
                        self.overlaps[topic, value, apr] = Conflict(topic, [value, apr], [other.source, official.source], apr, reason)
                        self.notes[key(official)] = reason

    def lookup(self, q):
        query = terms(q)
        pool = self.fees if re.search(r"fee|charge|cost|replacement", q) else self.faq
        scored = []
        for words, text, source in pool:
            overlap = len(query & words)
            if overlap >= 2 and overlap >= len(query)*0.65 and overlap >= len(words)*0.55:
                scored.append((overlap / len(query | words), text, source))
        if scored:
            scored.sort(key=lambda x: -x[0])
            if len(scored) == 1 or scored[0][0] > scored[1][0] or scored[0][1] == scored[1][1]:
                return Answer(scored[0][1], [scored[0][2]])


def cutoff(question):
    m = re.search(r"\b(?:as of|back in|in|during|on)\s+(\d{4}-\d\d-\d\d)\b", question)
    if m:
        return m[1]
    m = re.search(r"\b(?:as of|back in|in|during|on)\s+([a-z]+) (?:(\d{1,2}),? )?(\d{4})", question)
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
        self.records = defaultdict(dict)

    def ingest(self, snapshot):
        ed = Edition(snapshot)
        for k, candidates in ed.claims.items():
            seen = self.records[k]
            for value, row in candidates:
                # Normalize precision for comparisons while retaining the exact display text.
                signature = re.sub(r"\d+\.\d+", lambda m: str(float(m[0])).rstrip("0").rstrip("."), value)
                seen[signature] = (value, row)
            if len(seen) > 1:
                ed.notes[k[:3]] = "The selected snapshot's product disclosure takes precedence over older observations and secondary pages."
        self.history[snapshot.taken_on] = ed

    def answer(self, question, as_of=None):
        q = question.lower().replace("–", "-")
        date = as_of or cutoff(q)
        editions = [day for day in self.history if date is None or day <= date]
        if not editions:
            return Answer("I don't know. There is no snapshot for that date or earlier.", confident=False)
        ed = self.history[max(editions)]
        early = ed.evidence.answer(q)
        if early:
            return early
        unknown = Answer("I don't know. I couldn't verify that detail in the selected snapshot.", confident=False)
        for word, n in {"six":6, "ten":10, "twelve":12, "seventeen":17, "thirty":30, "sixty":60}.items():
            q = re.sub(r"\b"+word+r"(?=[ -](?:month|year))", str(n), q)
        family = family_for(q)
        if family and (re.search(r"rate|interest|apr|apy|yield|earn|pay|dividend|minimum|how much|special", q)
                       or family == "card" and "offer" in q):
            rows = choose(ed.rows.values(), q, family)
            if not rows:
                return ed.lookup(q) or unknown
            lines, sources = [], []
            for r in rows:
                fields = [f"{value} {metric}" if metric in ("APR", "APY", "rate", "dividend rate") else f"{metric} {value}" for metric, value in r.fields.items()]
                lines.append(" ".join(filter(None, [r.label, r.tier])) + " — " + ", ".join(fields))
                sources.append(r.source)
            percent = re.search(r"(\d+\.\d+)%", q)
            if family == "deposit" and percent and re.search("any|does|do |is there", q):
                matches = [r for r in rows if r.fields.get("APY") and float(r.fields["APY"][:-1]) == float(percent[1])]
                lines.insert(0, "Yes, within the listed tiers." if matches else "No, within the listed tiers for " + rows[0].label + ".")
            note = next((ed.notes[key(r)] for r in rows if key(r) in ed.notes), None)
            return Answer("\n".join(lines), sources, conflict_note=note)
        return ed.lookup(q) or unknown

    def conflicts(self):
        result = []
        latest = self.history[max(self.history)] if self.history else None
        for k, history in sorted(self.records.items()):
            if len(history) < 2:
                continue
            winner = latest.rows.get(k[:3])
            resolution = winner.fields.get(k[3]) if winner and winner.rank[0] >= 2 else None
            values = [v for v, r in history.values()]
            sources = [r.source for v, r in history.values()]
            if resolution and winner.source not in sources:
                sources.append(winner.source)
            reason = ("Most recent dated organizational statement." if k[0] == "organization" else
                      "The current product table for the same term, tier and measure supersedes older or secondary observations.")
            result.append(Conflict(" ".join(filter(None, k)), values, sources, resolution,
                                   reason if resolution else "No authoritative value for this tier in the newest snapshot."))
        if latest:
            result.extend(latest.overlaps.values())
        return result


def build():
    return System()
