import random
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

# === Sozlamalar ===
API_TOKEN = "8245319536:AAE9ofodgLDe38G44wRoiucsAjiADh5jdjI"
ADMIN_ID = 786171158  # Admin ID
CHANNEL_LINK = "https://t.me/SamandarKadirov"

# === Database yaratish ===
conn = sqlite3.connect("slot.db")
cursor = conn.cursor()

# Yangilangan jadval strukturasi
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    attempts INTEGER DEFAULT 50,
    total_won INTEGER DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    best_win INTEGER DEFAULT 0,
    daily_bonus_claimed DATE,
    vip_level INTEGER DEFAULT 1,
    total_spent INTEGER DEFAULT 0,
    stars_balance INTEGER DEFAULT 0,
    daily_bonus_used BOOLEAN DEFAULT FALSE,
    max_daily_win INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    type TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    achievement_type TEXT,
    achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    action TEXT,
    target_user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Slot belgilar va ularning ehtimolliklari (mukammal algoritm)
symbols = {
    "💎": {"weight": 12, "value": 10, "rarity": "rare"},
    "77": {"weight": 8, "value": 20, "rarity": "rare"},
    "🍒": {"weight": 25, "value": 5, "rarity": "common"},
    "🍋": {"weight": 30, "value": 0, "rarity": "common"},
    "🎰": {"weight": 3, "value": 50, "rarity": "epic"},
    "⭐": {"weight": 15, "value": 15, "rarity": "rare"},
    "🔥": {"weight": 5, "value": 25, "rarity": "epic"}
}

# VIP darajalari
VIP_LEVELS = {
    1: {"min_spent": 0, "bonus_multiplier": 1.0, "daily_bonus": 5, "max_daily_win": 10},
    2: {"min_spent": 100, "bonus_multiplier": 1.2, "daily_bonus": 10, "max_daily_win": 15},
    3: {"min_spent": 500, "bonus_multiplier": 1.5, "daily_bonus": 20, "max_daily_win": 20},
    4: {"min_spent": 1000, "bonus_multiplier": 2.0, "daily_bonus": 50, "max_daily_win": 30},
    5: {"min_spent": 5000, "bonus_multiplier": 3.0, "daily_bonus": 100, "max_daily_win": 50}
}

# === DATABASE FUNKSIYALAR ===
def add_user(user_id, username=None, first_name=None):
    """Foydalanuvchini qo'shish"""
    try:
        # Yangi foydalanuvchilar uchun 50 ta urinish
        attempts = 50 if user_id != ADMIN_ID else 999999
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, attempts) 
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, attempts))
        conn.commit()
    except Exception as e:
        print(f"add_user xatoligi: {e}")

def add_attempts(user_id, count, reason="admin_gift"):
    """Urinish qo'shish"""
    try:
        add_user(user_id)
        cursor.execute("UPDATE users SET attempts = attempts + ? WHERE user_id = ?", (count, user_id))
        
        # Tranzaksiya qo'shish
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, 'attempts', ?)
        """, (user_id, count, reason))
        
        conn.commit()
    except Exception as e:
        print(f"add_attempts xatoligi: {e}")

def get_attempts(user_id):
    """Urinishlar sonini olish"""
    try:
        cursor.execute("SELECT attempts FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        # Admin uchun cheksiz, boshqalar uchun 50 ta
        return row[0] if row else (999999 if user_id == ADMIN_ID else 50)
    except Exception as e:
        print(f"get_attempts xatoligi: {e}")
        return 50

def decrease_attempt(user_id):
    """Urinish kamaytirish"""
    try:
        # Admin uchun urinish kamaymaydi
        if user_id == ADMIN_ID:
            return
        
        cursor.execute("UPDATE users SET attempts = attempts - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        print(f"decrease_attempt xatoligi: {e}")

def add_winnings(user_id, amount):
    """Yutuq qo'shish"""
    try:
        # Kundalik bonus cheklovini tekshirish
        cursor.execute("SELECT daily_bonus_used, max_daily_win, vip_level FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            daily_bonus_used = row[0] if row[0] else False
            max_daily_win = row[1] if row[1] else 10
            vip_level = row[2] if row[2] else 1
        else:
            daily_bonus_used = False
            max_daily_win = 10
            vip_level = 1
        
        # Agar kundalik bonus ishlatgan bo'lsa va yutuq chegaradan oshsa
        if daily_bonus_used and amount > max_daily_win:
            amount = max_daily_win
        
        cursor.execute("""
            UPDATE users 
            SET total_won = total_won + ?, 
                games_played = games_played + 1,
                best_win = MAX(best_win, ?),
                stars_balance = stars_balance + ?
            WHERE user_id = ?
        """, (amount, amount, amount, user_id))
        
        # Tranzaksiya qo'shish
        if amount > 0:
            cursor.execute("""
                INSERT INTO transactions (user_id, amount, type, description)
                VALUES (?, ?, 'winning', 'slot_game')
            """, (user_id, amount))
        
        conn.commit()
    except Exception as e:
        print(f"add_winnings xatoligi: {e}")

def get_stats(user_id):
    """Statistikani olish"""
    try:
        cursor.execute("""
            SELECT games_played, total_won, best_win, vip_level, total_spent, stars_balance, daily_bonus_used, max_daily_win
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return row if row else (0, 0, 0, 1, 0, 0, False, 10)
    except Exception as e:
        print(f"get_stats xatoligi: {e}")
        return (0, 0, 0, 1, 0, 0, False, 10)

def get_top_players(limit=10):
    """Eng zo'r o'yinchilarni olish"""
    try:
        cursor.execute("""
            SELECT user_id, username, first_name, total_won 
            FROM users 
            ORDER BY total_won DESC 
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()
    except Exception as e:
        print(f"get_top_players xatoligi: {e}")
        return []

def check_daily_bonus(user_id):
    """Kundalik bonus olinishini tekshirish"""
    try:
        cursor.execute("SELECT daily_bonus_claimed FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return True
        
        last_claimed = datetime.strptime(row[0], '%Y-%m-%d').date()
        return datetime.now().date() > last_claimed
    except Exception as e:
        print(f"check_daily_bonus xatoligi: {e}")
        return True

def claim_daily_bonus(user_id):
    """Kundalik bonus olish"""
    try:
        if not check_daily_bonus(user_id):
            return False, 0
        
        bonus_amount = 5  # Har kuni 5 ta bepul urinish
        add_attempts(user_id, bonus_amount, "daily_bonus")
        
        cursor.execute("""
            UPDATE users 
            SET daily_bonus_claimed = ?, daily_bonus_used = TRUE
            WHERE user_id = ?
        """, (datetime.now().date(), user_id))
        
        conn.commit()
        return True, bonus_amount
    except Exception as e:
        print(f"claim_daily_bonus xatoligi: {e}")
        return False, 0

def reset_daily_bonus():
    """Har kuni ertalab barcha foydalanuvchilar uchun kundalik bonus qayta ochiladi"""
    try:
        cursor.execute("UPDATE users SET daily_bonus_used = FALSE")
        conn.commit()
    except Exception as e:
        print(f"reset_daily_bonus xatoligi: {e}")

def add_achievement(user_id, achievement_type):
    """Yutuq qo'shish"""
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO achievements (user_id, achievement_type)
            VALUES (?, ?)
        """, (user_id, achievement_type))
        conn.commit()
    except Exception as e:
        print(f"add_achievement xatoligi: {e}")

def get_achievements(user_id):
    """Yutuqlarni olish"""
    try:
        cursor.execute("""
            SELECT achievement_type, achieved_at 
            FROM achievements 
            WHERE user_id = ?
            ORDER BY achieved_at DESC
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"get_achievements xatoligi: {e}")
        return []

def get_stars_balance(user_id):
    """Stars balansini olish - total_won dan olinadi"""
    try:
        cursor.execute("SELECT total_won FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception as e:
        print(f"get_stars_balance xatoligi: {e}")
        return 0

def add_stars_to_balance(user_id, amount):
    """Stars balansiga qo'shish"""
    try:
        cursor.execute("UPDATE users SET stars_balance = stars_balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
    except Exception as e:
        print(f"add_stars_to_balance xatoligi: {e}")

def log_admin_action(admin_id, action, target_user_id=None, details=None):
    """Admin harakatlarini log qilish"""
    try:
        cursor.execute("""
            INSERT INTO admin_logs (admin_id, action, target_user_id, details)
            VALUES (?, ?, ?, ?)
        """, (admin_id, action, target_user_id, details))
        conn.commit()
    except Exception as e:
        print(f"log_admin_action xatoligi: {e}")

# === SLOT FUNKSIYASI (30% Yutuq algoritmi) ===
def slot_generator(user_id):
    """Slot o'yini natijasini yaratish - 30% yutuq algoritmi"""
    try:
        # Foydalanuvchi ma'lumotlarini olish
        cursor.execute("SELECT vip_level, daily_bonus_used, total_spent FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            vip_level = 1
            daily_bonus_used = False
            total_spent = 0
        else:
            vip_level = row[0] or 1
            daily_bonus_used = row[1] or False
            total_spent = row[2] or 0
        
        # Foydalanuvchining sotib olgan urinishlarini hisoblash
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type LIKE '%payment%'", (user_id,))
        payment_row = cursor.fetchone()
        total_purchased_attempts = payment_row[0] if payment_row[0] else 0
        
        # 30% yutuq algoritmi - sotib olgan urinishlaridan faqat 30% yuta oladi
        max_win_percentage = 0.30  # 30%
        max_possible_win = total_purchased_attempts * max_win_percentage
        
        # Slot belgilari va ularning ehtimolligi (yutuqni cheklash uchun)
        symbols = {
            "🍋": 0.35,  # 35% ehtimollik - yo'qotish
            "🍊": 0.25,  # 25% ehtimollik - yo'qotish
            "🍇": 0.15,  # 15% ehtimollik - yo'qotish
            "🍒": 0.10,  # 10% ehtimollik - kichik yutuq
            "7️⃣": 0.08,  # 8% ehtimollik - o'rtacha yutuq
            "💎": 0.05,  # 5% ehtimollik - yaxshi yutuq
            "🔥": 0.015, # 1.5% ehtimollik - katta yutuq
            "🎰": 0.005  # 0.5% ehtimollik - jackpot
        }
        
        # 3 ta belgi tanlash
        result = []
        for _ in range(3):
            # Ehtimollik asosida belgi tanlash
            rand = random.random()
            cumulative = 0
            for symbol, prob in symbols.items():
                cumulative += prob
                if rand <= cumulative:
                    result.append(symbol)
                    break
        
        # Yutuq hisoblash (30% algoritmi asosida)
        prize = 0
        
        # Jackpot: 🎰🎰🎰 (eng kam ehtimollik)
        if result == ["🎰", "🎰", "🎰"]:
            prize = min(100, max_possible_win)
        # Katta yutuq: 7️⃣7️⃣7️⃣
        elif result == ["7️⃣", "7️⃣", "7️⃣"]:
            prize = min(50, max_possible_win)
        # Yaxshi yutuq: 💎💎💎
        elif result == ["💎", "💎", "💎"]:
            prize = min(30, max_possible_win)
        # O'rtacha yutuq: 🔥🔥
        elif result.count("🔥") >= 2:
            prize = min(25, max_possible_win)
        # Kichik yutuq: 7️⃣7️⃣
        elif result.count("7️⃣") >= 2:
            prize = min(20, max_possible_win)
        # Eng kichik yutuq: mevalar
        elif len(set(result)) == 3 and all(s in ["🍋", "🍊", "🍇", "🍒"] for s in result):
            prize = min(10, max_possible_win)
        
        # VIP daraja ko'paytiruvchisi
        vip_multiplier = VIP_LEVELS.get(vip_level, {}).get("bonus_multiplier", 1.0)
        
        # Kundalik bonus ishlatgan foydalanuvchilar uchun yutuq chegarasi
        if daily_bonus_used:
            max_win = 10  # Kundalik bonus ishlatganlar uchun max 10 Stars
            prize = min(prize, max_win)
        
        # VIP ko'paytiruvchisini qo'llash
        prize = int(prize * vip_multiplier)
        
        # Yakuniy tekshirish - 30% dan oshmasligi kerak
        final_max_win = max_possible_win * vip_multiplier
        prize = min(prize, final_max_win)
        
        return result, prize
        
    except Exception as e:
        print(f"slot_generator xatoligi: {e}")
        return ["🍋", "🍊", "🍇"], 0

# === KEYBOARD YARATISH ===
def create_main_keyboard():
    """Asosiy keyboard yaratish"""
    builder = InlineKeyboardBuilder()
    
    # Birinchi qator - 3 ta tugma
    builder.row(
        InlineKeyboardButton(text="🎰 O'ynash", callback_data="play"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="stats"),
        InlineKeyboardButton(text="🏆 Reyting", callback_data="top")
    )
    
    # Ikkinchi qator - 3 ta tugma
    builder.row(
        InlineKeyboardButton(text="🎁 Kundalik bonus", callback_data="daily_bonus"),
        InlineKeyboardButton(text="💎 VIP ma'lumot", callback_data="vip_info"),
        InlineKeyboardButton(text="🏅 Yutuqlar", callback_data="achievements")
    )
    
    # Uchinchi qator - 3 ta tugma
    builder.row(
        InlineKeyboardButton(text="💰 Stars hisobim", callback_data="stars_balance"),
        InlineKeyboardButton(text="🎯 O'yin qoidalari", callback_data="rules"),
        InlineKeyboardButton(text="🛒 Urinish sotib olish", callback_data="buy_attempts")
    )
    
    # To'rtinchi qator - 1 ta tugma
    builder.row(
        InlineKeyboardButton(text="💸 Stars chiqarib olish", callback_data="withdraw_stars")
    )
    
    return builder.as_markup()

def create_game_keyboard():
    """O'yin keyboard yaratish"""
    builder = InlineKeyboardBuilder()
    
    # Birinchi qator - 2 ta tugma
    builder.row(
        InlineKeyboardButton(text="▶️ Yana o'ynash", callback_data="play_again"),
        InlineKeyboardButton(text="📊 Statistikam", callback_data="my_stats")
    )
    
    # Ikkinchi qator - 2 ta tugma
    builder.row(
        InlineKeyboardButton(text="💰 Stars hisobim", callback_data="stars_balance"),
        InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="main_menu")
    )
    
    return builder.as_markup()

def create_admin_keyboard():
    """Admin keyboard yaratish"""
    builder = InlineKeyboardBuilder()
    
    # Birinchi qator - 3 ta tugma
    builder.row(
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users"),
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton(text="🎁 Urinish berish", callback_data="admin_give")
    )
    
    # Ikkinchi qator - 3 ta tugma
    builder.row(
        InlineKeyboardButton(text="🏆 Reyting", callback_data="admin_top"),
        InlineKeyboardButton(text="📝 Loglar", callback_data="admin_logs"),
        InlineKeyboardButton(text="🔄 Reset bonus", callback_data="admin_reset")
    )
    
    return builder.as_markup()

# === HANDLERLAR ===
@dp.message(Command("start"))
async def start_game(message: types.Message):
    """Start buyrug'i"""
    try:
        user = message.from_user
        add_user(user.id, user.username, user.first_name)
        
        # Admin uchun maxsus xabar
        if user.id == ADMIN_ID:
            welcome_text = f"""
🎰 Salom Admin {user.first_name}! 👑

🎮 Slot o'yin botiga xush kelibsiz!
🔧 Siz to'liq nazorat qilishingiz mumkin
📊 Barcha ma'lumotlarni ko'rishingiz mumkin

📋 Admin buyruqlari:
/admin — Admin panel
/give <user_id> <soni> — Urinish berish
/stats_admin — Bot statistikasi
/reset_bonus — Kundalik bonus qayta ochish
            """
            await message.answer(welcome_text, reply_markup=create_admin_keyboard())
            return
        
        welcome_text = f"""
🎰 *Slot O'yiniga Xush Kelibsiz!*

👋 Salom {user.first_name}!

🎮 *O'yin Xususiyatlari:*
• 🎰 Slot o'yini - stikerlar bilan
• 🎁 Kundalik 5 bepul urinish
• 💎 Stars yutib hisobga qo'shish
• 🏆 VIP daraja tizimi
• 🏅 Yutuqlar va reyting
• 💸 Stars chiqarib olish

💰 *To'lov Paketlari:*
• 25 Stars = 25 urinish
• 35 Stars = 35 urinish
• 55 Stars = 55 urinish
• 100 Stars = 100 urinish + 10% bonus
• 200 Stars = 200 urinish + 20% bonus
• 500 Stars = 500 urinish + 20% bonus

🎯 *O'yin Qoidalari:*
• 🎰🎰🎰 = 100 Stars (Jackpot!)
• 7️⃣7️⃣7️⃣ = 50 Stars
• 💎💎💎 = 30 Stars
• 🔥🔥 = 25 Stars
• 7️⃣7️⃣ = 20 Stars
• Mevalar = 10 Stars

📱 *Tugmalar orqali boshqaring:*
Quyidagi tugmalardan foydalaning ⬇️
        """
        
        await message.answer(welcome_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"start_game xatoligi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

@dp.message(Command("buy"))
async def buy_attempts(message: types.Message):
    """Urinish sotib olish buyrug'i"""
    try:
        await show_buy_attempts(message)
    except Exception as e:
        print(f"buy_attempts xatoligi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Admin panel"""
    try:
        if message.from_user.id != ADMIN_ID:
            await message.answer("❌ Sizda bu buyruq uchun ruxsat yo'q!")
            return
        
        admin_text = f"""
👑 Admin Panel

🎮 Slot o'yin boti boshqaruvi
📊 Barcha ma'lumotlarni ko'rishingiz mumkin
🔧 Foydalanuvchilarni boshqarishingiz mumkin

📋 Mavjud funksiyalar:
• Foydalanuvchilar ro'yxati
• Bot statistikasi  
• Urinish berish
• Reyting ko'rish
• Loglar
• Kundalik bonus qayta ochish
        """
        
        await message.answer(admin_text, reply_markup=create_admin_keyboard())
    except Exception as e:
        print(f"admin_panel xatoligi: {e}")

@dp.message(Command("play"))
async def play_slot(message: types.Message):
    """Slot o'yini"""
    try:
        user_id = message.from_user.id
        
        # Admin uchun cheksiz urinish
        if user_id == ADMIN_ID:
            attempts = 999999
        else:
            attempts = get_attempts(user_id)
        
        if attempts <= 0:
            await message.answer("❌ Sizda urinish qolmadi. Admin bilan bog'laning!")
            return

        result, prize = slot_generator(user_id)
        decrease_attempt(user_id)
        add_winnings(user_id, prize)

        # Natija xabarini yaratish (stikerlar bilan)
        res_str = " | ".join(result)
        
        # Yutuq xabarini yaratish
        if prize > 0:
            if prize >= 100:
                msg = f"🎰 Natija: {res_str}\n\n🏆 JACKPOT! Siz {prize} Stars yutdingiz! 🎉"
                add_achievement(user_id, "jackpot")
            elif prize >= 50:
                msg = f"🎰 Natija: {res_str}\n\n🎉 Katta yutuq! Siz {prize} Stars yutdingiz! ✨"
                add_achievement(user_id, "big_winner")
            elif prize >= 20:
                msg = f"🎰 Natija: {res_str}\n\n🎊 Yaxshi! Siz {prize} Stars yutdingiz! 🎯"
                add_achievement(user_id, "good_win")
            else:
                msg = f"🎰 Natija: {res_str}\n\n🎁 Tabriklaymiz! Siz {prize} Stars yutdingiz! 💎"
        else:
            msg = f"🎰 Natija: {res_str}\n\n😢 Afsus, yutug'ingiz yo'q. Keyingi safar omad! 🍀"

        # Qolgan urinishlar sonini hisoblash (decrease_attempt dan keyin)
        remaining_attempts = attempts - 1 if user_id != ADMIN_ID else 999999
        
        # Admin uchun cheksiz urinish ko'rsatish
        if user_id == ADMIN_ID:
            msg += f"\n\nQolgan urinishlar: ♾️ Cheksiz (Admin)"
        else:
            msg += f"\n\nQolgan urinishlar: {remaining_attempts}"
        msg += f"\n💎 Stars hisobingiz: {get_stars_balance(user_id)} Stars"

        await message.answer(msg, reply_markup=create_game_keyboard())
    except Exception as e:
        print(f"play_slot xatoligi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

async def play_slot_callback(callback: types.CallbackQuery):
    """Callback uchun slot o'yini - mavjud xabarni yangilaydi"""
    try:
        user_id = callback.from_user.id
        
        # Admin uchun cheksiz urinish
        if user_id == ADMIN_ID:
            attempts = 999999
        else:
            attempts = get_attempts(user_id)
        
        if attempts <= 0:
            await callback.message.edit_text("❌ Sizda urinish qolmadi. Admin bilan bog'laning!")
            return

        result, prize = slot_generator(user_id)
        decrease_attempt(user_id)
        add_winnings(user_id, prize)

        # Natija xabarini yaratish (stikerlar bilan)
        res_str = " | ".join(result)
        
        # Yutuq xabarini yaratish
        if prize > 0:
            if prize >= 100:
                msg = f"🎰 Natija: {res_str}\n\n🏆 JACKPOT! Siz {prize} Stars yutdingiz! 🎉"
                add_achievement(user_id, "jackpot")
            elif prize >= 50:
                msg = f"🎰 Natija: {res_str}\n\n🎉 Katta yutuq! Siz {prize} Stars yutdingiz! ✨"
                add_achievement(user_id, "big_winner")
            elif prize >= 20:
                msg = f"🎰 Natija: {res_str}\n\n🎊 Yaxshi! Siz {prize} Stars yutdingiz! 🎯"
                add_achievement(user_id, "good_win")
            else:
                msg = f"🎰 Natija: {res_str}\n\n🎁 Tabriklaymiz! Siz {prize} Stars yutdingiz! 💎"
        else:
            msg = f"🎰 Natija: {res_str}\n\n😢 Afsus, yutug'ingiz yo'q. Keyingi safar omad! 🍀"

        # Qolgan urinishlar sonini hisoblash (decrease_attempt dan keyin)
        remaining_attempts = attempts - 1 if user_id != ADMIN_ID else 999999
        
        # Admin uchun cheksiz urinish ko'rsatish
        if user_id == ADMIN_ID:
            msg += f"\n\nQolgan urinishlar: ♾️ Cheksiz (Admin)"
        else:
            msg += f"\n\nQolgan urinishlar: {remaining_attempts}"
        msg += f"\n💎 Stars hisobingiz: {get_stars_balance(user_id)} Stars"

        # Mavjud xabarni yangilash
        await callback.message.edit_text(msg, reply_markup=create_game_keyboard())
    except Exception as e:
        print(f"play_slot_callback xatoligi: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

async def show_buy_attempts(message: types.Message):
    """Urinish sotib olish ma'lumotini ko'rsatish"""
    try:
        buy_text = f"""
🛒 Urinish sotib olish

💡 Telegram Stars orqali xavfsiz to'lov:

📋 Paketlar:
• 25 urinish = 25 Stars
• 35 urinish = 35 Stars
• 55 urinish = 55 Stars
• 100 urinish = 100 Stars
• 200 urinish = 200 Stars
• 500 urinish = 500 Stars

🎁 Bonus:
• 100+ Stars = 10% bonus urinish
• 200+ Stars = 20% bonus urinish

💳 Xavfsiz to'lov Telegram Stars orqali
🔒 Shaxsiy ma'lumotlar talab qilinmaydi
        """
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🛒 25 urinish (25 Stars)", callback_data="buy_25"))
        builder.row(InlineKeyboardButton(text="🛒 35 urinish (35 Stars)", callback_data="buy_35"))
        builder.row(InlineKeyboardButton(text="🛒 55 urinish (55 Stars)", callback_data="buy_55"))
        builder.row(InlineKeyboardButton(text="🛒 100 urinish (100 Stars)", callback_data="buy_100"))
        builder.row(InlineKeyboardButton(text="🛒 200 urinish (200 Stars)", callback_data="buy_200"))
        builder.row(InlineKeyboardButton(text="🛒 500 urinish (500 Stars)", callback_data="buy_500"))
        builder.row(InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="main_menu"))
        
        await message.answer(buy_text, reply_markup=builder.as_markup())
    except Exception as e:
        print(f"show_buy_attempts xatoligi: {e}")

@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    """Statistikani ko'rsatish"""
    try:
        user_id = message.from_user.id
        games, total, best, vip_level, spent, balance, daily_bonus_used, max_daily_win = get_stats(user_id)
        achievements = get_achievements(user_id)
        
        stats_text = f"""
📊 Sizning statistikangiz:

🎮 O'yinlar soni: {games}
💰 Umumiy yutug'ingiz: {total} Stars
🏆 Eng katta yutuq: {best} Stars
💎 VIP daraja: {vip_level}
💳 Umumiy sarflangan: {spent} Stars
🏅 Yutuqlar soni: {len(achievements)}
💎 Stars hisobingiz: {balance} Stars

📈 O'rtacha yutuq: {total/games if games > 0 else 0:.1f} Stars
🎁 Kundalik bonus: {'✅ Ishlatilgan' if daily_bonus_used else '❌ Ishlatilmagan'}
🎯 Max kundalik yutuq: {max_daily_win} Stars
        """
        
        await message.answer(stats_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_stats xatoligi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

@dp.message(Command("balance"))
async def show_balance(message: types.Message):
    """Stars balansini ko'rsatish"""
    try:
        user_id = message.from_user.id
        balance = get_stars_balance(user_id)
        
        balance_text = f"""
💰 Stars hisobingiz:

💎 Jami Stars: {balance} Stars

💡 Ma'lumot:
• Yutgan Stars hisobingizda saqlanadi
• Stars orqali boshqa o'yinlarda foydalanishingiz mumkin
• Har kuni kundalik bonus olishingiz mumkin
• To'lov qilingan Stars ham hisobda ko'rsatiladi
        """
        
        await message.answer(balance_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_balance xatoligi: {e}")

async def show_withdraw_stars(message: types.Message):
    """Stars chiqarib olish sahifasini ko'rsatish"""
    try:
        user_id = message.from_user.id
        balance = get_stars_balance(user_id)
        
        withdraw_text = f"""
💸 Stars chiqarib olish

💎 Jami Stars: {balance} Stars

📋 Chiqarib olish shartlari:
• Minimal: 50 Stars
• Maksimal: 500 Stars
• Admin tasdiqlaydi
• 24 soat ichida yuboriladi

💡 Ma'lumot:
• Faqat yutgan Stars chiqarib olinadi
• To'lov qilingan Stars chiqarib olinmaydi
• Har bir so'rov alohida ko'rib chiqiladi
        """
        
        builder = InlineKeyboardBuilder()
        
        # Chiqarib olish miqdorlari
        if balance >= 50:
            builder.row(InlineKeyboardButton(text="💸 50 Stars", callback_data="withdraw_50"))
        if balance >= 100:
            builder.row(InlineKeyboardButton(text="💸 100 Stars", callback_data="withdraw_100"))
        if balance >= 200:
            builder.row(InlineKeyboardButton(text="💸 200 Stars", callback_data="withdraw_200"))
        if balance >= 300:
            builder.row(InlineKeyboardButton(text="💸 300 Stars", callback_data="withdraw_300"))
        if balance >= 400:
            builder.row(InlineKeyboardButton(text="💸 400 Stars", callback_data="withdraw_400"))
        if balance >= 500:
            builder.row(InlineKeyboardButton(text="💸 500 Stars", callback_data="withdraw_500"))
        
        builder.row(InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="main_menu"))
        
        await message.answer(withdraw_text, reply_markup=builder.as_markup())
    except Exception as e:
        print(f"show_withdraw_stars xatoligi: {e}")
        await message.answer("❌ Xatolik yuz berdi")

@dp.message(Command("rules"))
async def show_rules(message: types.Message):
    """O'yin qoidalarini ko'rsatish"""
    try:
        rules_text = f"""
🎮 Slot O'yin Qoidalari:

🎰 Slot belgilari va yutuqlar:
• 🎰🎰 = 50 Stars (Jackpot!)
• 77 77 77 = 100 Stars
• 💎💎💎 = 30 Stars  
• 🔥🔥 = 25 Stars
• 77 77 = 20 Stars
• 💎💎 = 10 Stars
• 🍒🍒🍒 = 5 Stars
• ⭐⭐ = 15 Stars

🎁 Kundalik bonus:
• Har kuni 5 ta bepul urinish
• Kundalik bonus ishlatganlar {VIP_LEVELS[1]['max_daily_win']} Starsdan ko'p yuta olmaydi
• VIP darajaga qarab cheklov oshadi

💎 VIP darajalari:
• Bronze (1) - x1.0, max {VIP_LEVELS[1]['max_daily_win']} Stars
• Silver (2) - x1.2, max {VIP_LEVELS[2]['max_daily_win']} Stars  
• Gold (3) - x1.5, max {VIP_LEVELS[3]['max_daily_win']} Stars
• Platinum (4) - x2.0, max {VIP_LEVELS[4]['max_daily_win']} Stars
• Diamond (5) - x3.0, max {VIP_LEVELS[5]['max_daily_win']} Stars
        """
        
        await message.answer(rules_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_rules xatoligi: {e}")

@dp.message(Command("top"))
async def show_top(message: types.Message):
    """Reytingni ko'rsatish"""
    try:
        top_players = get_top_players()
        text = "🏆 Eng zo'r o'yinchilar:\n\n"
        
        for i, (user_id, username, first_name, total_won) in enumerate(top_players, start=1):
            name = username or first_name or f"User{user_id}"
            text += f"{i}. {name} — {total_won} Stars\n"
        
        await message.answer(text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_top xatoligi: {e}")

@dp.message(Command("vip"))
async def show_vip_info(message: types.Message):
    """VIP ma'lumotini ko'rsatish"""
    try:
        user_id = message.from_user.id
        games, total, best, vip_level, spent, balance, daily_bonus_used, max_daily_win = get_stats(user_id)
        
        current_vip = VIP_LEVELS[vip_level]
        next_level = vip_level + 1 if vip_level < 5 else 5
        next_vip = VIP_LEVELS.get(next_level, current_vip)
        
        vip_text = f"""
💎 VIP Ma'lumot

🎯 Hozirgi daraja: {vip_level}
💰 Ko'paytiruvchi: x{current_vip['bonus_multiplier']}
🎁 Kundalik bonus: {current_vip['daily_bonus']} urinish
🎯 Max kundalik yutuq: {current_vip['max_daily_win']} Stars

📊 Progress:
💳 Sarflangan: {spent} Stars
🎯 Keyingi daraja: {next_level}
📈 Kerakli: {next_vip['min_spent'] - spent} Stars

🎁 VIP afzalliklari:
• Yuqori yutuq ko'paytiruvchi
• Katta kundalik bonus
• Yuqori max kundalik yutuq
• Maxsus yutuqlar
        """
        
        await message.answer(vip_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_vip_info xatoligi: {e}")

@dp.message(Command("achievements"))
async def show_achievements(message: types.Message):
    """Yutuqlarni ko'rsatish"""
    try:
        user_id = message.from_user.id
        achievements = get_achievements(user_id)
        
        if not achievements:
            await message.answer("🏅 Sizda hali yutuqlar yo'q. O'ynashni davom eting!", reply_markup=create_main_keyboard())
            return
        
        achievement_names = {
            "big_winner": "🏆 Katta yutuq",
            "lucky_streak": "🍀 Omadli seriya",
            "first_win": "🎉 Birinchi yutuq",
            "vip_member": "💎 VIP a'zo",
            "jackpot": "🎰 Jackpot!",
            "good_win": "🎊 Yaxshi yutuq"
        }
        
        text = "🏅 Sizning yutuqlaringiz:\n\n"
        for achievement_type, achieved_at in achievements:
            name = achievement_names.get(achievement_type, achievement_type)
            date = datetime.strptime(achieved_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            text += f"• {name} - {date}\n"
        
        await message.answer(text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_achievements xatoligi: {e}")

# === CALLBACK HANDLERLAR ===
@dp.callback_query(F.data == "play")
async def callback_play(callback: types.CallbackQuery):
    """O'ynash callback"""
    try:
        await play_slot_callback(callback)
        await callback.answer()
    except Exception as e:
        print(f"callback_play xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "play_again")
async def callback_play_again(callback: types.CallbackQuery):
    """Yana o'ynash callback"""
    try:
        await play_slot_callback(callback)
        await callback.answer()
    except Exception as e:
        print(f"callback_play_again xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "stats")
async def callback_stats(callback: types.CallbackQuery):
    """Statistika callback"""
    try:
        await show_stats(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_stats xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "my_stats")
async def callback_my_stats(callback: types.CallbackQuery):
    """Shaxsiy statistika callback"""
    try:
        await show_stats(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_my_stats xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "top")
async def callback_top(callback: types.CallbackQuery):
    """Reyting callback"""
    try:
        await show_top(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_top xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "vip_info")
async def callback_vip_info(callback: types.CallbackQuery):
    """VIP ma'lumot callback"""
    try:
        await show_vip_info(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_vip_info xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "achievements")
async def callback_achievements(callback: types.CallbackQuery):
    """Yutuqlar callback"""
    try:
        await show_achievements(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_achievements xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: types.CallbackQuery):
    """Bosh sahifa callback"""
    try:
        await start_game(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_main_menu xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "daily_bonus")
async def callback_daily_bonus(callback: types.CallbackQuery):
    """Kundalik bonus callback"""
    try:
        user_id = callback.from_user.id
        success, amount = claim_daily_bonus(user_id)
        
        if success:
            await callback.message.answer(f"🎁 Kundalik bonus qabul qilindi! +{amount} urinish")
        else:
            await callback.message.answer("❌ Kundalik bonus allaqachon olingan. Ertaga qaytib keling!")
        
        await callback.answer()
    except Exception as e:
        print(f"callback_daily_bonus xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "stars_balance")
async def callback_stars_balance(callback: types.CallbackQuery):
    """Stars balansi callback"""
    try:
        await show_balance(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_stars_balance xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "rules")
async def callback_rules(callback: types.CallbackQuery):
    """O'yin qoidalari callback"""
    try:
        await show_rules(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_rules xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "buy_attempts")
async def callback_buy_attempts(callback: types.CallbackQuery):
    """Urinish sotib olish callback"""
    try:
        await show_buy_attempts(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_buy_attempts xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "withdraw_stars")
async def callback_withdraw_stars(callback: types.CallbackQuery):
    """Stars chiqarib olish callback"""
    try:
        await show_withdraw_stars(callback.message)
        await callback.answer()
    except Exception as e:
        print(f"callback_withdraw_stars xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data.startswith("buy_"))
async def callback_buy_package(callback: types.CallbackQuery):
    """To'lov paketini tanlash"""
    try:
        package = callback.data.split("_")[1]
        packages = {
            "25": {"attempts": 25, "price": 25, "title": "25 urinish"},
            "35": {"attempts": 35, "price": 35, "title": "35 urinish"},
            "55": {"attempts": 55, "price": 55, "title": "55 urinish"},
            "100": {"attempts": 100, "price": 100, "title": "100 urinish"},
            "200": {"attempts": 200, "price": 200, "title": "200 urinish"},
            "500": {"attempts": 500, "price": 500, "title": "500 urinish"}
        }
        
        if package not in packages:
            await callback.answer("❌ Noto'g'ri paket!")
            return
        
        pkg = packages[package]
        
        # Bonus hisoblash
        bonus = 0
        if pkg["price"] >= 200:
            bonus = int(pkg["attempts"] * 0.2)  # 20% bonus
        elif pkg["price"] >= 100:
            bonus = int(pkg["attempts"] * 0.1)  # 10% bonus
        
        total_attempts = pkg["attempts"] + bonus
        
        # Telegram Stars invoice yaratish
        prices = [LabeledPrice(label=pkg["title"], amount=pkg["price"])]  # Stars directly
        
        # Telegram Stars to'lovini kanalga yuborish
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"🎰 {pkg['title']} paketi",
            description=f"Slot o'yini uchun {pkg['attempts']} urinish" + (f" + {bonus} bonus" if bonus > 0 else ""),
            payload=f"attempts_{package}_{callback.from_user.id}",
            provider_token="",  # Digital goods uchun bo'sh
            currency="XTR",  # Telegram Stars
            prices=prices,
            start_parameter=f"attempts_{package}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False
        )
        
        await callback.answer()
        
    except Exception as e:
        print(f"callback_buy_package xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# === WITHDRAW STARS HANDLERS ===
@dp.callback_query(F.data.startswith("withdraw_"))
async def callback_withdraw_amount(callback: types.CallbackQuery):
    """Stars chiqarib olish miqdori"""
    try:
        amount = int(callback.data.split("_")[1])
        user_id = callback.from_user.id
        balance = get_stars_balance(user_id)
        
        # Tekshirishlar
        if amount < 50 or amount > 500:
            await callback.answer("❌ Noto'g'ri miqdor! (50-500 Stars)")
            return
        
        if balance < amount:
            await callback.answer("❌ Hisobingizda yetarli Stars yo'q!")
            return
        
        # Admin ga xabar yuborish
        admin_text = f"""
💸 Yangi Stars chiqarib olish so'rovi!

👤 Foydalanuvchi: {callback.from_user.first_name} (@{callback.from_user.username or 'username yo\'q'})
🆔 User ID: {user_id}
💎 So'ralgan miqdor: {amount} Stars
💎 Jami balans: {balance} Stars

⏰ Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        """
        
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_withdraw_{user_id}_{amount}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_withdraw_{user_id}_{amount}")
            ).as_markup()
        )
        
        # Foydalanuvchiga xabar
        await callback.message.edit_text(
            f"✅ Chiqarib olish so'rovi yuborildi!\n\n💎 Miqdor: {amount} Stars\n📢 Admin tasdiqlashini kuting...",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="🏠 Bosh sahifa", callback_data="main_menu")
            ).as_markup()
        )
        
        await callback.answer("✅ So'rov yuborildi!")
        
    except Exception as e:
        print(f"callback_withdraw_amount xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# === ADMIN WITHDRAW CONFIRMATION HANDLERS ===
@dp.callback_query(F.data.startswith("confirm_withdraw_"))
async def confirm_withdraw(callback: types.CallbackQuery):
    """Stars chiqarib olishni tasdiqlash"""
    try:
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Sizda ruxsat yo'q!")
            return
        
        # Payload ni parse qilish: confirm_withdraw_user_id_amount
        parts = callback.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        
        # Balansni tekshirish
        balance = get_stars_balance(user_id)
        if balance < amount:
            await callback.message.edit_text(
                f"❌ Foydalanuvchining balansi yetarli emas!\n\n👤 User ID: {user_id}\n💎 So'ralgan: {amount} Stars\n💎 Mavjud: {balance} Stars"
            )
            await callback.answer("❌ Balans yetarli emas!")
            return
        
        # Stars ni chiqarib olish
        cursor.execute("UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        
        # Log qilish
        log_admin_action(ADMIN_ID, "withdraw_confirmed", user_id, f"Withdrew {amount} Stars")
        
        # Foydalanuvchiga xabar
        success_msg = f"""
✅ Stars chiqarib olish tasdiqlandi!

💎 Chiqarib olingan: {amount} Stars
💎 Qolgan balans: {balance - amount} Stars

📢 Stars 24 soat ichida yuboriladi!
        """
        
        await bot.send_message(user_id, success_msg, reply_markup=create_main_keyboard())
        
        # Admin xabarini yangilash
        await callback.message.edit_text(
            f"✅ Stars chiqarib olish tasdiqlandi!\n\n👤 Foydalanuvchi: {user_id}\n💎 Miqdor: {amount} Stars\n📊 Qolgan: {balance - amount} Stars"
        )
        
        await callback.answer("✅ Tasdiqlandi!")
        
    except Exception as e:
        print(f"confirm_withdraw xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data.startswith("reject_withdraw_"))
async def reject_withdraw(callback: types.CallbackQuery):
    """Stars chiqarib olishni rad etish"""
    try:
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Sizda ruxsat yo'q!")
            return
        
        # Payload ni parse qilish: reject_withdraw_user_id_amount
        parts = callback.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        
        # Foydalanuvchiga xabar
        await bot.send_message(user_id, f"❌ Stars chiqarib olish rad etildi.\n\n💎 Miqdor: {amount} Stars\n📢 Sabab: Admin tomonidan rad etildi.")
        
        # Admin xabarini yangilash
        await callback.message.edit_text(
            f"❌ Stars chiqarib olish rad etildi!\n\n👤 Foydalanuvchi: {user_id}\n💎 Miqdor: {amount} Stars"
        )
        
        await callback.answer("❌ Rad etildi!")
        
    except Exception as e:
        print(f"reject_withdraw xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# === TELEGRAM STARS PAYMENT HANDLERS ===

# === TELEGRAM STARS PAYMENT HANDLERS ===
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout: PreCheckoutQuery):
    """Pre-checkout tekshirish"""
    try:
        await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)
    except Exception as e:
        print(f"pre_checkout_query xatoligi: {e}")
        await bot.answer_pre_checkout_query(
            pre_checkout.id,
            ok=False,
            error_message="To'lovni qayta ishlashda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."
        )

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Muvaffaqiyatli to'lovni qayta ishlash"""
    try:
        payment_info = message.successful_payment
        payload = payment_info.invoice_payload
        
        # Payload ni parse qilish: attempts_package_user_id
        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "attempts":
            await message.answer("❌ To'lov ma'lumotlari noto'g'ri!")
            return
        
        package = parts[1]
        user_id = int(parts[2])
        
        packages = {
            "25": {"attempts": 25, "price": 25},
            "35": {"attempts": 35, "price": 35},
            "55": {"attempts": 55, "price": 55},
            "100": {"attempts": 100, "price": 100},
            "200": {"attempts": 200, "price": 200},
            "500": {"attempts": 500, "price": 500}
        }
        
        if package not in packages:
            await message.answer("❌ Noto'g'ri paket!")
            return
        
        pkg = packages[package]
        
        # Bonus hisoblash
        bonus = 0
        if pkg["price"] >= 200:
            bonus = int(pkg["attempts"] * 0.2)  # 20% bonus
        elif pkg["price"] >= 100:
            bonus = int(pkg["attempts"] * 0.1)  # 10% bonus
        
        total_attempts = pkg["attempts"] + bonus
        
        # Urinish qo'shish
        add_attempts(user_id, total_attempts, f"telegram_stars_payment_{pkg['price']}")
        
        # VIP darajani yangilash
        cursor.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?", (pkg["price"], user_id))
        conn.commit()
        
        # VIP darajani tekshirish va yangilash
        cursor.execute("SELECT total_spent FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            total_spent = row[0]
            new_vip_level = 1
            for level, data in VIP_LEVELS.items():
                if total_spent >= data["min_spent"]:
                    new_vip_level = level
            
            cursor.execute("UPDATE users SET vip_level = ? WHERE user_id = ?", (new_vip_level, user_id))
            conn.commit()
        
        # Log qilish
        log_admin_action(ADMIN_ID, "telegram_stars_payment", user_id, 
                        f"Payment: {pkg['price']} Stars, Added: {total_attempts} attempts")
        
        # Foydalanuvchiga xabar
        success_msg = f"""
✅ To'lov muvaffaqiyatli amalga oshirildi!

🎰 Paket: {pkg['attempts']} urinish
💰 To'lov: {pkg['price']} Stars
🎁 Bonus: {bonus} urinish
📊 Jami: {total_attempts} urinish qo'shildi
💎 VIP daraja: {new_vip_level}

🎮 Endi o'ynashni boshlashingiz mumkin!
        """
        
        await message.answer(success_msg, reply_markup=create_main_keyboard())
        
    except Exception as e:
        print(f"successful_payment xatoligi: {e}")
        await message.answer("❌ To'lovni qayta ishlashda xatolik yuz berdi. Admin bilan bog'laning.")

# === ADMIN CALLBACK HANDLAR ===
@dp.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: types.CallbackQuery):
    """Admin foydalanuvchilar callback"""
    try:
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Sizda ruxsat yo'q!")
            return
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT user_id, username, first_name, attempts, total_won FROM users ORDER BY total_won DESC LIMIT 10")
        top_users = cursor.fetchall()
        
        text = f"👥 Foydalanuvchilar ({total_users} ta):\n\n"
        for i, (user_id, username, first_name, attempts, total_won) in enumerate(top_users, start=1):
            name = username or first_name or f"User{user_id}"
            text += f"{i}. {name} - {total_won} Stars ({attempts} urinish)\n"
        
        await callback.message.answer(text, reply_markup=create_admin_keyboard())
        await callback.answer()
    except Exception as e:
        print(f"callback_admin_users xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: types.CallbackQuery):
    """Admin statistika callback"""
    try:
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Sizda ruxsat yo'q!")
            return
        
        cursor.execute("SELECT COUNT(*), SUM(total_won), SUM(total_spent), SUM(stars_balance) FROM users")
        stats = cursor.fetchone()
        
        text = f"""
📊 Bot statistikasi:

👥 Jami foydalanuvchilar: {stats[0]}
💰 Umumiy yutug'lar: {stats[1] or 0} Stars
💳 Umumiy to'lovlar: {stats[2] or 0} Stars
💎 Umumiy Stars hisoblar: {stats[3] or 0} Stars
        """
        
        await callback.message.answer(text, reply_markup=create_admin_keyboard())
        await callback.answer()
    except Exception as e:
        print(f"callback_admin_stats xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

@dp.callback_query(F.data == "admin_reset")
async def callback_admin_reset(callback: types.CallbackQuery):
    """Admin reset bonus callback"""
    try:
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Sizda ruxsat yo'q!")
            return
        
        reset_daily_bonus()
        log_admin_action(ADMIN_ID, "reset_daily_bonus")
        
        await callback.message.answer("✅ Kundalik bonus barcha foydalanuvchilar uchun qayta ochildi!", reply_markup=create_admin_keyboard())
        await callback.answer()
    except Exception as e:
        print(f"callback_admin_reset xatoligi: {e}")
        await callback.answer("❌ Xatolik yuz berdi")

# === ADMIN FUNKSIYALAR ===
@dp.message(Command("give"))
async def admin_give(message: types.Message):
    """Admin urinish berish"""
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Foydalanish: /give <user_id> <soni>")
            return
        
        uid, attempts = int(parts[1]), int(parts[2])
        add_attempts(uid, attempts, "admin_gift")
        log_admin_action(ADMIN_ID, "give_attempts", uid, f"Gave {attempts} attempts")
        await message.answer(f"✅ {uid} foydalanuvchisiga {attempts} urinish qo'shildi.")
    except Exception as e:
        print(f"admin_give xatoligi: {e}")
        await message.answer("❌ Foydalanish: /give <user_id> <soni>")

@dp.message(Command("pay"))
async def admin_pay(message: types.Message):
    """Admin to'lovni tasdiqlash va urinish qo'shish"""
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Foydalanish: /pay <user_id> <stars_amount>")
            return
        
        uid, stars_amount = int(parts[1]), int(parts[2])
        
        # Bonus hisoblash
        bonus = 0
        if stars_amount >= 100:
            bonus = int(stars_amount * 0.2)  # 20% bonus
        elif stars_amount >= 50:
            bonus = int(stars_amount * 0.1)  # 10% bonus
        
        total_attempts = stars_amount + bonus
        
        # Urinish qo'shish
        add_attempts(uid, total_attempts, f"payment_{stars_amount}_stars")
        
        # VIP darajani yangilash
        cursor.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?", (stars_amount, uid))
        conn.commit()
        
        # VIP darajani tekshirish va yangilash
        cursor.execute("SELECT total_spent FROM users WHERE user_id = ?", (uid,))
        row = cursor.fetchone()
        if row:
            total_spent = row[0]
            new_vip_level = 1
            for level, data in VIP_LEVELS.items():
                if total_spent >= data["min_spent"]:
                    new_vip_level = level
            
            cursor.execute("UPDATE users SET vip_level = ? WHERE user_id = ?", (new_vip_level, uid))
            conn.commit()
        
        log_admin_action(ADMIN_ID, "payment_confirmed", uid, f"Payment: {stars_amount} Stars, Added: {total_attempts} attempts")
        
        await message.answer(f"""
✅ To'lov tasdiqlandi!

👤 Foydalanuvchi: {uid}
💰 To'lov: {stars_amount} Stars
🎁 Bonus: {bonus} urinish
📊 Jami: {total_attempts} urinish qo'shildi
💎 VIP daraja: {new_vip_level}
        """)
    except Exception as e:
        print(f"admin_pay xatoligi: {e}")
        await message.answer("❌ Foydalanish: /pay <user_id> <stars_amount>")

@dp.message(Command("stats_admin"))
async def admin_stats(message: types.Message):
    """Admin statistika"""
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        cursor.execute("SELECT COUNT(*), SUM(total_won), SUM(total_spent), SUM(stars_balance) FROM users")
        stats = cursor.fetchone()
        
        await message.answer(f"""
📊 Bot statistikasi:

👥 Jami foydalanuvchilar: {stats[0]}
💰 Umumiy yutug'lar: {stats[1] or 0} Stars
💳 Umumiy to'lovlar: {stats[2] or 0} Stars
💎 Umumiy Stars hisoblar: {stats[3] or 0} Stars
        """)
    except Exception as e:
        print(f"admin_stats xatoligi: {e}")

@dp.message(Command("reset_bonus"))
async def admin_reset_bonus(message: types.Message):
    """Admin reset bonus"""
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        reset_daily_bonus()
        log_admin_action(ADMIN_ID, "reset_daily_bonus")
        await message.answer("✅ Kundalik bonus barcha foydalanuvchilar uchun qayta ochildi!")
    except Exception as e:
        print(f"admin_reset_bonus xatoligi: {e}")

async def main():
    """Asosiy funksiya"""
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"main xatoligi: {e}")

if __name__ == "__main__":
    asyncio.run(main())
