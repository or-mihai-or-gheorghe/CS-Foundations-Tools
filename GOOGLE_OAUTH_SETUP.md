# Google OAuth Setup Guide - CS Foundations Tools

This guide shows you how to set up Google Authentication for the CS Foundations Tools leaderboard system.

## Prerequisites

✅ Streamlit >= 1.42.0 (in requirements.txt)
✅ Authlib >= 1.3.2 (in requirements.txt)

## Step 1: Google Cloud Console Setup

### 1. Create/Select Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one:
   - Project name: `CS Foundations Tools` (or similar)

### 2. Configure OAuth Consent Screen

1. Navigate to: **APIs & Services** → **OAuth consent screen**
2. Choose **"External"** user type (or "Internal" if using Google Workspace)
3. Fill in the form:
   - **App name**: `CS Foundations Tools`
   - **User support email**: Your email (e.g., `your.name@ase.ro`)
   - **App logo**: (optional)
   - **Application home page**: `https://cs-fundamentals.streamlit.app/`
   - **Authorized domains**: Add `streamlit.app`
   - **Developer contact information**: Your email
4. Click **"Save and Continue"**
5. **Scopes**: Skip (click "Save and Continue")
6. **Test users** (if in Testing mode):
   - Add test user emails (e.g., `student@ase.ro`, `teacher@ase.ro`)
   - Click "Add Users"
7. Click **"Save and Continue"** → **"Back to Dashboard"**

### 3. Create OAuth 2.0 Client ID

1. Go to: **APIs & Services** → **Credentials**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. Application type: **"Web application"**
4. Name: `CS Foundations Tools Web Client`
5. **Authorized redirect URIs** - Add both:
   - For Streamlit Cloud: `https://cs-fundamentals.streamlit.app/oauth2callback`
   - For local testing: `http://localhost:8501/oauth2callback`
6. Click **"Create"**
7. **IMPORTANT**: Save the Client ID and Client Secret shown in the popup
   - Client ID: `123456789.apps.googleusercontent.com`
   - Client Secret: `GOCSPX-xxxxxxxxxxxxx`

## Step 2: Configure Streamlit Secrets

### For Streamlit Cloud (Production)

1. Go to [Streamlit Cloud](https://share.streamlit.io/)
2. Select your app → **Settings** → **Secrets**
3. Add this configuration:

```toml
[auth]
redirect_uri = "https://cs-fundamentals.streamlit.app/oauth2callback"
cookie_secret = "GENERATE_THIS_WITH_COMMAND_BELOW"
client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret = "YOUR_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[firebase]
use_mock_auth = false
api_key = "AIzaSyCZnSywDMRn1mIdTxVcT6lO4EISSUtcvP4"
auth_domain = "cs-foundations-tools.firebaseapp.com"
database_url = "https://cs-foundations-tools-default-rtdb.europe-west1.firebasedatabase.app/"
project_id = "cs-foundations-tools"
storage_bucket = "cs-foundations-tools.firebasestorage.app"
messaging_sender_id = "256194113297"
app_id = "1:256194113297:web:04b18b2ca5b69a7165a6b0"
private_key_id = "77e4e1f6b1f8547cdecfd4fa27ae5fbd4a8f365d"
private_key = "-----BEGIN PRIVATE KEY-----\n[YOUR_PRIVATE_KEY]\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-fbsvc@cs-foundations-tools.iam.gserviceaccount.com"
client_id = "107349254050654173302"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40cs-foundations-tools.iam.gserviceaccount.com"
```

4. **Generate cookie secret**:
   ```bash
   openssl rand -hex 32
   ```
   Copy the output and paste it as `cookie_secret`

5. Replace `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET` with values from Step 1

6. Click **"Save"** - app will restart automatically

### For Local Development

1. Copy the template:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. Edit `.streamlit/secrets.toml`:
   ```toml
   [auth]
   redirect_uri = "http://localhost:8501/oauth2callback"
   cookie_secret = "YOUR_GENERATED_SECRET"
   client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
   client_secret = "YOUR_CLIENT_SECRET"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

   [firebase]
   use_mock_auth = false
   # ... (copy Firebase config from Streamlit Cloud)
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Step 3: Test the Setup

### On Streamlit Cloud

1. Visit: https://cs-fundamentals.streamlit.app/
2. Navigate to **Games Hub**
3. Click **"Sign in to save scores"** expander
4. Click **"Log in with Google"**
5. You should be redirected to Google sign-in
6. Select your account
7. Authorize the app
8. You should be redirected back and see your name/email

### Locally

1. Run the app:
   ```bash
   streamlit run app.py
   ```

2. Open: http://localhost:8501
3. Follow the same steps as above

## Step 4: Domain Restriction (@ase.ro only)

**IMPORTANT**: The app now **enforces** @ase.ro domain validation at the code level. Users with non-@ase.ro emails will be blocked and forced to sign out.

To also restrict at the Google OAuth level (recommended for better UX):

### Method 1: HD Parameter (Implemented)
The app already uses `hd=ase.ro` parameter which:
- Suggests @ase.ro accounts to users
- Pre-filters the account selection screen
- Note: This is a hint, not enforcement (users can still select other accounts)

### Method 2: Google Workspace - Internal App (Best)
If ASE has Google Workspace:
1. In OAuth consent screen, change User Type to **"Internal"**
2. This **completely restricts** access to @ase.ro domain users only
3. No other emails can even attempt to sign in

### Method 3: Authorized Domains (Hint only)
1. In OAuth consent screen settings
2. Under "Authorized domains", add `ase.ro`
3. This is informational only - doesn't prevent other emails

### Code-Level Enforcement (Already Active)
- The app checks email domain after sign-in
- Non-@ase.ro users see: "⛔ Access Denied"
- They are forced to sign out
- Prevents any access to games or data

## Troubleshooting

### "Redirect URI mismatch" error

**Cause**: The redirect URI in secrets doesn't match Google Cloud Console

**Fix**:
1. Go to Google Cloud Console → Credentials → Your OAuth Client
2. Verify "Authorized redirect URIs" matches exactly:
   - Production: `https://cs-fundamentals.streamlit.app/oauth2callback`
   - Local: `http://localhost:8501/oauth2callback`
3. Update `.streamlit/secrets.toml` to match

### "Access blocked: This app's request is invalid"

**Cause**: App is in Testing mode and you're not a test user

**Fix**:
1. Go to OAuth consent screen
2. Add your email to "Test users"
3. OR publish the app (click "Publish App")

### "Login doesn't work" / "Button does nothing"

**Cause**: Missing or incorrect secrets

**Fix**:
1. Verify `.streamlit/secrets.toml` exists
2. Check all fields are filled in correctly
3. Verify Authlib is installed: `pip list | grep Authlib`
4. Check browser console (F12) for errors

### App restarts after successful login

**This is normal!** OAuth requires a full page reload to set cookies properly.

## Security Notes

✅ `.streamlit/secrets.toml` is in `.gitignore` - NEVER commit it
✅ Cookie secret should be random (use `openssl rand -hex 32`)
✅ Identity cookie expires after 30 days
✅ Use HTTPS in production (Streamlit Cloud provides this)
✅ Firebase Admin SDK is used for database writes (secure)

## Publishing Your App

### Testing Mode (Current)
- Only test users can access
- Good for initial development
- No Google verification needed

### Published Mode (Production)
1. Go to OAuth consent screen
2. Click **"Publish App"**
3. Submit for verification (if required)
4. Once published, any Google user can sign in
5. Your code validates @ase.ro domain

## Summary

After completing all steps:

✅ Users can sign in with Google (@ase.ro domain)
✅ Game scores are saved to Firebase
✅ Leaderboard shows real player data
✅ Authentication is secure and standard OAuth 2.0
✅ No complex popup/iframe issues!

---

**Need help?** Check Streamlit's authentication docs: https://docs.streamlit.io/develop/api-reference/connections/st.user
