# LinkedIn Auto-Post Tool

> **Fully free, 24/7 LinkedIn automation** — powered by GitHub Actions + Gemini AI + LinkedIn API. Zero server costs, zero subscriptions.

---

## What It Does

Posts **3 human-like LinkedIn posts per day** automatically at 12:00, 17:00, and 23:00 PKT:

- **Generates text** via Gemini API — conversational, no AI clichés, no em dashes
- **Generates images** via Imagen API (with Unsplash fallback)
- **Posts via LinkedIn official API** (`w_member_social` scope)
- **Auto-refreshes OAuth tokens** and saves them back to GitHub Secrets
- **Dashboard** on GitHub Pages to preview, trigger, and monitor posts

### Post Type Mix
| Type | Weight | Example |
|---|---|---|
| Dev Tip | 25% | "Here's a React hook pattern I use in every project..." |
| Client Story | 20% | "A client's database crashed with no backup. At 3am." |
| Tech Discovery | 20% | "Just tried Hono.js. Actual thoughts." |
| Dev Journey | 15% | "The first time I deployed to prod and it crashed..." |
| Debug Story | 12% | "6 hours. Same error. It was a missing semicolon." |
| Community Q | 8% | "Tabs or spaces? I have strong opinions." |

---

## Architecture

```
GitHub Actions (cron: 3×/day)
  └── generate_post.py
       ├── topic_manager.py  →  selects post type + topic
       ├── Gemini API        →  generates natural text
       ├── Imagen API        →  generates relevant image
       │   └── Unsplash      →  fallback if quota hit
       ├── LinkedIn API      →  uploads image + publishes post
       ├── GitHub Secrets API→  updates tokens if refreshed
       └── post_history.json →  logs the published post

GitHub Pages (dashboard/)
  └── index.html + style.css + app.js
       ├── Reads post_history.json via GitHub Contents API
       ├── Triggers workflows via GitHub Actions API
       └── Shows stats, schedule, history, setup guide
```

---

## One-Time Setup

### Step 1 — Register LinkedIn Developer App

1. Go to [developers.linkedin.com](https://www.linkedin.com/developers/apps/new)
2. Create an app (associate with any LinkedIn Page)
3. Go to **Products** tab → Request **"Share on LinkedIn"** access
4. Under **Auth** tab → Add redirect URL: `http://localhost:8765/callback`
5. Copy your **Client ID** and **Client Secret**

> **Note:** LinkedIn "Share on LinkedIn" product approval typically takes 1-3 days.

### Step 2 — Get Gemini API Key

1. Visit [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with Google → Click **Create API Key**
3. Copy the key (free tier is sufficient)

### Step 3 — Get LinkedIn OAuth Tokens (run locally)

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "LINKEDIN_CLIENT_ID=your_client_id" > .env
echo "LINKEDIN_CLIENT_SECRET=your_client_secret" >> .env

# Run the token helper (opens LinkedIn login in browser)
python scripts/token_helper.py
```

Copy the printed values: `access_token`, `refresh_token`, `user_urn`

### Step 4 — Create GitHub PAT

1. Go to [github.com/settings/tokens/new](https://github.com/settings/tokens/new)
2. Name: "LinkedIn Auto-Post"
3. Scopes: ✅ **repo** (full) + ✅ **workflow**
4. Click **Generate token** → Copy it

### Step 5 — Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | From Google AI Studio |
| `LINKEDIN_CLIENT_ID` | From LinkedIn Developer Portal |
| `LINKEDIN_CLIENT_SECRET` | From LinkedIn Developer Portal |
| `LINKEDIN_ACCESS_TOKEN` | From `token_helper.py` output |
| `LINKEDIN_REFRESH_TOKEN` | From `token_helper.py` output |
| `LINKEDIN_USER_URN` | From `token_helper.py` output |
| `GH_PAT` | Your GitHub Personal Access Token |

### Step 6 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: LinkedIn Auto-Post Tool"

# Create a public repo on GitHub first, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Step 7 — Enable GitHub Pages (Dashboard)

1. Go to repo **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, Folder: `/dashboard`
4. Click **Save**

Dashboard URL: `https://YOUR_USERNAME.github.io/YOUR_REPO`

---

## Usage

### Automatic Posting
Posts go live automatically at:
- 12:00 PKT (07:00 UTC)
- 17:00 PKT (12:00 UTC)
- 23:00 PKT (18:00 UTC)

### Manual Post (via Dashboard)
1. Open your dashboard URL
2. Enter GitHub owner/repo/PAT in the top bar
3. Go to **Manual Post** tab → Click **Post Now**

### Preview Post (Dry Run)
Go to **Preview Post** tab → Click **Generate Preview**
Opens GitHub Actions log showing the generated post without publishing.

### Add Custom Topics
Edit `config/settings.json`:
```json
"topics": {
  "dev_tip": [
    "Your custom topic here",
    ...
  ]
}
```

---

## Cost Summary

| Service | Plan | Cost |
|---|---|---|
| GitHub Actions (public repo) | Free unlimited | **$0** |
| Gemini API | Free tier (~90 calls/month) | **$0** |
| Imagen API | Free tier (~90 images/month) | **$0** |
| LinkedIn API | Free `w_member_social` | **$0** |
| GitHub Pages | Free | **$0** |
| **Total** | | **$0/month** |

---

## Important Notes

### LinkedIn Policy
This tool uses the **official LinkedIn API** with proper OAuth 2.0 authentication. It does NOT use scraping or unofficial methods. This complies with LinkedIn's Terms of Service.

### Token Auto-Refresh
- LinkedIn access tokens expire every ~60 days
- The script automatically refreshes them before each post
- New tokens are saved back to GitHub Secrets via the GitHub API
- You only need to run `token_helper.py` once

### GitHub Actions Timing
- Cron schedules may be delayed by up to 15 minutes during high GitHub load
- For public repos, Actions are completely free with no minute limits

### Image Generation
- Primary: Imagen API (free tier) — photorealistic, relevant images
- Fallback: Unsplash (curated tech photos, no API key needed)
- If both fail, the post is published text-only

---

## Project Structure

```
linkedin-auto-post/
├── .github/
│   └── workflows/
│       └── post.yml          # GitHub Actions cron workflow
├── scripts/
│   ├── generate_post.py      # Main orchestrator
│   ├── token_helper.py       # One-time OAuth setup
│   └── topic_manager.py      # Topic rotation + history logging
├── config/
│   └── settings.json         # Persona, topics, schedule config
├── data/
│   └── post_history.json     # Auto-updated post log
├── dashboard/
│   ├── index.html            # Dashboard UI
│   ├── style.css             # Glassmorphism dark theme
│   └── app.js                # GitHub API integration
├── requirements.txt
└── README.md
```

---

## Troubleshooting

**Workflow not running?**
- Check if your LinkedIn "Share on LinkedIn" product is approved
- Verify all 7 secrets are set correctly
- Check the Actions tab for error logs

**Token expired?**
- Run `python scripts/token_helper.py` again locally
- Update `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_REFRESH_TOKEN` secrets

**Posts look AI-generated?**
- The prompts already enforce anti-AI rules
- Optionally edit `config/settings.json` → `persona.tone` to be more specific about your voice

**GitHub Actions cron not firing?**
- Ensure the repo has had recent commits (GitHub may disable crons on inactive repos)
- Trigger manually once from the Actions tab to wake it up
