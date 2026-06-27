import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import uuid
import json
import random
import string
import jwt
import time
import requests
from functools import wraps
import threading
import numpy as np

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
QUIZ_JWT_SECRET = "StDemianaChurch2025!QuizSecure#Key"
CACHE_TTL_SECONDS = 600  # 10 دقائق
CAIRO_TZ = timezone(timedelta(hours=3), name='Africa/Cairo')

def get_cairo_now():
    return datetime.now(CAIRO_TZ)

def format_cairo_time(dt):
    if dt is None:
        return "غير متاح"
    return dt.astimezone(CAIRO_TZ).strftime("%Y-%m-%d %I:%M:%S %p")

st.set_page_config(
    page_title="نظام- كنيسة الشهيدة دميانة",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CSS عصري احترافي
# =============================================================================
def inject_css():
    st.markdown("""
    <style>
    /* الخطوط والألوان */
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap');
    :root {
        --primary: #0f172a;
        --primary-light: #3b82f6;
        --secondary: #64748b;
        --bg: #f8fafc;
        --surface: #ffffff;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --text-primary: #1e293b;
        --text-secondary: #64748b;
        --border: #e2e8f0;
        --radius-card: 12px;
        --radius-btn: 8px;
        --shadow-card: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
        --shadow-hover: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
        --transition: all 0.3s ease;
    }
    * { font-family: 'Cairo', sans-serif; }
    body { direction: rtl; text-align: right; background-color: var(--bg); color: var(--text-primary); }
    .stApp { background: var(--bg); }

    /* إخفاء عناصر Streamlit الافتراضية */
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stSidebarNavToggle"],
    [data-testid="stSidebarCollapseButton"] { display: none !important; }

    /* الشريط الجانبي */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
        border-left: 1px solid var(--border) !important;
        box-shadow: var(--shadow-card);
        padding-top: 1.5rem !important;
        transition: transform 0.3s ease !important;
        z-index: 10000 !important;
        width: 280px !important;
    }

    /* أزرار عائمة */
    .floating-show-btn .stButton > button {
        position: fixed !important;
        top: 20px !important;
        right: 20px !important;
        z-index: 99999 !important;
        background: linear-gradient(135deg, var(--primary-light), #2563eb) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        width: 52px !important;
        height: 52px !important;
        font-size: 26px !important;
        font-weight: bold !important;
        box-shadow: var(--shadow-card) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: var(--transition) !important;
    }
    .floating-show-btn .stButton > button:hover {
        transform: scale(1.05) !important;
        box-shadow: var(--shadow-hover) !important;
    }
    .help-float-btn .stButton > button {
        position: fixed !important;
        top: 20px !important;
        right: 90px !important;
        z-index: 99998 !important;
        background: var(--warning) !important;
        color: white !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
        border: none !important;
        box-shadow: var(--shadow-card) !important;
        transition: var(--transition) !important;
    }
    .help-float-btn .stButton > button:hover {
        transform: scale(1.04) !important;
        box-shadow: var(--shadow-hover) !important;
    }

    /* بطاقة المستخدم */
    .user-profile-card {
        background: linear-gradient(135deg, var(--primary-light), #2563eb);
        border-radius: var(--radius-card);
        padding: 1rem;
        margin: 1rem 0;
        color: white;
        box-shadow: var(--shadow-card);
        text-align: center;
    }

    /* أزرار عامة */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-light), #2563eb);
        color: white;
        border: none;
        border-radius: var(--radius-btn);
        font-weight: 600;
        transition: var(--transition);
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-hover);
    }

    /* بطاقات */
    .custom-card {
        background: var(--surface);
        border-radius: var(--radius-card);
        padding: 1.5rem;
        box-shadow: var(--shadow-card);
        margin-bottom: 1rem;
        border: 1px solid var(--border);
        transition: var(--transition);
    }
    .custom-card:hover {
        box-shadow: var(--shadow-hover);
        transform: translateY(-2px);
    }

    /* عناوين */
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--primary-light);
    }

    /* أزرار القائمة */
    .nav-btn-container .stButton > button {
        width: 100%;
        text-align: right;
        justify-content: flex-start;
        padding: 0.7rem 1rem;
        background: transparent;
        color: var(--text-primary);
        border: none;
        box-shadow: none;
        font-weight: 500;
        border-radius: var(--radius-btn);
    }
    .nav-btn-container .stButton > button:hover {
        background: rgba(59,130,246,0.1);
    }
    .nav-btn-container .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--primary-light), #2563eb);
        color: white;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    /* جداول */
    .stDataFrame {
        border-radius: var(--radius-card) !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        border: 1px solid var(--border) !important;
    }

    /* نماذج */
    .stForm {
        background: var(--surface);
        padding: 1.5rem;
        border-radius: var(--radius-card);
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        border: 1px solid var(--border);
    }

    /* تبويبات */
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] {
        background: var(--surface);
        border-radius: var(--radius-btn) var(--radius-btn) 0 0;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        border: 1px solid var(--border);
        border-bottom: none;
        color: var(--text-secondary);
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary-light), #2563eb) !important;
        color: white !important;
    }

    /* مؤقت */
    .quiz-timer {
        background: linear-gradient(135deg, var(--primary-light), #2563eb);
        color: white;
        border-radius: var(--radius-card);
        padding: 0.8rem 1.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
    }

    @media (max-width: 768px) {
        .floating-show-btn .stButton > button {
            width: 44px; height: 44px; font-size: 22px; top: 12px; right: 12px;
        }
        .help-float-btn .stButton > button {
            right: 68px; top: 12px; padding: 8px 14px; font-size: 14px;
        }
        .main-header { font-size: 1.4rem; margin-top: 80px; }
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# Telegram & Support
# =============================================================================
def get_telegram_config():
    try:
        return st.secrets["telegram"]["bot_token"], st.secrets["telegram"]["chat_id"]
    except:
        return None, None

def get_support_config():
    try:
        return (
            st.secrets.get("support", {}).get("contact_name", "مسؤول النظام"),
            st.secrets.get("support", {}).get("whatsapp", "")
        )
    except:
        return "مسؤول النظام", ""

def get_credentials():
    try:
        return Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    except Exception as e:
        st.error(f"❌ خطأ في بيانات اعتماد Google: {e}")
        st.stop()

def get_spreadsheet_id():
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
    try:
        return st.secrets["sheets"]["jwt_secret"]
    except:
        return DEFAULT_JWT_SECRET

# =============================================================================
# إدارة الجلسة والتخزين المؤقت
# =============================================================================
def init_data_cache():
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
    if 'data_dirty' not in st.session_state:
        st.session_state.data_dirty = {}

def init_session():
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
        "quiz_submit_time": None,
        "quiz_token": None,
        "quiz_answers": {},
        "quiz_submitted": False,
        "last_score": 0,
        "menu_choice": "🏠 لوحة التحكم",
        "show_sidebar": True,
        "open_help_dialog": False,
        "current_attempt_id": None,
        "last_saved_answers_str": "",
        "quiz_questions": None,
        "show_review": False,
        "data_errors": [],
        "data_validated": False,
        "quiz_load_failures": 0
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout(db=None):
    if db and st.session_state.user:
        try:
            db.add_log(st.session_state.user["user_id"], "تسجيل خروج", "خروج يدوي")
        except:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# =============================================================================
# Retry Decorator
# =============================================================================
def retry_operation(max_retries=5, base_delay=2):
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
# Database Class – الأساسية مع السجلات المطورة
# =============================================================================
class Database:
    _request_times = []
    _lock = threading.Lock()

    @staticmethod
    def _rate_limit():
        now = time.time()
        with Database._lock:
            Database._request_times = [t for t in Database._request_times if now - t < 60]
            if len(Database._request_times) >= 40:
                sleep_time = 60 - (now - Database._request_times[0]) + 1
                if sleep_time > 0:
                    time.sleep(sleep_time)
                Database._request_times = []
            Database._request_times.append(time.time())

    def __init__(self, creds, spreadsheet_id):
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(self, name, columns):
        Database._rate_limit()
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(columns), 1))
            if columns:
                ws.append_row(columns)
        time.sleep(0.2)
        return ws

    def _get_cached_df(self, sheet_name, fetch_func):
        init_data_cache()
        cache = st.session_state.data_cache
        dirty = st.session_state.data_dirty
        now = time.time()
        if sheet_name in cache and not dirty.get(sheet_name, False):
            entry = cache[sheet_name]
            if now - entry['timestamp'] < CACHE_TTL_SECONDS:
                return entry['data'].copy()
        df = fetch_func()
        st.session_state.data_cache[sheet_name] = {'data': df.copy(), 'timestamp': now}
        st.session_state.data_dirty[sheet_name] = False
        return df.copy()

    def _invalidate_cache(self, sheet_name):
        init_data_cache()
        st.session_state.data_dirty[sheet_name] = True

    def _read_sheet_raw(self, sheet_name):
        Database._rate_limit()
        ws = self._get_or_create_worksheet(sheet_name, [])
        values = ws.get_all_values()
        time.sleep(0.2)
        if not values or len(values) < 1:
            return pd.DataFrame()
        raw_headers = [h.strip() for h in values[0]]
        seen = {}
        unique_headers = []
        for h in raw_headers:
            if h in seen:
                seen[h] += 1
                unique_headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 0
                unique_headers.append(h)
        data_rows = values[1:]
        df = pd.DataFrame(data_rows, columns=unique_headers)
        df.dropna(how='all', axis=1, inplace=True)
        df.dropna(how='all', inplace=True)
        return df.astype(object)

    def _sheet_to_df(self, sheet_name):
        return self._get_cached_df(sheet_name, lambda: self._read_sheet_raw(sheet_name))

    def _df_to_sheet(self, sheet_name, df, columns):
        if not isinstance(df, pd.DataFrame):
            raise ValueError("df must be a DataFrame")
        Database._rate_limit()
        ws = self._get_or_create_worksheet(sheet_name, columns)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        work_df = df[columns].copy()
        work_df.fillna("", inplace=True)
        work_df = work_df.astype(str)
        values = [columns] + work_df.values.tolist()
        try:
            ws.resize(rows=len(values), cols=len(columns))
            ws.update(values)
            time.sleep(0.2)
            self._invalidate_cache(sheet_name)
        except Exception as e:
            raise e

    @staticmethod
    def _safe_str(value):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, (dict, list)):
            return str(value)
        return str(value)

    # ---------- المستخدمين ----------
    def get_users(self):
        return self._sheet_to_df("Users")

    def add_user(self, user_data):
        df = self.get_users()
        if df.empty:
            df = pd.DataFrame(columns=["user_id", "username", "password", "role",
                                       "full_name", "section_id", "phone", "email"])
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        self._df_to_sheet("Users", df, ["user_id", "username", "password", "role",
                                        "full_name", "section_id", "phone", "email"])

    def update_user(self, user_id, updates):
        df = self.get_users()
        idx = df[df.user_id == user_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Users", df, df.columns.tolist())

    def delete_user(self, user_id):
        df = self.get_users()
        df = df[df.user_id != user_id]
        self._df_to_sheet("Users", df, df.columns.tolist())

    # ---------- المراحل ----------
    def get_stages(self):
        return self._sheet_to_df("Stages")

    def add_stage(self, stage_data):
        df = self.get_stages()
        if df.empty:
            df = pd.DataFrame(columns=["stage_id", "stage_name", "manager_user_id"])
        new_row = {"stage_id": stage_data["stage_id"], "stage_name": stage_data["stage_name"],
                   "manager_user_id": stage_data.get("manager_user_id", "")}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])

    def update_stage(self, stage_id, updates):
        df = self.get_stages()
        idx = df[df.stage_id == stage_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])

    def delete_stage(self, stage_id):
        df = self.get_stages()
        df = df[df.stage_id != stage_id]
        self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])

    # ---------- الفصول ----------
    def get_sections(self):
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data):
        self._get_or_create_worksheet("Sections", ["section_id", "section_name", "manager_user_id"])
        df = self.get_sections()
        if df.empty:
            df = pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
        new_row = {"section_id": sec_data["section_id"], "section_name": sec_data["section_name"],
                   "manager_user_id": sec_data.get("manager_user_id", "")}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    def update_section(self, section_id, updates):
        df = self.get_sections()
        idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, df.columns.tolist())

    # ---------- الطالبات ----------
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
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Students", df, df.columns.tolist())

    def delete_student(self, student_id):
        df = self.get_students()
        df = df[df.student_id != student_id]
        self._df_to_sheet("Students", df, df.columns.tolist())

    # ---------- الحضور ----------
    def get_attendance(self):
        return self._sheet_to_df("Attendance")

    def batch_add_attendance(self, records_list):
        if not records_list:
            return
        df = self.get_attendance()
        if df.empty:
            df = pd.DataFrame(columns=["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
        existing_ids = set(df["record_id"].tolist()) if not df.empty else set()
        new_records = []
        for rec in records_list:
            if rec["record_id"] in existing_ids:
                idx = df[df.record_id == rec["record_id"]].index[0]
                for k, v in rec.items():
                    df.at[idx, k] = self._safe_str(v)
            else:
                new_records.append(rec)
        if new_records:
            new_df = pd.DataFrame(new_records)
            df = pd.concat([df, new_df], ignore_index=True)
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    def get_attendance_by_date_section(self, date_str, section_id):
        df = self.get_attendance()
        if df.empty:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    def delete_attendance_record(self, record_id):
        df = self.get_attendance()
        df = df[df.record_id != record_id]
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    # ---------- الافتقاد ----------
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record):
        df = self.get_followup()
        if not df.empty:
            duplicate = df[(df.student_id == record["student_id"]) &
                           (df.followup_date == record["followup_date"]) &
                           (df.followup_type == record["followup_type"])]
            if not duplicate.empty:
                raise ValueError("⛔ تم تسجيل نفس الافتقاد مسبقاً لنفس الطالبة في نفس التاريخ ونفس النوع.")
        if df.empty:
            df = pd.DataFrame(columns=["record_id", "student_id", "teacher_id", "followup_date",
                                       "followup_type", "notes", "regularity_status"])
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date",
                                           "followup_type", "notes", "regularity_status"])

    def delete_followup_record(self, record_id):
        df = self.get_followup()
        df = df[df.record_id != record_id]
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date",
                                           "followup_type", "notes", "regularity_status"])

    # ---------- الاختبارات ----------
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
                df.at[idx[0], k] = self._safe_str(v)
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
                                               "score", "total_marks", "start_time", "submission_time", "answers", "status"])

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

    def get_quiz_results(self, quiz_id=None):
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return pd.DataFrame()
        if quiz_id:
            return df[df.quiz_id == quiz_id]
        return df

    def start_quiz_attempt(self, quiz_id, student_id, student_name):
        result_id = str(uuid.uuid4())
        now_iso = get_cairo_now().isoformat()
        new_row = {
            "result_id": result_id, "quiz_id": quiz_id, "student_id": student_id,
            "student_name": student_name, "score": "", "total_marks": "20",
            "start_time": now_iso, "submission_time": now_iso, "answers": "{}", "status": "started"
        }
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            df = pd.DataFrame(columns=["result_id", "quiz_id", "student_id", "student_name",
                                       "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        return result_id

    def save_answers(self, result_id, answers_dict):
        df = self._sheet_to_df("QuizResults")
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "answers"] = json.dumps(answers_dict, ensure_ascii=False)
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def submit_quiz_attempt(self, result_id, score, answers_json):
        df = self._sheet_to_df("QuizResults")
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "score"] = str(score)
            df.at[idx[0], "answers"] = answers_json
            df.at[idx[0], "submission_time"] = get_cairo_now().isoformat()
            df.at[idx[0], "status"] = "submitted"
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def delete_quiz_result(self, result_id):
        df = self._sheet_to_df("QuizResults")
        df = df[df.result_id != result_id]
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    # ---------- السجلات ----------
    def get_logs(self):
        return self._sheet_to_df("Logs")

    def add_log(self, user_id, action, details=""):
        log = {
            "log_id": str(uuid.uuid4()),
            "timestamp": get_cairo_now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": str(details)
        }
        df = self.get_logs()
        if df.empty:
            df = pd.DataFrame(columns=["log_id", "timestamp", "user_id", "action", "details"])
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

    def delete_log(self, log_id):
        df = self.get_logs()
        df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

# =============================================================================
# JWT والمصادقة
# =============================================================================
def generate_token(user: dict, secret: str) -> str:
    payload = {
        "user_id": user.get("user_id", ""),
        "role": user.get("role", ""),
        "full_name": user.get("full_name", ""),
        "section_id": user.get("section_id", ""),
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def generate_quiz_token(quiz_id: str, student_id: str) -> str:
    payload = {
        "quiz_id": quiz_id,
        "student_id": student_id,
        "exp": datetime.utcnow() + timedelta(hours=48)
    }
    return jwt.encode(payload, QUIZ_JWT_SECRET, algorithm="HS256")

def verify_quiz_token(token: str):
    try:
        return jwt.decode(token, QUIZ_JWT_SECRET, algorithms=["HS256"])
    except:
        return None

def verify_token(token: str, secret: str):
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except:
        return None

# =============================================================================
# إرسال Telegram
# =============================================================================
def send_telegram_message(message: str) -> bool:
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def send_telegram_photo(caption: str, file_bytes, filename: str) -> bool:
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    files = {'photo': (filename, file_bytes)}
    data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, data=data, files=files, timeout=15)
        return response.status_code == 200
    except:
        return False

# =============================================================================
# المساعدة المنبثقة
# =============================================================================
@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    hdr_col1, hdr_col2 = st.columns([0.85, 0.15])
    with hdr_col1:
        st.markdown("<h3 style='text-align:center; color:#3b82f6;'>📬 تواصل معنا</h3>", unsafe_allow_html=True)
    with hdr_col2:
        if st.button("✕ إغلاق", key="help_dialog_close_btn"):
            st.session_state.open_help_dialog = False
            st.rerun()
    contact_name, contact_whatsapp = get_support_config()
    if contact_whatsapp:
        st.info(f"📞 للدعم المباشر: {contact_name} - {contact_whatsapp}")
    with st.form("help_form_enhanced", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("الاسم *")
            whatsapp = st.text_input("رقم الواتساب *")
        with col2:
            issue_type = st.selectbox("نوع المشكلة *", ["مشكلة تقنية", "مشكلة في البيانات", "طلب مساعدة", "اقتراح تحسين", "أخرى"])
            urgency = st.selectbox("الأولوية", ["عادي", "مستعجل", "طارئ جداً"])
        issue_desc = st.text_area("وصف المشكلة *", height=150)
        uploaded_file = st.file_uploader("📎 إرفاق لقطة شاشة (اختياري)", type=["png", "jpg", "jpeg"])
        if st.form_submit_button("🚀 إرسال الطلب"):
            if not name or not whatsapp or not issue_desc:
                st.error("⚠️ الرجاء ملء جميع الحقول المطلوبة")
            else:
                message = (
                    f"🔔 بلاغ جديد من مركز المساعدة\n"
                    f"👤 الاسم: {name}\n"
                    f"📱 الواتساب: {whatsapp}\n"
                    f"📂 النوع: {issue_type}\n"
                    f"⚡ الأولوية: {urgency}\n"
                    f"📝 التفاصيل: {issue_desc}"
                )
                success = send_telegram_message(message)
                if uploaded_file:
                    success &= send_telegram_photo(message, uploaded_file.getvalue(), uploaded_file.name)
                if success:
                    st.success("✅ تم إرسال طلبك بنجاح!")
                    st.balloons()
                else:
                    st.error("❌ فشل الإرسال، يرجى المحاولة لاحقاً أو التواصل مباشرة عبر الواتساب.")

# =============================================================================
# التحقق من سلامة البيانات
# =============================================================================
def validate_data_integrity(db: Database):
    errors = []
    students = db.get_students()
    sections = db.get_sections()
    if not students.empty and not sections.empty:
        valid_sections = set(sections["section_id"].tolist())
        for _, row in students.iterrows():
            sid = row.get("section_id", "")
            if pd.isna(sid) or str(sid).strip() == "":
                errors.append(f"الطالبة {row.get('full_name', '')} ليس لديها فصل.")
            elif str(sid).strip() not in valid_sections:
                errors.append(f"الطالبة {row.get('full_name', '')} تنتمي لفصل غير موجود ({sid}).")
    return errors

def auto_fix_missing_sections(db: Database):
    students = db.get_students()
    sections = db.get_sections()
    if students.empty:
        return False
    existing_ids = set(sections["section_id"].tolist()) if not sections.empty else set()
    students_ids = students["section_id"].dropna().unique().tolist()
    missing = [sid for sid in students_ids if sid and str(sid).strip() not in existing_ids]
    for sid in missing:
        db.add_section({"section_id": str(sid), "section_name": f"فصل (معرف {sid[:8]})"})
    return len(missing) > 0

# =============================================================================
# التهيئة وتسجيل الدخول
# =============================================================================
def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='custom-card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", use_container_width=True):
            admin_data = {
                "user_id": "admin-001", "username": "admin", "password": "admin123",
                "role": "System Admin", "full_name": "مدير النظام",
                "section_id": "", "phone": "0100000000", "email": "admin@church.com"
            }
            db.add_user(admin_data)
            db.add_log("admin-001", "تهيئة النظام", "تم إنشاء مدير النظام الافتراضي")
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            time.sleep(2)
            st.rerun()
        st.stop()

def show_login_page(db: Database, jwt_secret: str):
    st.markdown("<h1 class='main-header'>⛪ كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
    show_initialization(db)
    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم").strip()
            password = st.text_input("كلمة المرور", type="password").strip()
            if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                if not username or not password:
                    st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                else:
                    users = db.get_users()
                    user_row = users[users.username == username]
                    if user_row.empty:
                        st.error("اسم المستخدم غير موجود")
                    else:
                        user = user_row.iloc[0].to_dict()
                        if password == user.get("password", ""):
                            token = generate_token(user, jwt_secret)
                            st.session_state.token = token
                            st.session_state.user = user
                            st.session_state.authenticated = True
                            st.session_state.menu_choice = "🏠 لوحة التحكم"
                            st.session_state.show_sidebar = True
                            db.add_log(user["user_id"], "تسجيل الدخول", f"تسجيل دخول بواسطة {username}")
                            st.success("تم تسجيل الدخول بنجاح!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("كلمة المرور غير صحيحة")
    with tab2:
        st.subheader("دخول الاختبار الإلكتروني")
        with st.form("student_login_form"):
            code = st.text_input("كود الاختبار").strip()
            passwd = st.text_input("كلمة مرور الاختبار", type="password").strip()
            if st.form_submit_button("بدء الاختبار", use_container_width=True):
                if not code or not passwd:
                    st.error("الرجاء إدخال الكود وكلمة المرور")
                else:
                    quizzes = db.get_quizzes()
                    quiz = quizzes[(quizzes.quiz_code == code) & (quizzes.password == passwd)]
                    if quiz.empty:
                        st.error("كود أو كلمة مرور خاطئة")
                    else:
                        quiz = quiz.iloc[0].to_dict()
                        expiry = pd.to_datetime(quiz["expiry_date"]).to_pydatetime().replace(tzinfo=CAIRO_TZ)
                        if expiry < get_cairo_now():
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
                            st.session_state.quiz_submit_time = None
                            st.session_state.quiz_token = None
                            st.session_state.quiz_answers = {}
                            st.session_state.quiz_submitted = False
                            st.session_state.last_score = 0
                            st.session_state.current_attempt_id = None
                            st.session_state.last_saved_answers_str = ""
                            st.session_state.quiz_questions = None
                            st.session_state.show_review = False
                            st.rerun()

# =============================================================================
# واجهة الطالبة للاختبار
# =============================================================================
def grade_attempt(db, quiz_id, answers_dict):
    questions = db.get_quiz_questions(quiz_id)
    if questions.empty:
        return 0
    correct_count = 0
    for _, q_row in questions.iterrows():
        q = q_row.to_dict()
        correct = str(q.get("correct_answer", "")).strip().lower()
        student_ans = str(answers_dict.get(q.get("question_id", ""), "")).strip().lower()
        if correct == student_ans:
            correct_count += 1
    num_q = len(questions)
    return round((correct_count / num_q) * 20, 1) if num_q > 0 else 0

def save_current_answers(db):
    if not st.session_state.current_attempt_id:
        return
    current_answers = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
    if current_answers != st.session_state.last_saved_answers_str:
        db.save_answers(st.session_state.current_attempt_id, st.session_state.quiz_answers)
        st.session_state.last_saved_answers_str = current_answers

def show_student_quiz(db: Database):
    # إدارة انتهاء الجلسة
    if st.session_state.quiz_phase in ["taking_quiz", "finished"]:
        if not st.session_state.get("quiz_token"):
            st.error("انتهت جلسة الاختبار.")
            st.stop()
        else:
            token_data = verify_quiz_token(st.session_state.quiz_token)
            if token_data is None:
                st.error("انتهت صلاحية جلسة الاختبار.")
                st.stop()

    quiz = st.session_state.student_quiz

    # مرحلة إدخال الاسم
    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz.get('title', '')}")
        st.markdown(f"**عدد الأسئلة:** {quiz.get('num_questions', '')} | **الدرجة الكلية:** 20 | **الوقت:** {quiz.get('time_limit_minutes', '')} دقيقة")
        students_df = db.get_students()
        active_students = students_df[students_df["status"] == "active"] if not students_df.empty else pd.DataFrame()
        if active_students.empty:
            st.warning("لا توجد طالبات مسجلات حالياً.")
            st.stop()
        options_dict = dict(zip(active_students["student_id"], active_students["full_name"]))
        selected_id = st.selectbox("اختر اسمك من القائمة", options=list(options_dict.keys()),
                                   format_func=lambda x: options_dict[x], index=None, placeholder="اختر اسمك...")
        if selected_id:
            student_row = active_students[active_students.student_id == selected_id].iloc[0]
            section_id = student_row.get("section_id", "")
            sections_df = db.get_sections()
            section_name = sections_df[sections_df.section_id == section_id]["section_name"].values[0] if not sections_df.empty and section_id else "لم يتم تعيين فصل"
            st.info(f"أنتِ في فصل: **{section_name}**")
        st.info("إذا لم تجد اسمك في القائمة، يرجى التواصل مع مشرف الخدمة.")
        if selected_id and st.button("بدء الاختبار", use_container_width=True):
            selected_student = active_students[active_students.student_id == selected_id].iloc[0].to_dict()
            st.session_state.student_name = selected_student["full_name"]
            st.session_state.student_id = selected_id
            st.session_state.quiz_start_time = get_cairo_now()
            time_limit_seconds = int(quiz.get("time_limit_minutes", 15)) * 60
            st.session_state.quiz_end_time = st.session_state.quiz_start_time + timedelta(seconds=time_limit_seconds)
            attempt_id = db.start_quiz_attempt(quiz["quiz_id"], selected_id, st.session_state.student_name)
            st.session_state.current_attempt_id = attempt_id
            st.session_state.quiz_answers = {}
            st.session_state.last_saved_answers_str = ""
            st.session_state.quiz_questions = None
            st.session_state.show_review = False
            token = generate_quiz_token(quiz["quiz_id"], selected_id)
            st.session_state.quiz_token = token
            st.session_state.quiz_phase = "taking_quiz"
            db.add_log("طالبة", "بدء اختبار", f"الطالبة {st.session_state.student_name} بدأت اختبار {quiz.get('title', '')}")
            st.rerun()
        return

    # مرحلة تأدية الاختبار
    elif st.session_state.quiz_phase == "taking_quiz":
        now = get_cairo_now()
        if now > st.session_state.quiz_end_time:
            st.warning("انتهى الوقت المخصص للامتحان. جاري تسليم إجاباتك تلقائياً...")
            score = grade_attempt(db, quiz["quiz_id"], st.session_state.quiz_answers)
            answers_json = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
            db.submit_quiz_attempt(st.session_state.current_attempt_id, score, answers_json)
            st.session_state.quiz_submitted = True
            st.session_state.last_score = score
            st.session_state.quiz_submit_time = now
            st.session_state.quiz_phase = "finished"
            db.add_log("طالبة", "تسليم اختبار تلقائي", f"الطالبة {st.session_state.student_name} سلمت اختبار {quiz.get('title', '')} تلقائياً لانتهاء الوقت")
            st.rerun()

        # مؤقت واجهة
        end_time_iso = st.session_state.quiz_end_time.isoformat()
        countdown_html = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>
        body {{ font-family: 'Cairo', sans-serif; background: transparent; display: flex; justify-content: center; }}
        #timer {{ font-size: 1.8rem; font-weight: bold; padding: 0.8rem 2rem; background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        </style></head><body>
        <div id="timer">⏳ الوقت المتبقي: <span id="time"></span></div>
        <script>
        var endTime = new Date("{end_time_iso}").getTime();
        function update() {{
            var now = new Date().getTime();
            var dist = endTime - now;
            if (dist <= 0) {{
                document.getElementById('time').innerHTML = "00:00";
                parent.postMessage({{type: "QUIZ_TIME_UP"}}, "*");
                clearInterval(intervalId);
                return;
            }}
            var mins = Math.floor((dist % (1000*60*60)) / (1000*60));
            var secs = Math.floor((dist % (1000*60)) / 1000);
            document.getElementById('time').innerHTML = (mins<10?'0'+mins:mins) + ":" + (secs<10?'0'+secs:secs);
        }}
        update();
        var intervalId = setInterval(update, 1000);
        </script></body></html>
        """
        st.components.v1.html(countdown_html, height=80, scrolling=False)

        st.title(f"📝 {quiz.get('title', '')}")
        st.markdown(f"الطالبة: **{st.session_state.student_name}** | الدرجة الكلية: 20")
        st.markdown("---")

        # تحميل الأسئلة
        if not st.session_state.get("quiz_questions"):
            try:
                questions_df = db.get_quiz_questions(quiz["quiz_id"])
                if questions_df.empty:
                    st.warning("لا توجد أسئلة في هذا الاختبار بعد.")
                    return
                st.session_state.quiz_questions = questions_df.to_dict('records')
            except Exception:
                st.error("تعذر تحميل الأسئلة.")
                return
        else:
            questions_df = pd.DataFrame(st.session_state.quiz_questions)

        for idx, row in questions_df.iterrows():
            q = row.to_dict()
            q_id = q.get("question_id", "")
            st.markdown(f"**سؤال {idx+1}:** {q.get('question_text', '')}")
            q_type = q.get("question_type", "")
            prev_answer = st.session_state.quiz_answers.get(q_id, "")
            if q_type in ["اختيار من متعدد", "صح وخطأ"]:
                options = [q.get("option1", ""), q.get("option2", ""), q.get("option3", ""), q.get("option4", "")] if q_type == "اختيار من متعدد" else ["صح", "خطأ"]
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

        if st.button("تسليم الاختبار", use_container_width=True, key="submit_quiz_btn"):
            score = grade_attempt(db, quiz["quiz_id"], st.session_state.quiz_answers)
            answers_json = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
            db.submit_quiz_attempt(st.session_state.current_attempt_id, score, answers_json)
            st.session_state.quiz_submitted = True
            st.session_state.last_score = score
            st.session_state.quiz_submit_time = get_cairo_now()
            st.session_state.quiz_phase = "finished"
            db.add_log("طالبة", "تسليم اختبار", f"الطالبة {st.session_state.student_name} سلمت اختبار {quiz.get('title', '')} وحصلت على {score}")
            st.rerun()
        return

    # مرحلة النتيجة والمراجعة
    elif st.session_state.quiz_phase == "finished":
        if not st.session_state.get("show_review", False):
            st.success("تم تسليم الاختبار بنجاح!")
            score = st.session_state.last_score
            score_display = int(score) if isinstance(score, float) and score.is_integer() else score
            st.info(f"نتيجتك: {score_display}/20")
            st.markdown("---")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.write("**بداية الامتحان:**")
                st.write(format_cairo_time(st.session_state.quiz_start_time))
            with col_t2:
                st.write("**نهاية الامتحان (التسليم):**")
                st.write(format_cairo_time(st.session_state.quiz_submit_time))

            col_btn, _ = st.columns([2, 3])
            if col_btn.button("عرض الإجابات والأخطاء", use_container_width=True):
                st.session_state.show_review = True
                st.rerun()
            if st.button("إنهاء والعودة إلى الرئيسية", use_container_width=True):
                for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                            "student_id", "quiz_start_time", "quiz_end_time", "quiz_submit_time",
                            "quiz_token", "quiz_answers", "quiz_submitted", "last_score",
                            "current_attempt_id", "last_saved_answers_str", "quiz_questions", "show_review"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        else:
            st.markdown("## مراجعة الإجابات")
            if not st.session_state.get("quiz_questions"):
                questions_df = db.get_quiz_questions(quiz["quiz_id"])
                if questions_df.empty:
                    st.warning("لا يمكن تحميل الأسئلة للمراجعة.")
                else:
                    st.session_state.quiz_questions = questions_df.to_dict('records')
            if st.session_state.get("quiz_questions"):
                questions_df = pd.DataFrame(st.session_state.quiz_questions)
                student_answers = st.session_state.quiz_answers
                for idx, row in questions_df.iterrows():
                    q = row.to_dict()
                    qid = q.get("question_id", "")
                    correct = str(q.get("correct_answer", "")).strip().lower()
                    student_ans = str(student_answers.get(qid, "")).strip().lower()
                    is_correct = (correct == student_ans)
                    st.markdown(f"**سؤال {idx+1}:** {q.get('question_text', '')}")
                    col1, col2 = st.columns(2)
                    col1.write(f"📝 إجابتك: {student_ans if student_ans else 'لم تجب'}")
                    col2.write(f"✅ الإجابة الصحيحة: {correct}")
                    if is_correct:
                        st.success("✔️ صحيح")
                    else:
                        st.error("❌ خطأ")
                    st.markdown("---")
                if st.button("إنهاء المراجعة والعودة إلى الرئيسية", use_container_width=True):
                    for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                                "student_id", "quiz_start_time", "quiz_end_time", "quiz_submit_time",
                                "quiz_token", "quiz_answers", "quiz_submitted", "last_score",
                                "current_attempt_id", "last_saved_answers_str", "quiz_questions", "show_review"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
        return

# =============================================================================
# مكونات الشريط الجانبي والرأس
# =============================================================================
def render_sidebar(db: Database):
    user = st.session_state.user
    role = user.get("role", "")
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1rem 0;'>
            <h2 style='color: #0f172a; margin: 0;'>⛪ Kenisa</h2>
            <p style='color: #64748b; margin: 0; font-size: 0.9rem;'>نظام الإدارة الذكي</p>
        </div>
        <hr style='border-color: #e2e8f0;'>
        """, unsafe_allow_html=True)

        menus = {
            "System Admin": [
                ("🏠", "لوحة التحكم"), ("👥", "إدارة المستخدمين"), ("🏫", "إدارة المراحل"),
                ("📋", "الحضور"), ("💬", "الافتقاد"), ("📝", "المسابقات"),
                ("📊", "التقارير"), ("📜", "سجل العمليات"), ("🔒", "تغيير كلمة المرور")
            ],
            "Father Account": [
                ("🏠", "لوحة التحكم"), ("📊", "التقارير"), ("🔒", "تغيير كلمة المرور")
            ],
            "Service Manager": [
                ("🏠", "لوحة التحكم"), ("👩‍🎓", "طالباتي"), ("💬", "الافتقاد"),
                ("📝", "المسابقات"), ("📊", "التقارير"), ("🔒", "تغيير كلمة المرور")
            ],
            "Teacher": [
                ("🏠", "لوحة التحكم"), ("👩‍🎓", "طالباتي"), ("📋", "الحضور"),
                ("💬", "الافتقاد"), ("🏆", "درجات المسابقات"), ("🔒", "تغيير كلمة المرور")
            ]
        }
        menu_items = menus.get(role, [])
        current = st.session_state.get("menu_choice", "🏠 لوحة التحكم")

        if st.button("✕ إخفاء القائمة", key="hide_sidebar_btn", use_container_width=True):
            st.session_state.show_sidebar = False
            st.rerun()

        st.markdown('<div class="nav-btn-container">', unsafe_allow_html=True)
        for icon, name in menu_items:
            label = f"{icon} {name}"
            btn_type = "primary" if label == current else "secondary"
            if st.button(label, key=f"nav_{name}", use_container_width=True, type=btn_type):
                if label != current:
                    st.session_state.menu_choice = label
                st.session_state.show_sidebar = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"""
        <div class='user-profile-card'>
            <div style='font-size: 2rem;'>👤</div>
            <div style='font-weight: 700;'>{user.get('full_name', '')}</div>
            <div style='font-size: 0.85rem; opacity: 0.9;'>{user.get('role', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout(db)

def render_header():
    choice = st.session_state.get("menu_choice", "لوحة التحكم").replace("🏠", "").strip()
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
        <div>
            <h1 style="margin:0; color:#0f172a;">{choice}</h1>
            <p style="color:#64748b; margin:0;">الرئيسية / {choice}</p>
        </div>
        <div style="color:#64748b; font-weight:600;">
            📅 {get_cairo_now().strftime('%Y-%m-%d  %I:%M %p')}
        </div>
    </div>
    """, unsafe_allow_html=True)

def kpi_cards(db: Database):
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    attendance = db.get_attendance()
    users = db.get_users()

    # تصفية حسب القسم
    if role in ["Teacher", "Service Manager"] and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
        if not attendance.empty and "section_id" in attendance.columns:
            attendance = attendance[attendance.section_id == section_id]

    # تحويل التاريخ
    if not attendance.empty and "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")

    total_students = len(students)
    today = get_cairo_now().strftime("%Y-%m-%d")
    present_today = len(attendance[(attendance.date == today) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent_today = len(attendance[(attendance.date == today) & (attendance.status == "غائب")]) if not attendance.empty else 0
    total_users = len(users)

    cols = st.columns(4)
    cards = [
        ("👩‍🎓", "إجمالي الطالبات", total_students, "العدد الكلي"),
        ("✅", "الحضور اليوم", present_today, "نشط"),
        ("❌", "الغياب اليوم", absent_today, "يحتاج متابعة"),
        ("👥", "المستخدمين", total_users, "خدام ومدرسين")
    ]
    for i, (icon, title, value, sub) in enumerate(cards):
        with cols[i]:
            st.markdown(f"""
            <div class='custom-card' style='text-align: center;'>
                <div style='font-size: 2rem;'>{icon}</div>
                <div style='font-size: 1.8rem; font-weight: 700; color: #0f172a;'>{value}</div>
                <div style='font-size: 0.9rem; color: #64748b;'>{title}</div>
                <div style='font-size: 0.8rem; color: #10b981;'>{sub}</div>
            </div>
            """, unsafe_allow_html=True)

# =============================================================================
# جميع صفحات التطبيق (مع التسجيل المفصل)
# =============================================================================
def show_dashboard(db: Database):
    render_header()
    kpi_cards(db)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()

    # تنبيهات البيانات
    if role in ["System Admin", "Service Manager"] and st.session_state.get("data_errors"):
        with st.expander("⚠️ تنبيهات هامة - أخطاء في البيانات", expanded=True):
            for err in st.session_state.data_errors:
                st.warning(err)
            if st.button("🔧 إصلاح تلقائي (إنشاء الفصول الناقصة)"):
                if auto_fix_missing_sections(db):
                    st.session_state.data_errors = validate_data_integrity(db)
                    st.success("تم إنشاء الفصول الناقصة.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("لا توجد فصول ناقصة لإصلاحها.")

    # تصفية حسب الفصل للصلاحيات المحدودة
    if role in ["Teacher", "Service Manager"] and section_id:
        if not students.empty:
            students = students[students.section_id == section_id]
        if not attendance.empty:
            attendance = attendance[attendance.section_id == section_id]
        if not followup.empty and not students.empty:
            followup = followup[followup.student_id.isin(students["student_id"])]

    if not attendance.empty and "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")

    total_students = len(students)
    today_str = get_cairo_now().strftime("%Y-%m-%d")
    present_today = len(attendance[(attendance.date == today_str) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent_today = len(attendance[(attendance.date == today_str) & (attendance.status == "غائب")]) if not attendance.empty else 0
    need_follow = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("عدد الطالبات", total_students)
    col2.metric("الحضور اليوم", present_today)
    col3.metric("الغياب اليوم", absent_today)
    col4.metric("منقطعات", need_follow)

    st.markdown("---")
    st.subheader("📈 الحضور الأسبوعي")
    if not attendance.empty:
        last_week = get_cairo_now().replace(tzinfo=None) - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty and "status" in recent.columns:
            fig = px.histogram(recent, x="date", color="status", barmode="group")
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور للأيام الماضية.")
    else:
        st.info("لا توجد بيانات حضور بعد.")

    st.markdown("---")
    st.subheader("🔔 بنات بحاجة لافتقاد عاجل")
    if not followup.empty and "regularity_status" in followup.columns:
        urgent = followup[followup.regularity_status.isin(["منقطع", "متقطع"])]
        if not urgent.empty and not students.empty:
            urgent = urgent.merge(students[["student_id", "full_name"]], on="student_id", how="left")
            st.dataframe(urgent[["full_name", "followup_date", "notes"]], use_container_width=True)
        else:
            st.info("كل البنات منتظمات.")
    else:
        st.info("لا توجد متابعات.")

    # إحصائيات إضافية للمديرين
    if role in ["System Admin", "Father Account", "Service Manager"]:
        st.markdown("---")
        st.subheader("🏆 أفضل فصل درجات في المسابقات")
        results = db.get_quiz_results()
        students_all = db.get_students()
        sections_all = db.get_sections()
        if not results.empty and not students_all.empty and not sections_all.empty:
            submitted = results[results.status == "submitted"]
            if not submitted.empty:
                merged = submitted.merge(students_all[["student_id", "section_id"]], on="student_id", how="left")
                merged["score"] = pd.to_numeric(merged["score"], errors="coerce").fillna(0)
                section_scores = merged.groupby("section_id")["score"].mean().reset_index()
                section_scores = section_scores.merge(sections_all[["section_id", "section_name"]], on="section_id")
                top = section_scores.sort_values("score", ascending=False).iloc[0]
                st.metric(f"أفضل فصل: {top.get('section_name', '')}", f"{top.get('score', 0):.1f} / 20 متوسط")
                st.dataframe(section_scores.rename(columns={"section_name": "الفصل", "score": "متوسط الدرجات"}).set_index("الفصل"), use_container_width=True)

def show_user_management(db: Database):
    render_header()
    users = db.get_users()
    sections = db.get_sections()
    stages = db.get_stages()
    students = db.get_students()
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول", "إدارة المراحل"])

    # تبويب الخدام
    with tab1:
        st.subheader("قائمة المستخدمين (خدام)")
        if not users.empty:
            display_cols = [c for c in ["user_id", "username", "full_name", "role", "section_id", "phone", "email"] if c in users.columns]
            st.dataframe(users[display_cols], use_container_width=True)
        else:
            st.info("لا يوجد مستخدمون مسجلون.")
        with st.expander("➕ إضافة مستخدم جديد"):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                username = col1.text_input("اسم المستخدم*").strip()
                full_name = col2.text_input("الاسم الكامل*")
                password = col1.text_input("كلمة المرور*", type="password").strip()
                role = col2.selectbox("الصلاحية", ["System Admin", "Father Account", "Service Manager", "Teacher"])
                section_id = ""
                if role in ["Service Manager", "Teacher"] and not sections.empty:
                    section_choice = st.selectbox("الفصل", ["None"] + sections["section_id"].tolist(),
                                                  format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف (اختياري)")
                email = st.text_input("البريد الإلكتروني (اختياري)")
                if st.form_submit_button("إضافة"):
                    if not username or not password or not full_name:
                        st.error("مطلوب اسم المستخدم وكلمة المرور والاسم الكامل")
                    elif not users[users.username == username].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({"user_id": str(uuid.uuid4()), "username": username, "password": password,
                                     "role": role, "full_name": full_name, "section_id": section_id, "phone": phone, "email": email})
                        db.add_log(st.session_state.user["user_id"], "إضافة مستخدم", f"تم إضافة المستخدم {username} بصلاحية {role}")
                        st.success("تم إضافة المستخدم بنجاح")
                        time.sleep(1)
                        st.rerun()

        with st.expander("✏️ تعديل / حذف مستخدم"):
            if not users.empty:
                selected = st.selectbox("اختر المستخدم", users["user_id"], key="sel_user_edit")
                user_data = users[users.user_id == selected].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=user_data.get("full_name", ""))
                new_phone = st.text_input("رقم الهاتف", value=user_data.get("phone", ""))
                new_email = st.text_input("البريد الإلكتروني", value=user_data.get("email", ""))
                roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher"]
                current_role = user_data.get("role", "Teacher")
                role_index = roles_list.index(current_role) if current_role in roles_list else 3
                new_role = st.selectbox("الصلاحية", roles_list, index=role_index)
                new_section_id = user_data.get("section_id", "")
                if new_role in ["Service Manager", "Teacher"] and not sections.empty:
                    sec_opts = ["None"] + sections["section_id"].tolist()
                    cur_idx = sec_opts.index(new_section_id) if new_section_id in sec_opts else 0
                    sec_choice = st.selectbox("الفصل", sec_opts, index=cur_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    new_section_id = sec_choice if sec_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات"):
                    db.update_user(selected, {"full_name": new_full_name, "phone": new_phone, "email": new_email, "role": new_role, "section_id": new_section_id})
                    db.add_log(st.session_state.user["user_id"], "تعديل مستخدم", f"تم تعديل بيانات المستخدم {user_data.get('username', '')}")
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المستخدم"):
                    if selected == st.session_state.user.get("user_id"):
                        st.error("لا يمكنك حذف حسابك الحالي!")
                    else:
                        db.delete_user(selected)
                        db.add_log(st.session_state.user["user_id"], "حذف مستخدم", f"تم حذف المستخدم {user_data.get('username', '')}")
                        st.success("تم الحذف")
                        time.sleep(1)
                        st.rerun()

    # تبويب المدرسات
    with tab2:
        st.subheader("قائمة المدرسات")
        teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
        if not teachers.empty:
            if not sections.empty:
                teachers = teachers.merge(sections[["section_id", "section_name"]].rename(columns={"section_name":"الفصل"}), on="section_id", how="left")
            display_cols = [c for c in ["user_id", "username", "full_name", "الفصل", "phone", "email"] if c in teachers.columns]
            st.dataframe(teachers[display_cols], use_container_width=True)
        else:
            st.info("لا توجد مدرسات مسجلات.")
        with st.expander("➕ إضافة مدرسة جديدة"):
            with st.form("add_teacher_form"):
                teacher_name = st.text_input("اسم المستخدم*").strip()
                password = st.text_input("كلمة المرور*", type="password").strip()
                section_id = ""
                if not sections.empty:
                    section_choice = st.selectbox("الفصل", ["None"] + sections["section_id"].tolist(),
                                                  format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة"):
                    if not teacher_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif not users[users.username == teacher_name].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({"user_id": str(uuid.uuid4()), "username": teacher_name, "password": password,
                                     "role": "Teacher", "full_name": teacher_name, "section_id": section_id, "phone": phone, "email": email})
                        db.add_log(st.session_state.user["user_id"], "إضافة مدرسة", f"تم إضافة المدرسة {teacher_name}")
                        st.success("تمت إضافة المدرسة بنجاح")
                        time.sleep(1)
                        st.rerun()

    # تبويب الطالبات
    with tab3:
        st.subheader("قائمة الطالبات")
        if not students.empty:
            if not sections.empty:
                students_display = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
            else:
                students_display = students
            display_cols = [c for c in ["student_id", "full_name", "section_name", "phone", "parent_phone", "birthdate", "school", "status"] if c in students_display.columns]
            st.dataframe(students_display[display_cols], use_container_width=True)
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
                        db.add_student({"student_id": str(uuid.uuid4()), "full_name": full_name, "section_id": section_id,
                                        "phone": phone, "parent_phone": parent_phone,
                                        "birthdate": birthdate.strftime("%Y-%m-%d") if birthdate else "",
                                        "address": address, "school": school, "notes": notes, "status": "active"})
                        db.add_log(st.session_state.user["user_id"], "إضافة طالبة", f"تم إضافة الطالبة {full_name}")
                        st.success("تمت الإضافة")
                        time.sleep(1)
                        st.rerun()

        with st.expander("✏️ تعديل بيانات طالبة"):
            if not students.empty:
                selected_student = st.selectbox("اختر طالبة", students["student_id"], key="sel_student_edit")
                student_row = students[students.student_id == selected_student].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""))
                sections_local = sections
                new_section_id = student_row.get("section_id", "")
                if not sections_local.empty:
                    sec_opts = sections_local["section_id"].tolist()
                    cur_idx = sec_opts.index(new_section_id) if new_section_id in sec_opts else 0
                    new_section_id = st.selectbox("الفصل", sec_opts, index=cur_idx, format_func=lambda x: sections_local[sections_local.section_id==x]["section_name"].values[0])
                new_phone = st.text_input("رقم الهاتف", value=student_row.get("phone", ""))
                new_parent = st.text_input("رقم ولي الأمر", value=student_row.get("parent_phone", ""))
                existing_birthdate = student_row.get("birthdate", "")
                try: birth_date_val = pd.to_datetime(existing_birthdate).date() if existing_birthdate else None
                except: birth_date_val = None
                new_birthdate = st.date_input("تاريخ الميلاد", value=birth_date_val)
                new_school = st.text_input("المدرسة", value=student_row.get("school", ""))
                new_notes = st.text_area("ملاحظات", value=student_row.get("notes", ""))
                status_list = ["active", "inactive"]
                current_status = student_row.get("status", "active")
                status_index = 0 if current_status == "active" else 1
                new_status = st.selectbox("الحالة", status_list, index=status_index)
                if st.button("حفظ التعديلات"):
                    db.update_student(selected_student, {"full_name": new_full_name, "section_id": new_section_id,
                                                         "phone": new_phone, "parent_phone": new_parent,
                                                         "birthdate": new_birthdate.strftime("%Y-%m-%d") if new_birthdate else "",
                                                         "school": new_school, "notes": new_notes, "status": new_status})
                    db.add_log(st.session_state.user["user_id"], "تعديل طالبة", f"تم تعديل بيانات الطالبة {student_row.get('full_name', '')}")
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()

        with st.expander("🗑️ حذف طالبة"):
            if not students.empty:
                delete_id = st.selectbox("اختر طالبة للحذف", students["student_id"], key="delete_student_sel")
                if st.button("تأكيد حذف الطالبة"):
                    student_name = students[students.student_id == delete_id]["full_name"].values[0]
                    db.delete_student(delete_id)
                    db.add_log(st.session_state.user["user_id"], "حذف طالبة", f"تم حذف الطالبة {student_name}")
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()

    # تبويب أمناء الخدمة
    with tab4:
        st.subheader("قائمة أمناء الخدمة")
        managers = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
        if not managers.empty:
            if not sections.empty:
                managers = managers.merge(sections[["section_id", "section_name"]].rename(columns={"section_name":"الفصل"}), on="section_id", how="left")
            display_cols = [c for c in ["user_id", "username", "full_name", "الفصل", "phone", "email"] if c in managers.columns]
            st.dataframe(managers[display_cols], use_container_width=True)
        else:
            st.info("لا يوجد أمناء خدمة.")

    # تبويب الفصول
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
                        db.add_log(st.session_state.user["user_id"], "إضافة فصل", f"تم إضافة فصل {name}")
                        st.success("تمت الإضافة")
                        time.sleep(1)
                        st.rerun()
        with st.expander("🗑️ حذف فصل"):
            if not sections.empty:
                del_sec = st.selectbox("اختر فصل", sections["section_id"], key="del_section_sel")
                if st.button("تأكيد حذف الفصل"):
                    sec_name = sections[sections.section_id == del_sec]["section_name"].values[0]
                    db.delete_section(del_sec)
                    db.add_log(st.session_state.user["user_id"], "حذف فصل", f"تم حذف فصل {sec_name}")
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()

    # تبويب المراحل
    with tab6:
        st.subheader("🏫 إدارة المراحل الدراسية")
        if not stages.empty:
            if not users.empty:
                stages_display = stages.merge(users[["user_id", "full_name"]].rename(columns={"user_id":"manager_user_id", "full_name":"المسؤول"}), on="manager_user_id", how="left")
            else:
                stages_display = stages
                stages_display["المسؤول"] = ""
            st.dataframe(stages_display[["stage_id", "stage_name", "المسؤول"]], use_container_width=True)
        else:
            st.info("لا توجد مراحل مسجلة بعد.")
        with st.expander("➕ إضافة مرحلة جديدة"):
            with st.form("add_stage_form"):
                stage_name = st.text_input("اسم المرحلة*")
                eligible = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
                manager_id = ""
                if not eligible.empty:
                    mgr_choice = st.selectbox("مسؤول المرحلة (اختياري)", ["None"] + eligible["user_id"].tolist(),
                                             format_func=lambda x: "بدون" if x=="None" else eligible[eligible.user_id==x]["full_name"].values[0])
                    manager_id = mgr_choice if mgr_choice != "None" else ""
                if st.form_submit_button("إضافة"):
                    if not stage_name:
                        st.error("يرجى إدخال اسم المرحلة")
                    else:
                        db.add_stage({"stage_id": str(uuid.uuid4()), "stage_name": stage_name.strip(), "manager_user_id": manager_id})
                        db.add_log(st.session_state.user["user_id"], "إضافة مرحلة", f"تم إضافة مرحلة {stage_name}")
                        st.success("✅ تمت إضافة المرحلة بنجاح")
                        time.sleep(1)
                        st.rerun()
        if not stages.empty:
            with st.expander("✏️ تعديل / حذف مرحلة"):
                stage_sel = st.selectbox("اختر مرحلة", stages["stage_id"], format_func=lambda x: stages[stages.stage_id==x]["stage_name"].values[0])
                stage_row = stages[stages.stage_id == stage_sel].iloc[0].to_dict()
                new_stage_name = st.text_input("اسم المرحلة", value=stage_row["stage_name"])
                eligible = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
                current_mgr = stage_row.get("manager_user_id", "")
                new_mgr_id = ""
                if not eligible.empty:
                    mgr_opts = ["None"] + eligible["user_id"].tolist()
                    cur_idx = mgr_opts.index(current_mgr) if current_mgr in mgr_opts else 0
                    new_manager = st.selectbox("مسؤول المرحلة", mgr_opts, index=cur_idx,
                                               format_func=lambda x: "بدون" if x=="None" else eligible[eligible.user_id==x]["full_name"].values[0])
                    new_mgr_id = new_manager if new_manager != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث المرحلة"):
                    db.update_stage(stage_sel, {"stage_name": new_stage_name, "manager_user_id": new_mgr_id})
                    db.add_log(st.session_state.user["user_id"], "تعديل مرحلة", f"تم تعديل المرحلة {stage_row.get('stage_name', '')}")
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المرحلة"):
                    db.delete_stage(stage_sel)
                    db.add_log(st.session_state.user["user_id"], "حذف مرحلة", f"تم حذف المرحلة {stage_row.get('stage_name', '')}")
                    st.success("تم حذف المرحلة")
                    time.sleep(1)
                    st.rerun()

def show_attendance(db: Database):
    user = st.session_state.user
    if user.get("role") == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور، هذه المهمة خاصة بالمدرسات فقط.")
        return
    render_header()
    sections = db.get_sections()
    if sections.empty:
        st.warning("لا توجد فصول.")
        return
    section_id = user.get("section_id", "")
    if user.get("role") == "Teacher" and section_id:
        selected_section = section_id
        section_name = sections[sections.section_id == section_id]["section_name"].values[0]
        st.write(f"**الفصل:** {section_name}")
    else:
        selected_section = st.selectbox("اختر الفصل", sections["section_id"],
                               format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
    date = st.date_input("التاريخ", get_cairo_now().date())
    date_str = date.strftime("%Y-%m-%d")
    students = db.get_students()
    section_students = students[students.section_id == selected_section]
    if section_students.empty:
        st.info("لا توجد طالبات في هذا الفصل.")
        return
    existing = db.get_attendance_by_date_section(date_str, selected_section)
    st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
    statuses = {}
    notes_dict = {}
    for _, s in section_students.iterrows():
        sid = s["student_id"]
        sname = s["full_name"]
        prev = existing[existing.student_id == sid]
        prev_status = prev.iloc[0]["status"] if not prev.empty else "حاضر"
        prev_notes = prev.iloc[0]["notes"] if not prev.empty else ""
        cols = st.columns([3, 2, 2])
        cols[0].write(f"**{sname}**")
        status = cols[1].radio("الحالة", ["حاضر", "غائب", "متأخر"], index=["حاضر", "غائب", "متأخر"].index(prev_status) if prev_status in ["حاضر", "غائب", "متأخر"] else 0, key=f"att_{sid}", horizontal=True)
        notes = cols[2].text_input("ملاحظة", value=prev_notes, key=f"note_{sid}", label_visibility="collapsed")
        statuses[sid] = status
        notes_dict[sid] = notes
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("💾 حفظ الحضور", use_container_width=True):
        records = []
        for sid, status in statuses.items():
            prev_record = existing[existing.student_id == sid]
            record_id = prev_record.iloc[0]["record_id"] if not prev_record.empty else str(uuid.uuid4())
            records.append({"record_id": record_id, "date": date_str, "student_id": sid,
                            "status": status, "notes": notes_dict.get(sid, ""),
                            "recorded_by": user["user_id"], "section_id": selected_section})
        db.batch_add_attendance(records)
        db.add_log(user["user_id"], "تسجيل حضور", f"تسجيل حضور فصل {section_name} ليوم {date_str}")
        st.success("✅ تم تسجيل الحضور بنجاح")
        time.sleep(1)
        st.rerun()

def show_followup(db: Database):
    render_header()
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()

    if role == "Teacher" and section_id:
        responsible = students[students.section_id == section_id]
    elif role == "Service Manager" and section_id:
        responsible = students[students.section_id == section_id]
    else:
        responsible = students

    if responsible.empty:
        st.info("لا توجد طالبات.")
        return

    st.subheader("➕ إضافة متابعة جديدة")
    student = st.selectbox("اختر الطالبة", responsible["student_id"],
                           format_func=lambda x: responsible[responsible.student_id==x]["full_name"].values[0], key="followup_student")
    with st.form("followup_form"):
        ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
        notes = st.text_area("ملاحظات")
        regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
        if st.form_submit_button("حفظ المتابعة"):
            try:
                db.add_followup_record({"record_id": str(uuid.uuid4()), "student_id": student,
                                        "teacher_id": user.get("user_id", ""),
                                        "followup_date": get_cairo_now().strftime("%Y-%m-%d"),
                                        "followup_type": ftype, "notes": notes, "regularity_status": regularity})
                student_name = responsible[responsible.student_id==student]["full_name"].values[0]
                db.add_log(user["user_id"], "إضافة متابعة", f"متابعة {ftype} للطالبة {student_name}")
                st.success("✅ تم تسجيل الافتقاد بنجاح")
                time.sleep(1)
                st.rerun()
            except ValueError as e:
                st.error(str(e))

def show_quizzes(db: Database):
    render_header()
    user = st.session_state.user
    role = user.get("role", "")
    quizzes = db.get_quizzes()
    if role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد")
        with st.form("quiz_form"):
            title = st.text_input("عنوان الاختبار*")
            num_q = st.selectbox("عدد الأسئلة", [10, 20, 30], index=1)
            time_limit = st.number_input("الوقت (بالدقائق)", 1, 180, 15)
            expiry = st.date_input("تاريخ الانتهاء", get_cairo_now().date() + timedelta(days=7))
            if st.form_submit_button("إنشاء"):
                if not title:
                    st.error("يرجى إدخال عنوان الاختبار")
                else:
                    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    pwd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    quiz_id = str(uuid.uuid4())
                    db.add_quiz({"quiz_id": quiz_id, "title": title, "description": "",
                                 "created_by": user["user_id"], "section_id": "",
                                 "num_questions": num_q, "time_limit_minutes": time_limit,
                                 "total_marks": 20, "expiry_date": expiry.strftime("%Y-%m-%d"),
                                 "quiz_code": code, "password": pwd, "is_active": "True"})
                    db.add_log(user["user_id"], "إنشاء اختبار", f"تم إنشاء اختبار {title} بالكود {code}")
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
                        display_cols = [c for c in ["question_text", "question_type", "correct_answer"] if c in questions.columns]
                        st.dataframe(questions[display_cols], use_container_width=True)
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
                                db.add_question({"question_id": str(uuid.uuid4()), "quiz_id": quiz_choice,
                                                 "question_text": qtext, "question_type": qtype,
                                                 "option1": opts.get("option1", ""), "option2": opts.get("option2", ""),
                                                 "option3": opts.get("option3", ""), "option4": opts.get("option4", ""),
                                                 "correct_answer": correct})
                                db.add_log(user["user_id"], "إضافة سؤال", f"إضافة سؤال للاختبار {active_quizzes[active_quizzes.quiz_id==quiz_choice]['title'].values[0]}")
                                st.success("✅ تمت إضافة السؤال")
                                time.sleep(1)
                                st.rerun()
                    if not questions.empty:
                        del_q = st.selectbox("اختر سؤالاً لحذفه", questions["question_id"])
                        if st.button("حذف السؤال"):
                            db.delete_question(del_q)
                            db.add_log(user["user_id"], "حذف سؤال", f"حذف سؤال من الاختبار {active_quizzes[active_quizzes.quiz_id==quiz_choice]['title'].values[0]}")
                            st.success("تم الحذف")
                            time.sleep(1)
                            st.rerun()

        st.markdown("---")
        st.subheader("📋 إدارة الاختبارات")
        if quizzes.empty:
            st.info("لا توجد اختبارات بعد.")
        else:
            for _, q in quizzes.iterrows():
                qid = q.get("quiz_id", "")
                title = q.get("title", "")
                active = q.get("is_active", "True") == "True"
                code = q.get("quiz_code", "")
                expiry = q.get("expiry_date", "")
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                col1.write(f"**{title}**")
                col2.write(f"الكود: {code}")
                col3.write("حالة: " + ("🟢 نشط" if active else "🔴 مغلق"))
                col4.write(f"ينتهي: {expiry}")
                col_actions = st.columns(4)
                if active:
                    if col_actions[0].button("إغلاق", key=f"deact_{qid}"):
                        db.update_quiz(qid, {"is_active": "False"})
                        db.add_log(user["user_id"], "إغلاق اختبار", f"تم إغلاق الاختبار {title}")
                        st.success(f"تم إغلاق الاختبار: {title}")
                        time.sleep(1)
                        st.rerun()
                else:
                    if col_actions[0].button("تفعيل", key=f"act_{qid}"):
                        db.update_quiz(qid, {"is_active": "True"})
                        db.add_log(user["user_id"], "تفعيل اختبار", f"تم تفعيل الاختبار {title}")
                        st.success(f"تم تفعيل الاختبار: {title}")
                        time.sleep(1)
                        st.rerun()
                if col_actions[1].button("حذف (النتائج تبقى)", key=f"del_keep_{qid}"):
                    db.delete_quiz_keep_results(qid)
                    db.add_log(user["user_id"], "حذف اختبار مع الاحتفاظ بالنتائج", f"حذف الاختبار {title}")
                    st.success(f"تم حذف الاختبار '{title}' مع الاحتفاظ بالنتائج.")
                    time.sleep(1)
                    st.rerun()
                st.markdown("---")

    st.markdown("### 📊 نتائج الاختبارات")
    results = db.get_quiz_results()
    students = db.get_students()
    sections_all = db.get_sections()
    if not results.empty:
        if "status" in results.columns:
            results = results[results["status"] == "submitted"]
        if role == "Teacher" and user.get("section_id"):
            if not students.empty:
                section_student_ids = students[students.section_id == user["section_id"]]["student_id"].tolist()
                results = results[results.student_id.isin(section_student_ids)]
        if not students.empty:
            results = results.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
            results.rename(columns={"full_name": "اسم الطالبة"}, inplace=True)
        if not sections_all.empty:
            results = results.merge(sections_all[["section_id", "section_name"]], on="section_id", how="left")
            results.rename(columns={"section_name": "الفصل"}, inplace=True)
        if not quizzes.empty:
            results = results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
            results.rename(columns={"title": "المسابقة"}, inplace=True)
        if "score" in results.columns:
            results["score"] = pd.to_numeric(results["score"], errors="coerce").fillna(0)
        st.dataframe(results, use_container_width=True)

def show_reports(db: Database):
    render_header()
    db.add_log(st.session_state.user["user_id"], "عرض التقارير", "تم فتح صفحة التقارير")
    attendance = db.get_attendance()
    students = db.get_students()
    user = st.session_state.user
    if user.get("role") in ["Teacher", "Service Manager"] and user.get("section_id"):
        if not attendance.empty:
            attendance = attendance[attendance.section_id == user["section_id"]]
        if not students.empty:
            students = students[students.section_id == user["section_id"]]
    if attendance.empty:
        st.info("لا توجد بيانات حضور.")
        return
    if "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    st.subheader("📅 تقرير الغياب الشهري")
    col1, col2 = st.columns(2)
    month = col1.selectbox("الشهر", range(1,13), index=get_cairo_now().month-1)
    year = col2.number_input("السنة", value=get_cairo_now().year, min_value=2020)
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
    if not attendance.empty and "status" in attendance.columns:
        absent_counts = attendance[attendance.status == "غائب"].groupby("student_id").size().reset_index(name="أيام الغياب")
        absent_counts = absent_counts.sort_values("أيام الغياب", ascending=False).head(10)
        if not students.empty:
            absent_counts = absent_counts.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(absent_counts[["full_name", "أيام الغياب"]], use_container_width=True)

def show_logs(db: Database):
    render_header()
    logs = db.get_logs()
    if not logs.empty:
        if "timestamp" in logs.columns:
            logs["timestamp"] = pd.to_datetime(logs["timestamp"]).dt.tz_convert(CAIRO_TZ)
        logs = logs.sort_values("timestamp", ascending=False)
        st.dataframe(logs, use_container_width=True)
        if "log_id" in logs.columns:
            del_id = st.selectbox("اختر سجلاً لحذفه", logs["log_id"], key="del_log_sel")
            if st.button("حذف السجل"):
                db.delete_log(del_id)
                st.success("تم الحذف")
                time.sleep(1)
                st.rerun()
    else:
        st.info("لا توجد سجلات بعد.")

def change_password(db: Database):
    render_header()
    with st.form("change_password_form"):
        old = st.text_input("كلمة المرور الحالية", type="password").strip()
        new = st.text_input("كلمة المرور الجديدة", type="password").strip()
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password").strip()
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old or not new or not confirm:
                st.error("الرجاء ملء جميع الحقول")
            elif old != st.session_state.user.get("password", ""):
                st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new) < 4:
                st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
            elif new != confirm:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                db.update_user(st.session_state.user["user_id"], {"password": new})
                st.session_state.user["password"] = new
                db.add_log(st.session_state.user["user_id"], "تغيير كلمة المرور", "تم تغيير كلمة المرور بنجاح")
                st.success("✅ تم تغيير كلمة المرور بنجاح!")

def show_my_students(db: Database):
    render_header()
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()
    if role == "Teacher" and section_id:
        my_students = students[students.section_id == section_id]
    elif role == "Service Manager" and section_id:
        my_students = students[students.section_id == section_id]
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
    display_cols = [c for c in ["full_name", "phone", "regularity_status"] if c in my_students.columns]
    st.dataframe(my_students[display_cols], use_container_width=True)
    st.markdown("---")
    st.subheader("➕ إضافة متابعة سريعة")
    selected = st.selectbox("اختر طالبة", my_students["student_id"],
                            format_func=lambda x: my_students[my_students.student_id==x]["full_name"].values[0], key="my_students_fup")
    with st.expander("فتح نموذج المتابعة"):
        with st.form("quick_followup_form"):
            ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
            notes = st.text_area("ملاحظات")
            regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
            if st.form_submit_button("حفظ المتابعة"):
                try:
                    db.add_followup_record({"record_id": str(uuid.uuid4()), "student_id": selected,
                                            "teacher_id": user["user_id"], "followup_date": get_cairo_now().strftime("%Y-%m-%d"),
                                            "followup_type": ftype, "notes": notes, "regularity_status": regularity})
                    student_name = my_students[my_students.student_id==selected]["full_name"].values[0]
                    db.add_log(user["user_id"], "متابعة سريعة", f"متابعة {ftype} للطالبة {student_name}")
                    st.success("✅ تمت المتابعة بنجاح")
                    time.sleep(1)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

def show_class_competition_scores(db: Database):
    render_header()
    user = st.session_state.user
    if user.get("role") != "Teacher" or not user.get("section_id"):
        st.error("🚫 هذه الصفحة متاحة للمدرسات فقط.")
        return
    section_id = user["section_id"]
    students = db.get_students()
    quizzes = db.get_quizzes()
    results = db.get_quiz_results()
    section_students = students[students.section_id == section_id]
    if section_students.empty:
        st.info("لا توجد طالبات في فصلك.")
        return
    section_student_ids = section_students["student_id"].tolist()
    class_results = results[results["student_id"].isin(section_student_ids)]
    if "status" in class_results.columns:
        class_results = class_results[class_results["status"] == "submitted"]
    if not quizzes.empty:
        class_results = class_results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
        class_results.rename(columns={"title": "اسم المسابقة"}, inplace=True)
    if not section_students.empty:
        class_results = class_results.merge(section_students[["student_id", "full_name"]], on="student_id", how="left")
        class_results.rename(columns={"full_name": "اسم الطالبة"}, inplace=True)
    if class_results.empty:
        st.info("لا توجد نتائج مسابقات لطالبات فصلك.")
        return
    if "score" in class_results.columns:
        class_results["score"] = pd.to_numeric(class_results["score"], errors="coerce").fillna(0)
    st.dataframe(class_results, use_container_width=True)

    # --- زر ترتيب الدرجات وعرض المراكز ---
    if st.button("🏆 عرض ترتيب الطالبات حسب مجموع الدرجات", use_container_width=True):
        if "اسم الطالبة" in class_results.columns and "score" in class_results.columns:
            total_scores = class_results.groupby("اسم الطالبة")["score"].sum().reset_index()
            total_scores = total_scores.sort_values("score", ascending=False)
            total_scores["الترتيب"] = range(1, len(total_scores) + 1)
            total_scores = total_scores[["الترتيب", "اسم الطالبة", "score"]].rename(columns={"score": "مجموع الدرجات"})
            st.dataframe(total_scores, use_container_width=True)
        else:
            st.warning("بيانات الدرجات غير مكتملة.")

# =============================================================================
# التطبيق الرئيسي
# =============================================================================
def main():
    inject_css()
    init_session()
    init_data_cache()

    if 'db_instance' not in st.session_state:
        creds = get_credentials()
        st.session_state.db_instance = Database(creds, get_spreadsheet_id())
    db = st.session_state.db_instance
    jwt_secret = get_jwt_secret()

    # زرا المساعدة والقائمة العائمة
    st.markdown('<div class="help-float-btn"></div>', unsafe_allow_html=True)
    if st.button("🆘 مركز المساعدة", key="fixed_help_btn"):
        st.session_state.open_help_dialog = True
        st.rerun()

    if st.session_state.student_quiz_started:
        show_student_quiz(db)
    else:
        if not st.session_state.authenticated:
            show_login_page(db, jwt_secret)
        else:
            token_data = verify_token(st.session_state.token, jwt_secret)
            if not token_data:
                st.error("⏰ انتهت صلاحية الجلسة.")
                st.session_state.clear()
                time.sleep(2)
                st.rerun()

            if not st.session_state.get("data_validated"):
                st.session_state.data_errors = validate_data_integrity(db)
                st.session_state.data_validated = True

            # إظهار/إخفاء الشريط الجانبي
            if not st.session_state.show_sidebar:
                st.markdown("""
                <style> section[data-testid="stSidebar"] { transform: translateX(100%) !important; } </style>
                """, unsafe_allow_html=True)
                st.markdown('<div class="floating-show-btn"></div>', unsafe_allow_html=True)
                if st.button("☰", key="show_sidebar_btn"):
                    st.session_state.show_sidebar = True
                    st.rerun()
            else:
                st.markdown("""
                <style> section[data-testid="stSidebar"] { transform: translateX(0) !important; } </style>
                """, unsafe_allow_html=True)
                render_sidebar(db)

            # توجيه الصفحات
            choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
            role = st.session_state.user.get("role", "")
            menus = {
                "System Admin": ["🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", "📋 الحضور", "💬 الافتقاد",
                                 "📝 المسابقات", "📊 التقارير", "📜 سجل العمليات", "🔒 تغيير كلمة المرور"],
                "Father Account": ["🏠 لوحة التحكم", "📊 التقارير", "🔒 تغيير كلمة المرور"],
                "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد", "📝 المسابقات", "📊 التقارير", "🔒 تغيير كلمة المرور"],
                "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد", "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"]
            }
            valid_choices = menus.get(role, [])
            if choice not in valid_choices:
                choice = valid_choices[0] if valid_choices else "🏠 لوحة التحكم"
                st.session_state.menu_choice = choice

            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            if choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "👥 إدارة المستخدمين":
                show_user_management(db)
            elif choice == "🏫 إدارة المراحل":
                show_user_management(db)  # ينقل لتبويب المراحل
            elif choice == "👩‍🎓 طالباتي":
                show_my_students(db)
            elif choice == "📋 الحضور":
                show_attendance(db)
            elif choice == "💬 الافتقاد":
                show_followup(db)
            elif choice == "🏆 درجات المسابقات":
                show_class_competition_scores(db)
            elif choice == "📝 المسابقات":
                show_quizzes(db)
            elif choice == "📊 التقارير":
                show_reports(db)
            elif choice == "📜 سجل العمليات":
                show_logs(db)
            elif choice == "🔒 تغيير كلمة المرور":
                change_password(db)
            st.markdown("</div>", unsafe_allow_html=True)

            if st.session_state.get("open_help_dialog"):
                show_help_dialog()
                st.session_state.open_help_dialog = False

    # تذييل الصفحة
    st.markdown("---")
    st.markdown("<div style='text-align:center; color:#64748b; font-size:0.85rem;'>© 2025 Kenisa System. v1.0.0</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
