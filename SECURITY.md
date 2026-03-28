# Security Policy

## Reporting a Vulnerability

Please do not report security vulnerabilities via public GitHub issues.
Open a private security advisory via GitHub's security tab instead.

## What counts as a security issue

- Credentials, API keys, or tokens committed to the repo
- Dependencies with known CVEs
- Input handling that could affect downstream consumers

## Scope

This is a static analysis library. It reads codebases — it does not execute
arbitrary code, make network requests, or store data. The attack surface is
limited to malicious input files fed to the extractors.

## For contributors and AI agents

- Never commit `.env` files, API keys, tokens, or passwords
- Never hardcode real IP addresses or personal data in tests or examples
- Use placeholder values in examples (e.g. `example.com`, `YOUR_API_KEY`)
