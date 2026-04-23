# 🚀 دليل النشر على Render.com

هذا الدليل يشرح خطوة بخطوة كيفية نشر بوت Aboud Trading OTC على منصة **Render.com** المجانية.

---

## 📋 المتطلبات قبل البدء

1. **حساب GitHub** - لرفع الكود
2. **حساب Render.com** - للاستضافة (مجاني)
3. **بيانات التيليغرام**:
   - `TELEGRAM_BOT_TOKEN` من @BotFather
   - `TELEGRAM_CHAT_ID` (معرّف القناة أو المجموعة)
   - `ADMIN_USER_IDS` (معرّف المستخدم)
4. **SSID من Pocket Option** (انظر README.md)

---

## ✅ الخطوة 1: رفع الكود على GitHub

### 1.1 إنشاء مستودع جديد

1. اذهب إلى [github.com/new](https://github.com/new)
2. أعط المستودع اسماً مثل: `aboud-trading-otc`
3. اختر **Public** (عام) أو **Private** (خاص)
4. انقر **Create repository**

### 1.2 رفع الملفات

```bash
cd /path/to/abood-otc
git init
git add .
git commit -m "Initial commit: Aboud Trading Bot OTC v1.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/aboud-trading-otc.git
git push -u origin main
```

---

## ✅ الخطوة 2: إنشاء Web Service على Render

### 2.1 الدخول إلى Render

1. اذهب إلى [render.com](https://render.com)
2. سجّل الدخول أو أنشئ حساباً جديداً
3. من لوحة التحكم، انقر **New +** ثم اختر **Web Service**

### 2.2 ربط GitHub

1. اختر **GitHub** كمصدر الكود
2. ابحث عن المستودع `aboud-trading-otc` وانقر **Connect**
3. Render سيطلب إذنك لربط حسابك

### 2.3 إعدادات الخدمة

ملء الحقول كالتالي:

| الحقل | القيمة |
|-------|--------|
| **Name** | `aboud-trading-otc` |
| **Environment** | `Python 3` |
| **Region** | اختر الأقرب لك (مثل Frankfurt) |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn -c gunicorn_config.py main:app` |
| **Plan** | `Free` |

---

## ✅ الخطوة 3: إضافة متغيرات البيئة

بعد إنشاء الخدمة، انتقل إلى تبويب **Environment** وأضف المتغيرات التالية:

### المتغيرات الإلزامية:

```
TELEGRAM_BOT_TOKEN = your_bot_token_here
TELEGRAM_CHAT_ID = your_chat_id_here
ADMIN_USER_IDS = your_user_id_here
POCKET_OPTION_SSID = 42["auth",{"session":"...","isDemo":1,"uid":...,"platform":1}]
WEBHOOK_SECRET = aboud_trading_secret_2024
```

### المتغيرات الاختيارية:

```
POCKET_OPTION_IS_DEMO = 1              # 1 = تجريبي, 0 = حقيقي
BOT_UTC_OFFSET = 3                     # توقيتك
SIGNALS_ENABLED = true
DAILY_REPORT_HOUR = 18
DEBUG = false
```

### لقاعدة البيانات السحابية (اختياري):

إذا أردت استخدام PostgreSQL بدلاً من SQLite:

```
DATABASE_URL = postgresql://user:password@host:5432/dbname
```

---

## ✅ الخطوة 4: النشر والتفعيل

### 4.1 بدء النشر

1. بعد إضافة المتغيرات، انقر **Deploy**
2. Render سيبني الخدمة (قد يستغرق 5-10 دقائق)
3. ستجد رابط الخدمة مثل: `https://aboud-trading-otc.onrender.com`

### 4.2 التحقق من الحالة

1. انتقل إلى **Logs** في لوحة التحكم
2. تأكد من رسالة النجاح:
   ```
   ✅ Aboud Trading Bot OTC v1.0
   🔌 Pocket Option: ✅ متصل
   🔄 التحليل: تلقائي 24/7
   ```

### 4.3 اختبار الـ Webhook

افتح في المتصفح:
```
https://aboud-trading-otc.onrender.com/webhook/test
```

يجب أن ترى:
```json
{"status": "ok", "ready": true}
```

---

## 🔄 الخطوة 5: تحديث SSID عند انتهاء الجلسة

عندما ينتهي SSID الخاص بك (بعد عدة ساعات أو أيام):

1. احصل على SSID جديد من Pocket Option (انظر README.md)
2. في لوحة تحكم Render، انتقل إلى **Environment**
3. عدّل قيمة `POCKET_OPTION_SSID`
4. انقر **Save**
5. Render سيعيد تشغيل الخدمة تلقائياً

---

## 🛠️ استكشاف الأخطاء

### المشكلة: البوت لا يتصل بـ Pocket Option

**الحل:**
1. تأكد من أن `POCKET_OPTION_SSID` صحيح
2. اذهب إلى Render Logs وابحث عن رسائل الخطأ
3. جرّب `/reconnect` في التيليغرام

### المشكلة: الخدمة تتوقف بعد 15 دقيقة

**السبب:** Render توقف الخدمات المجانية بعد 15 دقيقة من عدم النشاط.

**الحل:** استخدم خدمة Keep-Alive:
- البوت بالفعل يرسل ping كل 13 دقيقة
- أو استخدم [UptimeRobot](https://uptimerobot.com) (مجاني)

### المشكلة: الإشارات لا تصل

**الحل:**
1. تأكد من أن `SIGNALS_ENABLED = true`
2. اختبر الـ Webhook يدوياً:
   ```bash
   curl -X POST https://aboud-trading-otc.onrender.com/webhook \
     -H "Content-Type: application/json" \
     -d '{"secret":"aboud_trading_secret_2024","pair":"EURUSD_otc","direction":"CALL","signal_score":7}'
   ```

---

## 💾 النسخ الاحتياطية

### حفظ قاعدة البيانات

إذا كنت تستخدم SQLite محلي، قم بتحميل الملف:
1. في Render، انتقل إلى **Files**
2. ابحث عن `aboud_otc_trading.db`
3. انقر **Download**

### استخدام PostgreSQL

للحفاظ على البيانات بشكل دائم:
1. أنشئ PostgreSQL Database على Render
2. انسخ رابط الاتصال
3. أضفه كـ `DATABASE_URL` في Environment

---

## 📊 مراقبة الأداء

### عرض السجلات (Logs)

1. في لوحة تحكم Render، انقر **Logs**
2. ستجد جميع رسائل البوت والأخطاء
3. استخدم **Filters** للبحث عن كلمات معينة

### إعادة التشغيل

إذا احتجت لإعادة تشغيل البوت:
1. انقر **Manual Deploy**
2. اختر **Deploy latest commit**

---

## 🎉 النتيجة النهائية

بعد اتباع هذه الخطوات، سيكون لديك:

✅ بوت تداول تلقائي يعمل 24/7 على Render  
✅ تحليل فني مستقل لأزواج OTC  
✅ إشارات تصل إلى التيليغرام فوراً  
✅ تتبع النتائج (WIN/LOSS) تلقائياً  
✅ إحصائيات يومية وتراكمية  

---

**ملاحظة:** الخطة المجانية على Render قد تكون بطيئة قليلاً. إذا أردت أداءً أفضل، يمكنك الترقية إلى خطة مدفوعة.

---

*Aboud Trading Bot OTC v1.0 — دليل Render*
