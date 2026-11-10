# Credit union snapshot knowledge system

Ask about a credit union product today or as of an earlier crawl. The offline Python implementation scored **0.9643** on the 40 public questions, with 38 full-credit answers, one partial and one zero. No API keys or third-party packages are required.

- Start with the latest full snapshot on or before the requested date. If only an earlier crawl has evidence, cite it and label the answer with the date it was last seen.
- Match a published product, term, tier and metric, then return the supporting excerpt.
- Prefer the product disclosure when sources disagree. Use FAQ and paragraph search for service questions and decline when evidence is insufficient.

From this repository, with Python 3.11+ and the participant kit extracted elsewhere:

~~~sh
python ask.py --kit /path/to/hackathon-knowledge-kit-participant "6 mo cert"
~~~

Add `--as-of 2026-05-31` for a historical answer or replace the question with `--conflicts` for current disagreements. The participant kit is **not redistributed**. The harness unpacks the snapshot archives on first use.

## Run the assessment

From the top directory of the **organizers’ kit**, point the harness at the submission folder in your fresh clone:

~~~sh
python harness/run_eval.py --submission /absolute/path/to/credit-union-knowledge-system/submission --eval eval/public_eval.jsonl
~~~

From the repository root, run the independent synthetic tests with `python -m unittest discover -s tests -v`. GitHub Actions runs the same suite on Python 3.11.

The kit’s five-question self-test scored **1.0**, including conflict resolution.

## Design decisions and limits

Each crawl is a separate index. An earlier price is useful for a historical question. The conflict report focuses on disagreements that coexist in the newest crawl. A named savings product must match a published label before the system quotes a tier. A bare year term such as “30 yr” is interpreted as a mortgage.

Paragraph retrieval uses lexical matching and conservative thresholds. Unfamiliar aliases can produce a refusal. Some services still use patterns tied to the supplied website. The public score does not measure recall or precision against the private conflict key.

[Assessment review](docs/assessment-review.md) · [Source authority and retrieval rules](submission/NOTES.md)
