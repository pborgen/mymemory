# Google Sign-In for MyMemory (AWS prod)

The API already verifies Google ID tokens (`POST /api/auth/google` +
`Authorization: Bearer`). The web login page renders a GIS button when the API
exposes `googleClientId` via `GET /api/auth/config`.

## 1. Create an OAuth Web client (Google Cloud Console)

1. Open https://console.cloud.google.com/apis/credentials
2. Create project (or pick one) → **Create credentials → OAuth client ID**
3. Application type: **Web application**
4. Name: `MyMemory web`
5. **Authorized JavaScript origins** (no paths):
   - `https://d1x2llv8fpgnu8.cloudfront.net`   # current CloudFront web
   - `http://localhost:3000`                    # local Next
   - later: `https://memory.informedbydata.com`
6. Authorized redirect URIs: leave empty for GIS One Tap / button (ID token flow)
7. Copy the **Client ID** (`….apps.googleusercontent.com`)

If Google asks to configure the OAuth consent screen: External (or Internal for
Workspace-only), add your email as a test user while the app is in Testing.

## 2. Wire Terraform / App Runner

In `infra/terraform.tfvars`:

```hcl
google_client_id       = "YOUR_ID.apps.googleusercontent.com"
super_admin_email      = "you@gmail.com"   # your Google account → first admin
cors_origins           = "https://d1x2llv8fpgnu8.cloudfront.net"
allow_dev_auth_headers = "false"
app_environment        = "production"
```

Then:

```bash
cd infra && terraform apply
# App Runner picks up env from terraform apply automatically.
# Setting google_client_id also enables a NAT gateway (~$32/mo) so the API
# can fetch Google signing certs (VPC-only egress otherwise times out).
```

## 3. Redeploy the static web

```bash
NEXT_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com \
  ./infra/deploy-web-static.sh
```

## 4. Smoke test

1. Open https://d1x2llv8fpgnu8.cloudfront.net/login/
2. Click **Continue with Google**
3. Chat should work; `GET /api/session` with the Bearer token returns your email

## Local Mac

Leave `GOOGLE_CLIENT_ID=` empty and `ALLOW_DEV_AUTH_HEADERS=true` in
`apps/api/.env` — login stays on Paul/Alex. To test Google locally, set the
same client ID and add `http://localhost:3000` as a JS origin.
