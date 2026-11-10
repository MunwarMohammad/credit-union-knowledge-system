"""Independent, synthetic snapshots. No participant files or network needed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "submission"))
from contract import Page, Snapshot
from solution import build


def page(path, text):
    return Page("https://example.test/" + path, "", text, "2026-05-01")


def edition(day, rate, extra=()):
    table = (
        "| Certificate | Dividend Rate | APY |\n|---|---|---|\n"
        f"| 6 Month | 2.11% | {rate}% |\n"
        "| 6 Month Fixed Jumbo Certificate Special | 3.40% | 3.55% |\n\n"
        "| Account Type | Balance Tier | Dividend Rate | APY |\n|---|---|---|---|\n"
        "| Share Savings | $100+ | 0.10% | 0.11% |\n"
        "| Bright Savings | $100+ | 1.10% | 1.11% |\n"
        "| Investor's Choice Money Market | $100+ | 0.40% | 0.41% |"
    )
    return Snapshot(day, day, [page("personal/savings-account", table), *extra])


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.ks = build()
        self.ks.ingest(edition("2026-05-01", "2.12"))
        self.ks.ingest(edition("2026-09-01", "2.22"))

    def test_as_of_between_crawls(self):
        self.assertIn("2.12% APY", self.ks.answer("6 mo cert", "2026-08-31").text)

    def test_fee_must_match_reason(self):
        fees = page("fees", "Rush fee for debit card $50.00")
        self.ks.ingest(edition("2026-10-01", "2.30", [fees]))
        for question in ("lost debit card fee", "How much is a lost debit card fee?"):
            answer = self.ks.answer(question)
            self.assertFalse(answer.confident)
            self.assertEqual([], answer.sources)
        rush = self.ks.answer("How much is a rush debit card fee?")
        self.assertTrue(rush.confident)
        self.assertEqual(fees.markdown, rush.sources[0].quote)

    def test_no_future_evidence(self):
        self.assertFalse(self.ks.answer("6 mo cert", "2025-01-01").confident)

    def test_latest_citation(self):
        self.assertEqual(
            "2026-09-01", self.ks.answer("6 mo cert").sources[0].snapshot_id
        )

    def test_term_paraphrase(self):
        self.assertEqual(
            self.ks.answer("6 mo cert"), self.ks.answer("six month certificate APY")
        )

    def test_jumbo_tier(self):
        answer = self.ks.answer("6 month jumbo cert")
        self.assertIn("3.55% APY", answer.text)
        self.assertNotIn("2.22%", answer.text)

    def test_unknown_deposits(self):
        for product in (
            "Platinum Plus Savings",
            "Unicorn Savings",
            "Diamond Elite Money Market",
        ):
            with self.subTest(product=product):
                a = self.ks.answer("What is the rate on the " + product + " account?")
                self.assertFalse(a.confident)
                self.assertFalse(a.sources)

    def test_known_named_product(self):
        self.assertIn("1.11% APY", self.ks.answer("rate for Bright Savings").text)

    def test_unpublished_term(self):
        self.assertFalse(self.ks.answer("999 month cert APY").confident)

    def test_changes_are_history(self):
        self.assertEqual([], self.ks.conflicts())

    def test_conflicting_disclosures(self):
        stale = page(
            "calculators/cd", "| Certificate | APY |\n|---|---|\n| 6 Month | 2.00% |"
        )
        self.ks.ingest(edition("2026-10-01", "2.30", [stale]))
        (conflict,) = self.ks.conflicts()
        self.assertEqual("2.30%", conflict.resolution)
        self.assertEqual({"2.00%", "2.30%"}, set(conflict.values))
        self.assertEqual({"2026-10-01"}, {s.snapshot_id for s in conflict.sources})

    def test_recreational_table_excluded(self):
        rec = page(
            "personal/loans/recreational-loans",
            "| Loan Program | Term | APR |\n|---|---|---|\n| 2024-27 Model Year | 60 Months | 8.10% |",
        )
        self.ks.ingest(edition("2026-10-01", "2.30", [rec]))
        self.assertFalse(self.ks.answer("2025 auto loan APR for 60 months").confident)

    def test_mortgage_typo_and_short_term(self):
        home = page(
            "personal/loans/home-loans",
            "| Program | Rate | Points | APR |\n|---|---|---|---|\n| Purchase: 30-Year Fixed | 6.00% | 0 | 6.04% |",
        )
        self.ks.ingest(edition("2026-10-01", "2.30", [home]))
        self.assertIn("6.04% APR", self.ks.answer("30 yr").text)
        self.assertEqual(self.ks.answer("30 yr"), self.ks.answer("30 yr mortage rate"))

    def test_paragraph_search(self):
        source = page(
            "members/archive",
            "Members can download archived statements from the document center.",
        )
        self.ks.ingest(edition("2026-10-01", "2.30", [source]))
        result = self.ks.answer("How do I download archived statements?")
        self.assertEqual(source.markdown, result.sources[0].quote)
        self.assertFalse(
            self.ks.answer("How do I download lunar statements?").confident
        )

    def test_removed_fee_uses_latest_prior_evidence(self):
        system = build()
        for day, fee in [("2026-01-01", "$2"), ("2026-02-01", "$2.50")]:
            system.ingest(edition(day, "2.12", [page("fees", "Lost debit card replacement fee: " + fee)]))
        system.ingest(edition("2026-03-01", "2.12"))
        answer = system.answer("How much is a lost debit card replacement?")
        self.assertIn("$2.50", answer.text)
        self.assertIn("Last seen on 2026-02-01", answer.text)
        self.assertIn("2026-03-01", answer.conflict_note)
        self.assertEqual("2026-02-01", answer.sources[0].snapshot_id)

    def test_generic_business_deposit_categories(self):
        table = "| Account Type | Balance Tier | APY |\n|---|---|---|\n"
        table += "| Business 1st Rate Checking | $100+ | 1.00% |\n| Business Share Savings | $100+ | 0.50% |"
        self.ks.ingest(edition("2026-10-01", "2.30", [page("business/checking-accounts", table)]))
        for category, rate in [("checking", "1.00%"), ("savings", "0.50%")]:
            answer = self.ks.answer("What is the business " + category + " APY?")
            self.assertIn(rate, answer.text)
            self.assertEqual(1, len(answer.sources))
        self.assertTrue(self.ks.answer("Does Dupaco offer a 4.5% APY savings account?").text.startswith("No."))

    def test_prior_certificate_rate_repeated_in_live_promo(self):
        promo = page("promo", "Summer special: 6-month certificate APY 2.12% (offer ended)")
        self.ks.ingest(edition("2026-10-01", "2.30", [promo]))
        (conflict,) = self.ks.conflicts()
        self.assertEqual("2.30%", conflict.resolution)
        self.assertEqual({"2.12%", "2.30%"}, set(conflict.values))
        self.assertIn(promo.url, [s.url for s in conflict.sources])
        self.assertIn("2026-05-01", [s.snapshot_id for s in conflict.sources])
