import logging
import os
import sqlite3
from datetime import date
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import openai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.getenv("AIDA_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("AIDA_API_KEY")
LIMITES_MENSAJES = 10

if not TOKEN:
    logger.error("AIDA_BOT_TOKEN no encontrado en variables de entorno")
    exit(1)

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

def init_database():
    try:
        conn = sqlite3.connect("aida.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT '',
            accepted_terms INTEGER DEFAULT 0,
            age_confirmed INTEGER DEFAULT 0,
            selected_bot TEXT DEFAULT '',
            messages_count INTEGER DEFAULT 0,
            last_message_date TEXT DEFAULT '',
            is_subscribed INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
    except Exception as e:
        logger.error(f"Error inicializando DB: {e}")
    finally:
        conn.close()

def get_user_data(user_id):
    try:
        conn = sqlite3.connect("aida.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            c.execute("INSERT INTO users (user_id, last_message_date) VALUES (?, ?)", (user_id, str(date.today())))
            conn.commit()
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()
        return user
    except Exception as e:
        logger.error(f"Error obteniendo usuario {user_id}: {e}")
        return None
    finally:
        conn.close()

def update_user_data(user_id, **kwargs):
    try:
        conn = sqlite3.connect("aida.db")
        c = conn.cursor()
        updates = ", ".join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [user_id]
        c.execute(f"UPDATE users SET {updates} WHERE user_id = ?", values)
        conn.commit()
    except Exception as e:
        logger.error(f"Error actualizando usuario {user_id}: {e}")
    finally:
        conn.close()

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    text = update.message.text.strip()

    if not user_data:
        await update.message.reply_text("❌ Por favor, inicia con /start.")
        return

    is_subscribed = user_data[7]
    messages_today = user_data[5]
    last_date = user_data[6]
    today = str(date.today())

    if not is_subscribed and last_date == today and messages_today >= LIMITES_MENSAJES:
        await update.message.reply_text("🚫 Límite de mensajes alcanzado. Suscríbete con /subscribe.")
        return

    bot_name = user_data[4] or ""
    prompt = text
    if "VALENTINA" in bot_name:
        prompt = f"Eres Valentina, una mujer venezolana cariñosa y divertida. {text}"
    elif "EMMA" in bot_name:
        prompt = f"Eres Emma, una americana segura, atrevida y sarcástica. {text}"
    elif "ANDREA" in bot_name:
        prompt = f"Eres Andrea, una colombiana dulce, coqueta y encantadora. {text}"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Error OpenAI: {e}")
        reply = "⚠️ Error procesando tu mensaje con la IA."

    await update.message.reply_text(reply)

    if last_date == today:
        update_user_data(user_id, messages_count=messages_today + 1)
    else:
        update_user_data(user_id, messages_count=1, last_message_date=today)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Usa /start para comenzar. Puedes chatear con la IA. Usa /subscribe para acceder a mensajes ilimitados.")

def main():
    init_database()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Usa /start para iniciar el onboarding.")))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_message))
    logger.info("🤖 AIDA corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
