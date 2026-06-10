# =============================================================================
# نظام إدارة الكنيسة - كنيسة الشهيدة دميانة
# الإصدار: 2.0.0 (مُحسَّن بالكامل وفق تقرير التدقيق الأمني)
# =============================================================================
# المتطلبات: streamlit, gspread, pandas, plotly, PyJWT, requests
# التثبيت: pip install streamlit gspread pandas plotly PyJWT requests
# =============================================================================

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import uuid
import json
import random
import string
import jwt
import time
import requests
from functools import wraps
import hashlib
import os

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
CACHE_TTL_SECONDS = 120        # صلاحية التخزين المؤقت (ثانية)
MIN_PASSWORD_LENGTH = 8        # الحد الأدنى لطول كلمة المرور
TOKEN_EXPIRY_HOURS = 1         # صلاحية رمز JWT (ساعة واحدة للرمز المؤقت)
MAX_LOGIN_ATTEMPTS = 5         # أقصى عدد محاولات تسجيل دخول (غير مطبق حالياً)
RETRY_MAX_ATTEMPTS = 5         # عدد محاولات إعادة الاتصال بـ Google API
RETRY_BASE_DELAY = 2           # التأخير الأساسي بين المحاولات (ثانية)

st.set_page_config(
    page_title="نظام- كنيسة الشهيدة دميانة",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# تجزئة كلمات المرور باستخدام PBKDF2 (لا توجد خوارزمية bcrypt افتراضية)
# =============================================================================
def hash_password(plain_password: str) -> str:
    """
    تجزئة كلمة المرور باستخدام PBKDF2-HMAC-SHA256 مع salt عشوائي.
    التنسيق: salt_hex$hash_hex
    """
    if not plain_password:
        raise ValueError("كلمة المرور لا يمكن أن تكون فارغة")
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        plain_password.encode('utf-8'),
        salt,
        100_000  # عدد التكرارات الموصى به
    )
    return salt.hex() + '$' + key.hex()

def verify_password(plain_password: str, hashed: str) -> bool:
    """التحقق من كلمة المرور مقابل التجزئة المخزنة."""
    try:
        salt_hex, key_hex = hashed.split('$')
        salt = bytes.fromhex(salt_hex)
        stored_key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt,
            100_000
        )
        return new_key == stored_key
    except Exception:
        return False

# =============================================================================
# حماية من حقن الصيغ في Google Sheets
# =============================================================================
def safe_str_for_sheets(value) -> str:
    """
    تحويل القيمة إلى نص مع إضافة علامة اقتباس (') إذا بدأت القيمة بـ = أو + أو - أو @
    لمنع Google Sheets من تفسيرها كصيغة.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value)
    if s and s[0] in ('=', '+', '-', '@'):
        s = "'" + s
    return s

# =============================================================================
# تحميل إعدادات الأمان والاتصال
# =============================================================================
def get_telegram_config():
    """استرداد إعدادات بوت Telegram من الأسرار."""
    try:
        return st.secrets["telegram"]["bot_token"], st.secrets["telegram"]["chat_id"]
    except Exception:
        return None, None

def get_support_config():
    """استرداد معلومات الدعم الفني."""
    try:
        return (
            st.secrets.get("support", {}).get("contact_name", "مسؤول النظام"),
            st.secrets.get("support", {}).get("whatsapp", "")
        )
    except Exception:
        return "مسؤول النظام", ""

def get_credentials():
    """بناء كائن Credentials من حساب الخدمة المخزن في الأسرار."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return creds
    except Exception as e:
        st.error(f"❌ خطأ في بيانات اعتماد Google: {e}")
        st.stop()

def get_spreadsheet_id():
    """استرداد معرّف جدول البيانات من الأسرار."""
    try:
        sid = st.secrets["sheets"]["spreadsheet_id"]
        if not sid or not isinstance(sid, str) or sid.strip() == "":
            st.error("❌ معرف جدول البيانات غير صالح.")
            st.stop()
        return sid.strip()
    except Exception as e:
        st.error(f"❌ لم يتم العثور على spreadsheet_id: {e}")
        st.stop()

def get_jwt_secret():
    """
    استرداد مفتاح JWT من الأسرار.
    يمنع استخدام القيمة الافتراضية ويجب أن لا يقل طوله عن 16 حرفاً.
    """
    try:
        secret = st.secrets["sheets"]["jwt_secret"]
        if not secret or len(secret) < 16:
            st.error("❌ مفتاح JWT غير آمن. يجب أن يكون طوله 16 حرفًا على الأقل.")
            st.stop()
        return secret
    except KeyError:
        st.error("❌ لم يتم تعيين مفتاح JWT. يرجى إضافة 'jwt_secret' في secrets.toml.")
        st.stop()

# =============================================================================
# التخزين المؤقت العام لمشاركة البيانات بين جميع المستخدمين
# =============================================================================
@st.cache_resource
def get_gspread_client(_credentials_dict):
    """عميل gspread مُعاد استخدامه بين جميع المستخدمين."""
    creds = Credentials.from_service_account_info(
        _credentials_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_sheet_data(spreadsheet_id: str, sheet_name: str, _credentials_dict):
    """
    تحميل بيانات ورقة عمل كاملة مع التخزين المؤقت العام (جميع المستخدمين).
    المعامل _credentials_dict يضمن انتهاء صلاحية التخزين عند تغير الاعتماد.
    """
    try:
        client = get_gspread_client(_credentials_dict)
        spreadsheet = client.open_by_key(spreadsheet_id)
        try:
            ws = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return pd.DataFrame()
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df.dropna(how='all', axis=1, inplace=True)
        return df.astype(object)
    except Exception as e:
        st.error(f"❌ فشل تحميل {sheet_name}: {str(e)}")
        return pd.DataFrame()

def clear_sheet_cache(spreadsheet_id: str, sheet_name: str, credentials_dict):
    """مسح التخزين المؤقت لورقة عمل محددة بعد تعديلها."""
    load_sheet_data.clear(spreadsheet_id, sheet_name, credentials_dict)

# =============================================================================
# مُزَيِّن إعادة المحاولة (Retry Decorator)
# =============================================================================
def retry_operation(max_retries=RETRY_MAX_ATTEMPTS, base_delay=RETRY_BASE_DELAY):
    """مُزَيِّن لإعادة محاولة تنفيذ الدالة عند فشل اتصال Google API."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        st.warning(f"⏳ النظام مشغول، جاري المحاولة تاني... (محاولة {attempt+1})")
                        time.sleep(delay)
                    else:
                        st.error("❌ النظام مشغول حالياً، من فضلك انتظر دقيقة وحمّل الصفحة تاني")
                        raise last_exception
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(base_delay * (2 ** attempt))
                    else:
                        raise last_exception
            return None
        return wrapper
    return decorator

# =============================================================================
# كلاس قاعدة البيانات (Google Sheets) المُحسَّن
# =============================================================================
class Database:
    """طبقة الوصول إلى البيانات باستخدام Google Sheets مع تحسينات الأمان والأداء."""

    def __init__(self, spreadsheet_id, credentials_dict):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_dict = credentials_dict
        self.client = get_gspread_client(credentials_dict)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    @retry_operation()
    def _get_or_create_worksheet(self, name, columns):
        """إرجاع ورقة العمل أو إنشاؤها مع صف الرؤوس إذا لزم الأمر."""
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(columns), 1))
            if columns:
                ws.append_row([safe_str_for_sheets(col) for col in columns])
            return ws

    # ---------- قراءة عامة ----------
    def _sheet_to_df(self, sheet_name):
        return load_sheet_data(self.spreadsheet_id, sheet_name, self.credentials_dict)

    # ---------- كتابة كاملة (للكيانات القابلة للتعديل) ----------
    def _df_to_sheet(self, sheet_name, df, columns):
        """كتابة DataFrame كامل إلى ورقة العمل (يستبدل المحتوى بالكامل)."""
        if not isinstance(df, pd.DataFrame):
            raise ValueError("df must be a DataFrame")
        if not isinstance(columns, list) or not columns:
            raise ValueError("columns must be a non-empty list")
        ws = self._get_or_create_worksheet(sheet_name, columns)
        work_df = df[columns].copy()
        # تطبيق الحماية من حقن الصيغ على جميع القيم
        for col in columns:
            work_df[col] = work_df[col].apply(safe_str_for_sheets)
        ws.clear()
        values = [columns] + work_df.values.tolist()
        ws.update(values)
        clear_sheet_cache(self.spreadsheet_id, sheet_name, self.credentials_dict)

    # ---------- إلحاق صف جديد (للسجلات غير القابلة للتعديل) ----------
    def _append_row(self, sheet_name, row_dict, columns):
        ws = self._get_or_create_worksheet(sheet_name, columns)
        row = [safe_str_for_sheets(row_dict.get(col, "")) for col in columns]
        ws.append_row(row)
        clear_sheet_cache(self.spreadsheet_id, sheet_name, self.credentials_dict)

    # ==================== Users ====================
    def get_users(self):
        return self._sheet_to_df("Users")

    def add_user(self, user_data):
        df = self.get_users()
        if df.empty:
            df = pd.DataFrame(columns=["user_id", "username", "password", "role",
                                       "full_name", "section_id", "phone", "email"])
        # تجزئة كلمة المرور قبل التخزين
        user_data["password"] = hash_password(user_data["password"])
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        self._df_to_sheet("Users", df, ["user_id", "username", "password", "role",
                                        "full_name", "section_id", "phone", "email"])

    def update_user(self, user_id, updates):
        df = self.get_users()
        idx = df[df.user_id == user_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                if k == "password":
                    # إذا تم تحديث كلمة المرور، يجب تجزئتها
                    v = hash_password(v)
                df.at[idx[0], k] = safe_str_for_sheets(v)
            self._df_to_sheet("Users", df, df.columns.tolist())

    def delete_user(self, user_id):
        df = self.get_users()
        df = df[df.user_id != user_id]
        self._df_to_sheet("Users", df, df.columns.tolist())

    # ==================== Sections ====================
    def get_sections(self):
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data):
        if "section_id" not in sec_data or "section_name" not in sec_data:
            raise ValueError("يجب توفير section_id و section_name")
        self._get_or_create_worksheet("Sections", ["section_id", "section_name", "manager_user_id"])
        df = self.get_sections()
        if df.empty:
            df = pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
        new_row = {
            "section_id": sec_data["section_id"],
            "section_name": sec_data["section_name"],
            "manager_user_id": sec_data.get("manager_user_id", "")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    def update_section(self, section_id, updates):
        df = self.get_sections()
        idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = safe_str_for_sheets(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, df.columns.tolist())

    # ==================== Students ====================
    def get_students(self):
        return self._sheet_to_df("Students")

    def add_student(self, student_data):
        df = self.get_students()
        if df.empty:
            df = pd.DataFrame(columns=["student_id", "full_name", "section_id", "teacher_id",
                                       "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])
        student_data["teacher_id"] = ""
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        self._df_to_sheet("Students", df, ["student_id", "full_name", "section_id", "teacher_id",
                                           "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])

    def update_student(self, student_id, updates):
        df = self.get_students()
        idx = df[df.student_id == student_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = safe_str_for_sheets(v)
            self._df_to_sheet("Students", df, df.columns.tolist())

    def delete_student(self, student_id):
        df = self.get_students()
        df = df[df.student_id != student_id]
        self._df_to_sheet("Students", df, df.columns.tolist())

    # ==================== Attendance (سجلات غير قابلة للتعديل) ====================
    def get_attendance(self):
        return self._sheet_to_df("Attendance")

    def append_attendance_record(self, record_dict):
        """إضافة سجل حضور جديد (إلحاق فقط، لا تعديل)."""
        columns = ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"]
        self._append_row("Attendance", record_dict, columns)

    def batch_add_attendance(self, records_list):
        """إضافة مجموعة سجلات حضور مع إزالة التكرار بناءً على record_id."""
        # في هذا الإصدار البسيط نقوم بالإلحاق مباشرة؛ يمكن تحسينه لاحقًا
        for rec in records_list:
            self.append_attendance_record(rec)

    def get_attendance_by_date_section(self, date_str, section_id):
        df = self.get_attendance()
        if df.empty:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    def delete_attendance_record(self, record_id):
        df = self.get_attendance()
        df = df[df.record_id != record_id]
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    # ==================== FollowUp ====================
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record):
        columns = ["record_id", "student_id", "teacher_id", "followup_date",
                   "followup_type", "notes", "regularity_status"]
        self._append_row("FollowUp", record, columns)

    def delete_followup_record(self, record_id):
        df = self.get_followup()
        df = df[df.record_id != record_id]
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date",
                                           "followup_type", "notes", "regularity_status"])

    # ==================== Quizzes ====================
    def get_quizzes(self):
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data):
        df = self.get_quizzes()
        if df.empty:
            df = pd.DataFrame(columns=["quiz_id", "title", "description", "created_by", "section_id",
                                       "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                       "quiz_code", "password", "is_active"])
        df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active"])

    def update_quiz(self, quiz_id, updates):
        df = self.get_quizzes()
        idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = safe_str_for_sheets(v)
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def delete_quiz_keep_results(self, quiz_id):
        df = self.get_quizzes()
        df = df[df.quiz_id != quiz_id]
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active"])
        qdf = self._sheet_to_df("QuizQuestions")
        qdf = qdf[qdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizQuestions", qdf, ["question_id", "quiz_id", "question_text", "question_type",
                                                 "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_quiz(self, quiz_id):
        self.delete_quiz_keep_results(quiz_id)
        rdf = self._sheet_to_df("QuizResults")
        rdf = rdf[rdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizResults", rdf, ["result_id", "quiz_id", "student_id", "student_name",
                                               "score", "total_marks", "submission_time", "answers", "status"])

    # ==================== Quiz Questions ====================
    def get_quiz_questions(self, quiz_id):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            return pd.DataFrame()
        return df[df.quiz_id == quiz_id]

    def add_question(self, q_data):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            df = pd.DataFrame(columns=["question_id", "quiz_id", "question_text", "question_type",
                                       "option1", "option2", "option3", "option4", "correct_answer"])
        df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type",
                                                "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_question(self, question_id):
        df = self._sheet_to_df("QuizQuestions")
        df = df[df.question_id != question_id]
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type",
                                                "option1", "option2", "option3", "option4", "correct_answer"])

    # ==================== Quiz Results (إلحاق) ====================
    def get_quiz_results(self, quiz_id=None):
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return pd.DataFrame()
        if quiz_id:
            return df[df.quiz_id == quiz_id]
        return df

    def start_quiz_attempt(self, quiz_id, student_id, student_name):
        result_id = str(uuid.uuid4())
        new_row = {
            "result_id": result_id,
            "quiz_id": quiz_id,
            "student_id": student_id,
            "student_name": student_name,
            "score": "",
            "total_marks": "20",
            "submission_time": datetime.now().isoformat(),
            "answers": "{}",
            "status": "started"
        }
        columns = ["result_id", "quiz_id", "student_id", "student_name",
                   "score", "total_marks", "submission_time", "answers", "status"]
        self._append_row("QuizResults", new_row, columns)
        return result_id

    def save_answers(self, result_id, answers_dict):
        """تحديث حقل الإجابات لمحاولة قيد التقدم."""
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "answers"] = json.dumps(answers_dict, ensure_ascii=False)
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "submission_time", "answers", "status"])

    def submit_quiz_attempt(self, result_id, score, answers_json):
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "score"] = str(score)
            df.at[idx[0], "answers"] = answers_json
            df.at[idx[0], "submission_time"] = datetime.now().isoformat()
            df.at[idx[0], "status"] = "submitted"
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "submission_time", "answers", "status"])

    def delete_quiz_result(self, result_id):
        df = self._sheet_to_df("QuizResults")
        df = df[df.result_id != result_id]
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "submission_time", "answers", "status"])

    # ==================== Logs (إلحاق) ====================
    def get_logs(self):
        return self._sheet_to_df("Logs")

    def add_log(self, user_id, action, details=""):
        log = {
            "log_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details
        }
        columns = ["log_id", "timestamp", "user_id", "action", "details"]
        self._append_row("Logs", log, columns)

    def delete_log(self, log_id):
        df = self.get_logs()
        df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

# =============================================================================
# JWT وإنشاء الجلسات
# =============================================================================
def generate_token(user: dict, secret: str) -> str:
    """إنشاء رمز JWT بمعلومات المستخدم الأساسية."""
    payload = {
        "user_id": user["user_id"],
        "role": user["role"],
        "full_name": user["full_name"],
        "section_id": user.get("section_id", ""),
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def verify_token(token: str, secret: str):
    """التحقق من الرمز وإرجاع المحتوى إذا كان سليماً."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None

def init_session():
    """تهيئة جميع متغيرات الجلسة المطلوبة."""
    defaults = {
        "authenticated": False,
        "user": None,
        "token": None,
        "student_quiz": None,
        "student_quiz_started": False,
        "quiz_phase": "enter_name",
        "student_name": "",
        "student_id": "",
        "quiz_start_time": None,
        "quiz_end_time": None,
        "quiz_answers": {},
        "quiz_submitted": False,
        "last_score": 0,
        "menu_choice": "🏠 لوحة التحكم",
        "show_sidebar": True,
        "open_help_dialog": False,
        "current_attempt_id": None,
        "last_saved_answers_str": ""
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout(db=None):
    """تسجيل الخروج وتنظيف الجلسة بالكامل."""
    if db and st.session_state.get("user"):
        try:
            db.add_log(st.session_state.user["user_id"], "تسجيل خروج")
        except Exception:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def send_telegram_message(message: str) -> bool:
    """إرسال رسالة عبر بوت Telegram إذا تم تكوينه."""
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False

# =============================================================================
# واجهة المستخدم – CSS مُحسَّن (يدعم الوضع الليلي والاستجابة)
# =============================================================================
def inject_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { font-family: 'Cairo', sans-serif; }
        body { direction: rtl; text-align: right; background-color: #f0f2f6; color: #1a1a2e; }
        .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); }
        header[data-testid="stHeader"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        [data-testid="stSidebarNavToggle"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[aria-label*="Close sidebar"],
        button[aria-label*="Close"],
        [data-testid="baseButton-header"],
        [data-testid="stSidebarResizer"] {
            display: none !important;
        }

        section[data-testid="stSidebar"] {
            position: fixed !important;
            top: 0 !important;
            right: 0 !important;
            height: 100vh !important;
            width: 300px !important;
            max-width: 100vw !important;
            z-index: 10000 !important;
            transition: transform 0.3s ease !important;
            box-shadow: -5px 0 15px rgba(0,0,0,0.1);
            overflow-y: auto !important;
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%) !important;
            border-left: 1px solid rgba(0,0,0,0.08) !important;
        }

        @media (max-width: 768px) {
            section[data-testid="stSidebar"] { width: 100vw !important; }
        }

        .nav-btn-container .stButton > button {
            width: 100% !important; text-align: right !important;
            justify-content: flex-start !important; padding: 0.7rem 1rem !important;
            font-size: 1rem !important; font-weight: 600 !important;
            border-radius: 10px !important; background: transparent !important;
            color: #1a1a2e !important; border: 1px solid transparent !important;
            transition: all 0.2s ease !important;
        }
        .nav-btn-container .stButton > button:hover {
            background: rgba(102,126,234,0.08) !important;
            color: #667eea !important;
            border-color: rgba(102,126,234,0.15) !important;
            transform: translateX(-2px) !important;
        }
        .nav-btn-container .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border: none !important;
            box-shadow: 0 2px 8px rgba(102,126,234,0.3) !important;
        }

        .floating-show-btn .stButton > button {
            position: fixed !important; top: 20px !important; right: 20px !important;
            z-index: 99999 !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border: none !important; border-radius: 15px !important;
            width: 60px !important; height: 60px !important; font-size: 28px !important;
            box-shadow: 0 4px 15px rgba(102,126,234,0.4) !important;
            display: flex !important; align-items: center !important;
            justify-content: center !important; cursor: pointer !important;
            min-height: 60px !important;
        }

        .help-float-container .stButton > button {
            position: fixed !important; top: 20px !important; right: 100px !important;
            z-index: 99998 !important;
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important;
            color: white !important; font-weight: 700 !important;
            border-radius: 12px !important; padding: 12px 20px !important;
            font-size: 16px !important; border: none !important;
            box-shadow: 0 4px 15px rgba(243,156,18,0.4) !important;
            white-space: nowrap !important; min-height: 48px !important;
        }

        .main-header {
            font-size: 2.2rem; font-weight: 700; color: #1a1a2e; text-align: center;
            margin-bottom: 1.5rem; padding: 1rem;
            background: rgba(255,255,255,0.9); border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            backdrop-filter: blur(5px); border: 1px solid rgba(0,0,0,0.05);
            margin-top: 100px;
        }
        .card { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 1rem; }
        .stButton > button { border-radius: 8px; }

        @media (max-width: 768px) {
            .floating-show-btn .stButton > button {
                width: 50px; height: 50px; font-size: 24px; top: 14px; right: 14px;
            }
            .help-float-container .stButton > button {
                right: 80px; top: 14px; padding: 10px 16px; font-size: 14px;
            }
            .main-header { font-size: 1.6rem; margin-top: 110px; }
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# مركز المساعدة والدعم الفني
# =============================================================================
@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    """نافذة منبثقة لتقديم طلب مساعدة أو الإبلاغ عن مشكلة."""
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.markdown("<h3 style='text-align:center; color:#667eea;'>📬 تواصل معنا</h3>", unsafe_allow_html=True)
    with col2:
        if st.button("✕ إغلاق", key="help_dialog_close_btn", use_container_width=True):
            st.session_state.open_help_dialog = False
            st.rerun()

    contact_name, contact_whatsapp = get_support_config()
    if contact_whatsapp:
        st.info(f"📞 للدعم المباشر: {contact_name} - {contact_whatsapp}")

    with st.form("help_form_enhanced", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("الاسم *", placeholder="أدخل اسمك الكامل")
            whatsapp = st.text_input("رقم الواتساب *", placeholder="01xxxxxxxxx")
        with col2:
            issue_type = st.selectbox("نوع المشكلة *",
                                    ["مشكلة تقنية", "مشكلة في البيانات", "طلب مساعدة", "اقتراح تحسين", "أخرى"])
            urgency = st.selectbox("الأولوية", ["عادي", "مستعجل", "طارئ جداً"], index=0)
        issue_desc = st.text_area("وصف المشكلة أو الطلب *", placeholder="اشرح المشكلة بالتفصيل...", height=150)
        if st.form_submit_button("🚀 إرسال الطلب"):
            if not name or not whatsapp or not issue_desc:
                st.error("⚠️ الرجاء ملء جميع الحقول المطلوبة")
            else:
                urgency_icon = {"عادي": "ℹ️", "مستعجل": "⚠️", "طارئ جداً": "🔴"}
                message = (
                    f"{urgency_icon.get(urgency, '')} بلاغ جديد من مركز المساعدة\n"
                    f"👤 الاسم: {name}\n📱 الواتساب: {whatsapp}\n"
                    f"📂 النوع: {issue_type}\n⚡ الأولوية: {urgency}\n"
                    f"📝 التفاصيل: {issue_desc}"
                )
                if send_telegram_message(message):
                    st.success("✅ تم إرسال طلبك بنجاح! سنتواصل معك قريباً.")
                    st.balloons()
                else:
                    st.error("❌ فشل الإرسال، يرجى المحاولة لاحقاً أو التواصل مباشرة عبر الواتساب.")

# =============================================================================
# صفحة تسجيل الدخول وإعداد المسؤول الأول (آمنة)
# =============================================================================
def show_initialization(db: Database):
    """إذا لم يكن هناك مستخدمون، يطلب إنشاء مسؤول النظام بكلمة مرور قوية."""
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### الرجاء إنشاء حساب مدير النظام:")
        with st.form("init_admin_form_secure"):
            username = st.text_input("اسم المستخدم *", value="admin")
            full_name = st.text_input("الاسم الكامل *", value="مدير النظام")
            password = st.text_input("كلمة المرور *", type="password",
                                     help=f"يجب ألا تقل عن {MIN_PASSWORD_LENGTH} أحرف")
            confirm = st.text_input("تأكيد كلمة المرور *", type="password")
            email = st.text_input("البريد الإلكتروني (اختياري)")
            phone = st.text_input("رقم الهاتف (اختياري)")
            if st.form_submit_button("🛠️ إنشاء المدير"):
                if not username or not full_name or not password:
                    st.error("الرجاء ملء جميع الحقول المطلوبة")
                elif len(password) < MIN_PASSWORD_LENGTH:
                    st.error(f"كلمة المرور يجب ألا تقل عن {MIN_PASSWORD_LENGTH} أحرف")
                elif password != confirm:
                    st.error("كلمتا المرور غير متطابقتين")
                else:
                    admin_data = {
                        "user_id": "admin-001",
                        "username": username,
                        "password": password,
                        "role": "System Admin",
                        "full_name": full_name,
                        "section_id": "",
                        "phone": phone,
                        "email": email
                    }
                    db.add_user(admin_data)  # add_user ستقوم بتجزئة كلمة المرور
                    st.success("✅ تم إنشاء مدير النظام بنجاح! يمكنك تسجيل الدخول الآن.")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
        st.stop()

def show_login_page(db: Database, jwt_secret: str):
    """عرض صفحة تسجيل الدخول (خدام وطالبات)."""
    st.markdown("<h1 class='main-header'>⛪ <br>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
    show_initialization(db)

    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم")
            password = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                if not username or not password:
                    st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                else:
                    with st.spinner("جاري التحقق..."):
                        users = db.get_users()
                        user_row = users[users.username == username]
                        if user_row.empty:
                            st.error("اسم المستخدم غير موجود")
                        else:
                            user = user_row.iloc[0].to_dict()
                            if verify_password(password, user.get("password", "")):
                                token = generate_token(user, jwt_secret)
                                st.session_state.token = token
                                st.session_state.user = user
                                st.session_state.authenticated = True
                                st.session_state.menu_choice = "🏠 لوحة التحكم"
                                st.session_state.show_sidebar = True
                                db.add_log(user["user_id"], "تسجيل الدخول")
                                st.success("تم تسجيل الدخول بنجاح!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("كلمة المرور غير صحيحة")

    with tab2:
        st.subheader("دخول الاختبار الإلكتروني")
        with st.form("student_login_form"):
            code = st.text_input("كود الاختبار", placeholder="مثال: GEN123")
            passwd = st.text_input("كلمة مرور الاختبار", type="password", placeholder="مثال: QUIZ99")
            if st.form_submit_button("بدء الاختبار", use_container_width=True):
                if not code or not passwd:
                    st.error("الرجاء إدخال الكود وكلمة المرور")
                else:
                    with st.spinner("جاري التحقق من الكود..."):
                        quizzes = db.get_quizzes()
                        quiz = quizzes[(quizzes.quiz_code == code) & (quizzes.password == passwd)]
                        if quiz.empty:
                            st.error("كود أو كلمة مرور خاطئة")
                        else:
                            quiz = quiz.iloc[0].to_dict()
                            try:
                                expiry = pd.to_datetime(quiz["expiry_date"])
                                if expiry < datetime.now():
                                    st.error("انتهت صلاحية هذا الاختبار")
                                    db.update_quiz(quiz["quiz_id"], {"is_active": "False"})
                                elif quiz.get("is_active", "True") == "False":
                                    st.error("هذا الاختبار غير نشط حالياً")
                                else:
                                    st.session_state.student_quiz = quiz
                                    st.session_state.student_quiz_started = True
                                    st.session_state.quiz_phase = "enter_name"
                                    st.session_state.student_name = ""
                                    st.session_state.student_id = ""
                                    st.session_state.quiz_start_time = None
                                    st.session_state.quiz_end_time = None
                                    st.session_state.quiz_answers = {}
                                    st.session_state.quiz_submitted = False
                                    st.session_state.last_score = 0
                                    st.session_state.current_attempt_id = None
                                    st.session_state.last_saved_answers_str = ""
                                    st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")

# =============================================================================
# واجهة الطالبات للاختبار الإلكتروني
# =============================================================================
def grade_attempt(db, quiz_id, answers_dict, quiz_total_marks=20):
    """تصحيح إجابات الطالبة وإرجاع الدرجة."""
    questions = db.get_quiz_questions(quiz_id)
    if questions.empty:
        return 0
    correct_count = 0
    for _, q_row in questions.iterrows():
        q = q_row.to_dict()
        correct = str(q["correct_answer"]).strip().lower()
        student_ans = str(answers_dict.get(q["question_id"], "")).strip().lower()
        if correct == student_ans:
            correct_count += 1
    num_q = len(questions)
    return round((correct_count / num_q) * quiz_total_marks, 1) if num_q > 0 else 0

def save_current_answers(db):
    """حفظ الإجابات الحالية في قاعدة البيانات إذا تغيرت."""
    if not st.session_state.get("current_attempt_id"):
        return
    current_answers = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
    if current_answers != st.session_state.last_saved_answers_str:
        db.save_answers(st.session_state.current_attempt_id, st.session_state.quiz_answers)
        st.session_state.last_saved_answers_str = current_answers

def show_student_quiz(db: Database):
    """الصفحة الكاملة لتجربة الاختبار بالنسبة للطالبة."""
    quiz = st.session_state.student_quiz
    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz['title']}")
        total_marks = float(quiz.get("total_marks", 20))
        st.markdown(f"**عدد الأسئلة:** {quiz['num_questions']} | **الدرجة الكلية:** {total_marks} | **الوقت:** {quiz['time_limit_minutes']} دقيقة")
        students_df = db.get_students()
        active_students = students_df[students_df["status"] == "active"] if not students_df.empty else pd.DataFrame()
        if active_students.empty:
            st.warning("لا توجد طالبات مسجلات حالياً. يرجى التواصل مع المسؤول.")
            st.stop()
        active_students = active_students.sort_values("full_name", key=lambda col: col.str.strip().str.lower())
        options_dict = dict(zip(active_students["student_id"], active_students["full_name"]))
        selected_id = st.selectbox(
            "اختر اسمك من القائمة", options=list(options_dict.keys()),
            format_func=lambda x: options_dict[x], index=None, placeholder="اختر اسمك..."
        )
        st.info("إذا لم تجد اسمك في القائمة، يرجى التواصل مع مشرف الخدمة لإضافتك.")
        if selected_id is not None:
            existing = db.get_quiz_results(quiz["quiz_id"])
            if not existing.empty and "student_id" in existing.columns:
                student_attempts = existing[existing["student_id"] == selected_id]
                if not student_attempts.empty:
                    attempt = student_attempts.iloc[0]
                    if attempt["status"] == "started":
                        # تسليم المحاولة السابقة تلقائياً
                        answers_str = attempt["answers"]
                        try:
                            saved_answers = json.loads(answers_str) if answers_str else {}
                        except Exception:
                            saved_answers = {}
                        score = grade_attempt(db, quiz["quiz_id"], saved_answers, total_marks)
                        db.submit_quiz_attempt(attempt["result_id"], score, json.dumps(saved_answers, ensure_ascii=False))
                        st.warning("تم تسليم محاولتك السابقة تلقائياً بناءً على ما قمت بحفظه.")
                        st.session_state.last_score = score
                        st.session_state.quiz_phase = "finished"
                        st.session_state.quiz_submitted = True
                        st.rerun()
                    else:
                        st.error("لقد قمت بتسليم هذا الاختبار بالفعل. لا يمكنك الدخول مرة أخرى.")
                        st.stop()
        if st.button("بدء الاختبار", use_container_width=True, type="primary", disabled=(selected_id is None)):
            selected_student = active_students[active_students["student_id"] == selected_id].iloc[0].to_dict()
            st.session_state.student_name = selected_student["full_name"]
            st.session_state.student_id = selected_id
            st.session_state.quiz_start_time = datetime.now()
            time_limit_seconds = int(quiz["time_limit_minutes"]) * 60
            st.session_state.quiz_end_time = st.session_state.quiz_start_time + timedelta(seconds=time_limit_seconds)
            attempt_id = db.start_quiz_attempt(quiz["quiz_id"], selected_id, st.session_state.student_name)
            st.session_state.current_attempt_id = attempt_id
            st.session_state.quiz_answers = {}
            st.session_state.last_saved_answers_str = ""
            st.session_state.quiz_phase = "taking_quiz"
            st.rerun()
        return

    if st.session_state.quiz_submitted or st.session_state.quiz_phase == "finished":
        st.success("تم تسليم الاختبار بنجاح!")
        if "last_score" in st.session_state:
            score = st.session_state.last_score
            st.info(f"نتيجتك: {score}/{quiz.get('total_marks', 20)}")
        if st.button("إنهاء والعودة إلى الرئيسية", use_container_width=True):
            for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                        "student_id", "quiz_start_time", "quiz_end_time", "quiz_answers",
                        "quiz_submitted", "last_score", "current_attempt_id", "last_saved_answers_str"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        return

    # صفحة الأسئلة
    st.title(f"📝 {quiz['title']}")
    total_marks = float(quiz.get("total_marks", 20))
    st.markdown(f"الطالبة: **{st.session_state.student_name}** | الدرجة الكلية: {total_marks}")
    # Timer بسيط (اختياري) – يمكن تجاهله في هذا الإصدار
    questions = db.get_quiz_questions(quiz["quiz_id"])
    if questions.empty:
        st.warning("لا توجد أسئلة في هذا الاختبار بعد.")
        return
    for idx, row in questions.iterrows():
        q = row.to_dict()
        q_id = q["question_id"]
        st.markdown(f"**سؤال {idx+1}:** {q['question_text']}")
        q_type = q["question_type"]
        prev_answer = st.session_state.quiz_answers.get(q_id, "")
        if q_type in ["اختيار من متعدد", "صح وخطأ"]:
            options = [q["option1"], q["option2"], q["option3"], q["option4"]] if q_type == "اختيار من متعدد" else ["صح", "خطأ"]
            options = [opt for opt in options if opt and str(opt).strip()]
            if options:
                current_index = options.index(prev_answer) if prev_answer in options else None
                ans = st.radio("اختر الإجابة", options, key=f"q_{q_id}", index=current_index)
                new_answer = ans if ans else ""
        else:
            new_answer = st.text_input("الإجابة", key=f"q_{q_id}", value=prev_answer)
        if new_answer != prev_answer:
            st.session_state.quiz_answers[q_id] = new_answer
            save_current_answers(db)
        st.markdown("---")
    if st.button("تسليم الاختبار", type="primary", use_container_width=True):
        score = grade_attempt(db, quiz["quiz_id"], st.session_state.quiz_answers, total_marks)
        answers_json = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
        db.submit_quiz_attempt(st.session_state.current_attempt_id, score, answers_json)
        st.session_state.quiz_submitted = True
        st.session_state.last_score = score
        st.session_state.quiz_phase = "finished"
        st.rerun()

# =============================================================================
# القوائم الجانبية (حسب الصلاحية)
# =============================================================================
ROLE_MENUS = {
    "System Admin": [
        "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "📋 الحضور", "💬 الافتقاد",
        "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات",
        "📜 سجل العمليات", "🔒 تغيير كلمة المرور"
    ],
    "Father Account": [
        "🏠 لوحة التحكم", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"
    ],
    "Service Manager": [
        "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد",
        "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"
    ],
    "Teacher": [
        "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد",
        "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"
    ]
}

def show_sidebar_navigation(db: Database):
    """عرض القائمة الجانبية وأزرار التنقل."""
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.user
        st.markdown(f"**👤 {user['full_name']}**")
        st.caption(f"الصلاحية: {user['role']}")
        st.divider()

        menu_items = ROLE_MENUS.get(user["role"], [])
        if not menu_items:
            st.warning("صلاحية غير معروفة")
            return None

        current_choice = st.session_state.get("menu_choice", menu_items[0])
        if current_choice not in menu_items:
            current_choice = menu_items[0]
            st.session_state.menu_choice = current_choice

        if st.button("✕ إخفاء القائمة", use_container_width=True):
            st.session_state.show_sidebar = False
            st.rerun()

        st.markdown('<div class="nav-btn-container">', unsafe_allow_html=True)
        for item in menu_items:
            btn_type = "primary" if item == current_choice else "secondary"
            if st.button(item, key=f"nav_btn_{item}", use_container_width=True, type=btn_type):
                if item != current_choice:
                    st.session_state.menu_choice = item
                st.session_state.show_sidebar = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout(db)

    return current_choice

# =============================================================================
# الصفحات الوظيفية
# =============================================================================
def show_dashboard(db: Database):
    """لوحة التحكم الرئيسية."""
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)

    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()

    # تصفية حسب الفصل للمستخدمين المحددين
    if role in ["Teacher", "Service Manager"] and section_id:
        students = students[students.section_id == section_id] if not students.empty else students
        if not attendance.empty:
            attendance = attendance[attendance.section_id == section_id]
        if not followup.empty and not students.empty:
            followup = followup[followup.student_id.isin(students["student_id"])]

    total_students = len(students)
    today_str = datetime.now().strftime("%Y-%m-%d")
    present_today = len(attendance[(attendance.date == today_str) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent_today = len(attendance[(attendance.date == today_str) & (attendance.status == "غائب")]) if not attendance.empty else 0
    need_follow = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("عدد الطالبات", total_students)
    col2.metric("الحضور اليوم", present_today)
    col3.metric("الغياب اليوم", absent_today)
    col4.metric("منقطعات", need_follow)

    st.markdown("#### 📈 الحضور الأسبوعي")
    if not attendance.empty:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
        last_week = datetime.now() - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty:
            fig = px.histogram(recent, x="date", color="status", barmode="group")
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور للأيام الماضية.")
    else:
        st.info("لا توجد بيانات حضور بعد.")

    st.markdown("#### 🏅 أكثر 5 طالبات غياباً هذا الشهر")
    if not attendance.empty:
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_att = attendance[(attendance.date >= month_start) & (attendance.status == "غائب")]
        if not month_att.empty:
            absent_counts = month_att.groupby("student_id").size().reset_index(name="أيام الغياب")
            absent_counts = absent_counts.sort_values("أيام الغياب", ascending=False).head(5)
            if not students.empty:
                absent_counts = absent_counts.merge(students[["student_id", "full_name"]], on="student_id", how="left")
            st.dataframe(absent_counts[["full_name", "أيام الغياب"]], use_container_width=True)
        else:
            st.info("لا يوجد غياب هذا الشهر.")

    st.markdown("#### 🔔 بنات بحاجة لافتقاد عاجل")
    urgent = followup[followup.regularity_status.isin(["منقطع", "متقطع"])] if not followup.empty else pd.DataFrame()
    if not urgent.empty:
        if not students.empty:
            urgent = urgent.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(urgent[["full_name", "followup_date", "notes"]], use_container_width=True)
    else:
        st.info("كل البنات منتظمات.")

# ---------- إدارة المستخدمين ----------
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    students = db.get_students()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول"])

    # ---------- التبويب 1: الخدام ----------
    with tab1:
        st.subheader("قائمة المستخدمين (خدام)")
        if not users.empty:
            st.dataframe(users[["user_id", "username", "full_name", "role", "section_id", "phone", "email"]], use_container_width=True)
        else:
            st.info("لا يوجد مستخدمون مسجلون.")
        with st.expander("➕ إضافة مستخدم جديد"):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                username = col1.text_input("اسم المستخدم*")
                full_name = col2.text_input("الاسم الكامل*")
                password = col1.text_input("كلمة المرور*", type="password")
                role = col2.selectbox("الصلاحية", ["System Admin", "Father Account", "Service Manager", "Teacher"])
                section_id = ""
                if role in ["Service Manager", "Teacher"] and not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف (اختياري)")
                email = st.text_input("البريد الإلكتروني (اختياري)")
                if st.form_submit_button("إضافة"):
                    if not username or not password or not full_name:
                        st.error("مطلوب اسم المستخدم وكلمة المرور والاسم الكامل")
                    elif not users[users.username == username].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({
                            "user_id": str(uuid.uuid4()), "username": username, "password": password,
                            "role": role, "full_name": full_name,
                            "section_id": section_id, "phone": phone, "email": email
                        })
                        st.success("تم إضافة المستخدم بنجاح")
                        time.sleep(1)
                        st.rerun()
        with st.expander("✏️ تعديل / حذف مستخدم"):
            if not users.empty:
                selected_user_id = st.selectbox("اختر المستخدم", users["user_id"], key="sel_user_edit")
                user_data = users[users.user_id == selected_user_id].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=user_data.get("full_name", ""))
                new_phone = st.text_input("رقم الهاتف", value=user_data.get("phone", ""))
                new_email = st.text_input("البريد الإلكتروني", value=user_data.get("email", ""))
                roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher"]
                current_role = user_data.get("role", "Teacher")
                role_index = roles_list.index(current_role) if current_role in roles_list else 3
                new_role = st.selectbox("الصلاحية", roles_list, index=role_index)
                new_section_id = user_data.get("section_id", "")
                if new_role in ["Service Manager", "Teacher"] and not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    section_choice = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    new_section_id = section_choice if section_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات"):
                    db.update_user(selected_user_id, {"full_name": new_full_name, "phone": new_phone, "email": new_email, "role": new_role, "section_id": new_section_id})
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المستخدم"):
                    if selected_user_id == st.session_state.user["user_id"]:
                        st.error("لا يمكنك حذف حسابك الحالي!")
                    else:
                        db.delete_user(selected_user_id)
                        st.success("تم الحذف")
                        time.sleep(1)
                        st.rerun()

    # ---------- التبويب 2: المدرسات ----------
    with tab2:
        st.subheader("قائمة المدرسات")
        teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
        if not teachers.empty:
            if not sections.empty:
                teachers_display = teachers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                teachers_display = teachers_display.rename(columns={"section_name": "الفصل"})
            else:
                teachers_display = teachers
                teachers_display["الفصل"] = ""
            st.dataframe(teachers_display[["user_id", "username", "full_name", "الفصل", "phone", "email"]], use_container_width=True)
        else:
            st.info("لا توجد مدرسات مسجلات.")
        with st.expander("➕ إضافة مدرسة جديدة"):
            with st.form("add_teacher_form"):
                teacher_name = st.text_input("اسم المستخدم*")
                password = st.text_input("كلمة المرور*", type="password")
                section_id = ""
                if not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة"):
                    if not teacher_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif not users[users.username == teacher_name].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({
                            "user_id": str(uuid.uuid4()), "username": teacher_name, "password": password,
                            "role": "Teacher", "full_name": teacher_name,
                            "section_id": section_id, "phone": phone, "email": email
                        })
                        st.success("تمت إضافة المدرسة بنجاح")
                        time.sleep(1)
                        st.rerun()

    # ---------- التبويب 3: الطالبات ----------
    with tab3:
        st.subheader("قائمة الطالبات")
        if not students.empty:
            if not sections.empty:
                students_display = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
            else:
                students_display = students
                students_display["section_name"] = ""
            st.dataframe(students_display[["student_id", "full_name", "section_name", "phone", "parent_phone", "birthdate", "school", "status"]], use_container_width=True)
        else:
            st.info("لا توجد طالبات مسجلة.")
        with st.expander("➕ إضافة طالبة جديدة"):
            with st.form("add_student_form"):
                full_name = st.text_input("الاسم الكامل*")
                section_id = ""
                if not sections.empty:
                    section_id = st.selectbox("الفصل", sections["section_id"], format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
                phone = st.text_input("رقم الهاتف")
                parent_phone = st.text_input("رقم ولي الأمر")
                birthdate = st.date_input("تاريخ الميلاد", value=None)
                address = st.text_area("العنوان")
                school = st.text_input("المدرسة")
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("إضافة"):
                    if not full_name:
                        st.error("الاسم الكامل مطلوب")
                    else:
                        db.add_student({
                            "student_id": str(uuid.uuid4()), "full_name": full_name, "section_id": section_id,
                            "phone": phone, "parent_phone": parent_phone,
                            "birthdate": birthdate.strftime("%Y-%m-%d") if birthdate else "",
                            "address": address, "school": school, "notes": notes, "status": "active"
                        })
                        st.success("تمت الإضافة")
                        time.sleep(1)
                        st.rerun()
        with st.expander("✏️ تعديل بيانات طالبة"):
            if not students.empty:
                selected_student = st.selectbox("اختر طالبة", students["student_id"], key="sel_student_edit")
                student_row = students[students.student_id == selected_student].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""))
                new_section_id = student_row.get("section_id", "")
                if not sections.empty:
                    section_options = sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    new_section_id = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
                new_phone = st.text_input("رقم الهاتف", value=student_row.get("phone", ""))
                new_parent = st.text_input("رقم ولي الأمر", value=student_row.get("parent_phone", ""))
                birth_date_val = pd.to_datetime(student_row.get("birthdate", "")).date() if student_row.get("birthdate") else None
                new_birthdate = st.date_input("تاريخ الميلاد", value=birth_date_val)
                new_school = st.text_input("المدرسة", value=student_row.get("school", ""))
                new_notes = st.text_area("ملاحظات", value=student_row.get("notes", ""))
                status_list = ["active", "inactive"]
                current_status = student_row.get("status", "active")
                status_index = 0 if current_status == "active" else 1
                new_status = st.selectbox("الحالة", status_list, index=status_index)
                if st.button("حفظ التعديلات", key="save_student_btn"):
                    db.update_student(selected_student, {
                        "full_name": new_full_name, "section_id": new_section_id,
                        "phone": new_phone, "parent_phone": new_parent,
                        "birthdate": new_birthdate.strftime("%Y-%m-%d") if new_birthdate else "",
                        "school": new_school, "notes": new_notes, "status": new_status
                    })
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
        with st.expander("🗑️ حذف طالبة"):
            if not students.empty:
                delete_id = st.selectbox("اختر طالبة للحذف", students["student_id"], key="delete_student_sel")
                if st.button("تأكيد حذف الطالبة"):
                    db.delete_student(delete_id)
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()

    # ---------- التبويب 4: أمناء الخدمة ----------
    with tab4:
        st.subheader("قائمة أمناء الخدمة")
        managers = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
        if not managers.empty:
            if not sections.empty:
                mgr_display = managers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                mgr_display = mgr_display.rename(columns={"section_name": "الفصل"})
            else:
                mgr_display = managers
                mgr_display["الفصل"] = ""
            st.dataframe(mgr_display[["user_id", "username", "full_name", "الفصل", "phone", "email"]], use_container_width=True)
        else:
            st.info("لا يوجد أمناء خدمة.")

    # ---------- التبويب 5: إدارة الفصول ----------
    with tab5:
        st.subheader("قائمة الفصول")
        if not sections.empty:
            st.dataframe(sections[["section_id", "section_name"]], use_container_width=True)
        else:
            st.info("لا توجد فصول مسجلة.")
        with st.expander("➕ إضافة فصل جديد"):
            with st.form("add_section_form"):
                name = st.text_input("اسم الفصل*")
                if st.form_submit_button("إضافة"):
                    if not name:
                        st.error("اسم الفصل مطلوب")
                    else:
                        db.add_section({"section_id": str(uuid.uuid4()), "section_name": name.strip()})
                        st.success("تمت الإضافة")
                        time.sleep(1)
                        st.rerun()
        with st.expander("🗑️ حذف فصل"):
            if not sections.empty:
                del_sec = st.selectbox("اختر فصل", sections["section_id"], key="del_section_sel")
                if st.button("تأكيد حذف الفصل"):
                    db.delete_section(del_sec)
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()

# ---------- تسجيل الحضور (مع منع أمناء الخدمة) ----------
def show_attendance(db: Database):
    user = st.session_state.user
    role = user["role"]
    # أمناء الخدمة لا يمكنهم دخول هذه الصفحة
    if role == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور، هذه المهمة خاصة بالمدرسات فقط.")
        st.session_state.menu_choice = "🏠 لوحة التحكم"
        st.rerun()
        return

    st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
    sections = db.get_sections()
    if sections.empty:
        st.warning("لا توجد فصول.")
        return
    section_id = user.get("section_id", "")
    if role == "Teacher" and section_id:
        selected_section = section_id
        section_name = sections[sections.section_id == section_id]["section_name"].values[0] if not sections.empty else section_id
        st.write(f"**الفصل:** {section_name}")
    else:
        selected_section = st.selectbox("اختر الفصل", sections["section_id"],
                               format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
    date = st.date_input("التاريخ", datetime.now())
    date_str = date.strftime("%Y-%m-%d")
    students = db.get_students()
    section_students = students[students.section_id == selected_section] if not students.empty else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات في هذا الفصل.")
        return
    existing = db.get_attendance_by_date_section(date_str, selected_section)
    already_filled = not existing.empty
    if already_filled:
        st.warning("⚠️ يوجد تسجيل حضور سابق.")
    statuses = {}
    notes_dict = {}
    for _, s in section_students.iterrows():
        sid = s["student_id"]
        sname = s["full_name"]
        prev = existing[existing.student_id == sid] if already_filled else pd.DataFrame()
        prev_status = prev.iloc[0]["status"] if not prev.empty else "حاضر"
        prev_notes = prev.iloc[0]["notes"] if not prev.empty else ""
        cols = st.columns([3, 2, 2])
        cols[0].write(f"**{sname}**")
        status_list = ["حاضر", "غائب", "متأخر"]
        status_index = status_list.index(prev_status) if prev_status in status_list else 0
        status = cols[1].radio("الحالة", status_list, index=status_index, key=f"att_{sid}", horizontal=True)
        notes = cols[2].text_input("ملاحظة", value=prev_notes, key=f"note_{sid}", label_visibility="collapsed")
        statuses[sid] = status
        notes_dict[sid] = notes

    if st.button("💾 حفظ الحضور", use_container_width=True):
        with st.spinner("جاري حفظ الحضور..."):
            records = []
            for sid, status in statuses.items():
                records.append({
                    "record_id": str(uuid.uuid4()),
                    "date": date_str,
                    "student_id": sid,
                    "status": status,
                    "notes": notes_dict.get(sid, ""),
                    "recorded_by": user["user_id"],
                    "section_id": selected_section
                })
            db.batch_add_attendance(records)
            db.add_log(user["user_id"], f"تسجيل حضور فصل {selected_section} ليوم {date_str}")
            st.success("✅ تم تسجيل الحضور بنجاح")
            time.sleep(1)
            st.rerun()

    # عرض السجلات السابقة (اختياري)
    if not existing.empty:
        st.markdown("---")
        st.subheader("🗑️ إدارة سجلات الحضور السابقة")
        rec = existing.copy()
        rec["student_name"] = rec["student_id"].apply(
            lambda sid: section_students[section_students.student_id == sid]["full_name"].values[0]
            if sid in section_students["student_id"].values else sid
        )
        rec = rec[["record_id", "student_name", "status", "notes"]]
        st.dataframe(rec, use_container_width=True)
        del_id = st.selectbox("اختر سجل حضور لحذفه", rec["record_id"], key="del_att_sel")
        if st.button("حذف سجل الحضور"):
            db.delete_attendance_record(del_id)
            st.success("تم الحذف")
            time.sleep(1)
            st.rerun()

# ---------- الافتقاد والمتابعة ----------
def show_followup(db: Database):
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()
    if role in ["Teacher", "Service Manager"] and section_id:
        responsible = students[students.section_id == section_id] if not students.empty else pd.DataFrame()
    else:
        responsible = students
    if responsible.empty:
        st.info("لا توجد طالبات مسؤولات عنك.")
        return
    # تحليل الانتظام
    if not followup.empty:
        student_ids = responsible["student_id"].tolist()
        fups = followup[followup.student_id.isin(student_ids)]
        regular = len(fups[fups.regularity_status == "منتظم"])
        intermittent = len(fups[fups.regularity_status == "متقطع"])
        disconnected = len(fups[fups.regularity_status == "منقطع"])
    else:
        regular = intermittent = disconnected = 0
    col1, col2, col3 = st.columns(3)
    col1.metric("منتظمات", regular)
    col2.metric("متقطعات", intermittent)
    col3.metric("منقطعات", disconnected)
    st.markdown("---")
    st.subheader("⚠️ بنات بحاجة إلى افتقاد")
    if not followup.empty:
        urgent = followup[(followup.regularity_status.isin(["متقطع", "منقطع"])) & (followup.student_id.isin(responsible["student_id"]))]
        if not urgent.empty:
            urgent_display = urgent.merge(responsible[["student_id", "full_name"]], on="student_id", how="left")
            st.dataframe(urgent_display[["full_name", "followup_date", "followup_type", "notes"]], use_container_width=True)
        else:
            st.info("كل البنات منتظمات حالياً.")
    else:
        st.info("لا توجد متابعات سابقة.")
    st.markdown("---")
    st.subheader("➕ إضافة متابعة جديدة")
    student = st.selectbox("اختر الطالبة", responsible["student_id"],
                           format_func=lambda x: responsible[responsible.student_id==x]["full_name"].values[0], key="followup_student")
    with st.form("followup_form"):
        ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
        notes = st.text_area("ملاحظات")
        regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
        if st.form_submit_button("حفظ المتابعة"):
            db.add_followup_record({
                "record_id": str(uuid.uuid4()), "student_id": student,
                "teacher_id": user["user_id"], "followup_date": datetime.now().strftime("%Y-%m-%d"),
                "followup_type": ftype, "notes": notes, "regularity_status": regularity
            })
            st.success("✅ تم تسجيل الافتقاد بنجاح")
            time.sleep(1)
            st.rerun()

# ---------- طالباتي (عرض سريع) ----------
def show_my_students(db: Database):
    st.markdown("<h2 class='main-header'>👩‍🎓 طالباتي</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()
    if role == "Teacher" and section_id:
        my_students = students[students.section_id == section_id] if not students.empty else pd.DataFrame()
    elif role == "Service Manager" and section_id:
        my_students = students[students.section_id == section_id] if not students.empty else students
    else:
        my_students = students
    if my_students.empty:
        st.info("لا توجد طالبات مسجلات في فصلك.")
        return
    if not followup.empty:
        latest_fup = followup.sort_values("followup_date").groupby("student_id").last().reset_index()
        my_students = my_students.merge(latest_fup[["student_id", "regularity_status"]], on="student_id", how="left")
        my_students["regularity_status"] = my_students["regularity_status"].fillna("غير معروف")
    else:
        my_students["regularity_status"] = "غير معروف"
    st.dataframe(my_students[["full_name", "phone", "regularity_status"]], use_container_width=True)

# ---------- درجات مسابقات الفصل (للمدرسات فقط) ----------
def show_class_competition_scores(db: Database):
    st.markdown("<h2 class='main-header'>🏆 درجات مسابقات الفصل</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    if role != "Teacher" or not section_id:
        st.error("🚫 هذه الصفحة متاحة للمدرسات فقط.")
        return
    students = db.get_students()
    quizzes = db.get_quizzes()
    results = db.get_quiz_results()
    section_students = students[students.section_id == section_id] if not students.empty else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات مسجلات في فصلك.")
        return
    section_student_ids = section_students["student_id"].tolist()
    if not results.empty and "student_id" in results.columns:
        class_results = results[(results["student_id"].isin(section_student_ids)) & (results["status"] == "submitted")]
    else:
        class_results = pd.DataFrame()
    if not quizzes.empty and not class_results.empty and "quiz_id" in class_results.columns:
        class_results = class_results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
        class_results = class_results.rename(columns={"title": "اسم المسابقة"})
    if not class_results.empty:
        class_results = class_results.merge(section_students[["student_id", "full_name"]], on="student_id", how="left")
        class_results = class_results.rename(columns={"full_name": "اسم الطالبة"})
        class_results["score"] = pd.to_numeric(class_results["score"], errors="coerce").fillna(0)
        class_results["total_marks"] = pd.to_numeric(class_results["total_marks"], errors="coerce").fillna(20)
        st.dataframe(class_results[["اسم المسابقة", "اسم الطالبة", "score", "total_marks", "submission_time"]], use_container_width=True)
    else:
        st.info("لا توجد نتائج مسابقات لطالبات فصلك بعد.")

# ---------- المسابقات والاختبارات ----------
def show_quizzes(db: Database):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    quizzes = db.get_quizzes()
    if role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد")
        with st.form("quiz_form"):
            title = st.text_input("عنوان الاختبار*")
            num_questions = st.selectbox("عدد الأسئلة", [10, 20, 30], index=1)
            time_limit = st.number_input("الوقت (بالدقائق)", 1, 180, 15)
            total_marks = st.number_input("الدرجة الكلية", 1, 100, 20)
            expiry = st.date_input("تاريخ الانتهاء", datetime.now() + timedelta(days=7))
            if st.form_submit_button("إنشاء"):
                if not title:
                    st.error("يرجى إدخال عنوان الاختبار")
                else:
                    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    pwd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    quiz_id = str(uuid.uuid4())
                    db.add_quiz({
                        "quiz_id": quiz_id, "title": title, "description": "",
                        "created_by": user["user_id"], "section_id": "",
                        "num_questions": num_questions, "time_limit_minutes": time_limit,
                        "total_marks": total_marks, "expiry_date": expiry.strftime("%Y-%m-%d"),
                        "quiz_code": code, "password": pwd, "is_active": "True"
                    })
                    st.success(f"✅ تم إنشاء الاختبار! الكود: {code}")
                    time.sleep(2)
                    st.rerun()
        st.markdown("---")
        st.subheader("📝 إدارة الأسئلة")
        if not quizzes.empty:
            active_quizzes = quizzes[quizzes.is_active == "True"]
            if not active_quizzes.empty:
                quiz_choice = st.selectbox("اختر اختباراً لإدارة أسئلته", active_quizzes["quiz_id"],
                                           format_func=lambda x: active_quizzes[active_quizzes.quiz_id==x]["title"].values[0])
                if quiz_choice:
                    questions = db.get_quiz_questions(quiz_choice)
                    st.markdown(f"**عدد الأسئلة:** {len(questions)}")
                    if not questions.empty:
                        st.dataframe(questions[["question_text", "question_type", "correct_answer"]], use_container_width=True)
                    with st.form("add_question_form"):
                        qtext = st.text_area("نص السؤال*")
                        qtype = st.selectbox("نوع السؤال", ["اختيار من متعدد", "صح وخطأ", "أكمل", "إجابة قصيرة"])
                        opts = {}
                        if qtype == "اختيار من متعدد":
                            cols = st.columns(4)
                            opts["option1"] = cols[0].text_input("الخيار 1")
                            opts["option2"] = cols[1].text_input("الخيار 2")
                            opts["option3"] = cols[2].text_input("الخيار 3")
                            opts["option4"] = cols[3].text_input("الخيار 4")
                        elif qtype == "صح وخطأ":
                            opts["option1"] = "صح"; opts["option2"] = "خطأ"
                        else:
                            opts["option1"] = opts["option2"] = opts["option3"] = opts["option4"] = ""
                        correct = st.text_input("الإجابة الصحيحة*")
                        if st.form_submit_button("إضافة سؤال"):
                            if not qtext or not correct:
                                st.error("نص السؤال والإجابة الصحيحة مطلوبان")
                            else:
                                db.add_question({
                                    "question_id": str(uuid.uuid4()), "quiz_id": quiz_choice,
                                    "question_text": qtext, "question_type": qtype,
                                    "option1": opts.get("option1", ""), "option2": opts.get("option2", ""),
                                    "option3": opts.get("option3", ""), "option4": opts.get("option4", ""),
                                    "correct_answer": correct
                                })
                                st.success("✅ تمت إضافة السؤال")
                                time.sleep(1)
                                st.rerun()
                    if not questions.empty:
                        del_q = st.selectbox("اختر سؤالاً لحذفه", questions["question_id"])
                        if st.button("حذف السؤال"):
                            db.delete_question(del_q)
                            st.success("تم الحذف")
                            time.sleep(1)
                            st.rerun()
        st.markdown("---")
        st.subheader("📋 إدارة الاختبارات")
        if quizzes.empty:
            st.info("لا توجد اختبارات بعد.")
        else:
            for _, q in quizzes.iterrows():
                qid = q["quiz_id"]
                title = q["title"]
                active = q.get("is_active", "True") == "True"
                code = q.get("quiz_code", "")
                expiry = q.get("expiry_date", "")
                col1, col2, col3, col4 = st.columns([3,2,2,2])
                col1.write(f"**{title}**")
                col2.write(f"الكود: {code}")
                col3.write("حالة: " + ("🟢 نشط" if active else "🔴 مغلق"))
                col4.write(f"ينتهي: {expiry}")
                col_actions = st.columns(4)
                if active:
                    if col_actions[0].button("إغلاق", key=f"deact_{qid}"):
                        db.update_quiz(qid, {"is_active": "False"})
                        st.success(f"تم إغلاق الاختبار: {title}")
                        time.sleep(1)
                        st.rerun()
                else:
                    if col_actions[0].button("تفعيل", key=f"act_{qid}"):
                        db.update_quiz(qid, {"is_active": "True"})
                        st.success(f"تم تفعيل الاختبار: {title}")
                        time.sleep(1)
                        st.rerun()
                if col_actions[1].button("حذف (النتائج تبقى)", key=f"del_keep_{qid}"):
                    db.delete_quiz_keep_results(qid)
                    st.success(f"تم حذف الاختبار '{title}' مع الاحتفاظ بالنتائج.")
                    time.sleep(1)
                    st.rerun()
                st.markdown("---")
    st.markdown("### 📊 نتائج الاختبارات")
    results = db.get_quiz_results()
    if not results.empty:
        results = results[results["status"] == "submitted"]
        if role == "Teacher" and section_id:
            students = db.get_students()
            section_student_ids = students[students.section_id == section_id]["student_id"].tolist()
            results = results[results.student_id.isin(section_student_ids)]
        st.dataframe(results[["student_name", "score", "total_marks", "submission_time"]], use_container_width=True)
    else:
        st.info("لا توجد نتائج بعد.")

# ---------- التقارير والإحصائيات ----------
def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    attendance = db.get_attendance()
    students = db.get_students()
    if role in ["Teacher", "Service Manager"] and section_id:
        attendance = attendance[attendance.section_id == section_id] if not attendance.empty else attendance
        students = students[students.section_id == section_id] if not students.empty else students
    if attendance.empty:
        st.info("لا توجد بيانات حضور.")
        return
    attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    st.subheader("📅 تقرير الغياب الشهري")
    col1, col2 = st.columns(2)
    month = col1.selectbox("الشهر", range(1,13), index=datetime.now().month-1)
    year = col2.number_input("السنة", value=datetime.now().year, min_value=2020)
    monthly = attendance[(attendance.date.dt.month == month) & (attendance.date.dt.year == year)]
    if not monthly.empty:
        summary = monthly.groupby(["student_id", "status"]).size().reset_index(name="count")
        pivot = summary.pivot(index="student_id", columns="status", values="count").fillna(0).reset_index()
        if not students.empty:
            pivot = pivot.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(pivot, use_container_width=True)
        fig = px.pie(monthly, names="status", title=f"نسب الحضور لشهر {month}/{year}")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات لهذا الشهر.")
    st.markdown("---")
    st.subheader("🏆 أكثر 10 طالبات غياباً")
    if not attendance.empty:
        absent_counts = attendance[attendance.status == "غائب"].groupby("student_id").size().reset_index(name="أيام الغياب")
        absent_counts = absent_counts.sort_values("أيام الغياب", ascending=False).head(10)
        if not students.empty:
            absent_counts = absent_counts.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(absent_counts[["full_name", "أيام الغياب"]], use_container_width=True)

# ---------- سجل العمليات ----------
def show_logs(db: Database):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db.get_logs()
    if not logs.empty:
        logs["timestamp"] = pd.to_datetime(logs["timestamp"])
        st.dataframe(logs.sort_values("timestamp", ascending=False), use_container_width=True)
        del_id = st.selectbox("اختر سجلاً لحذفه", logs["log_id"], key="del_log_sel")
        if st.button("حذف السجل"):
            db.delete_log(del_id)
            st.success("تم الحذف")
            time.sleep(1)
            st.rerun()
    else:
        st.info("لا توجد سجلات.")

# ---------- تغيير كلمة المرور ----------
def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    with st.form("change_password_form"):
        old = st.text_input("كلمة المرور الحالية", type="password")
        new = st.text_input("كلمة المرور الجديدة", type="password")
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old or not new or not confirm:
                st.error("الرجاء ملء جميع الحقول")
            elif not verify_password(old, st.session_state.user.get("password", "")):
                st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new) < MIN_PASSWORD_LENGTH:
                st.error(f"كلمة المرور الجديدة يجب ألا تقل عن {MIN_PASSWORD_LENGTH} أحرف")
            elif new != confirm:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                hashed = hash_password(new)
                db.update_user(st.session_state.user["user_id"], {"password": hashed})
                st.session_state.user["password"] = hashed
                st.success("✅ تم تغيير كلمة المرور بنجاح!")
                db.add_log(st.session_state.user["user_id"], "تغيير كلمة المرور")

# =============================================================================
# التطبيق الرئيسي (Main Entry Point)
# =============================================================================
def main():
    inject_css()
    init_session()

    # تحميل الإعدادات وبناء كائن قاعدة البيانات
    try:
        spreadsheet_id = get_spreadsheet_id()
        jwt_secret = get_jwt_secret()
        credentials_dict = st.secrets["gcp_service_account"]  # قاموس الاعتماد للتخزين المؤقت
        db = Database(spreadsheet_id, credentials_dict)
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال: {e}")
        st.stop()

    # زر المساعدة العائم
    if st.button("🆘 مركز المساعدة", key="fixed_help_btn"):
        st.session_state.open_help_dialog = True
        st.rerun()

    # إذا كانت الطالبة تؤدي اختباراً
    if st.session_state.get("student_quiz_started"):
        show_student_quiz(db)
        return

    # تسجيل الدخول للمستخدمين
    if not st.session_state.get("authenticated"):
        show_login_page(db, jwt_secret)
        return

    # التحقق من صلاحية رمز JWT (قد يكون انتهى)
    token_data = verify_token(st.session_state.token, jwt_secret)
    if not token_data:
        st.error("⏰ انتهت صلاحية الجلسة. يرجى تسجيل الدخول مجدداً.")
        st.session_state.clear()
        time.sleep(2)
        st.rerun()
        return

    # التحكم في إظهار القائمة الجانبية
    if not st.session_state.show_sidebar:
        # إخفاء القائمة الجانبية
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] {
            transform: translateX(100%) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        if st.button("☰", key="show_sidebar_btn"):
            st.session_state.show_sidebar = True
            st.rerun()
    else:
        show_sidebar_navigation(db)

    # استخراج اختيار القائمة الحالي مع التحقق من الصلاحية
    choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
    user_role = st.session_state.user["role"]
    menu_items = ROLE_MENUS.get(user_role, [])

    # إعادة التوجيه التلقائي للصفحات غير المصرحة
    if choice == "👥 إدارة المستخدمين" and user_role != "System Admin":
        st.error("🚫 غير مصرح")
        st.session_state.menu_choice = "🏠 لوحة التحكم"
        st.rerun()
    elif choice == "📜 سجل العمليات" and user_role != "System Admin":
        st.error("🚫 غير مصرح")
        st.session_state.menu_choice = "🏠 لوحة التحكم"
        st.rerun()
    elif choice == "📋 الحضور" and user_role == "Service Manager":
        st.error("🚫 غير مصرح")
        st.session_state.menu_choice = "🏠 لوحة التحكم"
        st.rerun()
    elif choice == "🏆 درجات المسابقات" and user_role != "Teacher":
        st.error("🚫 غير مصرح")
        st.session_state.menu_choice = "🏠 لوحة التحكم"
        st.rerun()

    # عرض المحتوى حسب الاختيار
    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    if choice == "🏠 لوحة التحكم":
        show_dashboard(db)
    elif choice == "👥 إدارة المستخدمين":
        show_user_management(db)
    elif choice == "👩‍🎓 طالباتي":
        show_my_students(db)
    elif choice == "📋 الحضور":
        show_attendance(db)
    elif choice == "💬 الافتقاد":
        show_followup(db)
    elif choice == "🏆 درجات المسابقات":
        show_class_competition_scores(db)
    elif choice == "📝 المسابقات والاختبارات":
        show_quizzes(db)
    elif choice == "📊 التقارير والإحصائيات":
        show_reports(db)
    elif choice == "📜 سجل العمليات":
        show_logs(db)
    elif choice == "🔒 تغيير كلمة المرور":
        change_password(db)
    st.markdown("</div>", unsafe_allow_html=True)

    # عرض نافذة المساعدة إذا طلبها المستخدم
    if st.session_state.get("open_help_dialog"):
        show_help_dialog()
        st.session_state.open_help_dialog = False

if __name__ == "__main__":
    main()
