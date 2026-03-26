# 🎓 IB AI Agent System

Production-grade Telegram bot and web API for IBDP students. Features a 3-tier AI cascade (Gemini → Groq → Ollama), full IB curriculum support, SM-2 spaced repetition, and business tools — all on Railway's free tier.

---

## Prerequisites

### 1. Telegram Bot Token
1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name and username for your bot
4. Copy the token (format: `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`)

### 2. Your Telegram User ID
1. Open [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send `/start`
3. Copy your numeric user ID

### 3. Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/apikey) (or [Google Cloud Console](https://console.cloud.google.com))
2. Create an API key
3. Copy the key

### 4. Groq API Key (Recommended — free tier)
1. Go to [console.groq.com](https://console.groq.com)
2. Create an account and generate an API key
3. Copy the key

---

## Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd ib-agent-system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Edit .env with your actual values

# Run the server
python main.py
```

The server starts on `http://localhost:8080`. Visit `/` for the dashboard, `/health` for status.

**Note:** For local webhook testing, use [ngrok](https://ngrok.com):
```bash
ngrok http 8080
# Copy the https URL and set it as WEBHOOK_URL in .env
```

---

## Railway Deployment

### Step-by-step

1. **Create a Railway project**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Connect your GitHub and select this repository

2. **Set environment variables**
   - In your Railway project, go to **Settings → Variables**
   - Add all required variables:
     ```
     TELEGRAM_BOT_TOKEN=<your-token>
     ALLOWED_TELEGRAM_USER_IDS=<your-user-id>
     GEMINI_API_KEY=<your-key>
     GROQ_API_KEY=<your-key>
     WEBHOOK_SECRET=<random-32+-char-string>
     ```

3. **Add persistent volume (CRITICAL)**
   - Go to **Settings → Volumes**
   - Mount path: `/app/data`
   - **Without this, your SQLite database resets on every deploy**

4. **Set the webhook URL**
   - After Railway deploys, copy the public URL (e.g., `https://your-app.up.railway.app`)
   - Add it as `WEBHOOK_URL` in your environment variables
   - The bot auto-registers the webhook on startup

5. **Trigger redeploy**
   - After adding all variables, trigger a redeploy from the Railway dashboard

### Constraints
- **Free tier:** 512MB RAM, single container
- **Build time:** 10-minute limit
- **Port:** Railway injects `PORT` automatically — do not hardcode
- **Restart:** The app handles cold starts cleanly (idempotent DB init)

---

## Telegram Webhook Setup

The bot **automatically registers the webhook** on startup when `WEBHOOK_URL` is set.

### Auto-registration flow:
1. App starts → reads `WEBHOOK_URL` from environment
2. Calls `set_webhook(url=<WEBHOOK_URL>/webhook, secret_token=<WEBHOOK_SECRET>)`
3. Telegram starts sending updates to `POST /webhook`

### Manual backup:
If webhook isn't receiving updates, you can manually set it:
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-app.up.railway.app/webhook&secret_token=<SECRET>"
```

### Verify webhook:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message + full command list | `/start` |
| `/math` | Solve Math AA HL problems (auto-detects topic) | `/math Find the derivative of x³sin(x)` |
| `/markscheme` | Generate IB-style mark scheme with M/A/R marks | `/markscheme Prove that √2 is irrational` |
| `/essay` | Business HL essay structure (default 20 marks) | `/essay Evaluate the impact of globalization on SMEs` |
| `/econ` | Economics diagram + 4-step analysis | `/econ Effect of subsidy on market for solar panels` |
| `/ess` | ESS concept explanation with systems thinking | `/ess Carbon cycle` |
| `/spanish` | Spanish grammar check with corrections | `/spanish Yo tengo 17 años y vivo en Dubai` |
| `/english` | Paper 1 analysis with guiding questions | `/english [paste extract here]` |
| `/tok` | Generate knowledge questions from real-life situation | `/tok AI-generated art winning competitions` |
| `/cas` | CAS project ideas mapped to IB learning outcomes | `/cas` |
| `/ee` | Extended Essay research question refinement | `/ee The effect of social media on consumer behavior` |
| `/validate` | Business idea validation (viability, market, risks) | `/validate AI-powered tutoring for IB students` |
| `/study` | Review due flashcards (SM-2 spaced repetition) | `/study` |
| `/quota` | AI provider status + daily quota usage | `/quota` |

---

## Troubleshooting

### Bot not responding
- **Check allowed user IDs:** If `ALLOWED_TELEGRAM_USER_IDS` is set, your ID must be in the list. Get your ID from [@userinfobot](https://t.me/userinfobot).
- **Check logs:** In Railway dashboard → Deployments → View Logs

### AI not working
- **Check `/quota`:** Shows which providers are online and quota usage
- **Verify API keys:** Ensure `GEMINI_API_KEY` and `GROQ_API_KEY` are correct in Railway variables
- **Quota resets at midnight UTC:** Gemini (950/day), Groq (95/day)

### Data lost on redeploy
- **Volume not configured:** Go to Railway → Settings → Volumes → Mount `/app/data`
- Without a volume, SQLite resets to empty on every deploy
- After adding volume, data persists across deploys

### Webhook not receiving updates
- **Verify WEBHOOK_URL matches Railway domain:** Must be your exact Railway public URL
- **Check webhook secret:** Must match between Railway variables and Telegram
- **Test manually:** `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- **Check /health endpoint:** Should return HTTP 200

### Build fails on Railway
- **Build time limit:** Keep under 10 minutes (the Dockerfile is optimized)
- **Dependencies:** All packages are pinned to exact versions in `requirements.txt`
- **Check logs:** Railway dashboard → Deployments → Build Logs

---

## Architecture

### 3-Tier AI Cascade

The system uses a cascading fallback strategy to maximize uptime and minimize cost:

1. **Tier 1 — Gemini 1.5 Flash** (Primary)
   - Google's fast, free-tier model
   - Handles most requests with high quality
   - Skipped if daily quota reaches 950 requests or `prefer_fast=True`

2. **Tier 2 — Groq Llama 3 8B** (Fallback 1)
   - Ultra-fast inference via Groq's API
   - Engages when Gemini quota is exhausted
   - Skipped if daily quota reaches 95 requests

3. **Tier 3 — Ollama** (Optional Fallback 2)
   - Self-hosted local model
   - Only available if `OLLAMA_URL` is configured
   - Useful for offline/privacy-sensitive scenarios

4. **Fallback — Capacity message**
   - If all providers are at capacity: "⏳ All AI providers at capacity. Resets at midnight UTC."

**Additional features:**
- **LRU Cache:** Last 100 responses cached to avoid redundant API calls
- **Retry logic:** Each provider call retries up to 3 times with exponential backoff
- **Quota tracking:** SQLite-backed daily quotas per provider
- **Rate limiting:** 20 requests per user per 60-second rolling window

---

## License

MIT
