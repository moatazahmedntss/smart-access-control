# smart-access-control
smart-access-control
# 🚪 Smart Access Control System

> نظام تحكم ذكي في الوصول — الكاميرا · التعرف على الوجه · الأمان · الإنذارات

---

## 📌 Overview (نظرة عامة)

**Smart Access Control System** هو تطبيق سطح مكتب مكتوب بـ Python يتيح:

- **مراقبة الباب** في الوقت الحقيقي عبر الكاميرا
- **التعرف التلقائي على الوجوه** وفتح الباب للمصرّح لهم
- **رفض الدخول** وتسجيل لقطة عند اكتشاف وجه غير معروف
- **Panic Attack** — نظام طوارئ متكامل يُقفل النظام فوراً
- **إنذارات ذكية** بمستويات مختلفة (INFO / WARNING / DANGER / PANIC)
- **سجل دخول** كامل مع الصور والأوقات والأسباب
- **إدارة مستخدمين** متكاملة (إضافة / تعديل / حذف / بحث)

---

## 🖥️ System Architecture (هيكل النظام)

```
┌─────────────────────────────────────────────────────┐
│                   Main Window                        │
│  ┌──────────┐  ┌───────────────────────────────┐    │
│  │ Sidebar  │  │        Content Area            │    │
│  │          │  │  ┌─────────┐ ┌─────────────┐  │    │
│  │ Nav Menu │  │  │Dashboard│ │Camera View  │  │    │
│  │          │  │  └─────────┘ └─────────────┘  │    │
│  │ Quick    │  │  ┌─────────┐ ┌─────────────┐  │    │
│  │ Control  │  │  │  Users  │ │ Access Logs │  │    │
│  │          │  │  └─────────┘ └─────────────┘  │    │
│  │ PANIC    │  └───────────────────────────────┘    │
│  └──────────┘                                        │
│  ┌─────────────────────────────────────────────┐    │
│  │           Alert Banner (منبثق)               │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure (هيكل الملفات)

```
smart_access_control/
│
├── main.py                      # 🚀 نقطة البداية
├── config.py                    # ⚙️  كل الإعدادات
├── database.py                  # 🗄️  SQLite (users + logs)
├── face_recognition_module.py   # 🧠 كشف الوجه + التعرف
├── door_controller.py           # 🚪 الباب + AlertManager + PanicAttack
├── camera_module.py             # 🎥 الكاميرا (thread منفصل)
├── audio_module.py              # 🔊 الأصوات
│
├── gui/
│   ├── main_window.py           # 🖼️  النافذة الرئيسية
│   ├── dashboard.py             # 📊 لوحة الإحصائيات
│   ├── camera_window.py         # 📷 عرض الكاميرا + التعرف
│   ├── user_management.py       # 👥 إدارة المستخدمين
│   └── logs_window.py           # 📋 سجل الدخول
│
├── data/
│   ├── authorized/              # ✅ صور المسموح لهم (مجلد لكل مستخدم)
│   ├── unauthorized_log/        # ❌ لقطات المرفوضين تلقائياً
│   └── database.db              # قاعدة البيانات
│
├── assets/
│   ├── sounds/                  # ملفات الصوت (اختياري)
│   └── icons/                   # أيقونات (اختياري)
│
├── requirements.txt             # 📦 المكتبات مع الإصدارات
├── install.bat                  # 🪟 مثبّت Windows
├── install.sh                   # 🐧 مثبّت Mac/Linux
└── README.md                    # 📖 هذا الملف
```

---

## 🚀 Quick Start (البدء السريع)

### Windows
```batch
1. انقر مرتين على install.bat
2. انتظر اكتمال التثبيت
3. انقر مرتين على run.bat
```

### Mac / Linux
```bash
bash install.sh
python3 main.py
```

### يدوياً
```bash
pip install -r requirements.txt
python main.py
```

---

## 📦 Dependencies (المكتبات)

| المكتبة | الإصدار | الاستخدام |
|---------|---------|-----------|
| `opencv-python` | 4.8.1.78 | الكاميرا + كشف الوجه الأساسي |
| `customtkinter` | 5.2.2 | الواجهة الرسومية |
| `Pillow` | 10.3.0 | عرض الصور في tkinter |
| `numpy` | 1.26.4 | العمليات الحسابية |
| `pygame` | 2.5.2 | الأصوات |
| `face-recognition` | 1.3.0 | *(اختياري)* التعرف الدقيق على الهوية |
| `dlib` | 19.24.4 | *(اختياري)* مطلوب لـ face-recognition |

---

## 🔑 Key Features (المميزات الرئيسية)

### 🎥 نظام الكاميرا
- دعم كاميرا Laptop / USB / IP Camera (RTSP)
- عرض مباشر بـ ~30 FPS
- رسم مربع أخضر (مقبول) أو أحمر (مرفوض) حول الوجه
- نسبة ثقة AI Confidence Percentage

### 🧠 التعرف على الوجه
- **مع face-recognition:** تعرف دقيق بنسبة ثقة
- **بدونها:** كشف الوجه فقط بـ OpenCV Haar Cascade
- كشف Tailgating (أكثر من شخص)
- كشف Spoofing (صورة على شاشة)
- تعرف من زوايا مختلفة (بإضافة صور متعددة)

### 🚨 Panic Attack System
يُفعَّل تلقائياً عند:
- اكتشاف دخيل غير معروف متكرر
- كشف محاولة خداع (Spoofing)
- تجاوز الحد الأقصى للمحاولات الفاشلة
- كشف Tailgating
- الضغط اليدوي على زر PANIC ATTACK

عند التفعيل يقوم بـ:
1. ❌ قفل الباب فوراً
2. 📸 التقاط لقطة تلقائياً
3. 🔔 إصدار إنذار PANIC
4. 🔒 تجميد النظام لمدة محددة
5. 🗄️ تسجيل الحدث في قاعدة البيانات
6. 🔊 تشغيل صوت الطوارئ

### 🔔 Alert System (مستويات الإنذار)
| المستوى | اللون | الاستخدام |
|---------|-------|-----------|
| `INFO` | 🔵 أزرق | معلومات عادية (فتح/إغلاق يدوي) |
| `WARNING` | 🟡 أصفر | تحذيرات (محاولة فاشلة، Emergency Open) |
| `DANGER` | 🔴 أحمر | أحداث خطيرة (رفض متكرر) |
| `PANIC` | ⚫ أسود/أحمر | حالات طوارئ قصوى |

---

## ⚙️ Configuration (الإعدادات)

كل الإعدادات في `config.py`:

```python
DOOR_OPEN_DURATION      = 5     # ثواني قبل الإغلاق التلقائي
MAX_FAILED_ATTEMPTS     = 3     # محاولات قبل قفل النظام
LOCKOUT_DURATION        = 30    # ثواني لقفل النظام
FACE_RECOGNITION_TOLERANCE = 0.5  # دقة التعرف (0.4=أدق / 0.6=أكثر تساهلاً)
CAMERA_WIDTH            = 640
CAMERA_HEIGHT           = 480
CAMERA_FPS              = 30
```

---

## 👤 إضافة مستخدم مسموح له

```
1. افتح البرنامج → اضغط 👥 Users
2. اضغط ➕ Add New
3. أدخل الاسم والدور → 💾 Save
4. اضغط 📁 Import Face Image(s)
5. اختر 3-5 صور واضحة بإضاءة جيدة
```

**متطلبات الصورة الجيدة:**
- ✅ وجه واحد فقط
- ✅ إضاءة مناسبة (لا ظلام، لا إضاءة زائدة)
- ✅ الوجه كامل وواضح
- ❌ لا تقبل: صور مظلمة / أكثر من وجه / وجه مقطوع

---

## 🔧 Troubleshooting (حل المشاكل)

| المشكلة | الحل |
|---------|------|
| الكاميرا لا تفتح | جرّب Camera 1 أو Camera 2 |
| خطأ في dlib على Windows | حمّل wheel جاهز من [هنا](https://github.com/z-mahmud22/Dlib_Windows_Python3.x) |
| الواجهة بدون ألوان | `pip install --upgrade customtkinter` |
| بطء في التعرف | قلّل دقة الكاميرا في config.py |

---

## 🏗️ Build for Production

```bash
# تثبيت PyInstaller
pip install pyinstaller==6.3.0

# بناء التطبيق
pyinstaller --onedir --windowed --name "SmartAccessControl" \
  --add-data "gui;gui" \
  --add-data "data;data" \
  --add-data "assets;assets" \
  --add-data "config.py;." \
  --add-data "database.py;." \
  --add-data "face_recognition_module.py;." \
  --add-data "door_controller.py;." \
  --add-data "camera_module.py;." \
  --add-data "audio_module.py;." \
  main.py

# الناتج في: dist/SmartAccessControl/SmartAccessControl.exe
```

---

## 📊 Database Schema

```sql
-- المستخدمون
users (id, name, role, added_date, is_active, notes)

-- صور الوجه
user_images (id, user_id, image_path, added_date)

-- سجل الدخول
access_logs (id, user_id, user_name, timestamp, status,
             confidence, snapshot_path, rejection_reason, event_type)
```

---

## 📄 License
MIT License — حر الاستخدام للأغراض الشخصية والتجارية.

---

> 💡 **نصيحة:** أضف 3-5 صور لكل مستخدم من زوايا مختلفة لأفضل دقة في التعرف.
