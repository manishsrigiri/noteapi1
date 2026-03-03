# noteapi

## GitHub OAuth setup

1. Create a GitHub OAuth App:
   - Homepage URL: `http://localhost:8501`
   - Authorization callback URL: `http://localhost:8000/auth/github/callback`
2. Copy `.env.example` to `.env` and fill:
   - `OAUTH_GITHUB_CLIENT_ID`
   - `OAUTH_GITHUB_CLIENT_SECRET`
3. Start app:
   - `docker compose up -d --build`
4. Open `http://localhost:8501` and click `Login with GitHub`.

## Google OAuth setup

1. Create a Google OAuth Client (Web application) in Google Cloud Console.
2. Set:
   - Authorized JavaScript origin: `http://localhost:8501`
   - Authorized redirect URI: `http://localhost:8000/auth/google/callback`
3. Add to `.env`:
   - `OAUTH_GOOGLE_CLIENT_ID`
   - `OAUTH_GOOGLE_CLIENT_SECRET`
4. Restart:
   - `docker compose up -d --build`
5. Open `http://localhost:8501` and click `Login with Google`.

### Dev/testing mode without OAuth

Set `AUTH_DISABLED=true` in `.env` to bypass authentication locally.
