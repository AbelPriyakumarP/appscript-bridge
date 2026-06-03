# Google Cloud Platform Setup Guide

## Step 1: Create a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top → **New Project**
3. Enter a project name (e.g., `AppScript Event Bridge`)
4. Click **Create**
5. Make sure your new project is selected in the dropdown

---

## Step 2: Enable Required APIs

1. Go to **APIs & Services** → **Library**
2. Search for and **Enable** each of the following:

| API | Why it's needed |
|---|---|
| **Apps Script API** | Execute and manage Apps Script projects |
| **Google Drive API** | List Apps Script files in Drive |
| **Google Sheets API** | Access Sheets from triggered scripts |
| **Google Docs API** | Access Docs from triggered scripts |
| **Gmail API** | Allow scripts to send email |
| **Google Calendar API** | Allow scripts to manage calendar events |

---

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** user type → Click **Create**
3. Fill in:
   - App name: `AppScript Event Bridge`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. On the **Scopes** page, click **Add or Remove Scopes** and add all of the following:

   ```
   https://www.googleapis.com/auth/script.projects
   https://www.googleapis.com/auth/script.processes
   https://www.googleapis.com/auth/spreadsheets
   https://www.googleapis.com/auth/drive
   https://www.googleapis.com/auth/documents
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/calendar
   https://www.googleapis.com/auth/userinfo.email
   https://www.googleapis.com/auth/userinfo.profile
   openid
   ```

6. Click **Save and Continue**
7. On the **Test users** page, add your Google email address
8. Click **Save and Continue**

> **Note:** While the app is in "Testing" mode, only accounts listed as test users can authenticate.

---

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `AppScript Event Bridge`
5. Under **Authorized redirect URIs**, add:
   - `http://localhost:5000/auth/callback`  ← for local development
   - `https://<your-ngrok-subdomain>.ngrok-free.app/auth/callback`  ← if using ngrok (see Step 7)
6. Click **Create**
7. Copy the **Client ID** and **Client Secret** — you'll need these in Step 5

---

## Step 5: Configure the Application

1. Copy `.env.example` to `.env`:
   ```
   copy .env.example .env
   ```

2. Edit `.env` and fill in:
   ```env
   SECRET_KEY=any-long-random-string
   GOOGLE_CLIENT_ID=your-client-id-from-step-4.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret-from-step-4
   GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback
   BASE_URL=http://localhost:5000
   ```

> If using ngrok, set `GOOGLE_REDIRECT_URI` and `BASE_URL` to your ngrok URL (see Step 7).

---

## Step 6: Prepare Your Apps Script Project

For the Apps Script REST API (`scripts.run`) to work, your script must be linked to the same GCP project.

### 6a. Link the script to your GCP project

1. Open your script at [script.google.com](https://script.google.com)
2. Go to **Project Settings** (gear icon on the left)
3. Under **Google Cloud Platform (GCP) Project**, click **Change project**
4. Enter your GCP **Project Number** — found in GCP Console → Home → **Project number**
5. Click **Set project**

### 6b. Create an API Executable deployment

1. In your Apps Script project, click **Deploy** → **New deployment**
2. Click the gear icon next to "Select type" → choose **API Executable**
3. Description: `EventBridge trigger`
4. Execute as: **Me**
5. Who has access: **Anyone** (or restrict to your org)
6. Click **Deploy** and copy the **Deployment ID**

### 6c. Find your Script ID

- Go to **Project Settings** → under **IDs** copy the **Script ID**
- This is what you enter when adding a workflow action in the app

---

## Step 7: External Access with ngrok

Required if you want external apps (ServiceNow, Telegram, etc.) to reach your local server.

1. Install ngrok: [https://ngrok.com/download](https://ngrok.com/download)
2. Authenticate once: `ngrok config add-authtoken <your-token>`
3. Start tunnel: `ngrok http 5000`
4. Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok-free.app`)
5. Update `.env`:
   ```env
   GOOGLE_REDIRECT_URI=https://abc123.ngrok-free.app/auth/callback
   BASE_URL=https://abc123.ngrok-free.app
   ```
6. Add the callback URL to your GCP OAuth credentials:
   - GCP Console → **Credentials** → edit your OAuth client
   - Add `https://abc123.ngrok-free.app/auth/callback` to **Authorized redirect URIs**
7. Restart the Flask app

> Your webhook URLs will be `https://abc123.ngrok-free.app/webhook/trigger` etc.

---

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser and click **Connect Google Account** to complete OAuth.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `403 Forbidden` on script execution | Ensure Apps Script API is enabled and the script is linked to your GCP project (Step 6a) |
| `redirect_uri_mismatch` | The URI in `.env` must exactly match one of the URIs in your GCP OAuth credentials |
| Token keeps expiring | Make sure `refresh_token` is present — re-authenticate and grant offline access |
| `access_blocked` error | App is in Testing mode — add your account as a test user (Step 3, item 7) |
| ngrok URL changed | Update both `.env` and GCP Authorized redirect URIs every time ngrok restarts (use a fixed subdomain to avoid this) |
