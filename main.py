
import os
import sys
import time
import asyncio
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yaml

from agents.analyst import AnalystAgent
from agents.strategist import StrategistAgent
from agents.base_agent import BaseAgent

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

CHAT_PROMPT = """You are a helpful NBA assistant in normal chat mode.
- Be conversational and concise.
- Do not produce betting picks unless the user asks for analysis/picks.
- If the user asks for betting analysis, acknowledge and proceed with analysis mode."""

chat_agent = BaseAgent(
    name="NBA Assistant",
    system_prompt=CHAT_PROMPT,
    model=analyst_config["model"],
    temperature=0.3,
    **analyst_kwargs,
)


# Per-chat conversation histories
chat_histories: dict[int, list] = {}
chat_modes: dict[int, str] = {}
chat_session_files: dict[int, Path] = {}

# Persistent transcript logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs" / "chat_transcripts"
SNAPSHOT_DIR = BASE_DIR / "logs" / "saved_transcripts"

# Streaming config
STREAM_EDIT_INTERVAL = 0.8  # seconds between Telegram message edits
MIN_CHUNK_SIZE = 30          # min characters accumulated before editing
TELEGRAM_SEND_RETRIES = 3
TELEGRAM_BASE_RETRY_DELAY = 1.0

ANALYSIS_KEYWORDS = [
    "pick",
    "bet",
    "odds",
    "spread",
    "moneyline",
    "ml",
    "over",
    "under",
    "parlay",
    "line",
    "analyze",
    "analysis",
    "live",
    "who wins",
    "confidence",
    "ev",
]

AGENT_TARGET_ALIASES = {
    "sharp": "sharp",
    "analyst": "sharp",
    "contrarian": "contrarian",
    "contra": "contrarian",
    "strategist": "contrarian",
}


def _load_analysis_skill_text() -> str:
    for candidate in [Path("SKILL.md"), Path("skill.md")]:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8").strip()
            except Exception as exc:
                logger.warning("Failed to read %s: %s", candidate, exc)
    return ""


ANALYSIS_SKILL_TEXT = _load_analysis_skill_text()


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_log_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _start_chat_session(chat_id: int, reason: str = "new") -> Path:
    _ensure_log_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"chat_{chat_id}_{stamp}.md"
    header = (
        f"# Chat Transcript\n"
        f"- chat_id: {chat_id}\n"
        f"- started_at_utc: {_now_iso_utc()}\n"
        f"- reason: {reason}\n"
    )
    path.write_text(header, encoding="utf-8")
    chat_session_files[chat_id] = path
    return path


def _get_chat_session_path(chat_id: int) -> Path:
    path = chat_session_files.get(chat_id)
    if path and path.exists():
        return path
    return _start_chat_session(chat_id, reason="auto")


def _append_transcript(chat_id: int, speaker: str, content: str, meta: Optional[str] = None) -> None:
    try:
        path = _get_chat_session_path(chat_id)
        clean = (content or "").strip() or "(empty)"
        meta_clean = re.sub(r"\s+", " ", meta).strip() if meta else ""
        meta_suffix = f" [{meta_clean}]" if meta_clean else ""
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\n\n### {_now_iso_utc()} | {speaker}{meta_suffix}\n")
            f.write(clean)
            f.write("\n")
    except Exception as exc:
        logger.warning("Transcript append failed for chat %s: %s", chat_id, exc)


def _save_transcript_snapshot(chat_id: int) -> Optional[Path]:
    try:
        _ensure_log_dirs()
        source = _get_chat_session_path(chat_id)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination = SNAPSHOT_DIR / f"{source.stem}_saved_{stamp}.md"
        shutil.copy2(source, destination)
        return destination
    except Exception as exc:
        logger.warning("Transcript snapshot failed for chat %s: %s", chat_id, exc)
        return None


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
    return bool(card["pick"] and card["reason"])


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


def _has_analysis_intent(user_text: str) -> bool:
    text = _normalize(user_text)
    return any(keyword in text for keyword in ANALYSIS_KEYWORDS)


def _resolve_chat_mode(chat_id: int, user_text: str) -> str:
    mode = chat_modes.get(chat_id, "auto")
    if mode == "analysis":
        return "analysis"
    if mode == "normal":
        return "normal"
    return "analysis" if _has_analysis_intent(user_text) else "normal"


def _extract_agent_target(user_text: str) -> tuple[Optional[str], str]:
    found_targets: set[str] = set()
    cleaned = user_text

    for alias, target in AGENT_TARGET_ALIASES.items():
        pattern = rf"(?i)(?<!\w)@{re.escape(alias)}\b"
        if re.search(pattern, user_text):
            found_targets.add(target)
            cleaned = re.sub(pattern, " ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    target = next(iter(found_targets)) if len(found_targets) == 1 else None
    return target, cleaned


def _apply_analysis_skill(history: list[dict]) -> list[dict]:
    if not ANALYSIS_SKILL_TEXT:
        return list(history)
    return [
        {
            "role": "system",
            "content": (
                "Follow the SKILL.md analysis playbook for betting analysis turns.\n\n"
                f"{ANALYSIS_SKILL_TEXT}"
            ),
        }
    ] + list(history)


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
            f"Reason: {analyst_card['reason'] or strategist_card['reason'] or 'Aligned edge.'}\n"
            "Decision: aligned edge."
        )

    return (
        "⚖️ Consensus: NO AGREEMENT\n"
        f"The Sharp -> Pick: {analyst_card['pick'] or 'N/A'} | Reason: {analyst_card['reason'] or 'N/A'}\n"
        f"The Contrarian -> Pick: {strategist_card['pick'] or 'N/A'} | Reason: {strategist_card['reason'] or 'N/A'}\n"
        "Decision: no forced bet."
    )


async def _repair_card_if_needed(agent, history, full_text: str) -> str:
    if _is_structured_card_complete(full_text):
        return full_text

    repair_prompt = (
        "Return ONLY this exact 2-line decision card based on your previous analysis. "
        "No extra text.\n"
        "Pick: <team/side | over | under | no bet>\n"
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


async def stream_agent_response(agent, history, update, prefix_emoji, prefix_name, enforce_card: bool = True):
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
        if enforce_card:
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


async def run_agent_response_fast(agent, history, update, prefix_emoji, prefix_name, enforce_card: bool = True):
    """
    Faster non-streaming agent response path.
    Useful for analysis mode where two agents can run concurrently.
    """
    msg = await _safe_reply_text(update.message, f"{prefix_emoji} *{prefix_name} is thinking...*", markdown=True)

    full_text = ""
    try:
        full_text = await asyncio.to_thread(agent.chat, history)
        full_text = (full_text or "").strip()

        if enforce_card:
            full_text = await _repair_card_if_needed(agent, history, full_text)

        if msg:
            await _safe_edit_text(msg, f"{prefix_emoji} *{prefix_name}:*\n{full_text}", markdown=True)
        else:
            await _safe_reply_text(update.message, f"{prefix_emoji} {prefix_name}:\n{full_text}")

    except Exception as e:
        full_text = f"(Error: {e})"
        logger.error("%s fast-response error: %s", prefix_name, e)
        error_text = f"{prefix_emoji} {prefix_name}:\n⚠️ Error: {str(e)[:200]}"
        if msg:
            await _safe_edit_text(msg, error_text)
        else:
            await _safe_reply_text(update.message, error_text)

    return full_text


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    _append_transcript(chat_id, "System", "/start command received")
    await _safe_reply_text(
        update.message,
        "🏀 *NBA Betting Analysis Agents Online*\n\n"
        "Default mode is normal chat.\n"
        "When analysis is requested, two agents will respond:\n"
        "📊 *The Analyst* — Raw data & stats\n"
        "🎯 *The Strategist* — Betting plays & risk\n\n"
        "Commands:\n"
        "/start — Show this message\n"
        "/analysis — Force analysis mode\n"
        "/normal — Force normal chat mode\n"
        "/auto — Auto-detect mode from your message\n"
        "/save — Save current transcript snapshot\n"
        "/reset — Clear conversation history\n\n"
        "Examples:\n"
        "_\"what's up\"_ (normal)\n"
        "_\"analyze Lakers vs Suns and give a pick\"_ (analysis)\n"
        "_\"@sharp Lakers OKC live total?\"_ (single-agent analysis)\n"
        "_\"@contra same game, contrarian view\"_ (single-agent analysis)",
        markdown=True,
    )


async def analysis_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_modes[chat_id] = "analysis"
    _append_transcript(chat_id, "System", "Mode set to analysis via /analysis")
    await _safe_reply_text(update.message, "🧠 Mode set to ANALYSIS. I will use the SKILL.md workflow.")


async def normal_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_modes[chat_id] = "normal"
    _append_transcript(chat_id, "System", "Mode set to normal via /normal")
    await _safe_reply_text(update.message, "💬 Mode set to NORMAL chat.")


async def auto_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_modes[chat_id] = "auto"
    _append_transcript(chat_id, "System", "Mode set to auto via /auto")
    await _safe_reply_text(update.message, "🤖 Mode set to AUTO (normal chat unless analysis intent is detected).")


async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    _append_transcript(chat_id, "System", "/save command received")
    snapshot_path = _save_transcript_snapshot(chat_id)
    if snapshot_path is None:
        await _safe_reply_text(update.message, "⚠️ Failed to save transcript snapshot.")
        return
    await _safe_reply_text(
        update.message,
        f"💾 Transcript snapshot saved:\n{snapshot_path.resolve()}",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if not user_text:
        return

    target_agent, cleaned_text = _extract_agent_target(user_text)
    effective_user_text = cleaned_text if cleaned_text else user_text

    # Get or create history for this chat
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    
    history = chat_histories[chat_id]
    history.append({"role": "user", "content": effective_user_text})
    _append_transcript(chat_id, "User", effective_user_text, meta=f"raw={user_text}")
    turn_history = list(history)
    active_mode = "analysis" if target_agent else _resolve_chat_mode(chat_id, effective_user_text)

    if active_mode == "normal":
        normal_response = await stream_agent_response(
            chat_agent, turn_history, update, "💬", "Assistant", enforce_card=False
        )
        history.append({"role": "assistant", "name": "Assistant", "content": normal_response})
        _append_transcript(chat_id, "Assistant", normal_response, meta=f"mode={active_mode}")
        if len(history) > 30:
            chat_histories[chat_id] = history[-30:]
        return

    analysis_history = _apply_analysis_skill(turn_history)

    if target_agent == "sharp":
        analyst_response = await run_agent_response_fast(
            analyst, analysis_history, update, "📊", "The Sharp"
        )
        history.append({"role": "assistant", "name": "Analyst", "content": analyst_response})
        _append_transcript(chat_id, "The Sharp", analyst_response, meta="mode=analysis,target=sharp")
    elif target_agent == "contrarian":
        strategist_response = await run_agent_response_fast(
            strategist, analysis_history, update, "🎯", "The Contrarian"
        )
        history.append({"role": "assistant", "name": "Strategist", "content": strategist_response})
        _append_transcript(chat_id, "The Contrarian", strategist_response, meta="mode=analysis,target=contrarian")
    else:
        analyst_task = asyncio.create_task(
            run_agent_response_fast(analyst, analysis_history, update, "📊", "The Sharp")
        )
        strategist_task = asyncio.create_task(
            run_agent_response_fast(strategist, analysis_history, update, "🎯", "The Contrarian")
        )
        analyst_response, strategist_response = await asyncio.gather(analyst_task, strategist_task)

        history.append({"role": "assistant", "name": "Analyst", "content": analyst_response})
        history.append({"role": "assistant", "name": "Strategist", "content": strategist_response})
        _append_transcript(chat_id, "The Sharp", analyst_response, meta="mode=analysis,target=both")
        _append_transcript(chat_id, "The Contrarian", strategist_response, meta="mode=analysis,target=both")

        consensus = _build_consensus_message(analyst_response, strategist_response)
        await _safe_reply_text(update.message, consensus)
        _append_transcript(chat_id, "Consensus", consensus, meta="mode=analysis")

    # Keep history manageable (last 30 messages)
    if len(history) > 30:
        chat_histories[chat_id] = history[-30:]

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    _append_transcript(chat_id, "System", "Conversation reset via /reset")
    chat_histories[chat_id] = []
    chat_modes[chat_id] = "auto"
    new_session_path = _start_chat_session(chat_id, reason="reset")
    await _safe_reply_text(update.message, "🔄 Conversation history cleared.")
    await _safe_reply_text(
        update.message,
        f"🧾 New transcript session started:\n{new_session_path.resolve()}",
    )


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
    print(f"   SKILL.md:   {'loaded' if ANALYSIS_SKILL_TEXT else 'not found'}")
    _ensure_log_dirs()
    print(f"   Logs Dir:   {LOG_DIR.resolve()}")
    
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
    app.add_handler(CommandHandler("analysis", analysis_mode_command))
    app.add_handler(CommandHandler("normal", normal_mode_command))
    app.add_handler(CommandHandler("auto", auto_mode_command))
    app.add_handler(CommandHandler("save", save_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    print("   Bot is running. Send a message in Telegram!")
    app.run_polling()

if __name__ == "__main__":
    main()
