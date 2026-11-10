# Source authority and retrieval rules

Use Python 3.11 and the standard library. The submission reads the snapshot objects supplied by the harness and makes no network calls.

**Time.** Each ingest builds an independent edition. For an as-of question use the newest edition already observed by that date. A missing product does not inherit another account’s terms. The crawl date is an observation date and cannot establish when an unobserved change first took effect.

**Rates.** The canonical product table ranks first, followed by other product or rates pages. Secondary tables such as calculators and campaign pages can supply evidence of disagreement. A standalone promotional page cannot establish a current rate. The system does not parse arbitrary offer-expiration language: even an expired offer copied onto a canonical page could require further review. A mounted table row’s term, amount, product name and metric must apply to the question.

**News and branches.** For organizational facts, rank dated releases by publication date. A recrawl does not make an old article new. Compare dated volunteer figures with the requested reporting year, and label any historical alternatives. For branch schedules, cite the actual published schedule. The contact page supports the branch locator only.

**Conflicts.** Compare sources within the latest full crawl for the same qualified fact. Auto model-year bands compare only on their intersection. Ignore differences in numeric precision, changes seen only between crawls, and candidates without an authoritative winner. The report therefore omits unresolved disputes and disagreements confined to a previous edition. Duplicate model-year comparisons collapse to one entry per overlap and value pair. Counts describe detected discrepancies, not measured recall.

**Free text.** Service extractors and indexed FAQ or fee entries handle known structures. For other prose questions a BM25 index ranks snapshot-local, deduplicated paragraphs and returns a verbatim excerpt. It skips archived news, blog, calculator and asset paths, headings, questions and percentage-bearing paragraphs. Require at least two distinct content terms, every term present in the same paragraph, a score of at least 0.65 times the sum of query IDFs, and a 12% lead over the next eligible passage. The constants are heuristics, not calibrated probabilities. An unsuccessful structured rate lookup returns an unknown answer directly.
