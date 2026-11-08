# Snapshot knowledge system

The harness loads solution.py and calls build(). The submission uses only the Python standard library. It needs no API keys, model downloads or network access.

Each ingest creates a separate index for that full crawl. Current queries select the newest index. Historical queries select the last crawl on or before the requested date and decline when the requested date precedes the first crawl. A gap between crawls therefore represents the last observed website. Every confident answer carries its source URL, snapshot ID and excerpt.

The table parser labels each rate by product, metric, term and tier. Product disclosures take priority over secondary tables. Mortgage points, interest rate and APR occupy separate columns. Membership, branch and service answers use evidence from relevant pages, with publication dates distinguishing historical newsroom claims. Other requests can match a published FAQ or fee disclosure. Queries without sufficient matching evidence return an unconfident answer.

The conflict report groups competing observations of the same metric, retains the source for each value, and identifies the current authoritative value when available. Overlapping vehicle model-year bands are also compared for the years they share. Removed tiers can have an unresolved history. Coverage depends on the supported table formats, prose patterns and question wording. Arbitrary contradictions in narrative text may go undetected.

The 40-question public harness scored 0.9364 without the optional LLM judge. Two full misses illustrate limits of the public reference: the complete certificate list has no required tokens and therefore earns zero from the default scorer, and the volunteer question expects a 2023 count for “last year” relative to a 2026 snapshot. The system declines to supply a 2025 count without evidence. Some branch schedules cite different supporting branch releases than those named by the scorer. The full conflict answer key is private.
