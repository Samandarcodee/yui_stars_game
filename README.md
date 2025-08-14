# 🎰 YUI Stars Game Bot

Telegram slot o'yin boti - professional va funksional o'yin platformasi.

## 🌟 Xususiyatlar

### 🎮 O'yin xususiyatlari
- **Slot o'yini** - 3 ta belgi kombinatsiyasi
- **Mukammal algoritm** - balanslangan ehtimolliklar
- **VIP tizimi** - 5 ta daraja (Bronze, Silver, Gold, Platinum, Diamond)
- **Yutuqlar tizimi** - turli xil yutuqlar va achievementlar
- **Stars balansi** - yutgan Stars hisobda saqlanadi

### 🎁 Bonus tizimi
- **Kundalik bonus** - har kuni 5 ta bepul urinish
- **VIP darajalar** - yuqori darajada ko'proq bonus
- **Kundalik cheklov** - bonus ishlatganlar uchun max yutuq cheklovi

### 👑 Admin paneli
- **To'liq nazorat** - barcha foydalanuvchilarni boshqarish
- **Statistika** - bot ma'lumotlarini ko'rish
- **Urinish berish** - foydalanuvchilarga urinish qo'shish
- **Loglar** - barcha harakatlarni kuzatish

## 🎯 O'yin qoidalari

### Slot belgilari va yutuqlar:
- 🎰🎰 = 50 Stars (Jackpot!)
- 77 77 77 = 100 Stars
- 💎💎💎 = 30 Stars  
- 🔥🔥 = 25 Stars
- 77 77 = 20 Stars
- 💎💎 = 10 Stars
- 🍒🍒🍒 = 5 Stars
- ⭐⭐ = 15 Stars

### VIP darajalari:
- **Bronze (1)** - x1.0, max 10 Stars
- **Silver (2)** - x1.2, max 15 Stars  
- **Gold (3)** - x1.5, max 20 Stars
- **Platinum (4)** - x2.0, max 30 Stars
- **Diamond (5)** - x3.0, max 50 Stars

## 🚀 O'rnatish

### Talablar
```bash
pip install -r requirements.txt
```

### Sozlash
1. `main.py` faylida bot tokenini o'zgartiring
2. Admin ID ni o'zgartiring
3. Botni ishga tushiring

```bash
python main.py
```

## 📋 Buyruqlar

### Foydalanuvchilar uchun:
- `/start` - Botni ishga tushirish
- `/play` - O'ynash
- `/stats` - Statistika
- `/top` - Reyting
- `/vip` - VIP ma'lumot
- `/achievements` - Yutuqlar
- `/balance` - Stars hisobim
- `/rules` - O'yin qoidalari

### Admin uchun:
- `/admin` - Admin panel
- `/give <user_id> <soni>` - Urinish berish
- `/stats_admin` - Bot statistikasi
- `/reset_bonus` - Kundalik bonus qayta ochish

## 🛠 Texnik ma'lumotlar

- **Python 3.8+**
- **Aiogram 3.4.1**
- **SQLite3** - ma'lumotlar bazasi
- **Telegram Bot API**

## 📊 Database strukturasi

### users jadvali:
- user_id (PRIMARY KEY)
- username, first_name
- attempts, total_won, games_played
- best_win, vip_level, total_spent
- stars_balance, daily_bonus_used
- max_daily_win, created_at

### transactions jadvali:
- id (PRIMARY KEY)
- user_id, amount, type, description
- created_at

### achievements jadvali:
- id (PRIMARY KEY)
- user_id, achievement_type
- achieved_at

### admin_logs jadvali:
- id (PRIMARY KEY)
- admin_id, action, target_user_id
- details, created_at

## 🎨 Xususiyatlar

- **Mukammal algoritm** - balanslangan ehtimolliklar
- **Xavfsizlik** - barcha harakatlar loglanadi
- **Moslashuvchanlik** - oson sozlash va o'zgartirish
- **Professional UI** - chiroyli va tushunarli interfeys
- **To'liq funksionallik** - barcha kerakli funksiyalar

## 📞 Aloqa

Bot yaratuvchisi: @SamandarKadirov

---

⭐ Ushbu loyha professional slot o'yin boti bo'lib, barcha zamonaviy talablarga javob beradi!
