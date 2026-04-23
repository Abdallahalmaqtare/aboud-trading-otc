# 🤖 Aboud Trading Bot OTC v1.0

بوت تداول تلقائي على أزواج **OTC في Pocket Option** — فريم **15 دقيقة**.

---

## 📋 الفرق عن النسخة الأصلية

| الميزة | النسخة الأصلية | النسخة OTC |
|--------|---------------|------------|
| الأزواج | EUR/USD, GBP/USD (حقيقي) | EUR/USD OTC, GBP/USD OTC |
| مصدر البيانات | TradingView | Pocket Option WebSocket API |
| التحليل | Pine Script + Webhook | تلقائي داخلي (Python) |
| التوقيت | ساعات السوق | 24/7 (OTC لا يغلق) |
| نتائج الصفقات | TradingView webhook | Pocket Option API مباشرة |
| الاتصال | لا يحتاج | SSID من المتصفح |

---

## 🚀 طريقة التشغيل

### الخطوة 1: الحصول على SSID من Pocket Option

> هذه الخطوة الأهم — بدونها لن يعمل التحليل التلقائي.

1. افتح **pocketoption.com** في Chrome أو Firefox
2. **سجّل الدخول** إلى حسابك
3. اضغط **F12** لفتح أدوات المطور
4. انتقل إلى تبويب **Network** (الشبكة)
5. في مربع الفلتر، اكتب: **WS** (أو WebSocket)
6. أعد تحميل الصفحة بالضغط على **F5**
7. ستظهر اتصالات WebSocket — انقر على أي منها يبدأ بـ `api-l.po.market` أو `api-eu.po.market`
8. انتقل إلى تبويب **Messages**
9. ابحث عن رسالة تبدأ بـ:
   ```
   42["auth",{"session":"...
   ```
10. **انسخ الرسالة بالكامل** — هذا هو SSID

**مثال على الصيغة الصحيحة:**
```
42["auth",{"session":"abc123xyz456","isDemo":1,"uid":987654,"platform":1}]
```

> **ملاحظة:** `"isDemo":1` = حساب تجريبي | `"isDemo":0` = حساب حقيقي

---

### الخطوة 2: إعداد ملف .env

انسخ `env.example` إلى `.env` وأضف قيمك:

```bash
cp env.example .env
```

ثم عدّل الملف:

```env
# التيليغرام (إلزامي)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ADMIN_USER_IDS=your_telegram_user_id

# Pocket Option SSID (إلزامي للتحليل التلقائي)
POCKET_OPTION_SSID=42["auth",{"session":"your_session","isDemo":1,"uid":123456,"platform":1}]
POCKET_OPTION_IS_DEMO=1

# إعدادات اختيارية
BOT_UTC_OFFSET=3
WEBHOOK_SECRET=aboud_trading_secret_2024
```

---

### الخطوة 3: تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

---

### الخطوة 4: تشغيل البوت

```bash
python main.py
```

---

## 📊 المؤشرات الفنية المستخدمة

البوت يستخدم **7 مؤشرات** — يحتاج **6 على الأقل** لإرسال الإشارة:

| # | المؤشر | الشرط للـ CALL | الشرط للـ PUT |
|---|--------|---------------|--------------|
| 1 | **EMA Alignment** | EMA9 > EMA21 > EMA50 | EMA9 < EMA21 < EMA50 |
| 2 | **EMA200 Trend** | السعر فوق EMA200 | السعر تحت EMA200 |
| 3 | **MACD Histogram** | موجب ومتصاعد | سالب ومتنازل |
| 4 | **Supertrend** | اتجاه صاعد (UP) | اتجاه هابط (DOWN) |
| 5 | **ADX** | ADX >= 25 و +DI > -DI | ADX >= 25 و -DI > +DI |
| 6 | **Volume** | حجم > متوسط × 1.2 | حجم > متوسط × 1.2 |
| 7 | **Close Position** | الإغلاق في أعلى 30% | الإغلاق في أسفل 30% |

> **البوابات الإلزامية:** ADX و ROC يجب أن يكونا مستوفيَين حتى لو اكتملت النقاط.

---

## 💬 أوامر التيليغرام

| الأمر | الوصف |
|-------|-------|
| `/start` | تشغيل البوت وعرض القائمة |
| `/stats` | إحصائيات اليوم |
| `/overall` | الإحصائيات التراكمية |
| `/recent` | آخر 10 صفقات |
| `/active` | الصفقة النشطة الحالية |
| `/close` | إغلاق الصفقة يدوياً |
| `/news` | الأخبار الاقتصادية القادمة |
| `/enable` | تفعيل الإشارات |
| `/disable` | إيقاف الإشارات |
| `/connection` | حالة الاتصال بـ Pocket Option |
| `/reconnect` | إعادة الاتصال بـ Pocket Option |
| `/status` | حالة البوت |
| `/reset` | تصفير الإحصائيات |

---

## 🔌 آلية الاتصال بـ Pocket Option

```
المتصفح → F12 → Network → WS → نسخ SSID
    ↓
ملف .env → POCKET_OPTION_SSID
    ↓
pocket_option_service.py → WebSocket → api-l.po.market
    ↓
جلب 200 شمعة (15 دقيقة) لكل زوج
    ↓
analysis_service.py → تحليل فني كل 60 ثانية
    ↓
إشارة CALL/PUT → signal_manager.py → تيليغرام
    ↓
انتظار 15 دقيقة → جلب نتيجة الصفقة
    ↓
إرسال WIN/LOSS إلى تيليغرام
```

---

## 📁 هيكل الملفات

```
abood-otc/
├── main.py                  # نقطة الدخول الرئيسية
├── config.py                # الإعدادات (أزواج OTC، مؤشرات...)
├── pocket_option_service.py # الاتصال بـ Pocket Option WebSocket
├── analysis_service.py      # خدمة التحليل الفني التلقائي
├── signal_manager.py        # إدارة الإشارات وتتبع النتائج
├── price_service.py         # جلب الأسعار (PO + Yahoo + TwelveData)
├── messages.py              # تنسيق رسائل التيليغرام
├── admin_bot.py             # أوامر التيليغرام
├── database.py              # قاعدة البيانات (SQLite/PostgreSQL)
├── telegram_sender.py       # إرسال الرسائل
├── news_service.py          # أخبار ForexFactory
├── requirements.txt         # المتطلبات
├── env.example              # مثال متغيرات البيئة
└── render.yaml              # إعداد النشر على Render.com
```

---

## تحديث SSID عند انتهاء الجلسة

عند انتهاء جلسة Pocket Option:
1. افتح pocketoption.com وسجّل الدخول مجدداً
2. اتبع خطوات الحصول على SSID (الخطوة 1 أعلاه)
3. حدّث `POCKET_OPTION_SSID` في ملف `.env`
4. أرسل `/reconnect` في التيليغرام

---

## النشر على Render.com

1. ارفع المشروع على GitHub
2. أنشئ Web Service جديد على Render
3. أضف متغيرات البيئة من `.env`
4. أضف `RENDER_EXTERNAL_URL` = رابط خدمتك

---

*Aboud Trading Bot OTC v1.0 — مبني على أساس النسخة الأصلية*
