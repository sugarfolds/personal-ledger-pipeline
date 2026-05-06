# Vercel Deployment

The browser annual report is a static, browser-only app. Deploy only this folder:

```text
web/annual-report/
```

Recommended Vercel project setting:

- Framework preset: Other
- Root Directory: `web/annual-report`
- Build Command: leave empty
- Output Directory: `.`

This keeps the public website limited to:

- `index.html`
- `src/app.js`
- `src/styles.css`

Do not deploy the repository root as the public website. The repo contains docs, synthetic fixtures, examples, and local-run pipeline folders that are useful for GitHub but should not be part of the web product surface.

Before deploying, run:

```bash
make verify-web-mobile
```

For a one-off CLI deployment from a local checkout, use a temporary static bundle:

```bash
rm -rf /tmp/personal-annual-report-vercel-deploy
mkdir -p /tmp/personal-annual-report-vercel-deploy
cp -R web/annual-report/index.html web/annual-report/src /tmp/personal-annual-report-vercel-deploy/
npx vercel@latest deploy /tmp/personal-annual-report-vercel-deploy --prod
```

Privacy expectations:

- No user bill file should be committed.
- No private generated report should be committed.
- The browser page should not call backend APIs while parsing or rendering.
- The mobile verifier should report zero third-party requests before public release.
