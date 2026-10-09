# Security policy

## Supported versions

Security fixes go into the latest release.

## Reporting a vulnerability

Report privately through the repository's **Security** tab ("Report a vulnerability").
Do not open a public issue.

Include the mm-arena version, your OS, what goes wrong, and how to reproduce it. Expect an
acknowledgement within a week.

## Threat model

mm-arena is a local command-line tool that sends prompts to model providers you choose.

- **API keys come from the environment only.** mm-arena reads them from environment
  variables, never from config or trace files, and never logs or stores them. Do not paste
  keys into issues or result submissions.
- **The response cache may contain prompts and responses.** Cached provider responses and
  run traces include the full game text and raw model output. Treat the cache and run
  directories like any other data from your provider account, and check them before sharing.
- **Traces are plain JSONL.** They hold quotes, P&L, latency, token usage, cost and the raw
  model text in `info`. They do not contain credentials.
- **Provider SDKs are optional extras** and are not audited by this project.
