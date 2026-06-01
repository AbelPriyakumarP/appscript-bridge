# Google Cloud Platform Setup Guide

## Step 1: Create a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top → **New Project**
3. Enter a project name (e.g., "EventBridge Trigger")
4. Click **Create**
5. Make sure your new project is selected in the dropdown

## Step 2: Enable the Apps Script API

1. Go to **APIs & Services** → **Library**
2. Search for **"Apps Script API"**
3. Click on it → Click **Enable**
4. Also enable **"Google Drive API"** and **"Google Sheets API"** (needed for most Apps Script operations)

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** user type → Click **Create**
3. Fill in:
   - App name: `EventBridge`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. On the **Scopes** page, click **Add or Remove Scopes** and add:
   - `https://www.googleapis.com/auth/script.projects`
   - `https://www.googleapis.com/auth/script.processes`
   - `https://www.googleapis.com/auth/spreadsheets`
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
6. Click **Save and Continue**
7. On the **Test users** page, add your Google email address
8. Click **Save and Continue**

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `EventBridge Local`
5. Under **Authorized redirect URIs**, add:
   - `http://localhost:5000/auth/callback`
6. Click **Create**
7. Copy the **Client ID** and **Client Secret**

## Step 5: Configure the Application

1. Copy `.env.example` to `.env`:
   ```
   copy .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```
   SECRET_KEY=any-random-string-here
   GOOGLE_CLIENT_ID=your-client-id-from-step-4
   GOOGLE_CLIENT_SECRET=your-client-secret-from-step-4
   GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback
   BASE_URL=http://localhost:5000
   ```

## Step 6: Prepare Your Apps Script

For the Apps Script REST API to work, your Apps Script project must:

1. Be associated with a GCP project (the same one from Step 1):
   - Open your Apps Script project at [script.google.com](https://script.google.com)
   - Go to **Project Settings** (gear icon)
   - Under **Google Cloud Platform (GCP) Project**, click **Change project**
   - Enter your GCP **Project Number** (found in GCP Console → Project Settings)

2. Have an Apps Script API executable deployment:
   - In your Apps Script project, click **Deploy** → **New deployment**
   - Select type: **API Executable**
   - Set access to: **Anyone** (or your org)
   - Click **Deploy**

3. The Script ID can be found in **Project Settings** under **IDs** → **Script ID**

## Step 7: Using ngrok for External Access

1. Install ngrok: https://ngrok.com/download
2. Run: `ngrok http 5000`
3. Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok.io`)
4. Update `.env`:
   ```
   BASE_URL=https://abc123.ngrok.io
   ```
5. Add the ngrok callback URL to your GCP OAuth credentials:
   - Go to GCP Console → Credentials → Edit your OAuth client
   - Add: `https://abc123.ngrok.io/auth/callback` to Authorized redirect URIs
6. Restart the Flask app

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open http://localhost:5000 in your browser.
