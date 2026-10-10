# 0003: Authentication with Google Identity Platform

- Status: accepted
- Date: 2026-10-10

## Context

Users sign in with Google. Native iOS apps will later need Sign in with Apple, because Apple requires it alongside other third-party sign-in options. Password storage is something we want to avoid entirely.

## Decision

- Use Google Identity Platform (Firebase Authentication on Google Cloud) with the Google provider now and Apple added later.
- The web app signs the user in and obtains a short-lived ID token.
- Every API request carries that token. The API verifies signature, issuer, audience, expiry and `email_verified` on every request, then maps the token's subject to a `users` row.
- Token verification sits behind an interface so tests can use a fake verifier without network access.

## Consequences

- No passwords stored, no session database to protect.
- A stolen token is valid only until it expires (about an hour).
- The API never trusts identity claims from the web layer; it checks the token itself.
