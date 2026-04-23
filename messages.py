"""
Aboud Trading Bot OTC - Messages v1.0
======================================
رسائل التيليغرام لأزواج OTC في Pocket Option.
نفس تنسيق المشروع الأصلي مع تعديل أسماء الأزواج.
"""
from datetime import datetime, timezone, timedelta
from config import BOT_TIMEZONE, BOT_UTC_OFFSET, PAIR_DISPLAY_NAMES


def _now():
    return datetime.now(BOT_TIMEZONE)


def _get_display_name(pair: str) -> str:
    """الحصول على الاسم المعروض للزوج."""
    return PAIR_DISPLAY_NAMES.get(pair, pair.replace("_otc", " OTC").replace("_OTC", " OTC"))


def _to_local_hhmm(entry_time):
    """تحويل وقت الدخول إلى HH:MM بالتوقيت المحلي."""
    dt = None
    if entry_time is None:
        return ""
    if isinstance(entry_time, datetime):
        dt = entry_time if entry_time.tzinfo else entry_time.replace(tzinfo=timezone.utc)
    else:
        txt = str(entry_time).strip()
        try:
            ts = int(txt)
            if ts > 1_000_000_000_000:
                ts = ts / 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            pass
        if dt is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
                try:
                    dt = datetime.strptime(txt, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
        if dt is None:
            return txt[-8:-3] if len(txt) >= 16 else txt

    local = dt.astimezone(BOT_TIMEZONE)
    return local.strftime("%H:%M")


# ════════════════════════════════════════════════════════════
# رسالة الإشارة - نفس التنسيق الكلاسيكي
# ════════════════════════════════════════════════════════════

def format_signal_message(pair, direction, entry_time, stats, score=None):
    """رسالة إشارة OTC بتنسيق POCKETOPTION BOT الكلاسيكي."""
    de = "🟢" if direction == "CALL" else "🔴"
    w = stats.get("total_wins", 0)
    l = stats.get("total_losses", 0)
    t = w + l
    r = round((w / t) * 100) if t > 0 else 0

    hhmm = _to_local_hhmm(entry_time)
    display_pair = _get_display_name(pair)

    msg = (
        f"》 ABOUD 15 M 《\n\n"
        f"📊 <b>{display_pair}</b>\n"
        f"{de} <b>{direction}</b>\n"
        f"🕐 <b>{hhmm}</b>\n"
        f"⏳ <b>15 minutes</b>\n"
    )
    if t > 0:
        msg += f"\nWin: {w} | Loss: {l} ({r}%)\nPair {display_pair}: {w}x{l} ({r}%)\n"
    return msg


def format_result_message(pair, direction, entry_time, result):
    """رسالة نتيجة الصفقة الفورية."""
    arrow = "⬆️" if direction == "CALL" else "⬇️"
    hhmm = _to_local_hhmm(entry_time)
    display_pair = _get_display_name(pair)

    if result == "WIN":
        return (
            f"<b>Aboud Trading 15M POCKETOPTION BOT</b> 🔵\n\n"
            f"✅ → {display_pair} {hhmm} {arrow}\n\n"
            f"<b>🏆 WIN!</b>\n"
        )
    elif result == "LOSS":
        return (
            f"<b>Aboud Trading 15M POCKETOPTION BOT</b> 🔵\n\n"
            f"❌ → {display_pair} {hhmm} {arrow}\n\n"
            f"<b>💔 LOSS</b>\n"
        )
    else:
        return (
            f"<b>Aboud Trading 15M POCKETOPTION BOT</b> 🔵\n\n"
            f"➖ → {display_pair} {hhmm} {arrow}\n\n"
            f"<b>🤝 DRAW</b>\n"
        )


# ════════════════════════════════════════════════════════════
# رسائل الإحصائيات والإدارة
# ════════════════════════════════════════════════════════════

def format_stats_message(stats_list):
    tw = sum(s.get("total_wins", 0) for s in stats_list)
    tl = sum(s.get("total_losses", 0) for s in stats_list)
    t = tw + tl
    r = round((tw / t) * 100) if t > 0 else 0

    msg = (
        f"<b>📊 Aboud Trading OTC - Statistics</b>\n"
        f"{'━' * 30}\n\n"
        f"✅ Wins: <b>{tw}</b> | ❌ Losses: <b>{tl}</b>\n"
        f"📊 Total: <b>{t}</b> | 🎯 Rate: <b>{r}%</b>\n\n"
    )
    for s in stats_list:
        p = s.get("pair", "?")
        display_p = _get_display_name(p)
        w = s.get("total_wins", 0)
        l = s.get("total_losses", 0)
        st = w + l
        sr = round((w / st) * 100) if st > 0 else 0
        msg += f"  📊 <b>{display_p}</b>: ✅ {w} | ❌ {l} | 🎯 {sr}%\n"
    return msg


def format_overall_stats(stats_list):
    tw = sum(s.get("total_wins", 0) for s in stats_list)
    tl = sum(s.get("total_losses", 0) for s in stats_list)
    t = tw + tl
    r = round((tw / t) * 100) if t > 0 else 0

    msg = (
        f"<b>📈 الإحصائيات التراكمية - OTC</b>\n"
        f"{'━' * 32}\n\n"
        f"✅ إجمالي الأرباح: <b>{tw}</b>\n"
        f"❌ إجمالي الخسائر: <b>{tl}</b>\n"
        f"📊 إجمالي الصفقات: <b>{t}</b>\n"
        f"🎯 نسبة النجاح: <b>{r}%</b>\n\n"
        f"{'━' * 32}\n"
        f"<b>تفصيل حسب الزوج:</b>\n\n"
    )
    for s in stats_list:
        p = s.get("pair", "?")
        display_p = _get_display_name(p)
        w = s.get("total_wins", 0)
        l = s.get("total_losses", 0)
        st = w + l
        sr = round((w / st) * 100) if st > 0 else 0
        msg += f"  📊 <b>{display_p}</b>: ✅ {w} | ❌ {l} | 🎯 {sr}%\n"

    msg += f"\n<i>🤖 Aboud Trading Bot OTC v1.0</i>\n"
    return msg


def format_daily_report(daily_stats, today_trades=None):
    now = _now()
    dw = sum(s.get("daily_wins", 0) for s in daily_stats)
    dl = sum(s.get("daily_losses", 0) for s in daily_stats)
    dt = dw + dl
    dr = round((dw / dt) * 100) if dt > 0 else 0

    tw = sum(s.get("total_wins", 0) for s in daily_stats)
    tl = sum(s.get("total_losses", 0) for s in daily_stats)
    ta = tw + tl
    tr = round((tw / ta) * 100) if ta > 0 else 0

    msg = (
        f"<b>📋 إحصائيات اليوم - OTC</b>\n"
        f"<b>📅 {now.strftime('%Y-%m-%d')}</b>\n"
        f"{'━' * 32}\n\n"
        f"✅ أرباح: <b>{dw}</b> | ❌ خسائر: <b>{dl}</b>\n"
        f"📊 المجموع: <b>{dt}</b> | 🎯 النسبة: <b>{dr}%</b>\n\n"
        f"{'━' * 32}\n"
        f"<b>📈 الإجمالي الكلي:</b>\n"
        f"✅ {tw} | ❌ {tl} | 🎯 {tr}%\n\n"
    )

    for s in daily_stats:
        p = s.get("pair", "?")
        display_p = _get_display_name(p)
        w = s.get("daily_wins", 0)
        l = s.get("daily_losses", 0)
        st = w + l
        sr = round((w / st) * 100) if st > 0 else 0
        msg += f"  📊 <b>{display_p}</b>: ✅ {w} | ❌ {l} | 🎯 {sr}%\n"

    msg += f"\n<i>🤖 Aboud Trading Bot OTC v1.0</i>\n"
    return msg


def format_recent_trades(trades):
    if not trades:
        return "<b>📋 آخر الصفقات</b>\n\nلا توجد صفقات سابقة."

    msg = f"<b>📋 آخر {len(trades)} صفقات</b>\n{'━' * 32}\n\n"
    for t in trades:
        re = "✅" if t.get("result") == "WIN" else "❌"
        pair = t.get("pair", "?")
        display_p = _get_display_name(pair)
        dire = t.get("direction", "?")
        arrow = "⬆️" if dire == "CALL" else "⬇️"
        ep = t.get("entry_price")
        xp = t.get("exit_price")
        ep_str = f"{ep:.5f}" if ep else "N/A"
        xp_str = f"{xp:.5f}" if xp else "N/A"

        msg += (
            f"{re} <b>{display_p}</b> {arrow} {dire}\n"
            f"   Entry: {ep_str} → Exit: {xp_str}\n\n"
        )
    return msg


def format_active_trade(trade):
    if not trade:
        return "<b>📊 الصفقة النشطة</b>\n\n⚪ لا توجد صفقة نشطة حالياً."

    pair = trade.get("pair", "?")
    display_p = _get_display_name(pair)
    dire = trade.get("direction", "?")
    arrow = "⬆️" if dire == "CALL" else "⬇️"
    ep = trade.get("entry_price")
    ep_str = f"{ep:.5f}" if ep else "قيد الانتظار"

    return (
        f"<b>📊 الصفقة النشطة</b>\n"
        f"{'━' * 32}\n\n"
        f"📊 <b>{display_p}</b> {arrow} {dire}\n"
        f"💰 سعر الدخول: {ep_str}\n"
        f"⏳ المدة: 15 دقيقة\n"
        f"🔄 الحالة: <b>جارية...</b>\n\n"
        f"💡 استخدم /close لإغلاق يدوي"
    )


def format_signal_cancelled_message(pair, direction, reason="Signal reversed"):
    display_p = _get_display_name(pair)
    return (
        f"<b>Aboud Trading 15M OTC</b>\n"
        f"⚠️ Signal Cancelled\n\n"
        f"📊 {display_p} | {direction}\n"
        f"📝 Reason: {reason}\n"
    )


def format_admin_help():
    return (
        f"<b>🛠 Aboud Trading OTC v1.0 - لوحة التحكم</b>\n"
        f"{'━' * 32}\n\n"
        f"/start - تشغيل البوت\n"
        f"/stats - إحصائيات اليوم\n"
        f"/overall - الإحصائيات التراكمية\n"
        f"/recent - آخر 10 صفقات\n"
        f"/active - الصفقة النشطة\n"
        f"/close - إغلاق الصفقة يدوياً\n"
        f"/news - الأخبار القادمة\n"
        f"/enable - تشغيل الإشارات\n"
        f"/disable - إيقاف الإشارات\n"
        f"/reset - تصفير النتائج\n"
        f"/status - حالة البوت\n\n"
        f"<b>الأزواج:</b> EUR/USD OTC, GBP/USD OTC\n"
        f"<b>الحد الأدنى للإشارة:</b> 6/7\n"
        f"<b>مصدر البيانات:</b> Pocket Option API\n\n"
        f"<i>🔒 أوامر الأدمن فقط</i>\n"
    )


def format_status_message(signals_enabled, pending_count, today_count):
    se = "🟢" if signals_enabled else "🔴"
    st = "نشط" if signals_enabled else "متوقف"
    now = _now()
    return (
        f"<b>🤖 حالة البوت - OTC</b>\n"
        f"{'━' * 32}\n\n"
        f"الإشارات: {se} <b>{st}</b>\n"
        f"إشارات معلقة: <b>{pending_count}</b>\n"
        f"صفقات اليوم: <b>{today_count}</b>\n"
        f"الأزواج: EUR/USD OTC, GBP/USD OTC\n"
        f"الفريم: 15 دقيقة\n"
        f"التوقيت: UTC+{BOT_UTC_OFFSET}\n"
        f"الوقت: {now.strftime('%H:%M:%S')}\n"
        f"المصدر: Pocket Option API\n\n"
        f"<i>🤖 Aboud Trading Bot OTC v1.0</i>\n"
    )
