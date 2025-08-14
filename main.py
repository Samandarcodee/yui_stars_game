import random
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

# === Sozlamalar ===
API_TOKEN = "7630434422:AAGHtlX2PavWMr7zpPpzLV3Pit7MV-IEmY8"
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
    """Stars balansini olish"""
    try:
        cursor.execute("SELECT stars_balance FROM users WHERE user_id = ?", (user_id,))
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

# === SLOT FUNKSIYASI (Mukammal algoritm) ===
def slot_generator(user_id):
    """Slot o'yini natijasini yaratish"""
    try:
        # VIP darajasini olish
        cursor.execute("SELECT vip_level, daily_bonus_used FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            vip_level = row[0] if row[0] else 1
            daily_bonus_used = row[1] if row[1] else False
        else:
            vip_level = 1
            daily_bonus_used = False
            
        multiplier = VIP_LEVELS[vip_level]["bonus_multiplier"]
        
        # Belgilarni tanlash (mukammal algoritm)
        symbol_list = []
        for symbol, data in symbols.items():
            symbol_list.extend([symbol] * data["weight"])
        
        result = [random.choice(symbol_list) for _ in range(3)]
        
        # Yutuqni hisoblash (mukammal algoritm)
        prize = 0
        symbol_counts = {}
        for symbol in result:
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        # Yutuq qoidalari (mukammal)
        if symbol_counts.get("🎰", 0) >= 2:
            prize = 50
        elif symbol_counts.get("77", 0) == 3:
            prize = 100
        elif symbol_counts.get("💎", 0) == 3:
            prize = 30
        elif symbol_counts.get("🔥", 0) >= 2:
            prize = 25
        elif symbol_counts.get("77", 0) == 2:
            prize = 20
        elif symbol_counts.get("💎", 0) == 2:
            prize = 10
        elif symbol_counts.get("🍒", 0) == 3:
            prize = 5
        elif symbol_counts.get("⭐", 0) >= 2:
            prize = 15
        
        # Kundalik bonus cheklovi
        if daily_bonus_used:
            max_win = VIP_LEVELS[vip_level]["max_daily_win"]
            if prize > max_win:
                prize = max_win
        
        # VIP ko'paytiruvchi
        prize = int(prize * multiplier)
        
        return result, prize
    except Exception as e:
        print(f"slot_generator xatoligi: {e}")
        return ["🍒", "🍒", "🍒"], 0

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
    
    # Uchinchi qator - 2 ta tugma
    builder.row(
        InlineKeyboardButton(text="💰 Stars hisobim", callback_data="stars_balance"),
        InlineKeyboardButton(text="🎯 O'yin qoidalari", callback_data="rules")
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
🎰 Salom {user.first_name}!

🎮 Slot o'yiniga xush kelibsiz!
🎁 Har kuni 5 ta bepul urinish oling
🏆 VIP darajangizni oshiring
💰 Stars yutib hisobingizga qo'shiling

📋 Buyruqlar:
/play — o'ynash
/stats — statistika
/top — reyting
/vip — VIP ma'lumot
/achievements — yutuqlar
/balance — Stars hisobim
/rules — o'yin qoidalari
        """
        
        await message.answer(welcome_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"start_game xatoligi: {e}")
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
        msg += f"\n💰 Stars hisobingiz: {get_stars_balance(user_id)}"

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
        msg += f"\n💰 Stars hisobingiz: {get_stars_balance(user_id)}"

        # Mavjud xabarni yangilash
        await callback.message.edit_text(msg, reply_markup=create_game_keyboard())
    except Exception as e:
        print(f"play_slot_callback xatoligi: {e}")
        await callback.message.edit_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

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
        """
        
        await message.answer(balance_text, reply_markup=create_main_keyboard())
    except Exception as e:
        print(f"show_balance xatoligi: {e}")

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

# === ADMIN CALLBACK HANDLERLAR ===
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
