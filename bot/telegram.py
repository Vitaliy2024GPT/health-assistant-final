import logging
import json
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from bot import bot_commands
from flask import url_for

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.updater = Updater(token)
        self.dispatcher = self.updater.dispatcher
        self.dispatcher.add_handler(CommandHandler("start", self.start_command))
        self.dispatcher.add_handler(CommandHandler("help", self.help_command))
        self.dispatcher.add_handler(CommandHandler("connect", self.connect_command))
        
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

    async def connect_command(self, update: Update, context: CallbackContext):
        logging.info(f"Connect command from user {update.effective_user.id}")
        user_id = update.effective_user.id
        connect_url = f"{url_for('googleauth', _external=True)}?telegram_id={user_id}"
        message = f"Для привязки вашего аккаунта Telegram к Google, перейдите по ссылке: {connect_url}"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message
        )


    def handle_update(self, data: json):
        try:
            update = Update.de_json(data, self.updater.bot)
            self.dispatcher.process_update(update)
            logging.info(f"Telegram update processed: {update}")
        except Exception as e:
            logging.error(f"Error on handle_update {e}")
