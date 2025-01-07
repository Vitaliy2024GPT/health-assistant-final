import logging
import json
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackContext
from bot import bot_commands


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.application = ApplicationBuilder().token(token).build()
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))

    async def start_command(self, update: Update, context: CallbackContext):
        logging.info(f"Start command from user {update.effective_user.id}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=bot_commands["start"]
        )

    async def help_command(self, update: Update, context: CallbackContext):
        logging.info(f"Help command from user {update.effective_user.id}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=bot_commands["help"]
        )

    async def handle_update(self, data: json):
        try:
            update = Update.de_json(data, self.application.bot)
            await self.application.process_update(update)
            logging.info(f"Telegram update processed: {update}")
        except Exception as e:
            logging.error(f"Error on handle_update {e}")
