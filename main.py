
import os
import sys
import time
import asyncio
import logging
import re
from typing import Optional
from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yaml

from agents.analyst import AnalystAgent
from agents.strategist import StrategistAgent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()
base_url = config.get('system', {}).get('llm_base_url')


# Initialize Agents
analyst_config = config['agents']['agent_1']
strategist_config = config['agents']['agent_2']

# Analyst (Default OpenAI)
analyst_kwargs = {}
if analyst_config.get('provider') == 'openai' and base_url:
    analyst_kwargs['base_url'] = base_url

analyst = AnalystAgent(model=analyst_config['model'], **analyst_kwargs)

# Strategist (Novita / Kimi)
strategist_kwargs = {}
if strategist_config.get('provider') == 'novita':
    strategist_kwargs['base_url'] = strategist_config['base_url']
    strategist_kwargs['api_key'] = os.getenv("NOVITA_API_KEY")

strategist = StrategistAgent(model=strategist_config['model'], **strategist_kwargs)


# Per-chat conversation histories
chat_histories: dict[int, list] = {}

# Streaming config
STREAM_EDIT_INTERVAL = 0.8  # seconds between Telegram message edits
MIN_CHUNK_SIZE = 30          # min characters accumulated before editing
TELEGRAM_SEND_RETRIES = 3
TELEGRAM_BASE_RETRY_DELAY = 1.0


async def _wait_before_retry(exc: Exception, attempt: int) -> None:
    if isinstance(exc, RetryAfter):
        retry_after = float(getattr(exc, "retry_after", TELEGRAM_BASE_RETRY_DELAY))
        await asyncio.sleep(retry_after + 0.1)
        return
    await asyncio.sleep(TELEGRAM_BASE_RETRY_DELAY * (attempt + 1))


async def _safe_reply_text(message, text: str, markdown: bool = False):
    parse_mode = "Markdown" if markdown else None
    for attempt in range(TELEGRAM_SEND_RETRIES):
        try:
            kwargs = {"parse_mode": parse_mode} if parse_mode else {}
            return await message.reply_text(text, **kwargs)
        except (TimedOut, NetworkError, RetryAfter) as exc:
            logger.warning("reply_text failed (%s/%s): %s", attempt + 1, TELEGRAM_SEND_RETRIES, exc)
            if attempt < TELEGRAM_SEND_RETRIES - 1:
                await _wait_before_retry(exc, attempt)
                continue
            return None
        except Exception as exc:
            # Most common fallback here is markdown parsing problems.
            if parse_mode:
                parse_mode = None
                continue
            logger.error("reply_text failed: %s", exc)
            return None
    return None


async def _safe_edit_text(message, text: str, markdown: bool = False) -> bool:
    if message is None:
        return False

    parse_mode = "Markdown" if markdown else None
    for attempt in range(TELEGRAM_SEND_RETRIES):
        try:
            kwargs = {"parse_mode": parse_mode} if parse_mode else {}
            await message.edit_text(text, **kwargs)
            return True
        except BadRequest as exc:
            if "Message is not modified" in str(exc):
                return True
            if parse_mode:
                parse_mode = None
                continue
            logger.warning("edit_text bad request: %s", exc)
            return False
        except (TimedOut, NetworkError, RetryAfter) as exc:
            logger.warning("edit_text failed (%s/%s): %s", attempt + 1, TELEGRAM_SEND_RETRIES, exc)
            if attempt < TELEGRAM_SEND_RETRIES - 1:
                await _wait_before_retry(exc, attempt)
                continue
            return False
        except Exception as exc:
            if parse_mode:
                parse_mode = None
                continue
            logger.warning("edit_text failed: %s", exc)
            return False
    return False


def _extract_card_field(text: str, field_name: str) -> Optional[str]:
    cleaned = re.sub(r"[*`_]", "", text)
    pattern = rf"(?im)^\s*[-•]?\s*{re.escape(field_name)}\s*:\s*(.+?)\s*$"
    match = re.search(pattern, cleaned)
    if not match:
        return None
    value = match.group(1).strip()
    return value if value else None


def _parse_pick_card(text: str) -> dict[str, Optional[str]]:
    return {
        "pick": _extract_card_field(text, "Pick"),
        "confidence": _extract_card_field(text, "Confidence"),
        "reason": _extract_card_field(text, "Reason"),
    }


def _is_structured_card_complete(text: str) -> bool:
    card = _parse_pick_card(text)
    return bool(card["pick"] and card["confidence"] and card["reason"])


def _normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _canonical_pick(value: Optional[str]) -> str:
    norm = _normalize(value)
    if not norm:
        return ""

    if "no bet" in norm or norm in {"pass", "skip"}:
        return "no bet"
    if re.search(r"\bunder\b", norm):
        return "under"
    if re.search(r"\bover\b", norm):
        return "over"

    # For side picks, strip common betting noise and compare the core team/side text.
    norm = re.sub(r"\([^)]*\)", " ", norm)
    norm = re.sub(r"(?<!\w)[+-]?\d+(?:\.\d+)?", " ", norm)
    norm = re.sub(r"\b(ml|moneyline|spread|line|points?|best|available)\b", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def _build_consensus_message(analyst_response: str, strategist_response: str) -> str:
    analyst_card = _parse_pick_card(analyst_response)
    strategist_card = _parse_pick_card(strategist_response)

    analyst_pick = _normalize(analyst_card["pick"])
    strategist_pick = _normalize(strategist_card["pick"])
    analyst_pick_key = _canonical_pick(analyst_card["pick"])
    strategist_pick_key = _canonical_pick(strategist_card["pick"])

    if not analyst_pick or not strategist_pick:
        return (
            "⚖️ Consensus: insufficient structured card data this turn.\n"
            "No forced bet."
        )

    if analyst_pick_key and analyst_pick_key == strategist_pick_key:
        return (
            "🤝 Consensus: AGREE\n"
            f"Pick: {analyst_card['pick']}\n"
            f"Confidence: Sharp {analyst_card['confidence'] or 'N/A'} | Contrarian {strategist_card['confidence'] or 'N/A'}\n"
            f"Reason: {analyst_card['reason'] or strategist_card['reason'] or 'Aligned edge.'}\n"
            "Decision: aligned edge."
        )

    return (
        "⚖️ Consensus: NO AGREEMENT\n"
        f"The Sharp -> Pick: {analyst_card['pick'] or 'N/A'} | Confidence: {analyst_card['confidence'] or 'N/A'} | Reason: {analyst_card['reason'] or 'N/A'}\n"
        f"The Contrarian -> Pick: {strategist_card['pick'] or 'N/A'} | Confidence: {strategist_card['confidence'] or 'N/A'} | Reason: {strategist_card['reason'] or 'N/A'}\n"
        "Decision: no forced bet."
    )


async def _repair_card_if_needed(agent, history, full_text: str) -> str:
    if _is_structured_card_complete(full_text):
        return full_text

    repair_prompt = (
        "Return ONLY this exact 3-line decision card based on your previous analysis. "
        "No extra text.\n"
        "Pick: <team/side | over | under | no bet>\n"
        "Confidence: <0-100>\n"
        "Reason: <one sentence, max 20 words>"
    )
    repair_history = list(history) + [
        {"role": "assistant", "content": full_text},
        {"role": "user", "content": repair_prompt},
    ]

    try:
        repaired = await asyncio.to_thread(agent.chat, repair_history)
    except Exception as exc:
        logger.warning("%s card repair failed: %s", getattr(agent, "name", "agent"), exc)
        return full_text

    repaired = (repaired or "").strip()
    if not _is_structured_card_complete(repaired):
        return full_text

    return f"{full_text.rstrip()}\n\n{repaired}"


async def stream_agent_response(agent, history, update, prefix_emoji, prefix_name):
    """
    Stream an agent's response into a Telegram message.
    Sends an initial message, then edits it as tokens arrive.
    Returns the full response text.
    """
    # Send initial "thinking" message
    msg = await _safe_reply_text(update.message, f"{prefix_emoji} *{prefix_name} is thinking...*", markdown=True)

    full_text = ""
    buffer = ""
    last_edit_time = time.time()
    try:
        for chunk in agent.chat_stream(history):
            full_text += chunk
            buffer += chunk

            now = time.time()
            # Edit message periodically to simulate streaming
            if len(buffer) >= MIN_CHUNK_SIZE and (now - last_edit_time) >= STREAM_EDIT_INTERVAL:
                if msg:
                    display = f"{prefix_emoji} *{prefix_name}:*\n{full_text}▌"
                    await _safe_edit_text(msg, display, markdown=True)
                buffer = ""
                last_edit_time = now
        
        # Enforce a structured final card for downstream consensus parsing.
        full_text = await _repair_card_if_needed(agent, history, full_text)

        # Final edit with complete text (no cursor)
        if msg:
            await _safe_edit_text(msg, f"{prefix_emoji} *{prefix_name}:*\n{full_text}", markdown=True)
        else:
            await _safe_reply_text(update.message, f"{prefix_emoji} {prefix_name}:\n{full_text}")

    except Exception as e:
        full_text = f"(Error: {e})"
        logger.error(f"{prefix_name} error: {e}")
        error_text = f"{prefix_emoji} {prefix_name}:\n⚠️ Error: {str(e)[:200]}"
        if msg:
            await _safe_edit_text(msg, error_text)
        else:
            await _safe_reply_text(update.message, error_text)

    return full_text


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _safe_reply_text(
        update.message,
        "🏀 *NBA Betting Analysis Agents Online*\n\n"
        "Ask me anything about NBA games, matchups, or betting strategy.\n"
        "Two agents will respond:\n"
        "📊 *The Analyst* — Raw data & stats\n"
        "🎯 *The Strategist* — Betting plays & risk\n\n"
        "Commands:\n"
        "/start — Show this message\n"
        "/reset — Clear conversation history\n\n"
        "Example: _\"Who plays tonight?\"_",
        markdown=True,
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if not user_text:
        return

    # Get or create history for this chat
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    history = chat_histories[chat_id]
    history.append({"role": "user", "content": user_text})
    turn_history = list(history)

    # --- Analyst Turn (Independent) ---
    analyst_response = await stream_agent_response(
        analyst, turn_history, update, "📊", "The Sharp"
    )

    # --- Strategist Turn (Independent) ---
    strategist_response = await stream_agent_response(
        strategist, turn_history, update, "🎯", "The Contrarian"
    )

    history.append({"role": "assistant", "name": "Analyst", "content": analyst_response})
    history.append({"role": "assistant", "name": "Strategist", "content": strategist_response})

    consensus = _build_consensus_message(analyst_response, strategist_response)
    await _safe_reply_text(update.message, consensus)

    # Keep history manageable (last 30 messages)
    if len(history) > 30:
        chat_histories[chat_id] = history[-30:]

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = []
    await _safe_reply_text(update.message, "🔄 Conversation history cleared.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception while processing update", exc_info=context.error)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        sys.exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in .env")
        sys.exit(1)

    print(f"🏀 Starting Telegram Bot...")
    print(f"   Analyst:    model={analyst_config['model']}, temp=0.4")
    print(f"   Strategist: model={strategist_config['model']}, temp=0.6")
    print(f"   Max Tokens: 128,000")
    print(f"   Streaming:  ON")
    print(f"   LLM URL:    {base_url or 'default'}")
    
    app = (
        ApplicationBuilder()
        .token(token)
        .connect_timeout(15)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(15)
        .build()
    )
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("   Bot is running. Send a message in Telegram!")
    app.run_polling()

if __name__ == "__main__":
    main()
