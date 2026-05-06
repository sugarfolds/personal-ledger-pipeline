# Privacy And Local Run Checklist

This project is designed for local-first use. Treat real bills as private financial data.

## Before Running

- Keep private raw exports outside public Git history.
- Check that `.gitignore` covers generated private outputs.
- Prefer a private working directory for real bills.
- Do not paste real statements into issues, README files, examples, screenshots, or prompts intended for public sharing.

## Before Publishing

Run checks before any GitHub-facing action:

```bash
git status --short
rg -n "real-name|account|transaction|merchant|balance" raw processed final examples docs README.md
```

Then manually inspect:

- `raw/`
- `processed/`
- `final/`
- `examples/`
- screenshots and exported HTML

Public examples must use synthetic data only.

## Browser App Boundary

The browser annual report app is static. Uploaded files are parsed in browser memory. It has no backend API, no login, and no upload step.

If you deploy the static app later, keep it dependency-light and audit for outbound network requests before inviting people to use it with private exports.
