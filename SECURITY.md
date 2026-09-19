# Security Policy

## Supported Versions

There are no tagged releases yet. Only the latest commit on `main` is
supported. If you are running an older commit, update to the latest `main`
before reporting an issue.

## Reporting a Vulnerability

Report suspected vulnerabilities privately, not in a public issue:

- Preferred: GitHub Private Vulnerability Reporting — open this repository's
  Security tab and select "Report a vulnerability".
- If that option is not available to you, email hello@dkautomation.dev
  instead.

Do not open a public issue for a suspected vulnerability.

You should get a first response within 3 business days.

A good report includes:

- Steps to reproduce the issue
- The affected file (for example `scraper/http_client.py`, `scraper/sites.py`,
  or `scraper/cli.py`)
- The impact: what an attacker, or a malicious target page, could do with it

## Scope

The tool fetches HTML from a configured target site (`scraper/http_client.py`),
parses it into records (`scraper/sites.py`, `scraper/models.py`), deduplicates
and writes it to CSV (`scraper/pipeline.py`), driven by a CLI that also reads
`.env` configuration such as an optional outbound proxy URL (`scraper/cli.py`).

### Treated as a vulnerability here

- A code path that executes, evaluates, or imports content taken from a
  scraped page, instead of treating the response body strictly as inert
  text/HTML data. This is a boundary the current code respects — parsing in
  `scraper/sites.py` only reads HTML with BeautifulSoup and never runs it —
  so a report here should point to where that boundary would actually break,
  not just to the fact that a response body is being read.
- Credentials or secrets from `.env` (for example, a `SCRAPER_PROXY` value
  with an embedded `user:pass`) leaking into scraped-output CSV files
  (`sample_output/`, or any `--out` destination) or into log output.

### Not treated as a vulnerability here

- Defeating a target site's rate limits, `robots.txt`, or anti-bot/anti-scraping
  measures. That is normal, expected behavior for a tool like this one, not a
  vulnerability in it. Responsibility for how this tool is pointed at a given
  target site rests with whoever runs it, not with this project's threat model.
