# EC2 checklist

I wrote this while setting up Square OAuth on EC2. The app is live now, but these are still the things worth checking before opening it up to more merchants.

## Current setup

On November 5, 2026, the public site was switched to Docker image `forecastops-release:ba39344` on localhost port `8004`. Nginx handled HTTPS and all three public checks returned 200:

- `/api/health`
- `/api/demo`
- `/api/square/status`

The container reported healthy. The older Square-enabled container was left on port `8003` for rollback.

A real Square Production import worked on an earlier release and produced 180 daily observations. The public status check on this release confirms the connector is configured, **not** that another real import has been completed.

## Square configuration

The registered callback is `https://forecastops.jeshwanthanthony.com/api/square/callback`. Credentials and session keys belong only in the restricted environment file on EC2:

- `SQUARE_ENVIRONMENT=production`
- `SQUARE_PRODUCTION_APP_ID`
- `SQUARE_PRODUCTION_APPLICATION_SECRET`
- `SQUARE_REDIRECT_URI`
- `SESSION_SECRET` and `ENCRYPTION_KEY`
- `COOKIE_SECURE=true`
- `PUBLIC_ORIGIN`

Use the Square OAuth application secret, not a personal Square access token. Don't copy secrets into Git, Docker build arguments, screenshots, or terminal logs.

## Things to keep an eye on

- Nginx needs to forward `/api/square/` to the active app. Avoid recording callback query strings in access logs because they contain a one-time code and state.
- The SQLite file on the persistent volume contains encrypted visitor credentials. Keep its permissions restricted and retain the same encryption key across releases.
- The browser sessions are temporary, not user accounts. Expiring a local session doesn't necessarily revoke authorization in Square; users may need to disconnect in Square.
- The rate limiter works per process. Proxy IP handling and edge rate limits need a proper review before wider use.
- Don't expose configuration diagnostics or interactive API docs on the public domain.
- Keep public OpenAI requests disabled unless there's a real quota and abuse-control system.

## Before adding more merchants

Test two independent browser sessions, authorization, token refresh, cancellation, disconnect, reconnect, multiple Square locations, and merchants with no completed orders. Check logging and error handling along the way.

The Docker releases are still deployed manually, not by GitHub Actions. After each release, check the public endpoints and do a real Square import with an authorized account. Keep a working container and Nginx backup until those checks pass.
