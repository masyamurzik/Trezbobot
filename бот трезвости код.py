import os
import random
import httpx
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from datetime import datetime, time
import logging

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
START, COUNTING = range(2)
LOCAL_PHRASES = [
    "Каждый день трезвости делает тебя сильнее!",
    "Ты создаёшь новую версию себя!",
    "Гордись своим выбором - это достойно уважения!",
    "Трезвость - твой суперсила!",
    "Один день за раз - ты справишься!",
]

# Хранение данных (в продакшене используйте БД)
user_data = {}

async def get_motivational_quote():
    """Получаем мотивационную цитату из API или локального списка"""
    try:
        # Пробуем русскоязычное API Forismatic
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://api.forismatic.com/api/1.0/",
                params={"method": "getQuote", "format": "json", "lang": "ru"}
            )
            if response.status_code == 200:
                quote_data = response.json()
                return f"{quote_data['quoteText']}\n— {quote_data['quoteAuthor'] or 'Неизвестный автор'}"
    except Exception as e:
        logger.warning(f"Ошибка Forismatic API: {e}")

    try:
        # Fallback: Advice Slip API (английский)
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.adviceslip.com/advice")
            if response.status_code == 200:
                advice = response.json()["slip"]["advice"]
                return f"Совет дня: {advice}"
    except Exception as e:
        logger.warning(f"Ошибка Advice Slip API: {e}")

    # Если API недоступны - локальная фраза
    return random.choice(LOCAL_PHRASES)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Начать отсчёт"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот для подсчёта дней трезвости. Нажми 'Начать отсчёт' чтобы начать.",
        reply_markup=reply_markup,
    )
    return START

async def begin_counting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data[user_id] = {
        "start_date": datetime.now(),
        "last_check": datetime.now()
    }
    
    quote = await get_motivational_quote()
    
    keyboard = [["Сбросить счёт"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Отсчёт начат! Ты на 1 дне трезвости.\n\n{quote}",
        reply_markup=reply_markup,
    )
    return COUNTING

async def reset_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data[user_id] = {
        "start_date": datetime.now(),
        "last_check": datetime.now()
    }
    
    quote = await get_motivational_quote()
    
    await update.message.reply_text(
        f"Счёт сброшен. Начинаем новый отсчёт! Ты на 1 дне трезвости.\n\n{quote}",
    )
    return COUNTING

async def send_daily_update(context: ContextTypes.DEFAULT_TYPE):
    for user_id, data in user_data.items():
        days_passed = (datetime.now() - data["start_date"]).days
        quote = await get_motivational_quote()
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Сегодня {days_passed} день трезвости!\n\n{quote}"
            )
            user_data[user_id]["last_check"] = datetime.now()
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("До свидания! Если захочешь вернуться - нажми /start")
    return ConversationHandler.END

def main():
    # Проверяем наличие токена
    TOKEN = os.getenv("TELEGRAM_TOKEN", "7842761414:AAHNT3nilIA5MC0JCPG_-D2XyyhImrsRJqQ")
    if TOKEN == "7842761414:AAHNT3nilIA5MC0JCPG_-D2XyyhImrsRJqQ":
        logger.warning("Используется тестовый токен! Замените на реальный.")

    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START: [MessageHandler(filters.Regex("^Начать отсчёт$"), begin_counting)],
            COUNTING: [MessageHandler(filters.Regex("^Сбросить счёт$"), reset_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Настраиваем ежедневное обновление в 9:00
    if application.job_queue:
        application.job_queue.run_daily(
            send_daily_update,
            time=time(hour=9, minute=0),
            name="daily_motivation"
        )
    else:
        logger.warning("JobQueue не доступен!")
    
    application.run_polling()

if __name__ == "__main__":
    main()