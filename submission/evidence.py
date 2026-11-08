"""Snapshot-local evidence lookup for services, branch information and disclosures."""
import re
from datetime import datetime
from urllib.parse import urlsplit
from contract import Answer, Source


def plain(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s).replace("#### ", "")
    return " ".join(s.strip("# -*_").replace("**", "").split())


def published(p):
    m = re.search(r"(?m)^([A-Z][a-z]+ \d{1,2}, \d{4})\s*$", p.markdown[:700])
    if m:
        try:
            return datetime.strptime(m[1], "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    return ""


class Evidence:
    def __init__(self, snapshot):
        self.sid = snapshot.snapshot_id
        self.year = int(snapshot.taken_on[:4])
        self.pages = sorted(snapshot.pages, key=lambda p: (published(p), p.fetched_at, p.url), reverse=True)

    def find(self, path, regex, group=0, prefix="", suffix=""):
        for p in self.pages:
            if not re.search(path, urlsplit(p.url).path.rstrip("/"), re.I):
                continue
            m = re.search(regex, p.markdown, re.I | re.M)
            if m:
                return Answer(prefix + plain(m[group]) + suffix, [Source(p.url, self.sid, m[0])])

    def answer(self, q):
        find = self.find
        if re.search(r"routing|\baba\b", q):
            return find(r"/cash-management$", r"(?:our routing number|our ABA number)[:\s(]*(\d{9})", 1)
        if re.search(r"hy[- ]vee", q):
            pattern = r"[^.\n]*full-service branches at [^,.\n]+" if re.search(r"where|instead|full.service|alternative|nearby", q) else r"(?:This location|The branch) will close [^\n.]+\."
            return find("hy-vee.*clos", pattern)
        if re.search("how many|number of|branch count", q) and "branch" in q:
            return find("newsroom/", r"\b\d+ branch office locations\b")
        if "forbes" in q:
            return find("forbes.*credit-union", r"[^.\n]*\b(?:first|second|third|fourth|fifth|sixth|seventh) time Forbes [^.\n]+")
        if "volunteer" in q and re.search("employee|staff|how many", q):
            year = str(self.year - 1) if "last year" in q else next(iter(re.findall(r"\b20\d\d\b", q)), r"20\d\d")
            return find("volunteer", r"\d+ (?:Dupaco )?employees[^\n]{0,80}?in " + year + r" called Volunteer Time Off")
        if re.search(r"home[$s]tart|home.tart grant", q):
            return find("home.*tart|homebuy", r"[^.\n]*Home.tart program\.\s*[^.\n]*\$\d[\d,]+[^.\n]*")
        if re.search(r"wallet|apple pay|google pay|samsung pay", q):
            return find("mobile-payments", r"(?:Add your Dupaco debit and credit cards|Your Dupaco debit and credit cards are compatible)[^\n]+")
        if re.search(r"student|university|college", q) and not re.search("apr|interest rate", q):
            return find("student-loans", r"#### Flexible Repayment[\s\S]{0,650}?(?:origination fees|origination fee)[^\n]*", prefix="Student loans and refinancing. ")
        if ("member" in q or "join" in q) and re.search("eligib|who can|qualif", q):
            answer = find(r"/about/join$", r"- You live or work[\s\S]{1,450}?Rural Ideas Network[^\n]*")
            region = find(r"/about/join$", r"Iowa, Illinois and Wisconsin")
            if answer and region:
                answer.text += " The charter area includes counties in " + region.text + "."
                answer.sources.extend(region.sources)
            return answer
        if re.search(r"\bjoin\b", q) or "become a member" in q:
            return find(r"/about/join$", r"\[(?:Join Dupaco|Become a member)\]\((https?://[^)]+)\)", 1)
        if re.search(r"update|change", q) and re.search("contact|phone number|address", q):
            return find(r"/contact$", r"please call us immediately at \[([\d-]+)\]", 1, prefix="For help updating your details, call ")
        if re.search("locator|find.*(?:atm|branch)|(?:atm|branch).*url", q):
            a = find(r"/contact$", r"\[branch or ATM\]\([^)]+\)")
            if a:
                a.text = a.sources[0].url
            return a
        if re.search(r"address|where is|where.s", q) and "branch" in q:
            for p in self.pages:
                if urlsplit(p.url).path.rstrip("/") != "/contact":
                    continue
                for m in re.finditer(r"Dupaco Branch\s*\n\s*(\d+[^\n]*?,\s*[A-Z]{2},?\s*\d{5})", p.markdown):
                    address = m[1]
                    if any(w in q.split() for w in re.findall(r"[a-z]{4,}", address.lower())):
                        return Answer(address, [Source(p.url, self.sid, address)])
        if re.search(r"lobby|drive[ -]?(?:up|through|thru)", q) and re.search("hour|schedule|open|close", q):
            return self.hours(q)
        if re.search(r"link|url|website|where.*(?:see|find)", q) and re.search("certificate|\\bcd\\b", q):
            return find(r"/personal/savings-account$", r"\[[^\]\n]+\]\((https?://[^)]+/savings-account#rates)\)", 1)
        return None

    def hours(self, q):
        # A release applies only to the branch it describes. Name generic examples as such.
        named = re.search(r"(?:at|for|of) (?:the )?(.+?) branch\b", q)
        label = "Drive-up" if "drive" in q else "Lobby"
        examples = []
        specific = named and named[1] not in ("all", "every", "each", "a")
        for p in self.pages:
            if "newsroom/" not in p.url or (specific and named[1] not in plain(p.markdown[:2200]).lower()):
                continue
            m = re.search(r"\*\*"+label+r"\*\*\s*((?:Monday|Mon)[^\n]*(?:\s*\n\s*(?:Friday|Saturday|Sunday)[^\n]*)+)", p.markdown, re.I)
            if m:
                text = plain(m[1])
                src = Source(p.url, self.sid, m[0])
                if not examples or ("same" in q or "differ" in q) and "noon" in text and "noon" not in examples[0][0]:
                    examples.append((text, src))
                if specific or len(examples) == 2:
                    break
        if examples:
            text = " Hours at another branch are ".join(item[0] for item in examples)
            return Answer("One published " + label.lower() + " schedule is " + text +
                          (" Hours vary. Which branch do you need?" if not specific else "."),
                          sources=[item[1] for item in examples])
