import os
import random
import re
import asyncio
from collections import defaultdict, deque
from typing import Deque, Dict, List

import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# -----------------------------
# ENV
# -----------------------------
TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render provides this
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
ROAST_FILE = os.getenv("ROAST_FILE", "comments.txt")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not RENDER_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not set")
if not HF_API_TOKEN:
    raise RuntimeError("HF_API_TOKEN is not set")

HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json",
}

# -----------------------------
# ROAST LINES
# -----------------------------
def load_texts(path: str) -> List[str]:
    if not os.path.exists(path):
        raise RuntimeError(f"{path} file not found")
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

ROAST_LINES = load_texts(ROAST_FILE)
if not ROAST_LINES:
    raise RuntimeError("comments file is empty")

# -----------------------------
# LIGHTWEIGHT CONTEXT (IN RAM)
# -----------------------------
CHAT_HISTORY: Dict[int, Deque[str]] = defaultdict(lambda: deque(maxlen=3))
LAST_ROAST_AT: Dict[int, float] = {}  # chat_id -> monotonic time


# -----------------------------
# HELPERS
# -----------------------------
def is_group(update: Update) -> bool:
    msg = update.message
    return bool(msg and msg.chat and msg.chat.type in ("group", "supergroup"))

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def should_answer_with_llm(update: Update, bot_username: str) -> bool:
    msg = update.message
    if not msg or not msg.text:
        return False

    # 1) Mention triggers
    if bot_username and f"@{bot_username}".lower() in msg.text.lower():
        return True

    # 2) Reply-to-bot triggers
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.username == bot_username:
            return True

    return False


def roast_candidate_name(update: Update) -> str:
    user = update.message.from_user if update.message else None
    return user.first_name if user and user.first_name else "love"

def roast_probability() -> bool:
    # 1 in 25 chance
    return random.randint(1, 50) == 1

def roast_allowed(chat_id: int) -> bool:
    # Cooldown: at most 1 roast / 2 minutes / chat
    now = asyncio.get_event_loop().time()
    last = LAST_ROAST_AT.get(chat_id, 0.0)
    if now - last < 120:
        return False
    LAST_ROAST_AT[chat_id] = now
    return True

def build_prompt(user_text: str, history: Deque[str], bot_username: str) -> str:
    # remove the mention so the prompt is clean
    cleaned = re.sub(rf"@{re.escape(bot_username)}", "", user_text, flags=re.IGNORECASE).strip()
    cleaned = cleaned[:800]  # keep prompt sane

    context_block = "\n".join(f"- {h}" for h in list(history)[-2:])

    return f"""You are a bot in a telegram groupchat. Reply in 1-4 sentences and be helpful and clear

Recent chat context:
{context_block}

The user is addressing you directly and asked:
{cleaned}

Reply:"""

async def hf_generate(session: aiohttp.ClientSession, prompt: str) -> str:
    payload = {
        "model": HF_MODEL,  # e.g. "HuggingFaceH4/zephyr-7b-beta"
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 250,
        "temperature": 0.7,
        "top_p": 0.9,
    }

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            async with session.post(HF_CHAT_URL, headers=headers, json=payload, timeout=35) as r:
                if r.status == 200:
                    data = await r.json()
                    return data["choices"][0]["message"]["content"].strip()

                if r.status in (429, 503):
                    await asyncio.sleep(1.2 + attempt * 0.8)
                    continue

                txt = await r.text()
                return f"(LLM error {r.status}) {txt[:3500]}…"

        except asyncio.TimeoutError:
            if attempt == 2:
                return "Sorry love—my brain froze for a second. Try again?"
        except Exception:
            if attempt == 2:
                return "Oops love… something broke on my side. Try again in a moment?"

    return "I’m a bit busy right now, my dear—try again shortly."

# -----------------------------
# HANDLER
# -----------------------------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    if not is_group(update):
        return

    chat_id = update.message.chat_id
    bot_username = context.bot.username or ""
    user_name = roast_candidate_name(update)

    text = normalize_text(update.message.text)

    # Save some context (skip commands)
    if not text.startswith("/"):
        CHAT_HISTORY[chat_id].append(f"{user_name}: {text[:120]}")

    # 1) LLM reply ONLY when mentioned
    if should_answer_with_llm(update, bot_username):
        prompt = build_prompt(text, CHAT_HISTORY[chat_id], bot_username)
        async with aiohttp.ClientSession() as session:
            reply = await hf_generate(session, prompt)

        reply = (reply or "").strip()

        # If the model returned empty/whitespace, Telegram rejects it.
        if not reply:
            reply = "What love? Ask me again, please."

        if len(reply) > 3500:
            reply = reply[:3500].rsplit(" ", 1)[0] + "…"

        await update.message.reply_text(reply)

        return

    # 2) Otherwise: occasional roast (rare + cooldown)
    if roast_probability() and roast_allowed(chat_id):
        roast_line = random.choice(ROAST_LINES)
        await update.message.reply_text(f"{user_name} {roast_line}")

# -----------------------------
# MAIN (WEBHOOK)
# -----------------------------
def main() -> None:
    app: Application = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    port = int(os.environ.get("PORT", "10000"))

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{RENDER_URL}/webhook",
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()