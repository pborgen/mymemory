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

## 5. iPhone / Expo mobile

The mobile login screen uses `expo-auth-session` and posts the Google ID token
to the same `POST /api/auth/google` endpoint.

1. **Point the app at the AWS API** when building/running:

   ```bash
   cd apps/mobile
   EXPO_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com npx expo start
   # or for a native rebuild:
   EXPO_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com npx expo run:ios
   ```

2. **Create an iOS OAuth client** (required for Simulator / device builds):
   - Google Cloud Console → Credentials → **OAuth client ID** → type **iOS**
   - Bundle ID: `com.pborgen.mymemory`
   - Copy the iOS client ID (`….apps.googleusercontent.com`)

3. **Wire the iOS client into API + app build:**

   ```hcl
   # infra/terraform.tfvars
   google_ios_client_id = "YOUR_IOS_ID.apps.googleusercontent.com"
   ```

   ```bash
   cd infra && terraform apply
   # Rebuild native iOS so the reversed client ID URL scheme is in Info.plist:
   EXPO_PUBLIC_API_URL=https://gapyciuy6q.us-east-1.awsapprunner.com \
   EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=YOUR_IOS_ID.apps.googleusercontent.com \
     npx expo run:ios --project-dir apps/mobile
   ```

   The API accepts ID tokens whose `aud` is the web **or** iOS client id.
   `app.config.ts` adds `com.googleusercontent.apps.<guid>` as a URL scheme
   when `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` is set at prebuild time.

4. Smoke test: open the app → **Continue with Google** → chat against AWS.

## Local Mac

Leave `GOOGLE_CLIENT_ID=` empty and `ALLOW_DEV_AUTH_HEADERS=true` in
`apps/api/.env` — login stays on Paul/Alex. To test Google locally, set the
same client ID and add `http://localhost:3000` as a JS origin.
