"""Extract qualified rates from Markdown tables and filter them by member intent."""
import re
from collections import namedtuple
from urllib.parse import urlsplit

Row = namedtuple("Row", "family label tier fields source rank")
PCT = re.compile(r"\d+(?:\.\d+)?%")
MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)(k)?", re.I)


def amounts(text):
    return [float(n.replace(",", "")) * (1000 if k else 1) for n, k in MONEY.findall(text)]


def normal(text):
    return re.sub(r"\s+", " ", text.lower().replace("–", "-").replace("—", "-").replace(",", "").replace(".00", "").strip())


def key(row):
    return row.family, normal(row.label), normal(row.tier)


def extract(page, sid, Source):
    path = urlsplit(page.url).path.rstrip("/")
    header = []
    context = []
    for raw in page.markdown.splitlines():
        if not raw.startswith("|"):
            header = []
            if raw.strip():
                context = (context + [raw.strip()])[-3:]
            continue
        cells = [c.strip().strip("*") for c in raw.strip().strip("|").split("|")]
        if not header:
            header = [c.lower() for c in cells]
            continue
        if len(header) != len(cells) or not PCT.search(raw):
            continue
        label, tier, fields = cells[0], "", {}
        if header[0] == "certificate" or (header[0] == "term" and "dividend rate" in header):
            family = "certificate"
        elif header[0] in ("balance tier", "balance"):
            names = ("High-Yield Savings", "Health Savings Account", "Investor’s Choice", "Share Savings")
            label = next((n for n in names if n.lower() in " ".join(context).lower()), "")
            if not label:
                continue
            if label == "Investor’s Choice":
                label = "Investor's Choice Money Market"
            family, tier = "deposit", cells[0]
        elif "balance tier" in header:
            family, tier = "deposit", cells[1]
        elif "points" in header and "apr" in header:
            family = "mortgage"
        elif "model year" in label.lower() and "term" in header:
            family, tier = "auto loan", cells[1]
        elif header[0] == "product" and "home-equity" in path:
            family = "home equity"
        elif header[0] == "card type":
            family = "card"
        elif header[0] == "term" and "personal-loans" in path:
            family = "personal loan"
        else:
            continue
        for h, c in zip(header, cells):
            m = PCT.search(c)
            if m and h != "points":
                metric = "APY" if "yield" in h or "apy" in h else "APR" if "apr" in h or "annual percentage rate" in h else "dividend rate" if "dividend" in h else "rate"
                fields[metric] = m.group()
            elif "min." in h and "$" in c:
                fields[h] = c
        canonical = {"home equity": ("personal/loans/home-equity",), "certificate": ("personal/savings-account",), "mortgage": ("personal/loans/home-loans",),
                     "auto loan": ("personal/loans/auto-motorcycle-loans",), "personal loan": ("personal/loans/personal-loans",),
                     "card": ("business/credit-cards", "personal/credit-cards"), "deposit": ("personal/savings-account", "personal/checking-accounts", "business/savings-accounts", "business/checking-accounts")}
        rank = 3 if path.strip("/") in canonical[family] else 2 if path.startswith(("/personal/", "/business/", "/rates/")) else 1
        yield Row(family, label, tier, fields, Source(page.url, sid, raw), (rank, page.fetched_at))


def family_for(q):
    for pattern, family in [("home equity|heloc", "home equity"), (r"\bcds?\b|certificate", "certificate"), (r"mortgage|home loan", "mortgage"),
                            (r"\b(car|auto|vehicle|motorcycle)\b", "auto loan"), ("personal loan", "personal loan"),
                            (r"credit card|visa", "card"), (r"saving|checking|money market|\bhsa\b", "deposit")]:
        if re.search(pattern, q):
            return family


def model_years(label):
    m = re.search(r"(\d{4})(?:\s*[-–]\s*(\d{2,4}))?", label)
    if not m:
        return 1, 0
    start = int(m[1])
    end = int(m[2]) if m[2] else start
    if end < 100:
        end += start // 100 * 100
    return (0 if "older" in label.lower() else start), end


def choose(rows, q, family):
    q = q.replace("high yield", "high-yield").replace("first rate", "1st rate")
    q = q.replace("investor’s choice", "money market").replace("investor's choice", "money market")
    rows = [r for r in rows if r.family == family and r.rank[0] >= 2]
    if re.search(r"intro|balance.transfer|cash advance|foreign transaction|annual fee", q):
        return []
    if re.search(r"business|commercial", q) and family not in ("deposit", "card"):
        return []
    if family == "certificate":
        retirement = bool(re.search(r"\bira\b|roth|traditional|retirement", q))
        rows = [r for r in rows if ("retirement" in r.source.url or "ira" in r.label.lower()) == retirement]
        for qualifier in ("roth", "traditional"):
            if qualifier in q:
                rows = [r for r in rows if qualifier in r.label.lower()]
    term = re.search(r"\b(\d+)[ -]*(?:month|mo\b|year|yr\b)", q)
    if term:
        number = int(term[1])
        in_years = bool(re.search(r"year|yr", term[0]))
        if family == "mortgage":
            if not in_years and number % 12:
                return []
            number = number if in_years else number // 12
            unit = "year"
        else:
            number = number * 12 if in_years else number
            unit = r"(?:month|mo\b)"
        pattern = rf"\b{number}[- ]*{unit}"
        rows = [r for r in rows if re.search(pattern, normal(r.label+" "+r.tier))]
    if family == "home equity":
        line = bool(re.search(r"line of credit|heloc", q))
        rows = [r for r in rows if ("heloc" in r.label.lower()) == line]
    if family == "certificate":
        if "jumbo" in q or "standard" in q or "non-jumbo" in q:
            jumbo = "jumbo" in q and "non-jumbo" not in q
            rows = [r for r in rows if ("jumbo" in r.label.lower()) == jumbo]
        if "special" in q:
            rows = [r for r in rows if "special" in r.label.lower()]
    if family == "auto loan":
        years = re.findall(r"\b(?:19|20)\d\d\b", q)
        if years:
            year = int(years[0])
            rows = [r for r in rows if model_years(r.label)[0] <= year <= model_years(r.label)[1]]
    money = amounts(q)
    if family == "mortgage":
        purpose = "refinance" if "refi" in q else "purchase"
        rows = [r for r in rows if purpose in r.label.lower()]
        if re.search(r"adjustable|\barm\b|\d/\d|construction|fha|va loan|jumbo", q):
            return []
        rows.sort(key=lambda r: amounts(r.label) or [float("inf")])
        if money:
            rows = [r for r in rows if amounts(r.label) and amounts(r.label)[0] >= money[0]][:1]
    if family in ("card", "deposit"):
        if family == "deposit" or "business" in q or "personal" in q or "platinum" in q or "rewards" in q:
            rows = [r for r in rows if ("business" in r.label.lower()) == ("business" in q)]
        words = ("platinum", "rewards") if family == "card" else ("bright", "holiday", "health", "launchpad", "money market", "high-yield", "you name it", "free checking", "1st rate", "prime", "jump start", "achieve", "checking", "share savings")
        for word in words:
            if word in q:
                rows = [r for r in rows if word in r.label.lower()]
        if family == "deposit" and "hsa" in q:
            rows = [r for r in rows if "health" in r.label.lower()]
        elif family == "deposit" and not any(w in q for w in words):
            rows = [r for r in rows if r.label.lower() == "share savings"]
        if money:
            def within(tier):
                bounds = amounts(tier)
                return bounds and bounds[0] <= money[0] and (len(bounds) == 1 or money[0] <= bounds[1])
            rows = [r for r in rows if within(r.tier)]
        if rows and re.search(r"highest|maximum|top|best", q):
            rows = [max(rows, key=lambda r: float(r.fields.get("APY", "0%")[:-1]))]
    return rows
