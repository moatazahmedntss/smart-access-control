#!/usr/bin/env python3
# =============================================================
#   Smart Access Control System — Single File Version
#   كل الكود في ملف واحد — شغّله بـ:  python smart_access_control_app.py
# =============================================================

import os
import sys
import sqlite3
import threading
import time
import shutil
from datetime import datetime
from enum import Enum
from tkinter import filedialog, messagebox, ttk

# ── تحقق من المكتبات الأساسية ─────────────────────────────
_missing = []
try:
    import cv2
except ImportError:
    _missing.append("opencv-python")
try:
    import customtkinter as ctk
except ImportError:
    _missing.append("customtkinter")
try:
    from PIL import Image, ImageTk
except ImportError:
    _missing.append("Pillow")
try:
    import numpy as np
except ImportError:
    _missing.append("numpy")

if _missing:
    print("❌  مكتبات مفقودة — شغّل أولاً:")
    for m in _missing:
        print(f"    pip install {m}")
    input("\nاضغط Enter للخروج...")
    sys.exit(1)

# ── face_recognition (اختياري) ────────────────────────────
# Fix for PyInstaller: model files must be found at runtime
def _fix_face_recognition_models():
    """
    عند تحويل البرنامج لـ .exe بـ PyInstaller، ملفات الـ models
    تتوضع في مجلد مؤقت. الكود ده بيحدد مكانها الصح تلقائياً.
    """
    if not getattr(sys, 'frozen', False):
        return  # شغّال من Python عادي — مش محتاج تعديل

    try:
        import face_recognition_models
        models_dir = os.path.dirname(face_recognition_models.__file__)

        # لو الملفات مش موجودة في المكان الافتراضي، ندور عليها
        landmark_file = os.path.join(models_dir, 'models',
                                     'shape_predictor_68_face_landmarks.dat')
        if not os.path.exists(landmark_file):
            # دور في مجلد الـ exe نفسه
            exe_dir = os.path.dirname(sys.executable)
            alt_models = os.path.join(exe_dir, 'face_recognition_models', 'models')
            if os.path.exists(alt_models):
                # أخبر face_recognition_models بالمسار الجديد
                face_recognition_models.__file__ = os.path.join(
                    exe_dir, 'face_recognition_models', '__init__.py')
    except Exception:
        pass

_fix_face_recognition_models()

try:
    import face_recognition as _fr
    # تحقق إن الـ model files موجودة فعلاً
    try:
        import face_recognition_models as _frm
        _dat = os.path.join(os.path.dirname(_frm.__file__),
                            'models', 'shape_predictor_68_face_landmarks.dat')
        if not os.path.exists(_dat):
            raise FileNotFoundError(f"Model file missing: {_dat}")
    except Exception as _e:
        print(f"⚠️  face_recognition models غير مكتملة: {_e}")
        raise ImportError("models missing")
    FACE_REC_AVAILABLE = True
    print("✅  face_recognition محمّلة بنجاح")
except (ImportError, Exception):
    FACE_REC_AVAILABLE = False
    _fr = None
    print("⚠️  face_recognition غير متاحة — كشف الوجه الأساسي فقط (OpenCV).")

# ── pygame (اختياري) ──────────────────────────────────────
try:
    import pygame as _pg
    _pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

# =============================================================
#  ⚙️  الإعدادات  (CONFIG)
# =============================================================
BASE_DIR             = os.path.dirname(os.path.abspath(__file__))
DATA_DIR             = os.path.join(BASE_DIR, "data")
AUTHORIZED_DIR       = os.path.join(DATA_DIR, "authorized")
UNAUTHORIZED_LOG_DIR = os.path.join(DATA_DIR, "unauthorized_log")
DB_PATH              = os.path.join(DATA_DIR, "database.db")
ASSETS_DIR           = os.path.join(BASE_DIR, "assets")
SOUNDS_DIR           = os.path.join(ASSETS_DIR, "sounds")

for _d in [DATA_DIR, AUTHORIZED_DIR, UNAUTHORIZED_LOG_DIR, ASSETS_DIR, SOUNDS_DIR]:
    os.makedirs(_d, exist_ok=True)

DOOR_OPEN_DURATION         = 5
MAX_FAILED_ATTEMPTS        = 3
LOCKOUT_DURATION           = 30
FACE_RECOGNITION_TOLERANCE = 0.5
CAMERA_WIDTH               = 640
CAMERA_HEIGHT              = 480
CAMERA_FPS                 = 30

COLOR_SUCCESS = "#00C853"
COLOR_DANGER  = "#FF1744"
COLOR_WARNING = "#FFD600"
COLOR_PRIMARY = "#1565C0"
COLOR_DARK_BG = "#1a1a2e"
COLOR_CARD_BG = "#16213e"
COLOR_ACCENT  = "#0f3460"


# =============================================================
#  🗄️  قاعدة البيانات  (DATABASE)
# =============================================================
class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        conn = self._conn()
        cur  = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            added_date TEXT,
            is_active INTEGER DEFAULT 1,
            notes TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS user_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            image_path TEXT,
            added_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            timestamp TEXT,
            status TEXT,
            confidence REAL,
            snapshot_path TEXT,
            rejection_reason TEXT,
            event_type TEXT DEFAULT 'access')''')
        conn.commit()
        conn.close()

    # ── Users ─────────────────────────────────────────────
    def add_user(self, name, role='user', notes=''):
        conn = self._conn()
        cur  = conn.cursor()
        cur.execute('INSERT INTO users (name,role,added_date,notes) VALUES (?,?,?,?)',
                    (name, role, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notes))
        uid = cur.lastrowid
        conn.commit(); conn.close()
        return uid

    def get_all_users(self):
        conn = self._conn()
        rows = conn.cursor().execute('SELECT * FROM users WHERE is_active=1').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_user_by_id(self, uid):
        conn = self._conn()
        row  = conn.cursor().execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_user(self, uid, name, role, notes):
        conn = self._conn()
        conn.cursor().execute('UPDATE users SET name=?,role=?,notes=? WHERE id=?',
                              (name, role, notes, uid))
        conn.commit(); conn.close()

    def delete_user(self, uid):
        conn = self._conn()
        conn.cursor().execute('UPDATE users SET is_active=0 WHERE id=?', (uid,))
        conn.commit(); conn.close()

    def search_users(self, q):
        conn = self._conn()
        rows = conn.cursor().execute(
            "SELECT * FROM users WHERE is_active=1 AND (name LIKE ? OR role LIKE ?)",
            (f'%{q}%', f'%{q}%')).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── User Images ───────────────────────────────────────
    def add_user_image(self, uid, path):
        conn = self._conn()
        conn.cursor().execute(
            'INSERT INTO user_images (user_id,image_path,added_date) VALUES (?,?,?)',
            (uid, path, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit(); conn.close()

    def get_user_images(self, uid):
        conn = self._conn()
        rows = conn.cursor().execute(
            'SELECT * FROM user_images WHERE user_id=?', (uid,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_user_images(self, uid):
        conn = self._conn()
        conn.cursor().execute('DELETE FROM user_images WHERE user_id=?', (uid,))
        conn.commit(); conn.close()

    # ── Logs ──────────────────────────────────────────────
    def add_log(self, user_name, status, confidence=0,
                snapshot_path='', rejection_reason='',
                user_id=None, event_type='access'):
        conn = self._conn()
        conn.cursor().execute(
            'INSERT INTO access_logs '
            '(user_id,user_name,timestamp,status,confidence,'
            'snapshot_path,rejection_reason,event_type) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (user_id, user_name,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             status, confidence, snapshot_path,
             rejection_reason, event_type))
        conn.commit(); conn.close()

    def get_all_logs(self, limit=100):
        conn = self._conn()
        rows = conn.cursor().execute(
            'SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT ?',
            (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stats(self):
        conn = self._conn()
        c    = conn.cursor()
        total  = c.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]
        auth   = c.execute("SELECT COUNT(*) FROM access_logs WHERE status='authorized'").fetchone()[0]
        denied = c.execute("SELECT COUNT(*) FROM access_logs WHERE status='denied'").fetchone()[0]
        last   = c.execute("SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT 1").fetchone()
        conn.close()
        return {'total_users': total, 'authorized': auth,
                'denied': denied,
                'last_access': dict(last) if last else None}


# =============================================================
#  🔊  الأصوات  (AUDIO)
# =============================================================
class AudioModule:
    def __init__(self):
        self.enabled = True
        self._sounds = {}
        if PYGAME_AVAILABLE:
            self._build_sounds()

    def _build_sounds(self):
        sr = 44100
        def make(freqs, dur):
            parts = []
            for f in freqs:
                t    = np.linspace(0, dur, int(sr * dur), False)
                tone = np.sin(2 * np.pi * f * t)
                fi   = int(sr * 0.01)
                if len(tone) > fi * 2:
                    tone[:fi]  *= np.linspace(0, 1, fi)
                    tone[-fi:] *= np.linspace(1, 0, fi)
                parts.append(tone)
            raw    = np.concatenate(parts)
            raw16  = (raw * 32767).astype(np.int16)
            stereo = np.column_stack([raw16, raw16])
            return _pg.sndarray.make_sound(stereo)
        try:
            self._sounds['success'] = make([440, 550, 660], 0.15)
            self._sounds['denied']  = make([300, 250, 200], 0.20)
            self._sounds['panic']   = make([800, 600, 800], 0.10)
            self._sounds['warning'] = make([400, 400],      0.15)
        except Exception as e:
            print(f"⚠️  خطأ في بناء الأصوات: {e}")

    def _play(self, key):
        if not self.enabled:
            return
        snd = self._sounds.get(key)
        if snd:
            threading.Thread(target=snd.play, daemon=True).start()
        elif sys.platform == 'win32':
            try:
                import winsound
                fm = {'success': 880, 'denied': 300, 'panic': 1000, 'warning': 500}
                winsound.Beep(fm.get(key, 440), 180)
            except Exception:
                pass

    def play_success(self):  self._play('success')
    def play_denied(self):   self._play('denied')
    def play_panic(self):    self._play('panic')
    def play_warning(self):  self._play('warning')

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled


# =============================================================
#  🎥  الكاميرا  (CAMERA)
# =============================================================
class CameraModule:
    def __init__(self):
        self.cap             = None
        self.is_running      = False
        self.current_frame   = None
        self._lock           = threading.Lock()
        self._thread         = None
        self.frame_callbacks = []

    def start_camera(self, index=0):
        if self.is_running:
            self.stop_camera()
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            return False, "فشل فتح الكاميرا"
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True, "تم تشغيل الكاميرا ✅"

    def stop_camera(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None
        with self._lock:
            self.current_frame = None
        return True, "تم إيقاف الكاميرا"

    def _loop(self):
        while self.is_running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self._lock:
                        self.current_frame = frame.copy()
                    for cb in list(self.frame_callbacks):
                        try:
                            cb(frame)
                        except Exception:
                            pass
            cv2.waitKey(1)

    def get_current_frame(self):
        with self._lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def capture_snapshot(self, prefix="snapshot"):
        frame = self.get_current_frame()
        if frame is None:
            return None
        ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(UNAUTHORIZED_LOG_DIR, f"{prefix}_{ts}.jpg")
        cv2.imwrite(path, frame)
        return path

    def get_available_cameras(self):
        avail = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                avail.append(i)
                cap.release()
        return avail


# =============================================================
#  🧠  التعرف على الوجه  (FACE RECOGNITION)
# =============================================================
class FaceRecognitionModule:
    def __init__(self, database):
        self.db              = database
        self.known_encodings = []
        self.known_names     = []
        self.known_ids       = []
        cascade_path         = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade    = cv2.CascadeClassifier(cascade_path)
        self.load_known_faces()

    def load_known_faces(self):
        self.known_encodings = []
        self.known_names     = []
        self.known_ids       = []
        if not FACE_REC_AVAILABLE:
            return
        for user in self.db.get_all_users():
            for img_data in self.db.get_user_images(user['id']):
                path = img_data['image_path']
                if not os.path.exists(path):
                    continue
                try:
                    img  = _fr.load_image_file(path)
                    encs = _fr.face_encodings(img)
                    if encs:
                        self.known_encodings.append(encs[0])
                        self.known_names.append(user['name'])
                        self.known_ids.append(user['id'])
                except Exception as e:
                    print(f"خطأ تحميل {path}: {e}")
        print(f"✅ تم تحميل {len(self.known_encodings)} وجه")

    def validate_face_image(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            return False, "لا يمكن قراءة الصورة"
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        br   = np.mean(gray)
        if br < 40:
            return False, "الصورة مظلمة جداً"
        if br > 230:
            return False, "الصورة ساطعة جداً"
        if FACE_REC_AVAILABLE:
            locs = _fr.face_locations(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            if len(locs) == 0:
                return False, "لم يتم اكتشاف أي وجه"
            if len(locs) > 1:
                return False, "يوجد أكثر من وجه"
        else:
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            if len(faces) == 0:
                return False, "لم يتم اكتشاف أي وجه"
            if len(faces) > 1:
                return False, "يوجد أكثر من وجه"
        return True, "صورة صالحة ✅"

    def recognize_face(self, frame):
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = []
        if FACE_REC_AVAILABLE:
            locations = _fr.face_locations(rgb)
            if not locations:
                return [], []
            encodings = _fr.face_encodings(rgb, locations)
            for enc, loc in zip(encodings, locations):
                name, conf, uid, auth = "Unknown", 0.0, None, False
                if self.known_encodings:
                    distances = _fr.face_distance(self.known_encodings, enc)
                    matches   = _fr.compare_faces(
                        self.known_encodings, enc,
                        tolerance=FACE_RECOGNITION_TOLERANCE)
                    if True in matches:
                        idx  = int(np.argmin(distances))
                        if matches[idx]:
                            name = self.known_names[idx]
                            uid  = self.known_ids[idx]
                            conf = float(1 - distances[idx])
                            auth = True
                results.append({'location': loc, 'name': name,
                                'confidence': conf,
                                'user_id': uid, 'is_authorized': auth})
        else:
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            for (x, y, w, h) in faces:
                results.append({'location': (y, x+w, y+h, x),
                                'name': "Unknown", 'confidence': 0.0,
                                'user_id': None, 'is_authorized': False})
        return results, [r['location'] for r in results]

    def draw_face_boxes(self, frame, results):
        for r in results:
            top, right, bottom, left = r['location']
            color = (0, 255, 0) if r['is_authorized'] else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            label = f"{r['name']} ({r['confidence']:.0%})"
            cv2.rectangle(frame, (left, bottom-35), (right, bottom), color, cv2.FILLED)
            cv2.putText(frame, label, (left+6, bottom-6),
                        cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)
        return frame

    def detect_tailgating(self, face_count):
        return face_count > 1

    def detect_spoofing(self, frame, face_location):
        top, right, bottom, left = face_location
        roi = frame[top:bottom, left:right]
        if roi.size == 0:
            return False
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var() < 50


# =============================================================
#  🚪  التحكم في الباب + إنذارات + Panic Attack
# =============================================================
class AlertLevel(Enum):
    INFO    = "INFO"
    WARNING = "WARNING"
    DANGER  = "DANGER"
    PANIC   = "PANIC"


class Alert:
    def __init__(self, level, title, message):
        self.level     = level
        self.title     = title
        self.message   = message
        self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.read      = False

    def __repr__(self):
        return f"[{self.level.value}] {self.timestamp} — {self.title}: {self.message}"


class AlertManager:
    def __init__(self, max_alerts=100):
        self._alerts    = []
        self._callbacks = []
        self._lock      = threading.Lock()
        self.max_alerts = max_alerts

    def add(self, level, title, message):
        alert = Alert(level, title, message)
        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > self.max_alerts:
                self._alerts.pop(0)
        print(f"🔔 {alert}")
        for cb in self._callbacks:
            try:
                cb(alert)
            except Exception:
                pass
        return alert

    def info(self, t, m):    return self.add(AlertLevel.INFO,    t, m)
    def warning(self, t, m): return self.add(AlertLevel.WARNING, t, m)
    def danger(self, t, m):  return self.add(AlertLevel.DANGER,  t, m)
    def panic(self, t, m):   return self.add(AlertLevel.PANIC,   t, m)

    def get_all(self, unread_only=False):
        with self._lock:
            if unread_only:
                return [a for a in self._alerts if not a.read]
            return list(self._alerts)

    def mark_all_read(self):
        with self._lock:
            for a in self._alerts:
                a.read = True

    def unread_count(self):
        with self._lock:
            return sum(1 for a in self._alerts if not a.read)

    def on_alert(self, cb):
        self._callbacks.append(cb)


class PanicAttack:
    REASON_INTRUDER     = "intruder_detected"
    REASON_FORCED_ENTRY = "forced_entry"
    REASON_TAILGATING   = "tailgating"
    REASON_SPOOFING     = "spoofing_attempt"
    REASON_MAX_ATTEMPTS = "max_failed_attempts"
    REASON_MANUAL       = "manual_panic"

    def __init__(self, door_ctrl, alert_mgr, db=None, camera=None):
        self.door        = door_ctrl
        self.alerts      = alert_mgr
        self.db          = db
        self.camera      = camera
        self.is_active   = False
        self.active_reason = None
        self.active_since  = None
        self._callbacks  = []
        self._lock       = threading.Lock()

    def trigger(self, reason=REASON_MANUAL, details="",
                lock_door=True, lock_system=False, lock_duration=60):
        with self._lock:
            self.is_active     = True
            self.active_reason = reason
            self.active_since  = datetime.now()

        snapshot_path = ""
        if lock_door:
            self.door.close_door(reason=f"panic:{reason}")
        if lock_system:
            self.door.is_locked_out = True
            t = threading.Timer(lock_duration, self._auto_deactivate)
            t.daemon = True
            t.start()
        if self.camera:
            try:
                snapshot_path = self.camera.capture_snapshot(
                    prefix=f"panic_{reason}") or ""
            except Exception:
                pass

        msg = f"سبب: {reason}"
        if details:
            msg += f" | {details}"
        self.alerts.panic("🚨 PANIC ATTACK", msg)

        if self.db:
            try:
                self.db.add_log("PANIC SYSTEM", "panic", 0,
                                snapshot_path=snapshot_path,
                                rejection_reason=f"PANIC: {reason}",
                                event_type="panic_attack")
            except Exception:
                pass

        result = {
            'success': True, 'reason': reason, 'details': details,
            'timestamp': self.active_since.strftime('%Y-%m-%d %H:%M:%S'),
            'snapshot_path': snapshot_path,
        }
        for cb in self._callbacks:
            try:
                cb(result)
            except Exception:
                pass
        print(f"🚨 PANIC ATTACK — reason: {reason}")
        return result

    def deactivate(self, by="manual"):
        with self._lock:
            if not self.is_active:
                return False
            self.is_active = False
            self.active_reason = None
            self.active_since  = None
        self.door.is_locked_out   = False
        self.door.failed_attempts = 0
        self.alerts.info("✅ Panic Deactivated",
                         f"تم إلغاء الطوارئ بواسطة: {by}")
        return True

    def _auto_deactivate(self):
        self.deactivate(by="auto_timeout")

    def on_panic(self, cb):
        self._callbacks.append(cb)

    def trigger_tailgating(self, face_count=2):
        return self.trigger(self.REASON_TAILGATING,
                            f"اكتشاف {face_count} أشخاص", lock_door=True)

    def trigger_max_attempts(self):
        return self.trigger(self.REASON_MAX_ATTEMPTS,
                            "تجاوز الحد الأقصى",
                            lock_door=True, lock_system=True, lock_duration=30)


class DoorController:
    def __init__(self, auto_close_delay=5):
        self.is_open          = False
        self.auto_close_delay = auto_close_delay
        self.close_timer      = None
        self.failed_attempts  = 0
        self.is_locked_out    = False
        self.lockout_timer    = None
        self._cbs = {'on_open': [], 'on_close': [], 'on_auto_close': []}

    def add_callback(self, event, cb):
        if event in self._cbs:
            self._cbs[event].append(cb)

    def _fire(self, event, **kw):
        for cb in self._cbs.get(event, []):
            try:
                cb(**kw)
            except Exception:
                pass

    def open_door(self, reason="manual", auto_close=True):
        if self.is_locked_out:
            return False, "النظام مقفل"
        self.is_open         = True
        self.failed_attempts = 0
        self._fire('on_open', reason=reason)
        if self.close_timer:
            self.close_timer.cancel()
        if auto_close:
            self.close_timer = threading.Timer(self.auto_close_delay, self._auto_close)
            self.close_timer.daemon = True
            self.close_timer.start()
        return True, "تم فتح الباب"

    def close_door(self, reason="manual"):
        self.is_open = False
        if self.close_timer:
            self.close_timer.cancel()
            self.close_timer = None
        self._fire('on_close', reason=reason)
        return True, "تم إغلاق الباب"

    def _auto_close(self):
        self.is_open = False
        self._fire('on_auto_close')
        self._fire('on_close', reason="auto_close")

    def panic_mode(self):
        if self.close_timer:
            self.close_timer.cancel()
        self.is_open         = True
        self.is_locked_out   = False
        self.failed_attempts = 0
        self._fire('on_open', reason="panic_mode")
        return True, "وضع الطوارئ"

    def record_failed_attempt(self, max_attempts=3, lockout_duration=30):
        self.failed_attempts += 1
        if self.failed_attempts >= max_attempts:
            self.is_locked_out = True
            if self.lockout_timer:
                self.lockout_timer.cancel()
            self.lockout_timer = threading.Timer(lockout_duration, self._unlock)
            self.lockout_timer.daemon = True
            self.lockout_timer.start()
            return True
        return False

    def _unlock(self):
        self.is_locked_out   = False
        self.failed_attempts = 0


# =============================================================
#  📊  Dashboard
# =============================================================
class Dashboard(ctk.CTkFrame):
    def __init__(self, parent, db, door, camera, face_rec):
        super().__init__(parent, fg_color=COLOR_DARK_BG)
        self.db          = db
        self.door        = door
        self.camera      = camera
        self.face_rec    = face_rec
        self.stat_labels = {}
        self._build()
        self._tick()

    def _build(self):
        ctk.CTkLabel(self, text="📊  Dashboard",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(padx=15, pady=(15, 8), anchor='w')

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill='x', padx=15, pady=4)

        stats = self.db.get_stats()
        for icon, title, val, color in [
            ("👥", "Total Users",  str(stats['total_users']),  COLOR_PRIMARY),
            ("✅", "Authorized",   str(stats['authorized']),   COLOR_SUCCESS),
            ("❌", "Denied",       str(stats['denied']),       COLOR_DANGER),
            ("🚪", "Door Status",
             "OPEN" if self.door.is_open else "LOCKED",
             COLOR_SUCCESS if self.door.is_open else COLOR_DANGER),
        ]:
            card = ctk.CTkFrame(row, fg_color=COLOR_CARD_BG, corner_radius=10)
            card.pack(side='left', fill='both', expand=True, padx=4)
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=28)).pack(pady=(14, 0))
            lbl = ctk.CTkLabel(card, text=val,
                               font=ctk.CTkFont(size=22, weight="bold"),
                               text_color=color)
            lbl.pack()
            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(size=10), text_color="gray"
                         ).pack(pady=(0, 14))
            self.stat_labels[title] = lbl

        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill='both', expand=True, padx=15, pady=8)
        self._build_door_panel(bot)
        self._build_events_panel(bot)

    def _build_door_panel(self, parent):
        f = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG,
                         corner_radius=10, width=280)
        f.pack(side='left', fill='both', expand=True, padx=(0, 5))
        ctk.CTkLabel(f, text="🚪  Door Status",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(14, 4))
        self.door_visual = ctk.CTkLabel(
            f, text="🔴\n\nDOOR LOCKED",
            font=ctk.CTkFont(size=36),
            text_color=COLOR_DANGER, height=180)
        self.door_visual.pack(expand=True)
        ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=11)).pack(pady=(0, 14))

    def _build_events_panel(self, parent):
        f = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=10)
        f.pack(side='right', fill='both', expand=True, padx=(5, 0))
        ctk.CTkLabel(f, text="📋  Recent Events",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(pady=(14, 4), padx=14, anchor='w')
        self.events_scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        self.events_scroll.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self._reload_events()

    def _reload_events(self):
        for w in self.events_scroll.winfo_children():
            w.destroy()
        logs = self.db.get_all_logs(limit=12)
        if not logs:
            ctk.CTkLabel(self.events_scroll, text="No events yet",
                         text_color="gray").pack(pady=20)
            return
        for log in logs:
            auth  = log['status'] == 'authorized'
            color = COLOR_SUCCESS if auth else COLOR_DANGER
            row   = ctk.CTkFrame(self.events_scroll, fg_color=COLOR_ACCENT,
                                 corner_radius=5, height=46)
            row.pack(fill='x', pady=2)
            row.pack_propagate(False)
            ctk.CTkLabel(row,
                         text=f"{'✅' if auth else '❌'}  {log['user_name']}",
                         text_color=color,
                         font=ctk.CTkFont(size=11, weight="bold")
                         ).pack(side='left', padx=8)
            ctk.CTkLabel(row, text=log['timestamp'],
                         font=ctk.CTkFont(size=10), text_color="gray"
                         ).pack(side='right', padx=8)

    def _tick(self):
        try:
            stats = self.db.get_stats()
            for k, v, c in [
                ('Total Users', str(stats['total_users']),  COLOR_PRIMARY),
                ('Authorized',  str(stats['authorized']),   COLOR_SUCCESS),
                ('Denied',      str(stats['denied']),       COLOR_DANGER),
                ('Door Status',
                 "OPEN" if self.door.is_open else "LOCKED",
                 COLOR_SUCCESS if self.door.is_open else COLOR_DANGER),
            ]:
                if k in self.stat_labels:
                    self.stat_labels[k].configure(text=v, text_color=c)
            self.door_visual.configure(
                text="🟢\n\nDOOR OPEN" if self.door.is_open else "🔴\n\nDOOR LOCKED",
                text_color=COLOR_SUCCESS if self.door.is_open else COLOR_DANGER)
            self._reload_events()
        except Exception:
            pass
        self.after(3000, self._tick)


# =============================================================
#  🎥  Camera Window
# =============================================================
class CameraWindow(ctk.CTkFrame):
    def __init__(self, parent, camera, face_rec, door, db, audio, panic_atk=None):
        super().__init__(parent, fg_color=COLOR_DARK_BG)
        self.camera     = camera
        self.face_rec   = face_rec
        self.door       = door
        self.db         = db
        self.audio      = audio
        self.panic_atk  = panic_atk
        self.recog_on   = False
        self.running    = True
        self.last_ts    = 0
        self.cooldown   = 3
        self._build()
        self._start_loop()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, height=48)
        hdr.pack(fill='x', padx=10, pady=(10, 4))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🎥  Camera View & Face Recognition",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(side='left', padx=14)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill='both', expand=True, padx=10, pady=4)

        cam_f = ctk.CTkFrame(body, fg_color=COLOR_CARD_BG, corner_radius=10)
        cam_f.pack(side='left', fill='both', expand=True, padx=(0, 5))

        self.cam_lbl = ctk.CTkLabel(cam_f, text="📷  Camera Offline",
                                    font=ctk.CTkFont(size=15),
                                    width=630, height=450)
        self.cam_lbl.pack(padx=8, pady=8)

        self.status_bar = ctk.CTkLabel(
            cam_f, text="⚪  Camera Inactive",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_ACCENT, corner_radius=6)
        self.status_bar.pack(fill='x', padx=8, pady=(0, 8))

        ctrl = ctk.CTkFrame(body, fg_color=COLOR_CARD_BG,
                            corner_radius=10, width=268)
        ctrl.pack(side='right', fill='y', padx=(5, 0))
        ctrl.pack_propagate(False)
        self._build_ctrl(ctrl)

    def _build_ctrl(self, parent):
        p = dict(padx=14, pady=4)

        ctk.CTkLabel(parent, text="⚙️  Camera Source",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(**p, anchor='w')

        self.cam_var = ctk.StringVar(value="Camera 0 (Default)")
        ctk.CTkOptionMenu(parent,
                          values=["Camera 0 (Default)", "Camera 1",
                                  "Camera 2", "IP Camera (URL)"],
                          variable=self.cam_var, width=238).pack(**p)

        self.ip_ent = ctk.CTkEntry(parent,
                                   placeholder_text="rtsp://...",
                                   width=238)
        self.ip_ent.pack(**p)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill='x', padx=14, pady=4)
        ctk.CTkButton(row, text="▶  Start", command=self._start_cam,
                      fg_color=COLOR_SUCCESS, width=108).pack(side='left', padx=(0, 4))
        ctk.CTkButton(row, text="⏹  Stop",  command=self._stop_cam,
                      fg_color=COLOR_DANGER,  width=108).pack(side='right')

        ctk.CTkFrame(parent, height=1, fg_color="gray").pack(fill='x', padx=14, pady=10)

        ctk.CTkLabel(parent, text="🤖  Face Recognition",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(**p, anchor='w')

        self.recog_btn = ctk.CTkButton(parent, text="🤖  Start Recognition",
                                       command=self._toggle_recog,
                                       fg_color="#7b2ff7", height=38, width=238)
        self.recog_btn.pack(**p)

        self.result_lbl = ctk.CTkLabel(
            parent, text="Waiting…",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT, corner_radius=8,
            width=238, height=54)
        self.result_lbl.pack(**p)

        self.conf_lbl = ctk.CTkLabel(parent, text="Confidence: –",
                                     font=ctk.CTkFont(size=11))
        self.conf_lbl.pack()

        self.conf_bar = ctk.CTkProgressBar(parent, width=238)
        self.conf_bar.pack(**p)
        self.conf_bar.set(0)

        ctk.CTkFrame(parent, height=1, fg_color="gray").pack(fill='x', padx=14, pady=10)

        ctk.CTkLabel(parent, text="🛠  Tools",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(**p, anchor='w')

        ctk.CTkButton(parent, text="📸  Capture Snapshot",
                      command=self._snapshot,
                      fg_color=COLOR_PRIMARY, width=238).pack(**p)
        ctk.CTkButton(parent, text="📁  Import & Test Image",
                      command=self._import_test,
                      fg_color=COLOR_PRIMARY, width=238).pack(**p)

        ctk.CTkFrame(parent, height=1, fg_color="gray").pack(fill='x', padx=14, pady=10)
        ctk.CTkLabel(parent, text="⏱  Last Access:",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(**p, anchor='w')
        self.last_lbl = ctk.CTkLabel(parent, text="No access yet",
                                     font=ctk.CTkFont(size=10), wraplength=238)
        self.last_lbl.pack(**p)

    def _start_cam(self):
        val = self.cam_var.get()
        if "IP" in val:
            url = self.ip_ent.get().strip()
            if not url:
                messagebox.showerror("خطأ", "أدخل URL الكاميرا")
                return
            ok, msg = self.camera.start_camera(url)
        else:
            idx = int(val.split()[1])
            ok, msg = self.camera.start_camera(idx)
        self.status_bar.configure(
            text="🟢  Camera Active" if ok else f"❌  {msg}",
            text_color=COLOR_SUCCESS if ok else COLOR_DANGER)
        if not ok:
            messagebox.showerror("خطأ", msg)

    def _stop_cam(self):
        self.recog_on = False
        self.camera.stop_camera()
        self.cam_lbl.configure(image=None, text="📷  Camera Offline")
        self.status_bar.configure(text="⚪  Camera Inactive", text_color="gray")

    def _toggle_recog(self):
        self.recog_on = not self.recog_on
        if self.recog_on:
            self.recog_btn.configure(text="⏹  Stop Recognition",
                                     fg_color=COLOR_DANGER)
            self.face_rec.load_known_faces()
        else:
            self.recog_btn.configure(text="🤖  Start Recognition",
                                     fg_color="#7b2ff7")
            self.result_lbl.configure(text="Stopped", text_color="gray")

    def _start_loop(self):
        def loop():
            while self.running:
                try:
                    frame = self.camera.get_current_frame()
                    if frame is not None:
                        disp = frame.copy()
                        if self.recog_on:
                            now = time.time()
                            results, _ = self.face_rec.recognize_face(disp)
                            if results:
                                if self.face_rec.detect_tailgating(len(results)):
                                    self.after(0, self._on_tailgating)
                                elif now - self.last_ts > self.cooldown:
                                    self.last_ts = now
                                    self.after(0, self._process, results[0])
                            disp = self.face_rec.draw_face_boxes(disp, results)
                        rgb   = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
                        img   = Image.fromarray(rgb).resize((620, 445))
                        photo = ImageTk.PhotoImage(image=img)
                        self.cam_lbl.configure(image=photo, text="")
                        self.cam_lbl.image = photo
                except Exception:
                    pass
                time.sleep(0.033)
        threading.Thread(target=loop, daemon=True).start()

    def _process(self, result):
        auth = result['is_authorized']
        name = result['name']
        conf = result['confidence']
        if auth:
            self.result_lbl.configure(
                text=f"✅  {name}\nAUTHORIZED",
                text_color=COLOR_SUCCESS, fg_color="#1a4a2e")
            self.conf_lbl.configure(text=f"Confidence: {conf:.1%}")
            self.conf_bar.set(conf)
            self.door.open_door(reason=f"face:{name}")
            self.audio.play_success()
            self.db.add_log(name, "authorized", conf, user_id=result['user_id'])
            self.last_lbl.configure(
                text=f"✅  {name}\n{datetime.now().strftime('%H:%M:%S')}")
        else:
            self.result_lbl.configure(
                text="❌  UNKNOWN\nDENIED",
                text_color=COLOR_DANGER, fg_color="#4a1a1a")
            self.conf_bar.set(0)
            snap   = self.camera.capture_snapshot("denied")
            locked = self.door.record_failed_attempt(MAX_FAILED_ATTEMPTS)
            self.audio.play_denied()
            self.db.add_log("Unknown", "denied", 0,
                            snapshot_path=snap or '',
                            rejection_reason="Face not recognized")
            if locked:
                if self.panic_atk:
                    self.panic_atk.trigger_max_attempts()
                self.status_bar.configure(
                    text="🔴  SYSTEM LOCKED!",
                    text_color=COLOR_DANGER)

    def _on_tailgating(self):
        self.result_lbl.configure(text="⚠️  TAILGATING\nDETECTED!",
                                  text_color=COLOR_WARNING)
        self.audio.play_warning()
        if self.panic_atk:
            self.panic_atk.trigger_tailgating()
        else:
            self.door.close_door(reason="tailgating")
            snap = self.camera.capture_snapshot("tailgating")
            self.db.add_log("Multiple Persons", "denied", 0,
                            snapshot_path=snap or '',
                            rejection_reason="Tailgating")

    def _snapshot(self):
        path = self.camera.capture_snapshot("manual")
        if path:
            messagebox.showinfo("✅", f"تم الحفظ:\n{path}")
        else:
            messagebox.showerror("خطأ", "الكاميرا غير نشطة")

    def _import_test(self):
        path = filedialog.askopenfilename(
            title="اختر صورة",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            messagebox.showerror("خطأ", "تعذّر قراءة الصورة")
            return
        results, _ = self.face_rec.recognize_face(frame)
        if results:
            self._process(results[0])
        else:
            messagebox.showinfo("نتيجة", "لم يُكتشف وجه في الصورة")

    def destroy(self):
        self.running = False
        super().destroy()


# =============================================================
#  👥  User Management
# =============================================================
class UserManagement(ctk.CTkFrame):
    def __init__(self, parent, db, face_rec):
        super().__init__(parent, fg_color=COLOR_DARK_BG)
        self.db           = db
        self.face_rec     = face_rec
        self.selected_uid = None
        self._build()
        self._reload_list()

    def _build(self):
        ctk.CTkLabel(self, text="👥  User Management",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(padx=15, pady=(15, 8), anchor='w')
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill='both', expand=True, padx=15, pady=4)
        self._build_list(body)
        self._build_form(body)

    def _build_list(self, parent):
        f = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=10)
        f.pack(side='left', fill='both', expand=True, padx=(0, 5))

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill='x', padx=10, pady=10)
        self.search_ent = ctk.CTkEntry(row, placeholder_text="🔍  Search…")
        self.search_ent.pack(fill='x', expand=True)
        self.search_ent.bind('<KeyRelease>',
                             lambda e: self._reload_list(self.search_ent.get() or None))

        self.list_scroll = ctk.CTkScrollableFrame(f, fg_color="transparent")
        self.list_scroll.pack(fill='both', expand=True, padx=10)

        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.pack(fill='x', padx=10, pady=10)
        ctk.CTkButton(btns, text="➕  Add New", command=self._new_user,
                      fg_color=COLOR_SUCCESS, width=120
                      ).pack(side='left', padx=(0, 6))
        ctk.CTkButton(btns, text="🗑  Delete", command=self._delete_user,
                      fg_color=COLOR_DANGER, width=120).pack(side='left')

    def _build_form(self, parent):
        f = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG,
                         corner_radius=10, width=340)
        f.pack(side='right', fill='y', padx=(5, 0))
        f.pack_propagate(False)
        p = dict(padx=18, pady=4)

        ctk.CTkLabel(f, text="✏️  User Details",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(14, 6))
        ctk.CTkLabel(f, text="Name:").pack(anchor='w', **p)
        self.name_ent = ctk.CTkEntry(f, placeholder_text="Full name", width=295)
        self.name_ent.pack(**p)
        ctk.CTkLabel(f, text="Role:").pack(anchor='w', **p)
        self.role_var = ctk.StringVar(value="user")
        ctk.CTkOptionMenu(f, values=["user", "admin", "guest", "staff"],
                          variable=self.role_var, width=295).pack(**p)
        ctk.CTkLabel(f, text="Notes:").pack(anchor='w', **p)
        self.notes_box = ctk.CTkTextbox(f, height=70, width=295)
        self.notes_box.pack(**p)

        ctk.CTkFrame(f, height=1, fg_color="gray").pack(fill='x', padx=18, pady=10)
        ctk.CTkLabel(f, text="📸  Face Images",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor='w', **p)
        ctk.CTkButton(f, text="📁  Import Face Image(s)",
                      command=self._import_face,
                      fg_color=COLOR_PRIMARY, width=295).pack(**p)
        self.img_scroll = ctk.CTkScrollableFrame(f, height=90, fg_color="transparent")
        self.img_scroll.pack(fill='x', padx=18)

        ctk.CTkFrame(f, height=1, fg_color="gray").pack(fill='x', padx=18, pady=10)
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill='x', padx=18, pady=(0, 14))
        ctk.CTkButton(row, text="💾  Save", command=self._save_user,
                      fg_color=COLOR_SUCCESS, width=130).pack(side='left', padx=(0, 6))
        ctk.CTkButton(row, text="🔄  Reset", command=self._reset_form,
                      fg_color="gray", width=130).pack(side='right')

    def _reload_list(self, query=None):
        for w in self.list_scroll.winfo_children():
            w.destroy()
        users = self.db.search_users(query) if query else self.db.get_all_users()
        if not users:
            ctk.CTkLabel(self.list_scroll, text="No users found",
                         text_color="gray").pack(pady=20)
            return
        for u in users:
            row = ctk.CTkFrame(self.list_scroll, fg_color=COLOR_ACCENT,
                               corner_radius=5, height=52, cursor="hand2")
            row.pack(fill='x', pady=2)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=f"👤  {u['name']}",
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).pack(side='left', padx=10)
            ctk.CTkLabel(row, text=f"[{u['role']}]",
                         font=ctk.CTkFont(size=10), text_color="gray"
                         ).pack(side='left')
            for widget in [row] + list(row.winfo_children()):
                widget.bind('<Button-1>', lambda e, uu=u: self._select(uu))

    def _select(self, user):
        self.selected_uid = user['id']
        self.name_ent.delete(0, 'end')
        self.name_ent.insert(0, user['name'])
        self.role_var.set(user['role'])
        self.notes_box.delete('1.0', 'end')
        if user.get('notes'):
            self.notes_box.insert('1.0', user['notes'])
        self._reload_images()

    def _reload_images(self):
        for w in self.img_scroll.winfo_children():
            w.destroy()
        if not self.selected_uid:
            return
        imgs = self.db.get_user_images(self.selected_uid)
        if not imgs:
            ctk.CTkLabel(self.img_scroll, text="No images yet",
                         text_color="gray", font=ctk.CTkFont(size=10)).pack()
            return
        for img in imgs:
            ctk.CTkLabel(self.img_scroll,
                         text=f"📸  {os.path.basename(img['image_path'])}",
                         font=ctk.CTkFont(size=10)).pack(anchor='w')

    def _import_face(self):
        if not self.selected_uid:
            messagebox.showwarning("تحذير", "احفظ المستخدم أولاً")
            return
        paths = filedialog.askopenfilenames(
            title="اختر صور الوجه",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        added = 0
        for path in paths:
            ok, msg = self.face_rec.validate_face_image(path)
            if not ok:
                messagebox.showwarning("صورة غير صالحة",
                                       f"{os.path.basename(path)}\n{msg}")
                continue
            user_dir = os.path.join(AUTHORIZED_DIR, str(self.selected_uid))
            os.makedirs(user_dir, exist_ok=True)
            fname = f"face_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}.jpg"
            dest  = os.path.join(user_dir, fname)
            shutil.copy2(path, dest)
            self.db.add_user_image(self.selected_uid, dest)
            added += 1
        if added:
            messagebox.showinfo("✅", f"تمت إضافة {added} صورة/صور")
            self.face_rec.load_known_faces()
            self._reload_images()

    def _new_user(self):
        self.selected_uid = None
        self._reset_form()

    def _save_user(self):
        name = self.name_ent.get().strip()
        if not name:
            messagebox.showerror("خطأ", "أدخل اسم المستخدم")
            return
        role  = self.role_var.get()
        notes = self.notes_box.get('1.0', 'end').strip()
        if self.selected_uid:
            self.db.update_user(self.selected_uid, name, role, notes)
            messagebox.showinfo("✅", "تم التحديث")
        else:
            uid = self.db.add_user(name, role, notes)
            self.selected_uid = uid
            messagebox.showinfo("✅",
                                f"تمت الإضافة (ID: {uid})\nيمكنك الآن إضافة صوره")
        self._reload_list()

    def _delete_user(self):
        if not self.selected_uid:
            messagebox.showwarning("تحذير", "اختر مستخدماً أولاً")
            return
        u = self.db.get_user_by_id(self.selected_uid)
        if messagebox.askyesno("تأكيد", f"حذف '{u['name']}'؟"):
            self.db.delete_user(self.selected_uid)
            self.face_rec.load_known_faces()
            self._reset_form()
            self._reload_list()

    def _reset_form(self):
        self.selected_uid = None
        self.name_ent.delete(0, 'end')
        self.role_var.set("user")
        self.notes_box.delete('1.0', 'end')
        for w in self.img_scroll.winfo_children():
            w.destroy()


# =============================================================
#  📋  Access Logs
# =============================================================
class LogsWindow(ctk.CTkFrame):
    def __init__(self, parent, db):
        super().__init__(parent, fg_color=COLOR_DARK_BG)
        self.db = db
        self._build()
        self._load()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill='x', padx=15, pady=(15, 6))
        ctk.CTkLabel(hdr, text="📋  Access Logs",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side='left')
        ctk.CTkButton(hdr, text="🔄  Refresh", command=self._load,
                      fg_color=COLOR_PRIMARY, width=100).pack(side='right')

        flt = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=8)
        flt.pack(fill='x', padx=15, pady=4)
        ctk.CTkLabel(flt, text="Filter:").pack(side='left', padx=12, pady=8)
        self.filter_var = ctk.StringVar(value="All")
        for opt in ["All", "Authorized", "Denied"]:
            ctk.CTkRadioButton(flt, text=opt, variable=self.filter_var,
                               value=opt, command=self._load
                               ).pack(side='left', padx=10)

        tbl_f = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=8)
        tbl_f.pack(fill='both', expand=True, padx=15, pady=6)

        cols = ('Time', 'Name', 'Status', 'Confidence', 'Reason', 'Snapshot')
        self.tree = ttk.Treeview(tbl_f, columns=cols, show='headings', height=20)
        for c, w in zip(cols, [155, 150, 100, 100, 210, 130]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)

        vsb = ttk.Scrollbar(tbl_f, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True, padx=4, pady=4)
        vsb.pack(side='right', fill='y')

        sty = ttk.Style()
        sty.theme_use("clam")
        sty.configure("Treeview",
                       background=COLOR_CARD_BG, foreground="white",
                       fieldbackground=COLOR_CARD_BG, rowheight=32)
        sty.configure("Treeview.Heading",
                       background=COLOR_ACCENT, foreground="white",
                       font=('Segoe UI', 10, 'bold'))
        sty.map("Treeview", background=[('selected', COLOR_PRIMARY)])
        self.tree.tag_configure('authorized', foreground='#00C853')
        self.tree.tag_configure('denied',     foreground='#FF1744')

        self.stats_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self.stats_lbl.pack(pady=4)

    def _load(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        logs  = self.db.get_all_logs(limit=500)
        filt  = self.filter_var.get().lower()
        an, dn = 0, 0
        for log in logs:
            if filt != "all" and log['status'] != filt:
                continue
            tag = 'authorized' if log['status'] == 'authorized' else 'denied'
            an += (tag == 'authorized')
            dn += (tag == 'denied')
            conf = f"{log['confidence']:.1%}" if log.get('confidence') else "–"
            snap = "📸  Yes" if log.get('snapshot_path') else "–"
            self.tree.insert('', 'end',
                             values=(log['timestamp'], log['user_name'],
                                     log['status'].upper(), conf,
                                     log.get('rejection_reason') or '–', snap),
                             tags=(tag,))
        self.stats_lbl.configure(
            text=f"✅  Authorized: {an}   |   ❌  Denied: {dn}   |   📊  Total: {an+dn}")


# =============================================================
#  🔔  Alert Banner
# =============================================================
class AlertBanner(ctk.CTkFrame):
    COLORS = {
        AlertLevel.INFO:    ("#1565C0", "ℹ️"),
        AlertLevel.WARNING: ("#F57F17", "⚠️"),
        AlertLevel.DANGER:  ("#B71C1C", "🔴"),
        AlertLevel.PANIC:   ("#4A0000", "🚨"),
    }

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLOR_DANGER,
                         corner_radius=0, height=0)
        self._visible = False
        self.icon_lbl = ctk.CTkLabel(self, text="",
                                      font=ctk.CTkFont(size=18),
                                      text_color="white")
        self.icon_lbl.pack(side='left', padx=12)
        self.msg_lbl = ctk.CTkLabel(self, text="",
                                     font=ctk.CTkFont(size=13, weight="bold"),
                                     text_color="white")
        self.msg_lbl.pack(side='left', fill='x', expand=True)
        ctk.CTkButton(self, text="✕", width=30, height=30,
                      fg_color="transparent", hover_color="#c0392b",
                      command=self.hide).pack(side='right', padx=8)

    def show(self, alert):
        color, icon = self.COLORS.get(alert.level, ("#1565C0", "🔔"))
        self.configure(fg_color=color, height=44)
        self.icon_lbl.configure(text=icon)
        self.msg_lbl.configure(text=f"{alert.title}  —  {alert.message}")
        if not self._visible:
            children = self.master.winfo_children()
            if children:
                self.pack(fill='x', before=children[0])
            else:
                self.pack(fill='x')
            self._visible = True
        if alert.level == AlertLevel.INFO:
            self.after(4000, self.hide)

    def hide(self):
        if self._visible:
            self.pack_forget()
            self._visible = False


# =============================================================
#  🖼️  Main Window  (النافذة الرئيسية)
# =============================================================
class MainWindow:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("🚪  Smart Access Control System")
        self.root.geometry("1340x840")
        self.root.minsize(1100, 720)

        # ── Core modules ──────────────────────────────────
        self.db        = Database()
        self.audio     = AudioModule()
        self.door      = DoorController(auto_close_delay=DOOR_OPEN_DURATION)
        self.camera    = CameraModule()
        self.face_rec  = FaceRecognitionModule(self.db)
        self.alerts    = AlertManager(max_alerts=200)
        self.panic_atk = PanicAttack(self.door, self.alerts,
                                      db=self.db, camera=self.camera)

        self.door.add_callback('on_open',       self._cb_open)
        self.door.add_callback('on_close',      self._cb_close)
        self.door.add_callback('on_auto_close', self._cb_close)
        self.alerts.on_alert(self._cb_alert)
        self.panic_atk.on_panic(self._cb_panic)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.alerts.info("النظام جاهز", "Smart Access Control تم تشغيله ✅")

    # ── Build UI ──────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self.alert_banner = AlertBanner(self.root)
        self.main_frame = ctk.CTkFrame(self.root, fg_color=COLOR_DARK_BG)
        self.main_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self._build_sidebar()
        self.content = ctk.CTkFrame(self.main_frame, fg_color=COLOR_DARK_BG)
        self.content.pack(side='right', fill='both', expand=True)
        self._show_dashboard()

    def _build_header(self):
        hdr = ctk.CTkFrame(self.root, fg_color=COLOR_ACCENT,
                           height=58, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="🚪  Smart Access Control System",
                     font=ctk.CTkFont(size=21, weight="bold"),
                     text_color="white").pack(side='left', padx=18)

        ctk.CTkButton(hdr, text="🚨  PANIC ATTACK",
                      command=self._trigger_panic_manual,
                      fg_color="#7b0000", hover_color="#c0392b",
                      width=145, height=40,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      border_color="#ff4444", border_width=2
                      ).pack(side='right', padx=10)

        ctk.CTkButton(hdr, text="🔓  Emergency Open",
                      command=self._emergency_open,
                      fg_color="#e67e22", hover_color="#f39c12",
                      width=140, height=40,
                      font=ctk.CTkFont(size=12, weight="bold")
                      ).pack(side='right', padx=4)

        self.alert_count_btn = ctk.CTkButton(
            hdr, text="🔔 0",
            command=self._show_alerts_popup,
            fg_color="transparent", border_width=1,
            width=60, height=38, font=ctk.CTkFont(size=13))
        self.alert_count_btn.pack(side='right', padx=6)

        self.hdr_door = ctk.CTkLabel(
            hdr, text="🔴  LOCKED",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_DANGER)
        self.hdr_door.pack(side='right', padx=16)

        self._theme_mode = "dark"
        ctk.CTkButton(hdr, text="☀️", command=self._toggle_theme,
                      width=38, height=38,
                      fg_color="transparent").pack(side='right', padx=4)

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self.main_frame, fg_color=COLOR_CARD_BG,
                          width=220, corner_radius=10)
        sb.pack(side='left', fill='y', padx=(8, 4), pady=8)
        sb.pack_propagate(False)

        ctk.CTkLabel(sb, text="NAVIGATION",
                     font=ctk.CTkFont(size=10),
                     text_color="gray").pack(pady=(18, 4))

        for txt, cmd in [
            ("🏠   Dashboard",   self._show_dashboard),
            ("🎥   Camera View", self._show_camera),
            ("👥   Users",       self._show_users),
            ("📋   Access Logs", self._show_logs),
            ("🔔   Alerts",      self._show_alerts_popup),
        ]:
            ctk.CTkButton(sb, text=txt, command=cmd,
                          fg_color="transparent",
                          hover_color=COLOR_ACCENT,
                          anchor='w', height=44,
                          font=ctk.CTkFont(size=13)
                          ).pack(fill='x', padx=8, pady=2)

        ctk.CTkFrame(sb, height=1, fg_color=COLOR_ACCENT
                     ).pack(fill='x', padx=10, pady=12)

        ctk.CTkLabel(sb, text="QUICK CONTROL",
                     font=ctk.CTkFont(size=10),
                     text_color="gray").pack(pady=(2, 4))

        self.door_lbl = ctk.CTkLabel(
            sb, text="🔴  LOCKED",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_DANGER)
        self.door_lbl.pack(pady=6)

        ctk.CTkButton(sb, text="🚪  Open Door",
                      command=self._manual_open,
                      fg_color=COLOR_SUCCESS, height=38
                      ).pack(fill='x', padx=10, pady=2)

        ctk.CTkButton(sb, text="🔒  Close Door",
                      command=self._manual_close,
                      fg_color=COLOR_PRIMARY, height=38
                      ).pack(fill='x', padx=10, pady=2)

        ctk.CTkFrame(sb, height=1, fg_color="#7b0000"
                     ).pack(fill='x', padx=10, pady=10)

        ctk.CTkLabel(sb, text="SECURITY",
                     font=ctk.CTkFont(size=10),
                     text_color="gray").pack(pady=(0, 4))

        self.panic_status_lbl = ctk.CTkLabel(
            sb, text="🟢  System Normal",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_SUCCESS)
        self.panic_status_lbl.pack(pady=2)

        ctk.CTkButton(sb, text="🚨  PANIC ATTACK",
                      command=self._trigger_panic_manual,
                      fg_color="#7b0000", hover_color="#c0392b",
                      height=38, border_width=1, border_color="#ff4444",
                      font=ctk.CTkFont(size=12, weight="bold")
                      ).pack(fill='x', padx=10, pady=2)

        ctk.CTkButton(sb, text="✅  Deactivate Panic",
                      command=self._deactivate_panic,
                      fg_color="#2d6a2d", height=34
                      ).pack(fill='x', padx=10, pady=2)

        ctk.CTkFrame(sb, height=1, fg_color=COLOR_ACCENT
                     ).pack(fill='x', padx=10, pady=10)

        self.sound_btn = ctk.CTkButton(
            sb, text="🔊  Sound: ON",
            command=self._toggle_sound,
            fg_color="transparent", border_width=1, height=32)
        self.sound_btn.pack(fill='x', padx=10, pady=2)

        ctk.CTkFrame(sb, height=1, fg_color=COLOR_ACCENT
                     ).pack(fill='x', padx=10, pady=10)

        self.stats_lbl = ctk.CTkLabel(
            sb, text="", font=ctk.CTkFont(size=11), justify='left')
        self.stats_lbl.pack(padx=10)
        self._update_stats()

    # ── Page switchers ────────────────────────────────────
    def _clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _show_dashboard(self):
        self._clear()
        Dashboard(self.content, self.db, self.door,
                  self.camera, self.face_rec).pack(fill='both', expand=True)

    def _show_camera(self):
        self._clear()
        CameraWindow(self.content, self.camera, self.face_rec,
                     self.door, self.db, self.audio,
                     self.panic_atk).pack(fill='both', expand=True)

    def _show_users(self):
        self._clear()
        UserManagement(self.content, self.db,
                       self.face_rec).pack(fill='both', expand=True)

    def _show_logs(self):
        self._clear()
        LogsWindow(self.content, self.db).pack(fill='both', expand=True)

    # ── Panic Attack ──────────────────────────────────────
    def _trigger_panic_manual(self):
        win = ctk.CTkToplevel(self.root)
        win.title("🚨 PANIC ATTACK")
        win.geometry("420x300")
        win.grab_set()
        win.configure(fg_color="#2d0000")

        ctk.CTkLabel(win, text="🚨  PANIC ATTACK",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="#ff4444").pack(pady=(20, 4))
        ctk.CTkLabel(win, text="اختر نوع حالة الطوارئ:",
                     font=ctk.CTkFont(size=13),
                     text_color="white").pack(pady=(0, 10))

        cfg = dict(height=40, width=360, font=ctk.CTkFont(size=12, weight="bold"))

        def do(reason, details=""):
            win.destroy()
            self.panic_atk.trigger(reason=reason, details=details,
                                   lock_door=True, lock_system=True, lock_duration=60)
            self.audio.play_panic()

        ctk.CTkButton(win, text="🔴  دخيل / Intruder Detected",
                      command=lambda: do(PanicAttack.REASON_INTRUDER),
                      fg_color="#7b0000", **cfg).pack(pady=4)
        ctk.CTkButton(win, text="🖼️  محاولة خداع / Spoofing",
                      command=lambda: do(PanicAttack.REASON_SPOOFING),
                      fg_color="#7b3000", **cfg).pack(pady=4)
        ctk.CTkButton(win, text="🚪  اقتحام قسري / Forced Entry",
                      command=lambda: do(PanicAttack.REASON_FORCED_ENTRY),
                      fg_color="#4a0050", **cfg).pack(pady=4)
        ctk.CTkButton(win, text="❌  إلغاء",
                      command=win.destroy,
                      fg_color="gray", **cfg).pack(pady=(8, 0))

    def _deactivate_panic(self):
        if self.panic_atk.is_active:
            self.panic_atk.deactivate(by="manual_user")
            self.audio.play_success()
            self.panic_status_lbl.configure(text="🟢  System Normal",
                                             text_color=COLOR_SUCCESS)
        else:
            self.alerts.info("لا توجد طوارئ", "النظام يعمل بشكل طبيعي")

    def _emergency_open(self):
        if messagebox.askyesno("🔓 Emergency Open", "فتح الباب فوراً؟"):
            self.door.panic_mode()
            self.audio.play_success()
            self.db.add_log("Emergency Open", "authorized",
                            event_type="emergency_open")
            self.alerts.warning("🔓 Emergency Open", "تم فتح الباب يدوياً")

    # ── Alerts popup ──────────────────────────────────────
    def _show_alerts_popup(self):
        win = ctk.CTkToplevel(self.root)
        win.title("🔔 System Alerts")
        win.geometry("560x460")
        win.grab_set()

        hdr = ctk.CTkFrame(win, fg_color=COLOR_CARD_BG, height=46)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🔔  System Alerts",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(side='left', padx=12)
        ctk.CTkButton(hdr, text="✓ Mark all read",
                      command=lambda: [self.alerts.mark_all_read(),
                                       self._refresh_count(), win.destroy()],
                      fg_color=COLOR_SUCCESS, width=130, height=32
                      ).pack(side='right', padx=10)

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill='both', expand=True, padx=10, pady=8)

        COLS = {
            AlertLevel.INFO:    ("#1565C0", "ℹ️"),
            AlertLevel.WARNING: ("#7a5c00", "⚠️"),
            AlertLevel.DANGER:  ("#7b0000", "🔴"),
            AlertLevel.PANIC:   ("#4a0000", "🚨"),
        }
        all_alerts = list(reversed(self.alerts.get_all()))
        if not all_alerts:
            ctk.CTkLabel(scroll, text="لا توجد إنذارات",
                         text_color="gray").pack(pady=30)
        else:
            for a in all_alerts:
                color, icon = COLS.get(a.level, ("#1565C0", "🔔"))
                row = ctk.CTkFrame(scroll, fg_color=color,
                                   corner_radius=6, height=62)
                row.pack(fill='x', pady=3)
                row.pack_propagate(False)
                ctk.CTkLabel(row, text=icon,
                             font=ctk.CTkFont(size=20)
                             ).pack(side='left', padx=10)
                info = ctk.CTkFrame(row, fg_color="transparent")
                info.pack(side='left', fill='both', expand=True)
                ctk.CTkLabel(info,
                             text=f"{a.title}{'  🔵 NEW' if not a.read else ''}",
                             font=ctk.CTkFont(size=12, weight="bold"),
                             text_color="white").pack(anchor='w')
                ctk.CTkLabel(info, text=a.message,
                             font=ctk.CTkFont(size=10),
                             text_color="#cccccc",
                             wraplength=360).pack(anchor='w')
                ctk.CTkLabel(row, text=a.timestamp,
                             font=ctk.CTkFont(size=9),
                             text_color="#aaaaaa"
                             ).pack(side='right', padx=8)

        self.alerts.mark_all_read()
        self._refresh_count()

    # ── Callbacks ─────────────────────────────────────────
    def _cb_open(self, **_):
        self.root.after(0, self._refresh_door_ui, True)

    def _cb_close(self, **_):
        self.root.after(0, self._refresh_door_ui, False)

    def _cb_alert(self, alert):
        self.root.after(0, self._handle_alert, alert)

    def _handle_alert(self, alert):
        self.alert_banner.show(alert)
        self._refresh_count()
        if alert.level == AlertLevel.PANIC:
            self.audio.play_panic()
        elif alert.level == AlertLevel.DANGER:
            self.audio.play_denied()
        elif alert.level == AlertLevel.WARNING:
            self.audio.play_warning()

    def _cb_panic(self, result):
        self.root.after(0, self._handle_panic_ui, result)

    def _handle_panic_ui(self, result):
        self.panic_status_lbl.configure(text="🚨  PANIC ACTIVE!",
                                         text_color="#ff4444")
        win = ctk.CTkToplevel(self.root)
        win.title("🚨 PANIC ATTACK ACTIVE")
        win.geometry("400x200")
        win.configure(fg_color="#2d0000")
        win.lift()
        win.grab_set()
        ctk.CTkLabel(win, text="🚨  PANIC ATTACK ACTIVE",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#ff4444").pack(pady=20)
        ctk.CTkLabel(win,
                     text=f"السبب: {result['reason']}\nالوقت: {result['timestamp']}",
                     font=ctk.CTkFont(size=13), text_color="white").pack()
        ctk.CTkButton(win, text="✅  حسناً", command=win.destroy,
                      fg_color="#7b0000", width=160).pack(pady=20)
        win.after(8000, win.destroy)

    # ── Helpers ───────────────────────────────────────────
    def _manual_open(self):
        ok, _ = self.door.open_door(reason="manual")
        if ok:
            self.audio.play_success()
            self.db.add_log("Manual", "authorized", event_type="manual_open")
            self.alerts.info("🚪 الباب مفتوح", "تم الفتح اليدوي")

    def _manual_close(self):
        self.door.close_door(reason="manual")
        self.alerts.info("🔒 الباب مغلق", "تم الإغلاق اليدوي")

    def _refresh_door_ui(self, is_open):
        txt   = "🟢  OPEN"   if is_open else "🔴  LOCKED"
        color = COLOR_SUCCESS if is_open else COLOR_DANGER
        self.door_lbl.configure(text=txt, text_color=color)
        self.hdr_door.configure(text=txt, text_color=color)

    def _refresh_count(self):
        n = self.alerts.unread_count()
        self.alert_count_btn.configure(
            text=f"🔔 {n}",
            fg_color="#7b0000" if n > 0 else "transparent")

    def _toggle_sound(self):
        on = self.audio.toggle()
        self.sound_btn.configure(
            text=f"{'🔊' if on else '🔇'}  Sound: {'ON' if on else 'OFF'}")

    def _toggle_theme(self):
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        ctk.set_appearance_mode(self._theme_mode)

    def _update_stats(self):
        s = self.db.get_stats()
        self.stats_lbl.configure(
            text=f"👥  Users:        {s['total_users']}\n"
                 f"✅  Authorized:  {s['authorized']}\n"
                 f"❌  Denied:       {s['denied']}")
        self.root.after(10_000, self._update_stats)

    def _on_close(self):
        self.camera.stop_camera()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# =============================================================
#  🚀  نقطة البداية
# =============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  🚪  Smart Access Control System  ")
    print("=" * 55)
    app = MainWindow()
    app.run()
