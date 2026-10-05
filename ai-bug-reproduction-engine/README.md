# AI Bug Reproduction Engine

A developer submits a natural-language bug report and a small Python repository. The engine writes **one Pytest test that asserts the expected behaviour**, runs it in an isolated sandbox, and returns an evidence-backed verdict:

- `REPRODUCED` — a failed assertion (the bug is still present)
- `NOT_REPRODUCED` — the test passed every time
- `INCONCLUSIVE` — import errors, wrong API use, timeouts, or mixed error/assertion noise

The engine **never edits application code** and **never claims a reproduction without a real matching failed assertion**.

## Quick start

```bash
cd ~/Projects/ai-bug-reproduction-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; works offline without ANTHROPIC_API_KEY
```

**Demo (offline, local sandbox warning):**

```bash
python -m bugrepro run --report examples/bug_report.json --repo examples/sample-shop --local
python -m bugrepro retest RUN-0001 --repo examples/sample-shop-fixed --local
python -m bugrepro list
python -m bugrepro show RUN-0001
```

Expected: `REPRODUCED` on `examples/sample-shop`, then `FIX_VERIFIED` on `examples/sample-shop-fixed`. A sequential single-click test in each shop **passes on both** and hides the race.

**Tests:**

```bash
python -m pytest
```

**API + dashboard:**

```bash
uvicorn bugrepro.api:app --reload --port 8000
# open http://127.0.0.1:8000
```

**Docker runner image (untrusted-repo sandbox):**

```bash
docker build -t bugrepro-runner:latest runner
python -m bugrepro run --report examples/bug_report.json --repo examples/sample-shop
```

A zip of the project is produced with `make zip`.

## Folder tree

```
ai-bug-reproduction-engine/
├── bugrepro/                 # engine, CLI, API
│   ├── analyzer.py
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── generator.py
│   ├── llm.py
│   ├── locator.py
│   ├── models.py
│   ├── paths.py
│   ├── pipeline.py
│   ├── report.py
│   ├── runner.py
│   ├── store.py
│   ├── verifier.py
│   └── static/index.html     # dashboard
├── runner/Dockerfile         # non-root pytest image
├── examples/
│   ├── bug_report.json
│   ├── sample-shop/          # buggy check-then-create
│   └── sample-shop-fixed/    # lock around check+create
├── tests/
├── benchmark/
├── requirements.txt
├── Makefile
├── pytest.ini
└── README.md
```

## Architecture

One module per pipeline step:

1. **Collect** — store the original report under `RUN-0001`, `RUN-0002`, …
2. **Analyse** — observed vs expected, a *testable* hypothesis (not a confirmed root cause), bug class, keywords, follow-up questions
3. **Locate** — score `.py` files against keywords; top files with a one-line reason
4. **Generate** — one Pytest file asserting **expected** behaviour (fails while the bug exists). Race cases use `threading.Barrier`. No network, no long sleeps.
5. **Execute** — run the test several times (default 3) in Docker (or local-dev mode)
6. **Verify** — `PASS` / `ASSERT_FAIL` / `ERROR` / `TIMEOUT`. Only `ASSERT_FAIL` is a reproduction. Errors trigger **one** LLM (or no-op offline) repair pass.
7. **Report** — Markdown + JSON, plus a timeline
8. **Retest** — rerun the **saved** test against a fixed tree

Offline (no API key): heuristics plus a built-in duplicate-submission / race-condition template.

With `ANTHROPIC_API_KEY`, Claude is used for analysis, generation, and a single repair attempt. Failures fall back to heuristics.

## Safety design

Repository code is **untrusted**.

Docker flags:

- `--network none`
- `--read-only`
- `tmpfs /tmp`
- `--cap-drop ALL`
- `no-new-privileges`
- memory / CPU / PID limits
- repo mounted **read-only**
- per-run timeout
- non-root `uid 1000` in `runner/Dockerfile`
- **no** secrets or host credentials in the container (`ANTHROPIC_API_KEY` is stripped even in local mode)

The **API** rejects any repository path outside `BUGREPRO_ALLOWED_ROOT` (default `./examples`).

Local subprocess mode exists for development only and prints a clear warning.

Every run writes an audit trail: original report, generated test, attempt outputs, timeline, Markdown and JSON reports under `data/runs/RUN-xxxx/`. The file layout is intentionally table-shaped so PostgreSQL can replace it later (`runs`, `analyses`, `executions`, `reports`).

## Demo scenario

`place_order()` checks an idempotency key and then creates an order + payment. On the buggy shop those steps are **not atomic**, so two rapid requests create two orders and two payments. The fixed shop wraps check-and-create in a `threading.Lock`.

`examples/sample-shop/tests/test_single_click.py` calls `place_order` twice **sequentially** and passes on both trees.

## Benchmark

```bash
python -m benchmark.harness --local
```

Reads `benchmark/manifest.json` (`report` + buggy repo + fixed repo) and prints:

- reproduction rate
- false-positive rate (generated test still fails on the fixed repo)
- mean time to reproduce

## Limitations (honest)

- Offline mode only has a strong generator for **duplicate-submission / race-condition** bugs. Other classes get the same template and will often be `INCONCLUSIVE`.
- LLM-generated tests can import the wrong API, miss the real trigger, or overfit examples. The verifier treats that as `INCONCLUSIVE`, not as a reproduction.
- Bugs that need production data, auth, browsers, or network services cannot be reproduced here (sandbox is `--network none`).
- A reproduction is **not** a root-cause diagnosis. The hypothesis is explicitly testable behaviour.
- Docker on macOS still uses a VM; resource limits apply inside the container, not as a perfect security boundary.
- Intermittent races may need several repeats; mixed `ERROR` + `ASSERT_FAIL` is classified `INCONCLUSIVE` on purpose.

## Roadmap

- PostgreSQL store with the same JSON schemas
- Broader offline templates (off-by-one, None vs empty, timezone)
- Coverage-guided file location
- Optional browser sandbox for UI bugs
- Signed audit bundles for sharing a run

## License

Use and modify freely for internal engineering tools.
