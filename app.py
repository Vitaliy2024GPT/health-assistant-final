from database import add_user, get_user_by_email, add_meal, get_user_meals
from telegram.ext import CommandHandler

# Команда /adduser name email
def adduser_command(update, context):
    if len(context.args) < 2:
        update.message.reply_text("Usage: /adduser name email")
        return
    name = context.args[0]
    email = context.args[1]
    
    # Проверим, нет ли уже такого email
    user = get_user_by_email(email)
    if user:
        update.message.reply_text("Этот email уже зарегистрирован.")
    else:
        user_id = add_user(name, email)
        update.message.reply_text(f"Пользователь добавлен! ID: {user_id}")

# Команда /addmeal food_name calories
def addmeal_command(update, context):
    if len(context.args) < 2:
        update.message.reply_text("Usage: /addmeal food_name calories")
        return
    food_name = context.args[0]
    try:
        calories = int(context.args[1])
    except ValueError:
        update.message.reply_text("Calories must be a number.")
        return
    
    # Для теста предполагаем, что у нас есть пользователь с id=1
    # В будущем можно будет связывать user_id с тем, кто пишет в бота.
    # Например, использовать email из /adduser или чат id.
    user_id = 1  
    from datetime import date
    today = date.today().isoformat()
    add_meal(user_id, food_name, calories, today)
    update.message.reply_text(f"Meal added: {food_name}, {calories} kcal")

# Команда /meals
def meals_command(update, context):
    user_id = 1  # тестово
    meals = get_user_meals(user_id)
    if not meals:
        update.message.reply_text("No meals found.")
    else:
        # Сформируем текстовый отчёт
        lines = []
        for m in meals:
            lines.append(f"{m['date']}: {m['food_name']} - {m['calories']} kcal")
        update.message.reply_text("\n".join(lines))

dispatcher.add_handler(CommandHandler("adduser", adduser_command))
dispatcher.add_handler(CommandHandler("addmeal", addmeal_command))
dispatcher.add_handler(CommandHandler("meals", meals_command))
