# noteapi

## Basic login (no OAuth)

You can log in without OAuth using the built-in username/password flow.

1. Open `http://localhost:8501`.
2. In login page, use `Sign Up` tab to create a new account.
3. Login with your created username/password.

Fallback mode:
- You can still set `.env`:
  - `BASIC_AUTH_USERNAME`
  - `BASIC_AUTH_PASSWORD`
  - `ADMIN_USERNAMES` (comma-separated usernames allowed to view login/session stats)
- These fallback credentials continue to work if no matching DB user exists.
4. Restart:
   - `docker compose up -d --build`

Default credentials in `.env.example`:
- Username: `demo`
- Password: `demo123`

Privacy note:
- Login/session stats are visible only to admin users listed in `ADMIN_USERNAMES`.
- App does not display login location/IP in UI.

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

## Google Workspace (Corporate) OAuth setup

1. Create a Google OAuth Client (Web application) in Google Cloud Console.
2. Set:
   - Authorized JavaScript origin: `http://localhost:8501`
   - Authorized redirect URI: `http://localhost:8000/auth/google-workspace/callback`
3. Add to `.env`:
   - `OAUTH_GOOGLE_WORKSPACE_CLIENT_ID`
   - `OAUTH_GOOGLE_WORKSPACE_CLIENT_SECRET`
   - `OAUTH_GOOGLE_WORKSPACE_DOMAIN` (your workspace domain, e.g. `yourcompany.com`)
4. Restart:
   - `docker compose up -d --build`
5. Open `http://localhost:8501` and click `Continue with Google Workspace`.

### Dev/testing mode without OAuth

Set `AUTH_DISABLED=true` in `.env` to bypass authentication locally.
