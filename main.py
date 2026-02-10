
import os
import sys
import time
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
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
base_url = config['system'].get('llm_base_url')
analyst_model = config['agents']['agent_1']['model']
strategist_model = config['agents']['agent_2']['model']

# Initialize Agents
analyst = AnalystAgent()
analyst.model = analyst_model
if base_url:
    analyst.client.base_url = base_url

strategist = StrategistAgent()
strategist.model = strategist_model
if base_url:
    strategist.client.base_url = base_url

# Per-chat conversation histories
chat_histories: dict[int, list] = {}

# Streaming config
STREAM_EDIT_INTERVAL = 0.8  # seconds between Telegram message edits
MIN_CHUNK_SIZE = 30          # min characters accumulated before editing


async def stream_agent_response(agent, history, update, prefix_emoji, prefix_name):
    """
    Stream an agent's response into a Telegram message.
    Sends an initial message, then edits it as tokens arrive.
    Returns the full response text.
    """
    # Send initial "thinking" message
    msg = await update.message.reply_text(f"{prefix_emoji} *{prefix_name} is thinking...*", parse_mode="Markdown")

    full_text = ""
    buffer = ""
    last_edit_time = time.time()
    tool_calls_happened = False

    try:
        for chunk in agent.chat_stream(history):
            full_text += chunk
            buffer += chunk

            now = time.time()
            # Edit message periodically to simulate streaming
            if len(buffer) >= MIN_CHUNK_SIZE and (now - last_edit_time) >= STREAM_EDIT_INTERVAL:
                try:
                    display = f"{prefix_emoji} *{prefix_name}:*\n{full_text}▌"
                    await msg.edit_text(display, parse_mode="Markdown")
                except Exception:
                    # If markdown parse fails, send without formatting
                    try:
                        await msg.edit_text(f"{prefix_emoji} {prefix_name}:\n{full_text}▌")
                    except Exception:
                        pass
                buffer = ""
                last_edit_time = now
        
        # Final edit with complete text (no cursor)
        try:
            await msg.edit_text(f"{prefix_emoji} *{prefix_name}:*\n{full_text}", parse_mode="Markdown")
        except Exception:
            try:
                await msg.edit_text(f"{prefix_emoji} {prefix_name}:\n{full_text}")
            except Exception:
                pass

    except Exception as e:
        full_text = f"(Error: {e})"
        logger.error(f"{prefix_name} error: {e}")
        try:
            await msg.edit_text(f"{prefix_emoji} {prefix_name}:\n⚠️ Error: {str(e)[:200]}")
        except Exception:
            pass

    return full_text


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏀 *NBA Betting Analysis Agents Online*\n\n"
        "Ask me anything about NBA games, matchups, or betting strategy.\n"
        "Two agents will respond:\n"
        "📊 *The Analyst* — Raw data & stats\n"
        "🎯 *The Strategist* — Betting plays & risk\n\n"
        "Commands:\n"
        "/start — Show this message\n"
        "/reset — Clear conversation history\n\n"
        "Example: _\"Who plays tonight?\"_",
        parse_mode="Markdown"
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

    # --- Analyst Turn (Streaming) ---
    analyst_response = await stream_agent_response(
        analyst, history, update, "📊", "The Sharp"
    )
    history.append({"role": "assistant", "name": "Analyst", "content": analyst_response})

    # --- Strategist Turn (Streaming) ---
    strategist_response = await stream_agent_response(
        strategist, history, update, "🎯", "The Contrarian"
    )
    history.append({"role": "assistant", "name": "Strategist", "content": strategist_response})

    # Keep history manageable (last 30 messages)
    if len(history) > 30:
        chat_histories[chat_id] = history[-30:]

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = []
    await update.message.reply_text("🔄 Conversation history cleared.")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        sys.exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in .env")
        sys.exit(1)

    print(f"🏀 Starting Telegram Bot...")
    print(f"   Analyst:    model={analyst_model}, temp=0.4")
    print(f"   Strategist: model={strategist_model}, temp=0.6")
    print(f"   Max Tokens: 128,000")
    print(f"   Streaming:  ON")
    print(f"   LLM URL:    {base_url or 'default'}")
    
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("   Bot is running. Send a message in Telegram!")
    app.run_polling()

if __name__ == "__main__":
    main()
