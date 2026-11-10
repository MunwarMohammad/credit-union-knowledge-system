# Credit union knowledge system assessment

A member asking for a loan rate needs to know which rate applies to their vehicle and term on the date they ask about. The website can contain a correct product disclosure and an older calculator at the same time. Searching for the first percentage on either page can give a plausible but wrong answer.

## Assignment and materials

The assignment PDF sets the contract, timing limits, evaluation weights and submission checklist. The participant ZIP contains five website captures dated May 12, May 19, June 9, August 27 and September 28, 2026. Each full capture pairs a page manifest with Markdown content. The ZIP also supplies 40 public questions, starter code, and the harness used for grading.

The system must ingest the captures in order, answer current or historical questions with citations, resolve conflicts, and acknowledge missing evidence. The assessment weights accuracy at 55%, and conflict handling, consistency and speed at 15% each. The full conflict key and additional questions are private. To reproduce the public run, use the original kit and [the command in the README](../README.md#run-the-assessment).

## How a question becomes an answer

1. **Select the edition.** A question dated May 31 uses the May 19 capture. For the 10-month fixed jumbo certificate that edition lists 3.90% APY. The September edition lists 4.00%. Both observations remain accessible.
2. **Resolve the requested product.** The parser retains row labels and distinguishes APY, dividend rate, interest rate and APR. A term alone cannot select a loan price if the year or balance puts the member in another tier. Named deposit accounts are matched against the edition’s product labels. “Platinum Plus Savings,” “Unicorn Savings,” and “Diamond Elite Money Market” are regression cases for refusal.
3. **Compare applicable sources.** For a 2025 vehicle on a 60-month loan, two tables in September quote 5.34% and 5.39%. Their model-year bands overlap. The official product table supports 5.39%. A change between two otherwise consistent crawls belongs to the historical index.
4. **Return the evidence.** Each confident answer carries the URL, snapshot ID and excerpt. Rates use structured rows. Service questions can use a targeted extractor, a published FAQ, or a distinctive matching paragraph. If the selected evidence is insufficient, the program can decline.

## Public results

| Measure | Result |
|---|---:|
| Weighted public score | 0.9643 |
| Full / partial / zero | 38 / 1 / 1 |
| Runtime errors / flagged stale values | 0 / 0 |
| Consistent repeat checks | 20 of 20 |
| Current conflict entries with a selected value | 37 of 37 |

The lobby question now cites the branch locator alongside its schedule. The drive-up answer also cites the locator, but the grader accepts a different release or the home page for that item and awards 0.85. The certificate-list question returns the rates but earns zero because the default grader has no required tokens for that free-text item. The optional model judge was disabled.

For the volunteer question, the evidence supports 294 employees in 2023 and 256 in 2024. The answer supplies both dated figures and says it could not verify a 2025 count. All three public refusal items receive full credit. The synthetic tests separately exercise unknown products and paraphrases that do not appear in the practice set.

## Why use rules and search

Keeping row structure preserves qualifiers that can disappear when a table is flattened into paragraphs. Deterministic date and source selection makes the results reproducible without a model or API key. Paragraph retrieval extends coverage to unfamiliar service questions without generating new claims. A retrieved paragraph can still be topically relevant but insufficient, and strict matching can miss valid paraphrases. The latest-crawl conflict policy favors actionable disputes at the cost of historical conflict coverage. Its impact on hidden grading is unknown.

## Files in the repository

| File | Purpose |
|---|---|
| ask.py | Local CLI that loads the kit and prints JSON answers or conflicts. |
| submission/solution.py | Harness entry point, dated indexes, conflict assembly and answer formatting. |
| submission/rates.py | Rate extraction, product, balance, model-year and term matching. |
| submission/evidence.py | Dated statements, branch information and service evidence. |
| submission/search.py | BM25 index and conservative passage selection. |
| submission/contract.py | Snapshot, page, source, answer and conflict types. |
| submission/requirements.txt | Declares the standard-library-only runtime. |
| submission/NOTES.md | Source ranking, eligibility, thresholds and limitations. |
| tests/test_knowledge.py | Independent unittest cases with small, invented snapshots. |
| .github/workflows/test.yml | Runs the tests on pushes and pull requests. |
| README.md, docs/assessment-review.md, .gitignore | Usage, evaluation review and exclusion of participant data and credential files. |

The submission is the public repository and the specific Git commit to grade. The organizers can use their own harness and captures without relying on a hosted service.
