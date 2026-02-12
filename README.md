# Sophia Telegram Bot (LLM + occasional comments)

A Vibe-coded Telegram group bot that:
- Replies when you **mention** her (e.g. `@SophiaBot ...`)
- Optionally replies when you **reply to her message** (if enabled in code)
- Occasionally posts a random comment line from `comments.txt`
- Runs on **Render** (webhook)
- Uses **Hugging Face Router** to call an LLM provider (e.g. **Groq**) with your own provider key

---

## How it works

### LLM replies
Sophia calls an LLM **only when she is addressed** (mention / optionally reply-to-bot depending on your code).
The bot sends a chat-completions request to:

- `https://router.huggingface.co/v1/chat/completions`

and receives a text response which is posted back to Telegram.

### Comments
On normal messages (not addressed to the bot), Sophia stays quiet but has a small chance to reply with a random line from `comments.txt`.

---

## Repo files

- `bot.py` – main bot code
- `requirements.txt` – Python dependencies
- `comments.txt` – roast lines (one per line)

---

## Requirements

- Python 3.11+ (Render currently defaults to modern Python)
- A Telegram bot token from **BotFather**
- A Hugging Face account + token
- A provider key (recommended: **Groq**) added to Hugging Face Inference Providers

---

## Setup

### 1) Create your Telegram bot
1. Talk to **@BotFather**
2. Create a new bot and copy the `BOT_TOKEN`
3. (Recommended) Disable privacy so the bot can see group messages:
   - BotFather → `/setprivacy` → choose bot → **Disable**

### 2) Create Hugging Face token
1. Go to Hugging Face → **Settings → Access Tokens**
2. Create a token (fine-grained is OK)
3. Enable permission:
   - **Inference → Make calls to Inference Providers**
4. Copy the token → this becomes `HF_API_TOKEN`

### 3) Add Groq as a custom provider key (recommended)
1. Create a Groq API key in Groq Console
2. Hugging Face → **Settings → Inference Providers**
3. Add your Groq key as a **custom key**
4. Drag **Groq** above other providers (optional, helps routing)
5. Set your model in the format:  
   `MODEL_ID:groq`

Example:
- `HF_MODEL = openai/gpt-oss-20b:groq`

> Note: provider availability depends on what you enabled in HF Inference Providers.

---

## Deploy on Render

1. Push this repo to GitHub
2. On Render: **New → Web Service → Connect repo**
3. Start command:
   ```bash
   python bot.py
4. Set environment variables (Render Dashboard → Environment):
BOT_TOKEN := Telegram bot token
HF_API_TOKEN := Hugging Face token (hf_...)
HF_MODEL	:= e.g. openai/gpt-oss-20b:groq

Render will set:
  RENDER_EXTERNAL_URL
  <br>PORT
  
