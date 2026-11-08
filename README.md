# Credit union snapshot knowledge system

Place the extracted participant kit in this directory as hackathon-knowledge-kit-participant/. The kit and local evaluation outputs are excluded from version control. Use Python 3.11 or newer.

Ask about the most recent crawl or specify an earlier date.

~~~sh
python3 ask.py "What is the APR for a 60-month auto loan on a 2025 vehicle?"
python3 ask.py "What is the 10-month jumbo certificate APY?" --as-of 2026-05-31
python3 ask.py --conflicts
~~~

Each command prints JSON with snapshot citations. Pass --kit PATH if the kit is elsewhere.

Run the official public evaluation from the extracted kit.

~~~sh
cd hackathon-knowledge-kit-participant
python3 harness/run_eval.py --submission ../submission --eval eval/public_eval.jsonl --out ../results
~~~

The submission folder contains the complete grader entry point, its dependencies and design notes. The queries run entirely from the supplied website captures.
