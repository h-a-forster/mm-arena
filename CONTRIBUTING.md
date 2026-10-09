# Contributing

Bug reports, new game families, providers, baselines and benchmark results are welcome.

## Setup

You need [uv](https://docs.astral.sh/uv/) and git.

```sh
uv sync --all-extras --dev
uv run mm-arena --help
```

## Checks

```sh
uv run pytest -m "not slow"
uv run ruff check src tests
uv run ruff format --check src tests
```

CI runs these on Linux, macOS and Windows with Python 3.11 to 3.13, then runs the `smoke`
suite with the `bayes` agent and builds a report.

Test rules:

- No network and no API keys. Use fake providers.
- Use `tmp_path` for every file.
- Must pass on Windows: `pathlib`, forward slashes in code, no shell assumptions.
- Mark anything over a few seconds with `@pytest.mark.slow`.

## Adding a game family

Families live in `src/mmarena/games/families.py`.

1. Write a builder that returns a `Game`: the enumerated outcomes, their probabilities, the
   settlement value of each outcome, the reveal groups and the `Market` parameters.
2. Register it so `make_game(family, seed, variant)` can build it, with both a `classic` and
   a `perturbed` variant.
3. Hidden state must stay finite and enumerated. The exact posterior and the Bayes-optimal
   quote depend on it.
4. Add tests: probabilities sum to 1, values match the contract text, and `bayes` earns
   non-negative expected P&L.
5. Add the family to a suite TOML in `src/mmarena/suites/` only if it belongs there. Do not
   change a released suite; add a new version instead.

## Adding a provider or agent

An LLM provider lives in `src/mmarena/providers/` and implements
`complete(system, user, *, max_tokens) -> Completion`. Register its spec prefix in
`src/mmarena/agents/registry.py`; `LLMAgent` handles prompting, parsing and repair. Any other
agent implements the `Agent` protocol in `src/mmarena/agents/base.py`:

1. Implement `name`, `reset(game)` and `act(obs) -> Quote`.
2. Raise `AgentError` for unusable model output (scored as an invalid quote). Raise
   `InfraError` for provider failures (the episode is marked `error` and excluded).
3. Read API keys from environment variables only. Never log or store them.
4. Put the SDK behind an optional extra in `pyproject.toml`. The only runtime dependency is
   numpy.
5. Return raw text, token usage and cost in the `Completion` (or `Quote.info`).
6. Test with a fake client. No network in tests.

## Submitting benchmark results

Open an issue with the "Result submission" template. Include:

- The run directory: the traces (`*.jsonl`) and `summary.json`. A summary alone is not
  accepted.
- Suite name and version, for example `core-v1`.
- Exact model id and provider, and every setting that affects output: temperature, reasoning
  effort or thinking budget, max tokens, prompt changes.
- The mm-arena version (`mm-arena --version`) or commit.
- The command you ran.

Remove API keys and private paths first. Results from a modified suite or engine are labelled
as such.

## Guidelines

- Do not change scoring (`market.py`, `engine.py`) without an issue first. It changes every
  published number.
- Common random numbers must hold: the hidden outcome and counterparty draws depend only on
  (game id, seed), never on the agent.
- Runtime dependencies: numpy only. Discuss new ones in an issue first.
- Match the surrounding style; ruff enforces the rest (line length 100).

## Pull requests

One change per pull request, with tests and docs. Add a line under "Unreleased" in
[CHANGELOG.md](CHANGELOG.md) for user-visible changes.

Security issues: see [SECURITY.md](SECURITY.md).
