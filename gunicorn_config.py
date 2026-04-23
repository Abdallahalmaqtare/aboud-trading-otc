"""
Gunicorn Configuration for Render.com
======================================
إعدادات Gunicorn لتشغيل البوت على Render بشكل مستقر.
"""

import multiprocessing
import os

# عدد العمال (workers) - Render عادة يوفر CPU واحد للخطة المجانية
workers = 1

# نوع العامل (worker class) - استخدم sync للتطبيقات البسيطة
worker_class = "sync"

# مهلة انتظار العامل (ثانية)
timeout = 120

# مهلة انتظار الإقلاع (ثانية)
graceful_timeout = 30

# ربط على جميع العناوين (0.0.0.0) والمنفذ من متغير البيئة
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"

# مستوى السجل (logging level)
loglevel = "info"

# تنسيق السجل
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# السماح بإعادة تحميل الكود (للتطوير فقط - عطّله في الإنتاج)
reload = False

# عدد الاتصالات المعلقة المسموحة
backlog = 2048

# مهلة الاتصال
timeout = 120

# تجنب مشاكل الذاكرة
max_requests = 1000
max_requests_jitter = 50
