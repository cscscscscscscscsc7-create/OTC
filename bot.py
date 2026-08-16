import telebot
import random
import json
import os
import time
import threading
from datetime import datetime

TOKEN = "8625146440:AAHVuOM-RV9zUYc4yMhoysauYJKWzT0Zu0A"
bot = telebot.TeleBot(TOKEN)
DATA_FILE = "ots_data.json"

def clean_for_json(obj):
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items() if not callable(v)}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj if not callable(item)]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"users": {}, "deals": {}, "reviews": {}, "workers": {}, "ads": [], "logs": [], "withdraws": {}, "blacklist": []}
    return {"users": {}, "deals": {}, "reviews": {}, "workers": {}, "ads": [], "logs": [], "withdraws": {}, "blacklist": []}

def save_data(data):
    clean = clean_for_json(data)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

data = load_data()
users = data["users"]
deals = data["deals"]
reviews = data.get("reviews", {})
workers = data.get("workers", {})
ads = data.get("ads", [])
logs = data.get("logs", [])
withdraws = data.get("withdraws", {})
blacklist = data.get("blacklist", [])

data["workers"] = workers
save_data(data)

def save():
    data["users"] = users
    data["deals"] = deals
    data["reviews"] = reviews
    data["workers"] = workers
    data["ads"] = ads
    data["logs"] = logs
    data["withdraws"] = withdraws
    data["blacklist"] = blacklist
    save_data(data)

def get_uid(msg):
    return str(msg.chat.id)

def ensure_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "deals": [],
            "ref_code": str(random.randint(100000, 999999)),
            "ref_count": 0,
            "ref_earned": 0,
            "invited_by": None,
            "username": None,
            "total_deals": 0,
            "rating": 0,
            "balance": {"TON": 0, "USDT": 0, "BTC": 0, "Stars": 0}
        }
        save()

def is_banned(user_id):
    return user_id in blacklist

def get_balance_text(user_id):
    bal = users[user_id]["balance"]
    text = "💰 Баланс:\n"
    text += f"💎 TON: {bal.get('TON', 0)}\n"
    text += f"💵 USDT: {bal.get('USDT', 0)}\n"
    text += f"₿ BTC: {bal.get('BTC', 0)}\n"
    text += f"⭐ Stars: {bal.get('Stars', 0)}"
    return text

def add_balance(user_id, currency, amount):
    if currency not in users[user_id]["balance"]:
        users[user_id]["balance"][currency] = 0
    users[user_id]["balance"][currency] += amount
    save()

def subtract_balance(user_id, currency, amount):
    if currency not in users[user_id]["balance"]:
        users[user_id]["balance"][currency] = 0
    users[user_id]["balance"][currency] -= amount
    if users[user_id]["balance"][currency] < 0:
        users[user_id]["balance"][currency] = 0
    save()

def main_menu():
    kb = telebot.types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        telebot.types.InlineKeyboardButton("🛒 Создать сделку", callback_data="new_deal"),
        telebot.types.InlineKeyboardButton("📦 Продать", callback_data="sell_start"),
        telebot.types.InlineKeyboardButton("🏪 Маркет", callback_data="market"),
        telebot.types.InlineKeyboardButton("📋 Мои сделки", callback_data="my_deals"),
        telebot.types.InlineKeyboardButton("👥 Рефералы", callback_data="ref"),
        telebot.types.InlineKeyboardButton("⭐ Отзывы", callback_data="reviews"),
        telebot.types.InlineKeyboardButton("👤 Продавцы", callback_data="sellers"),
        telebot.types.InlineKeyboardButton("ℹ️ О боте", callback_data="about")
    )
    return kb

def back():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
    return kb

def deal_link(deal_id):
    return f"https://t.me/GNT_Guarant_Bot?start=deal_{deal_id}"

def get_status_emoji(status):
    emojis = {
        "waiting_seller": "🔄",
        "waiting_payment": "⏳",
        "frozen": "🔒",
        "completed": "✅",
        "cancelled": "❌",
        "checking_payment": "🔍"
    }
    return emojis.get(status, "")

def get_status_text(status):
    texts = {
        "waiting_seller": "⏳ Ожидает продавца",
        "waiting_payment": "💳 Ожидает оплаты",
        "frozen": "🔒 Заморожена",
        "completed": "✅ Завершена",
        "cancelled": "❌ Отменена",
        "checking_payment": "🔍 Проверка платежа"
    }
    return texts.get(status, status)

def format_deal_short(deal_id):
    d = deals.get(str(deal_id))
    if not d:
        return "❌ Сделка не найдена"
    emoji = get_status_emoji(d['status'])
    status = get_status_text(d['status'])
    text = f"{emoji} Сделка #{deal_id}\n📌 Статус: {status}\n💱 Сумма: {d.get('amount', 0)} {d.get('currency', 'TON')}\n"
    if d.get('buyer'):
        buyer_name = users.get(d['buyer'], {}).get('username', d['buyer'])
        text += f"👤 Покупатель: @{buyer_name}\n"
    if d.get('seller'):
        seller_name = users.get(d['seller'], {}).get('username', d['seller'])
        text += f"👤 Продавец: @{seller_name}\n"
    return text

def get_deal_keyboard(deal_id, user_id):
    d = deals.get(str(deal_id))
    if not d:
        return back()
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    if d['status'] == 'waiting_seller' and d.get('buyer') != user_id:
        kb.add(telebot.types.InlineKeyboardButton("✅ Взять сделку", callback_data=f"take_{deal_id}"))
    elif d['status'] == 'waiting_payment':
        if d.get('buyer') is None:
            d['buyer'] = user_id
            save()
            seller_id = d.get('seller')
            if seller_id:
                bot.send_message(seller_id, f"🔔 Покупатель @{users.get(user_id, {}).get('username', user_id)} зашёл в сделку #{deal_id} и готов оплатить.\nОжидайте подтверждения оплаты.")
            kb.add(telebot.types.InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"pay_{deal_id}"))
        elif d.get('buyer') == user_id:
            kb.add(telebot.types.InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"pay_{deal_id}"))
    elif d['status'] == 'frozen' and d.get('seller') == user_id:
        kb.add(telebot.types.InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"complete_{deal_id}"))
    elif d['status'] == 'completed':
        kb.add(telebot.types.InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f"review_deal_{deal_id}"))
    if d['status'] in ['waiting_seller', 'waiting_payment', 'checking_payment', 'frozen']:
        if d.get('buyer') == user_id or d.get('seller') == user_id:
            kb.add(telebot.types.InlineKeyboardButton("❌ Отменить сделку", callback_data=f"cancel_{deal_id}"))
    kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
    return kb

def safe_edit(chat_id, msg_id, text, reply_markup=None, parse_mode='HTML'):
    try:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        if "message to edit" in str(e) or "message not found" in str(e):
            bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            return False
        else:
            raise e

def safe_answer(call_id, text=None):
    try:
        bot.answer_callback_query(call_id, text=text)
    except:
        pass

user_temp = {}

@bot.message_handler(commands=['start'])
def start(msg):
    user_id = get_uid(msg)
    ensure_user(user_id)
    if msg.from_user.username:
        users[user_id]["username"] = msg.from_user.username
        save()
    if len(msg.text.split()) > 1:
        param = msg.text.split()[1]
        if param.startswith("deal_"):
            deal_id = param.replace("deal_", "")
            if deal_id in deals:
                text = format_deal_short(deal_id)
                kb = get_deal_keyboard(deal_id, user_id)
                bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
                return
            else:
                bot.send_message(user_id, "❌ Сделка не найдена.", reply_markup=back())
                return
        code = param
        for u, d in users.items():
            if d.get("ref_code") == code and u != user_id:
                users[u]["ref_count"] += 1
                add_balance(u, "TON", 0.5)
                users[user_id]["invited_by"] = u
                save()
                bot.send_message(u, "👤 Новый реферал! +0.5 TON.")
                break
    welcome = "🏦 ОТС — ГАРАНТ\n\n" + get_balance_text(user_id)
    try:
        bot.send_photo(
            user_id,
            "https://i.ibb.co/wZq5MCX0/IMG-20260813-121036-325.jpg",
            caption=welcome,
            parse_mode='HTML',
            reply_markup=main_menu()
        )
    except:
        bot.send_message(user_id, welcome, parse_mode='HTML', reply_markup=main_menu())

@bot.message_handler(commands=['clteam'])
def worker_panel(msg):
    user_id = get_uid(msg)
    ensure_user(user_id)
    try:
        bot.delete_message(msg.chat.id, msg.message_id)
    except:
        pass
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("📊 Все сделки", callback_data="worker_all_deals"),
        telebot.types.InlineKeyboardButton("📌 Активные сделки", callback_data="worker_active_deals"),
        telebot.types.InlineKeyboardButton("👥 Пользователи", callback_data="worker_users"),
        telebot.types.InlineKeyboardButton("🔍 Поиск пользователя", callback_data="worker_find_user"),
        telebot.types.InlineKeyboardButton("🏆 Топ", callback_data="worker_top"),
        telebot.types.InlineKeyboardButton("📈 Статистика", callback_data="worker_stats"),
        telebot.types.InlineKeyboardButton("⛔ Чёрный список", callback_data="worker_blacklist"),
        telebot.types.InlineKeyboardButton("📨 Рассылка", callback_data="worker_mailing"),
        telebot.types.InlineKeyboardButton("❌ Отменить сделку", callback_data="worker_cancel_deal"),
        telebot.types.InlineKeyboardButton("➕ Добавить в ЧС", callback_data="worker_blacklist_add"),
        telebot.types.InlineKeyboardButton("➖ Удалить из ЧС", callback_data="worker_blacklist_remove"),
        telebot.types.InlineKeyboardButton("🔑 Выдать доступ", callback_data="worker_give_access"),
    )
    kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
    bot.send_message(user_id, "👨‍💼 Панель управления", reply_markup=kb, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    safe_answer(call.id)
    user_id = get_uid(call.message)
    data = call.data

    if data == "back":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        welcome = "🏦 ОТС — ГАРАНТ\n\n" + get_balance_text(user_id)
        bot.send_message(user_id, welcome, reply_markup=main_menu(), parse_mode='HTML')
        return

    if data == "new_deal":
        if is_banned(user_id):
            bot.send_message(user_id, "⛔ Вы в чёрном списке.", reply_markup=back())
            return
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("👤 Я продавец", callback_data="new_deal_seller"),
            telebot.types.InlineKeyboardButton("🛒 Я покупатель", callback_data="new_deal_buyer"),
            telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back")
        )
        safe_edit(call.message.chat.id, call.message.message_id, "🛒 Кто вы в этой сделке?", reply_markup=kb, parse_mode='HTML')
        return

    if data == "new_deal_seller":
        if is_banned(user_id):
            bot.send_message(user_id, "⛔ Вы в чёрном списке.", reply_markup=back())
            return
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("💎 TON", callback_data="nd_seller_TON"),
            telebot.types.InlineKeyboardButton("💵 USDT", callback_data="nd_seller_USDT"),
            telebot.types.InlineKeyboardButton("₿ BTC", callback_data="nd_seller_BTC"),
            telebot.types.InlineKeyboardButton("⭐ Stars", callback_data="nd_seller_Stars")
        )
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="new_deal"))
        safe_edit(call.message.chat.id, call.message.message_id, "📦 Выберите валюту сделки:", reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("nd_seller_"):
        currency = data.split("_")[2]
        user_temp[user_id] = {"role": "seller", "currency": currency, "step": "amount"}
        bot.send_message(user_id, f"💱 {currency}\n💰 Введите сумму:", reply_markup=back(), parse_mode='HTML')
        bot.register_next_step_handler(call.message, nd_seller_amount)
        return

    if data == "new_deal_buyer":
        if is_banned(user_id):
            bot.send_message(user_id, "⛔ Вы в чёрном списке.", reply_markup=back())
            return
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("💎 TON", callback_data="nd_buyer_TON"),
            telebot.types.InlineKeyboardButton("💵 USDT", callback_data="nd_buyer_USDT"),
            telebot.types.InlineKeyboardButton("₿ BTC", callback_data="nd_buyer_BTC"),
            telebot.types.InlineKeyboardButton("⭐ Stars", callback_data="nd_buyer_Stars")
        )
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="new_deal"))
        safe_edit(call.message.chat.id, call.message.message_id, "📦 Выберите валюту сделки:", reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("nd_buyer_"):
        currency = data.split("_")[2]
        user_temp[user_id] = {"role": "buyer", "currency": currency, "step": "amount"}
        bot.send_message(user_id, f"💱 {currency}\n💰 Введите сумму:", reply_markup=back(), parse_mode='HTML')
        bot.register_next_step_handler(call.message, nd_buyer_amount)
        return

    if data == "sell_start":
        if is_banned(user_id):
            bot.send_message(user_id, "⛔ Вы в чёрном списке.", reply_markup=back())
            return
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton("💎 TON", callback_data="sell_cur_TON"),
            telebot.types.InlineKeyboardButton("💵 USDT", callback_data="sell_cur_USDT"),
            telebot.types.InlineKeyboardButton("₿ BTC", callback_data="sell_cur_BTC"),
            telebot.types.InlineKeyboardButton("⭐ Stars", callback_data="sell_cur_Stars")
        )
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        safe_edit(call.message.chat.id, call.message.message_id, "📦 Выберите валюту:", reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("sell_cur_"):
        currency = data.split("_")[2]
        user_temp[user_id] = {"role": "seller_ad", "currency": currency, "step": "amount"}
        bot.send_message(user_id, f"💱 {currency}\n💰 Введите сумму:", reply_markup=back(), parse_mode='HTML')
        bot.register_next_step_handler(call.message, sell_amount_input)
        return

    if data == "market":
        active_ads = [a for a in ads if a.get("status") == "active"]
        if not active_ads:
            bot.send_message(user_id, "🏪 Маркет пуст", reply_markup=back())
            return
        text = "🏪 Маркет\n\n"
        for ad in active_ads[:10]:
            seller_name = users.get(ad['seller'], {}).get('username', ad['seller'])
            text += f"🆔 #{ad['id']}\n💱 {ad['currency']} — {ad['amount']} шт.\n👤 @{seller_name}\n\n"
        kb = telebot.types.InlineKeyboardMarkup()
        for ad in active_ads[:5]:
            kb.add(telebot.types.InlineKeyboardButton(f"🛒 Купить #{ad['id']}", callback_data=f"buy_ad_{ad['id']}"))
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        safe_edit(call.message.chat.id, call.message.message_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("buy_ad_"):
        ad_id = int(data.split("_")[2])
        ad = next((a for a in ads if a["id"] == ad_id and a.get("status") == "active"), None)
        if not ad:
            bot.send_message(user_id, "❌ Объявление не найдено.", reply_markup=back())
            return
        if ad["seller"] == user_id:
            bot.send_message(user_id, "❌ Нельзя купить своё.", reply_markup=back())
            return
        
        buyer_balance = users[user_id]["balance"].get(ad["currency"], 0)
        if buyer_balance < ad["amount"]:
            bot.send_message(user_id, f"❌ Недостаточно средств. Нужно {ad['amount']} {ad['currency']}, у вас {buyer_balance} {ad['currency']}.", reply_markup=back())
            return
        
        subtract_balance(user_id, ad["currency"], ad["amount"])
        
        deal_id = random.randint(10000, 99999)
        deal_id_str = str(deal_id)
        deals[deal_id_str] = {
            "id": deal_id,
            "creator": user_id,
            "role": "buyer",
            "status": "waiting_payment",
            "amount": ad["amount"],
            "currency": ad["currency"],
            "buyer": user_id,
            "seller": ad["seller"],
            "ad_id": ad_id,
            "created_at": datetime.now().isoformat()
        }
        if user_id not in users:
            ensure_user(user_id)
        if deal_id_str not in users[user_id]["deals"]:
            users[user_id]["deals"].append(deal_id_str)
        ad["status"] = "sold"
        save()

        link = deal_link(deal_id_str)
        text = f"✅ Сделка #{deal_id}\n\n{format_deal_short(deal_id_str)}\n\n💸 Переведите {ad['amount']} {ad['currency']} на кошелёк @Managerguarantnft\n\n✅ После оплаты нажмите «Подтвердить оплату».\n\nЕсли возникнут проблемы, пишите @Henryus03"
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"pay_{deal_id_str}"))
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

        seller_text = f"📦 Продажа #{deal_id}\n\n👤 Покупатель: @{users.get(user_id, {}).get('username', user_id)}\n💱 {ad['currency']}\n📦 {ad['amount']} шт.\n\n🔗 {link}"
        kb_seller = telebot.types.InlineKeyboardMarkup()
        kb_seller.add(telebot.types.InlineKeyboardButton("🔗 Перейти", url=link))
        kb_seller.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(ad["seller"], seller_text, reply_markup=kb_seller, parse_mode='HTML')
        return

    if data.startswith("take_"):
        deal_id = data.split("_")[1]
        if deal_id not in deals:
            return
        d = deals[deal_id]
        if d['status'] != 'waiting_seller':
            safe_answer(call.id, "❌ Уже не ждёт продавца")
            return
        if d.get('buyer') == user_id:
            safe_answer(call.id, "❌ Нельзя взять свою")
            return
        d['seller'] = user_id
        d['status'] = 'waiting_payment'
        save()
        buyer_id = d.get('buyer')
        if buyer_id:
            text = format_deal_short(deal_id)
            kb = get_deal_keyboard(deal_id, buyer_id)
            safe_edit(call.message.chat.id, call.message.message_id, f"✅ Продавец найден!\n\n{text}\n\n💸 Переведите {d['amount']} {d['currency']} на кошелёк @Managerguarantnft и нажмите «Подтвердить оплату».\n\nЕсли возникнут проблемы, пишите @Henryus03", reply_markup=kb, parse_mode='HTML')
        bot.send_message(user_id, f"✅ Вы взяли сделку #{deal_id}.\nОжидайте оплаты.", reply_markup=back(), parse_mode='HTML')
        return

    if data.startswith("pay_"):
        deal_id = data.split("_")[1]
        if deal_id not in deals:
            return
        d = deals[deal_id]
        if d['status'] != 'waiting_payment':
            safe_answer(call.id, "⏳ Не ожидает оплаты")
            return
        if d.get('buyer') != user_id:
            safe_answer(call.id, "❌ Вы не покупатель")
            return
        d['status'] = 'checking_payment'
        save()
        text = format_deal_short(deal_id)
        kb = get_deal_keyboard(deal_id, user_id)
        safe_edit(call.message.chat.id, call.message.message_id, text, reply_markup=kb, parse_mode='HTML')

        seller_id = d.get('seller')
        if seller_id:
            text_s = format_deal_short(deal_id)
            kb_s = get_deal_keyboard(deal_id, seller_id)
            bot.send_message(seller_id, f"🔔 Оплата по сделке #{deal_id}!\n🔍 Проверка...\n\n{text_s}", reply_markup=kb_s, parse_mode='HTML')

        def confirm_payment(deal_id):
            time.sleep(30)
            if deal_id in deals:
                d = deals[deal_id]
                if d['status'] == 'checking_payment':
                    d['status'] = 'frozen'
                    save()
                    buyer_id = d.get('buyer')
                    if buyer_id:
                        text_b = format_deal_short(deal_id)
                        kb_b = get_deal_keyboard(deal_id, buyer_id)
                        bot.send_message(buyer_id, f"✅ Платёж подтверждён!\n⏳ Ожидайте от продавца.\n\n{text_b}", reply_markup=kb_b, parse_mode='HTML')
                    seller_id = d.get('seller')
                    if seller_id:
                        text_s = format_deal_short(deal_id)
                        kb_s = get_deal_keyboard(deal_id, seller_id)
                        bot.send_message(seller_id, f"✅ Платёж подтверждён!\n✅ Нажмите «Подтвердить получение».\n\n{text_s}", reply_markup=kb_s, parse_mode='HTML')
        threading.Thread(target=confirm_payment, args=(deal_id,), daemon=True).start()
        return

    if data.startswith("complete_"):
        deal_id = data.split("_")[1]
        if deal_id not in deals:
            return
        d = deals[deal_id]
        if d['status'] != 'frozen':
            safe_answer(call.id, "❌ Не заморожена")
            return
        if d.get('seller') != user_id:
            safe_answer(call.id, "❌ Вы не продавец")
            return
        d['status'] = 'completed'
        currency = d['currency']
        amount = d['amount']
        add_balance(user_id, currency, amount)
        save()
        buyer_id = d.get('buyer')
        if buyer_id:
            text = format_deal_short(deal_id)
            kb = get_deal_keyboard(deal_id, buyer_id)
            bot.send_message(buyer_id, f"✅ Сделка #{deal_id} завершена!\n⭐ Оставьте отзыв.\n\n{text}", reply_markup=kb, parse_mode='HTML')
        if seller_id := d.get('seller'):
            text = format_deal_short(deal_id)
            kb = get_deal_keyboard(deal_id, seller_id)
            bot.send_message(seller_id, f"✅ Сделка #{deal_id} завершена!\n💰 Начислено {amount} {currency}.\n\n{get_balance_text(seller_id)}\n\nДля вывода обратитесь к @Managerguarantnft", reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("cancel_"):
        deal_id = data.split("_")[1]
        if deal_id not in deals:
            return
        d = deals[deal_id]
        if d['status'] in ['completed', 'cancelled']:
            safe_answer(call.id, "❌ Уже завершена")
            return
        d['status'] = 'cancelled'
        save()
        buyer_id = d.get('buyer')
        seller_id = d.get('seller')
        for uid in [buyer_id, seller_id]:
            if uid:
                bot.send_message(uid, f"❌ Сделка #{deal_id} отменена.", reply_markup=back(), parse_mode='HTML')
        return

    if data == "my_deals":
        user_deals = users[user_id]["deals"]
        if not user_deals:
            bot.send_message(user_id, "📋 Нет сделок.", reply_markup=back())
            return
        text = "📋 Мои сделки\n\n"
        for deal_id in user_deals[-10:]:
            if deal_id in deals:
                d = deals[deal_id]
                emoji = get_status_emoji(d['status'])
                status = get_status_text(d['status'])
                text += f"{emoji} #{deal_id} — {status}\n"
        kb = telebot.types.InlineKeyboardMarkup()
        for deal_id in user_deals[-5:]:
            kb.add(telebot.types.InlineKeyboardButton(f"🔍 #{deal_id}", callback_data=f"view_deal_{deal_id}"))
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("view_deal_"):
        deal_id = data.split("_")[2]
        if deal_id not in deals:
            bot.send_message(user_id, "❌ Сделка не найдена", reply_markup=back())
            return
        text = format_deal_short(deal_id)
        kb = get_deal_keyboard(deal_id, user_id)
        safe_edit(call.message.chat.id, call.message.message_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data == "ref":
        ref_code = users[user_id]["ref_code"]
        ref_count = users[user_id]["ref_count"]
        ref_earned = users[user_id]["ref_earned"]
        text = f"👥 Рефералы\n\n🔗 Код: {ref_code}\n👤 Приглашено: {ref_count}\n💰 Заработано: {ref_earned} TON\n\n📤 Ссылка:\nhttps://t.me/GNT_Guarant_Bot?start={ref_code}"
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data == "reviews":
        all_reviews = list(reviews.values())
        if not all_reviews:
            bot.send_message(user_id, "⭐ Нет отзывов.", reply_markup=back())
            return
        text = "⭐ Отзывы\n\n"
        for review in all_reviews[-5:]:
            text += f"👤 @{review.get('username', 'unknown')}\n⭐ {review.get('rating', 0)}/5\n💬 {review.get('text', '')}\n\n"
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data == "sellers":
        seller_list = [(uid, u) for uid, u in users.items() if u.get("total_deals", 0) > 0]
        seller_list.sort(key=lambda x: x[1].get("rating", 0), reverse=True)
        if not seller_list:
            bot.send_message(user_id, "👤 Нет продавцов.", reply_markup=back())
            return
        text = "👤 Продавцы\n\n"
        for uid, u in seller_list[:10]:
            name = u.get('username', uid)
            rating = u.get('rating', 0)
            deals_count = u.get('total_deals', 0)
            text += f"👤 @{name}\n⭐ {rating}/5\n📦 {deals_count} сделок\n\n"
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data == "about":
        text = "ℹ️ О боте\n\n🏦 ОТС — ГАРАНТ\n🔒 Безопасные сделки\n\n👨‍💼 Менеджер: @Managerguarantnft\n🆘 Поддержка: @Henryus03"
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
        bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
        return

    if data.startswith("review_deal_"):
        deal_id = data.split("_")[2]
        if deal_id not in deals:
            bot.send_message(user_id, "❌ Сделка не найдена.", reply_markup=back())
            return
        d = deals[deal_id]
        if d['status'] != 'completed':
            bot.send_message(user_id, "❌ Сделка ещё не завершена.", reply_markup=back())
            return
        if d.get('buyer') != user_id:
            bot.send_message(user_id, "❌ Только покупатель может оставить отзыв.", reply_markup=back())
            return
        bot.send_message(user_id, "⭐ Оцените продавца от 1 до 5 (числом):", reply_markup=back(), parse_mode='HTML')
        bot.register_next_step_handler(call.message, review_rating_input, deal_id)
        return

    if data.startswith("worker_"):
        if data == "worker_all_deals":
            if not deals:
                bot.send_message(user_id, "📊 Нет сделок.", reply_markup=back())
                return
            text = "📊 Все сделки\n\n"
            for deal_id, d in list(deals.items())[-20:]:
                emoji = get_status_emoji(d['status'])
                status = get_status_text(d['status'])
                text += f"{emoji} #{deal_id} — {status}\n"
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
            bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
            return

        if data == "worker_active_deals":
            active = {k: v for k, v in deals.items() if v['status'] in ['waiting_seller', 'waiting_payment', 'checking_payment', 'frozen']}
            if not active:
                bot.send_message(user_id, "📌 Нет активных.", reply_markup=back())
                return
            text = "📌 Активные\n\n"
            for deal_id, d in list(active.items())[-20:]:
                emoji = get_status_emoji(d['status'])
                status = get_status_text(d['status'])
                text += f"{emoji} #{deal_id} — {status}\n"
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
            bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
            return

        if data == "worker_users":
            text = f"👥 Пользователи\n\n👤 Всего: {len(users)}\n"
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
            bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
            return

        if data == "worker_find_user":
            bot.send_message(user_id, "🔍 Введите ID или @username:", reply_markup=back(), parse_mode='HTML')
            bot.register_next_step_handler(call.message, find_user_input)
            return

        if data == "worker_top":
            top = sorted(users.items(), key=lambda x: sum(x[1].get('balance', {}).values()), reverse=True)[:10]
            text = "🏆 Топ по балансу\n\n"
            for i, (uid, u) in enumerate(top, 1):
                name = u.get('username', uid)
                bal = u.get('balance', {})
                total = sum(bal.values())
                text += f"{i}. @{name} — {total} TON\n"
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
            bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
            return

        if data == "worker_stats":
            total_deals = len(deals)
            total_users = len(users)
            total_volume = sum(d.get('amount', 0) for d in deals.values())
            text = f"📈 Статистика\n\n👥 Пользователей: {total_users}\n📦 Сделок: {total_deals}\n💰 Объём: {total_volume} (в валютах)"
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
            bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
            return

        if data == "worker_blacklist":
            if not blacklist:
                bot.send_message(user_id, "⛔ ЧС пуст.", reply_markup=back())
                return
            text = "⛔ Чёрный список\n\n"
            for uid in blacklist:
                username = users.get(uid, {}).get('username', 'неизвестно')
                text += f"🆔 {uid} (@{username})\n"
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
            bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')
            return

        if data == "worker_mailing":
            bot.send_message(user_id, "📨 Введите текст рассылки:", reply_markup=back(), parse_mode='HTML')
            bot.register_next_step_handler(call.message, handle_mailing)
            return

        if data == "worker_cancel_deal":
            bot.send_message(user_id, "❌ Введите ID сделки:", reply_markup=back(), parse_mode='HTML')
            bot.register_next_step_handler(call.message, worker_cancel_deal_input)
            return

        if data == "worker_give_access":
            bot.send_message(user_id, "🔑 Введите ID пользователя:", reply_markup=back(), parse_mode='HTML')
            bot.register_next_step_handler(call.message, handle_give_access)
            return

        if data == "worker_blacklist_add":
            bot.send_message(user_id, "➕ Введите ID пользователя:", reply_markup=back(), parse_mode='HTML')
            bot.register_next_step_handler(call.message, blacklist_add_input)
            return

        if data == "worker_blacklist_remove":
            bot.send_message(user_id, "➖ Введите ID пользователя:", reply_markup=back(), parse_mode='HTML')
            bot.register_next_step_handler(call.message, blacklist_remove_input)
            return

        return

def find_user_input(msg):
    user_id = get_uid(msg)
    query = msg.text.strip()
    if query.startswith("@"):
        username = query[1:]
        found = None
        for uid, u in users.items():
            if u.get('username') == username:
                found = uid
                break
        if not found:
            bot.send_message(user_id, "❌ Не найден.", reply_markup=back())
            return
    else:
        if not query.isdigit():
            bot.send_message(user_id, "❌ Введите ID или @username.", reply_markup=back())
            return
        found = query
        if found not in users:
            bot.send_message(user_id, "❌ Не найден.", reply_markup=back())
            return
    u = users[found]
    username = u.get('username', 'неизвестно')
    total_deals = u.get('total_deals', 0)
    rating = u.get('rating', 0)
    ref_count = u.get('ref_count', 0)
    deals_list = u.get('deals', [])
    text = f"🔍 Информация\n\n🆔 ID: {found}\n👤 @{username}\n📦 Сделок: {total_deals}\n⭐ Рейтинг: {rating}/5\n👥 Рефералов: {ref_count}\n📋 Сделок: {len(deals_list)} шт.\n\n{get_balance_text(found)}"
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
    bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

def nd_seller_amount(msg):
    user_id = get_uid(msg)
    ensure_user(user_id)
    try:
        amount = float(msg.text.replace(',', '.'))
        if amount <= 0:
            bot.send_message(user_id, "❌ Сумма должна быть больше 0", reply_markup=back())
            return
    except:
        bot.send_message(user_id, "❌ Введите число", reply_markup=back())
        return
    currency = user_temp[user_id]["currency"]
    deal_id = random.randint(10000, 99999)
    deal_id_str = str(deal_id)
    deals[deal_id_str] = {
        "id": deal_id,
        "creator": user_id,
        "role": "seller",
        "status": "waiting_payment",
        "amount": amount,
        "currency": currency,
        "buyer": None,
        "seller": user_id,
        "created_at": datetime.now().isoformat()
    }
    if deal_id_str not in users[user_id]["deals"]:
        users[user_id]["deals"].append(deal_id_str)
    save()
    if user_id in user_temp:
        del user_temp[user_id]
    link = deal_link(deal_id_str)
    text = f"✅ Сделка #{deal_id}\n\n{format_deal_short(deal_id_str)}\n\n📤 Отправьте ссылку покупателю:\n{link}"
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🔗 Поделиться", url=link))
    kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
    bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

def nd_buyer_amount(msg):
    user_id = get_uid(msg)
    ensure_user(user_id)
    try:
        amount = float(msg.text.replace(',', '.'))
        if amount <= 0:
            bot.send_message(user_id, "❌ Сумма должна быть больше 0", reply_markup=back())
            return
    except:
        bot.send_message(user_id, "❌ Введите число", reply_markup=back())
        return
    currency = user_temp[user_id]["currency"]
    deal_id = random.randint(10000, 99999)
    deal_id_str = str(deal_id)
    deals[deal_id_str] = {
        "id": deal_id,
        "creator": user_id,
        "role": "buyer",
        "status": "waiting_seller",
        "amount": amount,
        "currency": currency,
        "buyer": user_id,
        "seller": None,
        "created_at": datetime.now().isoformat()
    }
    if deal_id_str not in users[user_id]["deals"]:
        users[user_id]["deals"].append(deal_id_str)
    save()
    if user_id in user_temp:
        del user_temp[user_id]
    link = deal_link(deal_id_str)
    text = f"✅ Сделка #{deal_id}\n\n{format_deal_short(deal_id_str)}\n\n📤 Отправьте ссылку продавцу:\n{link}"
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🔗 Поделиться", url=link))
    kb.add(telebot.types.InlineKeyboardButton("◀ Назад", callback_data="back"))
    bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

def sell_amount_input(msg):
    user_id = get_uid(msg)
    ensure_user(user_id)
    try:
        amount = float(msg.text.replace(',', '.'))
        if amount <= 0:
            bot.send_message(user_id, "❌ Сумма должна быть больше 0", reply_markup=back())
            return
    except:
        bot.send_message(user_id, "❌ Введите число", reply_markup=back())
        return
    currency = user_temp[user_id]["currency"]
    ad_id = random.randint(10000, 99999)
    ads.append({
        "id": ad_id,
        "seller": user_id,
        "currency": currency,
        "amount": amount,
        "status": "active",
        "created_at": datetime.now().isoformat()
    })
    save()
    if user_id in user_temp:
        del user_temp[user_id]
    text = f"✅ Объявление #{ad_id}\n💱 {currency}\n📦 {amount} шт."
    bot.send_message(user_id, text, reply_markup=back(), parse_mode='HTML')

def review_rating_input(msg, deal_id):
    user_id = get_uid(msg)
    try:
        rating = int(msg.text)
        if rating < 1 or rating > 5:
            bot.send_message(user_id, "❌ Оценка от 1 до 5.", reply_markup=back())
            return
    except:
        bot.send_message(user_id, "❌ Введите число от 1 до 5.", reply_markup=back())
        return
    bot.send_message(user_id, "✏️ Напишите текст отзыва:", reply_markup=back(), parse_mode='HTML')
    bot.register_next_step_handler(msg, review_text_input, deal_id, rating)

def review_text_input(msg, deal_id, rating):
    user_id = get_uid(msg)
    text = msg.text
    d = deals.get(deal_id)
    if not d:
        bot.send_message(user_id, "❌ Сделка не найдена.", reply_markup=back())
        return
    seller_id = d.get('seller')
    if seller_id:
        reviews[deal_id] = {
            "user_id": user_id,
            "username": users[user_id].get('username', 'unknown'),
            "seller_id": seller_id,
            "rating": rating,
            "text": text,
            "created_at": datetime.now().isoformat()
        }
        users[seller_id]["rating"] = (users[seller_id].get('rating', 0) + rating) / 2
        save()
        bot.send_message(user_id, "✅ Отзыв оставлен! Спасибо.", reply_markup=back())
        bot.send_message(seller_id, f"⭐ Новый отзыв!\n👤 @{users[user_id].get('username', 'unknown')}\n⭐ {rating}/5\n💬 {text}", reply_markup=back())

def handle_mailing(msg):
    user_id = get_uid(msg)
    text = msg.text
    sent = 0
    for uid in users:
        try:
            bot.send_message(uid, f"📨 Рассылка\n\n{text}")
            sent += 1
            time.sleep(0.05)
        except:
            pass
    bot.send_message(user_id, f"✅ Отправлено {sent} пользователям.", reply_markup=back())

def worker_cancel_deal_input(msg):
    user_id = get_uid(msg)
    deal_id = msg.text.strip()
    if deal_id not in deals:
        bot.send_message(user_id, "❌ Не найдена.", reply_markup=back())
        return
    d = deals[deal_id]
    if d['status'] in ['completed', 'cancelled']:
        bot.send_message(user_id, "❌ Уже завершена.", reply_markup=back())
        return
    d['status'] = 'cancelled'
    save()
    bot.send_message(user_id, f"✅ Сделка #{deal_id} отменена.", reply_markup=back())
    buyer_id = d.get('buyer')
    seller_id = d.get('seller')
    for uid in [buyer_id, seller_id]:
        if uid:
            bot.send_message(uid, f"❌ Сделка #{deal_id} отменена администратором.", reply_markup=back(), parse_mode='HTML')

def blacklist_add_input(msg):
    user_id = get_uid(msg)
    target_id = msg.text.strip()
    if not target_id.isdigit():
        bot.send_message(user_id, "❌ Введите ID.", reply_markup=back())
        return
    if target_id in blacklist:
        bot.send_message(user_id, "❌ Уже в ЧС.", reply_markup=back())
        return
    blacklist.append(target_id)
    save()
    bot.send_message(user_id, f"✅ {target_id} в ЧС.", reply_markup=back())

def blacklist_remove_input(msg):
    user_id = get_uid(msg)
    target_id = msg.text.strip()
    if not target_id.isdigit():
        bot.send_message(user_id, "❌ Введите ID.", reply_markup=back())
        return
    if target_id not in blacklist:
        bot.send_message(user_id, "❌ Не в ЧС.", reply_markup=back())
        return
    blacklist.remove(target_id)
    save()
    bot.send_message(user_id, f"✅ {target_id} удалён из ЧС.", reply_markup=back())

def handle_give_access(msg):
    user_id = get_uid(msg)
    target_id = msg.text.strip()
    if not target_id.isdigit():
        bot.send_message(user_id, "❌ Введите ID.", reply_markup=back())
        return
    if target_id not in users:
        bot.send_message(user_id, "❌ Пользователь не найден.", reply_markup=back())
        return
    workers[target_id] = True
    save()
    bot.send_message(user_id, f"✅ Доступ выдан {target_id}.", reply_markup=back())
    bot.send_message(target_id, "🔑 Вам выдан доступ к панели управления!", reply_markup=back())

@bot.message_handler(commands=['pay'])
def pay_command(msg):
    user_id = get_uid(msg)
    ensure_user(user_id)
    parts = msg.text.split()
    if len(parts) < 2:
        bot.reply_to(msg, "❌ /pay ID")
        return
    deal_id = parts[1]
    if deal_id not in deals:
        bot.reply_to(msg, "❌ Не найдена")
        return
    d = deals[deal_id]
    if d['status'] != 'waiting_payment':
        bot.reply_to(msg, "❌ Не ожидает оплаты")
        return
    if d.get('buyer') != user_id:
        bot.reply_to(msg, "❌ Вы не покупатель")
        return
    d['status'] = 'checking_payment'
    save()
    bot.reply_to(msg, "✅ На проверке")
    seller_id = d.get('seller')
    if seller_id:
        text = format_deal_short(deal_id)
        kb = get_deal_keyboard(deal_id, seller_id)
        bot.send_message(seller_id, f"🔔 Оплата #{deal_id}!\n🔍 Проверка...\n\n{text}", reply_markup=kb, parse_mode='HTML')
    def confirm_payment(deal_id):
        time.sleep(30)
        if deal_id in deals:
            d = deals[deal_id]
            if d['status'] == 'checking_payment':
                d['status'] = 'frozen'
                save()
                buyer_id = d.get('buyer')
                if buyer_id:
                    text = format_deal_short(deal_id)
                    kb = get_deal_keyboard(deal_id, buyer_id)
                    bot.send_message(buyer_id, f"✅ Платёж подтверждён!\n⏳ Ожидайте.\n\n{text}", reply_markup=kb, parse_mode='HTML')
                seller_id = d.get('seller')
                if seller_id:
                    text = format_deal_short(deal_id)
                    kb = get_deal_keyboard(deal_id, seller_id)
                    bot.send_message(seller_id, f"✅ Платёж подтверждён!\n✅ Нажмите «Подтвердить получение».\n\n{text}", reply_markup=kb, parse_mode='HTML')
    threading.Thread(target=confirm_payment, args=(deal_id,), daemon=True).start()

print("🚀 Бот запущен!")
bot.polling(none_stop=True)
