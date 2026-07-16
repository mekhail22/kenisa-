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

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
QUIZ_JWT_SECRET = "StDemianaChurch2025!QuizSecure#Key"
CACHE_TTL_SECONDS = 600
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
# Visitor Data Collection for AuditLog - Functions to collect client information
# =============================================================================
def get_browser_info():
    """Get browser information from user agent"""
    try:
        user_agent = st.request.headers.get("User-Agent", "")
        if "Chrome" in user_agent:
            return "Chrome"
        elif "Firefox" in user_agent:
            return "Firefox"
        elif "Safari" in user_agent:
            return "Safari"
        elif "Edge" in user_agent:
            return "Edge"
        else:
            return "Other"
    except:
        return "Unknown"

def get_os_info():
    """Get OS information from user agent"""
    try:
        user_agent = st.request.headers.get("User-Agent", "")
        if "Windows" in user_agent:
            return "Windows"
        elif "Mac" in user_agent:
            return "macOS"
        elif "Linux" in user_agent:
            return "Linux"
        elif "Android" in user_agent:
            return "Android"
        elif "iPhone" in user_agent or "iPad" in user_agent:
            return "iOS"
        else:
            return "Other"
    except:
        return "Unknown"

def get_device_type():
    """Determine device type from user agent"""
    try:
        user_agent = st.request.headers.get("User-Agent", "")
        if "Mobile" in user_agent or "Android" in user_agent:
            return "Mobile"
        elif "Tablet" in user_agent or "iPad" in user_agent:
            return "Tablet"
        else:
            return "Desktop"
    except:
        return "Unknown"

def get_screen_size():
    """Get screen size from request"""
    try:
        width = st.request.headers.get("Width", "1920")
        height = st.request.headers.get("Height", "1080")
        return f"{width}x{height}"
    except:
        return "Unknown"

def get_client_ip_masked():
    """Get client IP and mask to show only first 2 octets - e.g., 192.168.xxx.xxx"""
    try:
        ip = st.headers.get("X-Forwarded-For", st.headers.get("X-Real-IP", ""))
        if not ip:
            ip = st.headers.get("CF-Connecting-IP", "")
        if ip:
            parts = ip.split(",")[0].strip().split(".")
            if len(parts) >= 2:
                return f"{parts[0]}.{parts[1]}.xxx.xxx"
        return "127.0.0.1 (محلي)"
    except:
        return "Unknown"

def get_client_country_city():
    """Get client country, city, and region using ip-api.com"""
    try:
        response = requests.get("http://ip-api.com/json/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("country", ""), data.get("city", ""), data.get("regionName", "")
    except:
        pass
    return "", "", ""

# =============================================================================
# Telegram & Support Configuration
# =============================================================================
def get_telegram_config():
    try:
        return st.secrets["telegram"]["bot_token"], st.secrets["telegram"]["chat_id"]
    except Exception:
        return None, None

def get_support_config():
    try:
        return (
            st.secrets.get("support", {}).get("contact_name", "مسؤول النظام"),
            st.secrets.get("support", {}).get("whatsapp", "")
        )
    except Exception:
        return "مسؤول النظام", ""

# =============================================================================
# Google Cloud Credentials & Spreadsheet Configuration
# =============================================================================
def get_credentials():
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
    except Exception:
        return DEFAULT_JWT_SECRET

# =============================================================================
# CSS Styles - Light Theme with Responsive Design
# =============================================================================
def inject_css():
    st.markdown("""
    <style>
        html, body, .stApp { color-scheme: light !important; }
        @media (prefers-color-scheme: dark) {
            html, body, .stApp { background-color: #f0f2f6 !important; color: #1a1a2e !important; }
        }
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { font-family: 'Cairo', sans-serif; }
        body { direction: rtl; text-align: right; background-color: #f0f2f6; color: #1a1a2e; }
        .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); }
        header[data-testid="stHeader"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        
        section[data-testid="stSidebar"] {
            position: fixed !important; top: 0 !important; right: 0 !important; height: 100vh !important;
            width: 300px !important; z-index: 10000 !important;
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%) !important;
            transform: translateX(0);
        }
        [data-testid="stAppViewContainer"] > [data-testid="stMain"] { max-width: 100% !important; }
        .nav-btn-container .stButton > button { width: 100% !important; text-align: right !important; }
        .floating-show-btn .stButton > button { position: fixed !important; top: 20px !important; right: 20px !important; z-index: 99999 !important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; }
        .help-float-container .stButton > button { position: fixed !important; top: 20px !important; right: 100px !important; z-index: 99998 !important; background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important; }
        .main-header { font-size: 2.2rem; text-align: center; margin-top: 100px; }
        .card { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.5rem; }
        .stButton > button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# Data Cache Initialization
# =============================================================================
def init_data_cache():
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
    if 'data_dirty' not in st.session_state:
        st.session_state.data_dirty = {}

# =============================================================================
# Retry Decorator for API Resilience
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
                        time.sleep(base_delay * (2 ** attempt))
                    else:
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
# AnomalyDetector Class - Security Monitoring (LOG ONLY - NO BLOCKING)
# All methods log anomalies but NEVER block the user
# =============================================================================
class AnomalyDetector:
    """Inline security anomaly detection class - LOG ONLY, NO BLOCKING"""
    
    @staticmethod
    def check_login(user_id, ip_country):
        """Check if login country is suspicious (not Egypt) - LOG ONLY, NEVER BLOCK"""
        if ip_country and ip_country != "Egypt":
            if 'db_instance' in st.session_state:
                db = st.session_state.db_instance
                db.add_audit_log(
                    user_id=user_id, user_name="زائر", action="ANOMALY_DETECTED",
                    details=f"Suspicious login from country: {ip_country}"
                )
        return True  # Always return True - NO BLOCKING
    
    @staticmethod
    def check_behavior(user_id, action_count):
        """Check if user has suspicious behavior (>100 deletes in 1 min) - LOG ONLY, NEVER BLOCK"""
        if action_count > 100:
            if 'db_instance' in st.session_state:
                db = st.session_state.db_instance
                db.add_audit_log(
                    user_id=user_id, user_name="زائر", action="ANOMALY_DETECTED",
                    details=f"Suspicious behavior: {action_count} actions in 1 minute"
                )
        return True  # Always return True - NO BLOCKING
    
    @staticmethod
    def check_time(user_id):
        """Check if login time is suspicious (00:00-05:00 Cairo) - LOG ONLY, NEVER BLOCK"""
        current_hour = get_cairo_now().hour
        if 0 <= current_hour < 5:
            if 'db_instance' in st.session_state:
                db = st.session_state.db_instance
                db.add_audit_log(
                    user_id=user_id, user_name="زائر", action="ANOMALY_DETECTED",
                    details=f"Suspicious time login: Hour {current_hour}"
                )
        return True  # Always return True - NO BLOCKING

# =============================================================================
# Data Masking Functions - For non-admin users
# =============================================================================
def mask_data(value, mask_type):
    """Mask sensitive data based on type for non-admin users
    Names: 'سارة جـ***'
    Phones: '010***1234'
    """
    if value is None or pd.isna(value):
        return ""
    value = str(value).strip()
    if mask_type == "name":
        return value[:2] + "ـ***" if len(value) > 2 else value[0] + "***"
    elif mask_type == "phone":
        return value[:3] + "***" + value[-4:] if len(value) >= 8 else "*******"
    return value

def apply_masking(df, columns_to_mask, is_admin=False):
    """Apply masking to DataFrame for non-admins"""
    if is_admin or df.empty:
        return df
    result_df = df.copy()
    for col, mask_type in columns_to_mask.items():
        if col in result_df.columns:
            result_df[col] = result_df[col].apply(lambda x: mask_data(x, mask_type))
    return result_df

# =============================================================================
# Auto Logout - Session Timeout Management
# =============================================================================
def check_auto_logout():
    """Check inactivity and trigger auto-logout if needed
    Warning at 4:30 minutes (270 seconds)
    Auto-logout at 5:00 minutes (300 seconds)
    """
    if "last_activity_time" not in st.session_state:
        st.session_state.last_activity_time = time.time()
    current_time = time.time()
    inactive_seconds = current_time - st.session_state.last_activity_time
    if 270 <= inactive_seconds < 300 and not st.session_state.get("logout_warning_shown", False):
        st.session_state.logout_warning_shown = True
        st.warning("⚠️ سيتم تسجيل الخروج خلال 30 ثانية بسبب عدم النشاط لمدة 4.5 دقيقة")
    elif inactive_seconds >= 300:
        st.error("⏰ تم تسجيل الخروج تلقائياً بسبب عدم النشاط لمدة 5 دقائق")
        time.sleep(2)
        logout()
        return True
    st.session_state.last_activity_time = current_time
    if inactive_seconds < 270 and st.session_state.get("logout_warning_shown", False):
        st.session_state.logout_warning_shown = False
    return False

# =============================================================================
# GDPR Delete - Permanently delete student records from ALL sheets
# =============================================================================
def gdpr_delete_student(db, student_id):
    """Permanently delete ALL records of a student from ALL sheets including AuditLog"""
    try:
        db.delete_student(student_id)
        for sheet_name, id_col in [("Attendance", "student_id"), ("FollowUp", "student_id"), ("QuizResults", "student_id")]:
            df = db._sheet_to_df(sheet_name)
            if not df.empty and id_col in df.columns:
                cols = {"Attendance": ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"],
                        "FollowUp": ["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"],
                        "QuizResults": ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"]}[sheet_name]
                df = df[df[id_col] != student_id]
                db._df_to_sheet(sheet_name, df, cols)
        audit_log = db._sheet_to_df("AuditLog")
        if not audit_log.empty and "user_id" in audit_log.columns:
            audit_log = audit_log[audit_log.user_id != student_id]
            db._df_to_sheet("AuditLog", audit_log, ["timestamp", "user_id", "user_name", "action", "details", "browser", "os", "device_type", "screen_size", "ip_masked", "country", "city", "region", "privacy_consent"])
        return True
    except Exception as e:
        st.error(f"خطأ في حذف الطالبة: {str(e)}")
        return False

# =============================================================================
# Database Class with Caching and Rate Limiting
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
                time.sleep(1)
                Database._request_times = []
            Database._request_times.append(now)

    def __init__(self, creds, spreadsheet_id):
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(self, name, columns):
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(columns), 1))
            if columns: ws.append_row(columns)
        return ws

    def _sheet_to_df(self, sheet_name):
        ws = self._get_or_create_worksheet(sheet_name, [])
        values = ws.get_all_values()
        if not values or len(values) < 1: return pd.DataFrame()
        raw_headers = [h.strip() for h in values[0]]
        seen, unique_headers = {}, []
        for h in raw_headers:
            if h in seen: seen[h] += 1; unique_headers.append(f"{h}_{seen[h]}")
            else: seen[h] = 0; unique_headers.append(h)
        df = pd.DataFrame(values[1:], columns=unique_headers)
        df.dropna(how='all', axis=1, inplace=True)
        df.dropna(how='all', inplace=True)
        return df.astype(object)

    def _df_to_sheet(self, sheet_name, df, columns):
        ws = self._get_or_create_worksheet(sheet_name, columns)
        for col in columns:
            if col not in df.columns: df[col] = ""
        work_df = df[columns].copy()
        work_df.fillna("", inplace=True)
        work_df = work_df.astype(str)
        values = [columns] + work_df.values.tolist()
        ws.resize(rows=len(values), cols=len(columns))
        ws.update(values)

    @staticmethod
    def _safe_str(value):
        if value is None or (isinstance(value, float) and pd.isna(value)): return ""
        return str(value)

    # --- Users CRUD ---
    def get_users(self): return self._sheet_to_df("Users")

    def add_user(self, user_data):
        df = self.get_users()
        if df.empty: df = pd.DataFrame(columns=["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"])
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        self._df_to_sheet("Users", df, ["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"])

    def update_user(self, user_id, updates):
        df = self.get_users()
        idx = df[df.user_id == user_id].index
        if len(idx) > 0:
            for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Users", df, df.columns.tolist())

    def delete_user(self, user_id):
        df = self.get_users(); df = df[df.user_id != user_id]
        self._df_to_sheet("Users", df, ["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"])

    # --- Stages CRUD ---
    def get_stages(self): return self._sheet_to_df("Stages")

    def add_stage(self, stage_data):
        df = self.get_stages()
        if df.empty: df = pd.DataFrame(columns=["stage_id", "stage_name", "manager_user_id"])
        df = pd.concat([df, pd.DataFrame([{"stage_id": stage_data["stage_id"], "stage_name": stage_data["stage_name"], "manager_user_id": stage_data.get("manager_user_id", "")}])], ignore_index=True)
        self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])

    def update_stage(self, stage_id, updates):
        df = self.get_stages(); idx = df[df.stage_id == stage_id].index
        if len(idx) > 0:
            for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])

    def delete_stage(self, stage_id):
        df = self.get_stages(); df = df[df.stage_id != stage_id]
        self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])

    # --- Sections CRUD ---
    def get_sections(self): return self._sheet_to_df("Sections")

    def add_section(self, sec_data):
        self._get_or_create_worksheet("Sections", ["section_id", "section_name", "manager_user_id"])
        df = self.get_sections()
        if df.empty: df = pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
        df = pd.concat([df, pd.DataFrame([{"section_id": sec_data["section_id"], "section_name": sec_data["section_name"], "manager_user_id": sec_data.get("manager_user_id", "")}])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    def update_section(self, section_id, updates):
        df = self.get_sections(); idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections(); df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    # --- Students CRUD ---
    def get_students(self): return self._sheet_to_df("Students")

    def add_student(self, student_data):
        df = self.get_students()
        if df.empty: df = pd.DataFrame(columns=["student_id", "full_name", "section_id", "teacher_id", "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])
        student_data["teacher_id"] = ""
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        self._df_to_sheet("Students", df, ["student_id", "full_name", "section_id", "teacher_id", "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])

    def update_student(self, student_id, updates):
        df = self.get_students(); idx = df[df.student_id == student_id].index
        if len(idx) > 0:
            for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Students", df, df.columns.tolist())

    def delete_student(self, student_id):
        df = self.get_students(); df = df[df.student_id != student_id]
        self._df_to_sheet("Students", df, ["student_id", "full_name", "section_id", "teacher_id", "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])

    # --- Attendance CRUD ---
    def get_attendance(self): return self._sheet_to_df("Attendance")

    def batch_add_attendance(self, records_list):
        if not records_list: return
        df = self.get_attendance()
        if df.empty: df = pd.DataFrame(columns=["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
        existing_ids = set(df["record_id"].tolist()) if not df.empty else set()
        for rec in records_list:
            if rec["record_id"] in existing_ids:
                idx = df[df.record_id == rec["record_id"]].index[0]
                for k, v in rec.items(): df.at[idx, k] = self._safe_str(v)
            else:
                df = pd.concat([df, pd.DataFrame([rec])], ignore_index=True)
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    def get_attendance_by_date_section(self, date_str, section_id):
        df = self.get_attendance()
        if df.empty: return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    def delete_attendance_record(self, record_id):
        df = self.get_attendance(); df = df[df.record_id != record_id]
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    # --- FollowUp CRUD ---
    def get_followup(self): return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record):
        df = self.get_followup()
        if not df.empty:
            duplicate = df[(df.student_id == record["student_id"]) & (df.followup_date == record["followup_date"]) & (df.followup_type == record["followup_type"])]
            if not duplicate.empty: raise ValueError("⛔ تم تسجيل نفس الافتقاد مسبقاً")
        if df.empty: df = pd.DataFrame(columns=["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])

    def delete_followup_record(self, record_id):
        df = self.get_followup(); df = df[df.record_id != record_id]
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])

    # --- Quizzes CRUD ---
    def get_quizzes(self): return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data):
        df = self.get_quizzes()
        if df.empty: df = pd.DataFrame(columns=["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])
        df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])

    def update_quiz(self, quiz_id, updates):
        df = self.get_quizzes(); idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def delete_quiz_keep_results(self, quiz_id):
        df = self.get_quizzes(); df = df[df.quiz_id != quiz_id]
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])
        qdf = self._sheet_to_df("QuizQuestions"); qdf = qdf[qdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizQuestions", qdf, ["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_quiz(self, quiz_id):
        self.delete_quiz_keep_results(quiz_id)
        rdf = self._sheet_to_df("QuizResults"); rdf = rdf[rdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizResults", rdf, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    # --- Quiz Questions CRUD ---
    def get_quiz_questions(self, quiz_id):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty: return pd.DataFrame()
        return df[df.quiz_id == quiz_id]

    def add_question(self, q_data):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty: df = pd.DataFrame(columns=["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])
        df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_question(self, question_id):
        df = self._sheet_to_df("QuizQuestions"); df = df[df.question_id != question_id]
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])

    # --- Quiz Results CRUD ---
    def get_quiz_results(self, quiz_id=None):
        df = self._sheet_to_df("QuizResults")
        if df.empty: return pd.DataFrame()
        return df[df.quiz_id == quiz_id] if quiz_id else df

    def start_quiz_attempt(self, quiz_id, student_id, student_name):
        result_id = str(uuid.uuid4()); now_iso = get_cairo_now().isoformat()
        new_row = {"result_id": result_id, "quiz_id": quiz_id, "student_id": student_id, "student_name": student_name, "score": "", "total_marks": "20", "start_time": now_iso, "submission_time": now_iso, "answers": "{}", "status": "started"}
        df = self._sheet_to_df("QuizResults")
        if df.empty: df = pd.DataFrame(columns=["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        return result_id

    def save_answers(self, result_id, answers_dict):
        df = self._sheet_to_df("QuizResults")
        idx = df[df.result_id == result_id].index
        if len(idx) > 0: df.at[idx[0], "answers"] = json.dumps(answers_dict, ensure_ascii=False)
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def submit_quiz_attempt(self, result_id, score, answers_json):
        df = self._sheet_to_df("QuizResults"); idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "score"] = str(score); df.at[idx[0], "answers"] = answers_json
            df.at[idx[0], "submission_time"] = get_cairo_now().isoformat(); df.at[idx[0], "status"] = "submitted"
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def delete_quiz_result(self, result_id):
        df = self._sheet_to_df("QuizResults"); df = df[df.result_id != result_id]
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    # --- Legacy Logs ---
    def get_logs(self): return self._sheet_to_df("Logs")

    def add_log(self, user_id, action, details=""):
        log = {"log_id": str(uuid.uuid4()), "timestamp": get_cairo_now().isoformat(), "user_id": user_id, "action": action, "details": details}
        df = self.get_logs()
        if df.empty: df = pd.DataFrame(columns=["log_id", "timestamp", "user_id", "action", "details"])
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

    def delete_log(self, log_id):
        df = self.get_logs(); df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

    # --- AuditLog (14 columns) ---
    def get_audit_log(self):
        return self._sheet_to_df("AuditLog")

    def add_audit_log(self, user_id, user_name, action, details=""):
        """Add entry to AuditLog with full visitor tracking (14 columns)
        All 14 columns in exact order.
        """
        ip_masked = get_client_ip_masked()
        country, city, region = get_client_country_city()
        audit_entry = {"timestamp": get_cairo_now().isoformat(), "user_id": user_id or "anonymous", "user_name": user_name or "زائر", "action": action, "details": details, "browser": get_browser_info(), "os": get_os_info(), "device_type": get_device_type(), "screen_size": get_screen_size(), "ip_masked": ip_masked, "country": country, "city": city, "region": region, "privacy_consent": "true"}
        df = self.get_audit_log()
        if df.empty: df = pd.DataFrame(columns=["timestamp", "user_id", "user_name", "action", "details", "browser", "os", "device_type", "screen_size", "ip_masked", "country", "city", "region", "privacy_consent"])
        df = pd.concat([df, pd.DataFrame([audit_entry])], ignore_index=True)
        self._df_to_sheet("AuditLog", df, ["timestamp", "user_id", "user_name", "action", "details", "browser", "os", "device_type", "screen_size", "ip_masked", "country", "city", "region", "privacy_consent"])

# =============================================================================
# JWT Token Helpers
# =============================================================================
def generate_token(user: dict, secret: str) -> str:
    return jwt.encode({"user_id": user.get("user_id", ""), "role": user.get("role", ""), "full_name": user.get("full_name", ""), "section_id": user.get("section_id", ""), "exp": datetime.utcnow() + timedelta(hours=24)}, secret, algorithm="HS256")

def generate_quiz_token(quiz_id: str, student_id: str) -> str:
    return jwt.encode({"quiz_id": quiz_id, "student_id": student_id, "exp": datetime.utcnow() + timedelta(hours=48)}, QUIZ_JWT_SECRET, algorithm="HS256")

def verify_quiz_token(token: str):
    try: return jwt.decode(token, QUIZ_JWT_SECRET, algorithms=["HS256"])
    except: return None

def verify_token(token: str, secret: str):
    try: return jwt.decode(token, secret, algorithms=["HS256"])
    except: return None

# =============================================================================
# Session Management
# =============================================================================
def init_session():
    defaults = {"authenticated": False, "user": None, "token": None, "student_quiz": None, "student_quiz_started": False, "quiz_phase": "enter_name", "student_name": "", "student_id": "", "quiz_start_time": None, "quiz_end_time": None, "quiz_submit_time": None, "quiz_token": None, "quiz_answers": {}, "quiz_submitted": False, "last_score": 0, "menu_choice": "🏠 لوحة التحكم", "show_sidebar": True, "open_help_dialog": False, "current_attempt_id": None, "last_saved_answers_str": "", "quiz_questions": None, "show_review": False, "data_errors": [], "data_validated": False, "quiz_load_failures": 0, "last_activity_time": time.time()}
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def logout(db=None):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# =============================================================================
# Telegram Integration
# =============================================================================
def send_telegram_message(message: str) -> bool:
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id: return False
    try: requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass
    return True

# =============================================================================
# Help Dialog
# =============================================================================
@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    st.markdown("### 📬 تواصل معنا")
    st.info("يرجى ملء النموذج أدناه للحصول على المساعدة")

# =============================================================================
# Data Validation
# =============================================================================
def validate_data_integrity(db: Database):
    errors = []; students = db.get_students(); sections = db.get_sections()
    if not students.empty and not sections.empty:
        valid = set(sections["section_id"].tolist())
        for _, r in students.iterrows():
            s = r.get("section_id", "")
            if pd.isna(s) or str(s).strip() == "": errors.append(f"الطالبة {r.get('full_name', '')} ليس لديها فصل.")
            elif str(s).strip() not in valid: errors.append(f"الطالبة {r.get('full_name', '')} تنتمي لفصل غير موجود ({s}).")
    return errors

def auto_fix_missing_sections(db: Database):
    students = db.get_students(); sections = db.get_sections()
    if students.empty: return False
    existing = set(sections["section_id"].tolist()) if not sections.empty else set()
    missing = [s for s in students["section_id"].dropna().unique().tolist() if s and str(s).strip() not in existing]
    for s in missing: db.add_section({"section_id": str(s), "section_name": f"فصل (معرف {s[:8]})"})
    return len(missing) > 0

# =============================================================================
# Initialization Page
# =============================================================================
def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", use_container_width=True, key="init_btn"):
            db.add_user({"user_id": "admin-001", "username": "admin", "password": "admin123", "role": "System Admin", "full_name": "مدير النظام", "section_id": "", "phone": "0100000000", "email": "admin@church.com"})
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.info("**اسم المستخدم:** `admin`\n\n**كلمة المرور:** `admin123`")
            time.sleep(2); st.rerun()
        st.stop()

# =============================================================================
# Login Page
# =============================================================================
def show_login_page(db: Database, jwt_secret: str):
    st.markdown("<h1 class='main-header'>⛪ <br>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
    show_initialization(db)
    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم").strip()
            password = st.text_input("كلمة المرور", type="password").strip()
            if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                if not username or not password: st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                else:
                    with st.spinner("جاري التحقق..."):
                        users = db.get_users(); user_row = users[users.username == username]
                        if user_row.empty: st.error("اسم المستخدم غير موجود")
                        else:
                            user = user_row.iloc[0].to_dict()
                            if password == user.get("password", ""):
                                country, _, _ = get_client_country_city()
                                AnomalyDetector.check_login(user.get("user_id", ""), country)
                                AnomalyDetector.check_time(user.get("user_id", ""))
                                token = generate_token(user, jwt_secret)
                                st.session_state.token = token; st.session_state.user = user; st.session_state.authenticated = True
                                st.session_state.menu_choice = "🏠 لوحة التحكم"; st.session_state.show_sidebar = True
                                st.session_state.last_activity_time = time.time()
                                db.add_log(user["user_id"], "تسجيل الدخول")
                                st.success("تم تسجيل الدخول بنجاح!"); time.sleep(1); st.rerun()
                            else: st.error("كلمة المرور غير صحيحة")
    with tab2:
        st.subheader("دخول الاختبار الإلكتروني")
        with st.form("quiz_form"):
            code = st.text_input("كود الاختبار", placeholder="مثال: GEN123").strip()
            passwd = st.text_input("كلمة مرور الاختبار", type="password", placeholder="مثال: QUIZ99").strip()
            if st.form_submit_button("بدء الاختبار", use_container_width=True):
                if not code or not passwd: st.error("الرجاء إدخال الكود وكلمة المرور")
                else:
                    with st.spinner("جاري التحقق..."):
                        qz = db.get_quizzes(); quiz = qz[(qz.quiz_code == code) & (qz.password == passwd)]
                        if quiz.empty: st.error("كود أو كلمة مرور خاطئة")
                        else:
                            quiz = quiz.iloc[0].to_dict()
                            try:
                                exp = pd.to_datetime(quiz.get("expiry_date", "")).to_pydatetime().replace(tzinfo=CAIRO_TZ)
                                if exp < get_cairo_now(): st.error("انتهت صلاحية الاختبار")
                                elif quiz.get("is_active", "True") == "False": st.error("الاختبار غير نشط")
                                else:
                                    st.session_state.student_quiz = quiz; st.session_state.student_quiz_started = True
                                    for k in ["student_name","student_id","quiz_start_time","quiz_end_time","quiz_submit_time","quiz_token","quiz_answers","quiz_submitted","last_score"]: st.session_state[k] = "" if k in ["student_name","student_id"] else None if k in ["quiz_start_time","quiz_end_time","quiz_submit_time"] else {} if k=="quiz_answers" else 0
                                    st.rerun()
                            except Exception as e: st.error(f"خطأ: {str(e)}")

# =============================================================================
# Student Quiz Interface (Placeholder)
# =============================================================================
def show_student_quiz(db: Database):
    st.markdown("### واجهة الاختبار - تحت التطوير")

# =============================================================================
# Sidebar Navigation
# =============================================================================
def show_sidebar_navigation(db: Database):
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        u = st.session_state.get("user", {})
        st.markdown(f"**👤 {u.get('full_name', '')}**"); st.caption(f"الصلاحية: {u.get('role', '')}")
        st.divider()
        role = u.get("role", "")
        menus = {"System Admin": ["🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات", "📊 التقارير", "📜 السجلات", "🔒 كلمة المرور"], "Father Account": ["🏠 لوحة التحكم", "📊 التقارير", "🔒 كلمة المرور"], "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد", "📝 المسابقات", "📊 التقارير", "🔒 كلمة المرور"], "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد", "🏆 الدرجات", "🔒 كلمة المرور"]}
        items = menus.get(role, [])
        if not items: return None
        choice = st.session_state.get("menu_choice", items[0])
        if st.button("✕ إخفاء", key="hide_nav"): st.session_state.show_sidebar = False; st.rerun()
        for item in items:
            if st.button(item, key=f"nav_{item}", use_container_width=True, type="primary" if item==choice else "secondary"):
                st.session_state.menu_choice = item; st.session_state.show_sidebar = False; st.rerun()
        st.divider()
        if st.button("🚪 خروج", use_container_width=True, key="logout_nav"): logout()
    return st.session_state.get("menu_choice")

# =============================================================================
# Dashboard
# =============================================================================
def show_dashboard(db: Database):
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
    students = db.get_students(); att = db.get_attendance(); fup = db.get_followup()
    role = st.session_state.get("user", {}).get("role", ""); sec = st.session_state.get("user", {}).get("section_id", "")
    if role in ["Teacher", "Service Manager"] and sec:
        students = students[students.section_id == sec] if not students.empty else students
        att = att[att.section_id == sec] if not att.empty else att
    if not att.empty and "date" in att.columns: att["date"] = pd.to_datetime(att["date"], errors="coerce")
    today = get_cairo_now().strftime("%Y-%m-%d")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("الطالبات", len(students))
    c2.metric("حاضر اليوم", len(att[(att.date==today) & (att.status=="حاضر")]) if not att.empty else 0)
    c3.metric("غائب اليوم", len(att[(att.date==today) & (att.status=="غائب")]) if not att.empty else 0)
    c4.metric("منقطعات", len(fup[fup.regularity_status=="منقطع"]) if not fup.empty else 0)

# =============================================================================
# User Management with GDPR Delete
# =============================================================================
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users(); secs = db.get_sections(); sts = db.get_students()
    is_admin = st.session_state.get("user", {}).get("role") == "System Admin"
    st.subheader("قائمة الطالبات")
    if not sts.empty:
        disp = apply_masking(sts.merge(secs[["section_id","section_name"]], on="section_id", how="left") if not secs.empty else sts, {"full_name":"name","phone":"phone","parent_phone":"phone"}, is_admin)
        st.dataframe(disp, use_container_width=True)
    else: st.info("لا توجد طالبات.")
    if is_admin:
        st.markdown("---"); st.subheader("🔒 حذف نهائي GDPR")
        st.warning("⚠️ حذف جميع السجلات المتعلقة بالطالبة")
        if not sts.empty:
            sid = st.selectbox("اختر طالبة", sts["student_id"], key="gdpr_sel")
            pwd = st.text_input("كلمة مرور المشرف", type="password", key="gdpr_pwd")
            if st.button("🔴 حذف نهائي", key="gdpr_btn"):
                admin = db.get_users()[db.get_users().user_id==st.session_state.user.get("user_id")].iloc[0] if not db.get_users().empty else None
                if admin and pwd==admin.get("password",""):
                    if gdpr_delete_student(db, sid): st.success("✅ تم الحذف"); time.sleep(1); st.rerun()
                else: st.error("كلمة مرور غير صحيحة")

# =============================================================================
# Reports Page
# =============================================================================
def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير</h2>", unsafe_allow_html=True)
    st.info("صفحة التقارير - تحت التطوير")

# =============================================================================
# Logs Page
# =============================================================================
def show_logs(db: Database):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db.get_logs()
    if logs.empty: st.info("لا توجد سجلات."); return
    st.dataframe(logs.sort_values("timestamp", ascending=False) if "timestamp" in logs.columns else logs, use_container_width=True)

# =============================================================================
# Change Password Page
# =============================================================================
def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    u = st.session_state.get("user", {})
    with st.form("pwd_form"):
        old = st.text_input("كلمة المرور الحالية", type="password").strip()
        new = st.text_input("كلمة المرور الجديدة", type="password").strip()
        confirm = st.text_input("تأكيد كلمة المرور", type="password").strip()
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old or not new or not confirm: st.error("الرجاء ملء جميع الحقول")
            elif old != u.get("password", ""): st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new) < 4: st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
            elif new != confirm: st.error("كلمتا المرور غير متطابقتين")
            else: db.update_user(u["user_id"], {"password": new}); st.session_state.user["password"] = new; st.success("✅ تم التغيير بنجاح!")

# =============================================================================
# Main Application Entry Point
# =============================================================================
def main():
    inject_css(); init_session(); init_data_cache()
    if 'db_instance' not in st.session_state:
        try: st.session_state.db_instance = Database(get_credentials(), get_spreadsheet_id())
        except Exception as e: st.error(f"❌ خطأ: {e}"); st.stop()
    db = st.session_state.db_instance; jwt_secret = get_jwt_secret()
    st.markdown('<div class="help-float-container"></div>', unsafe_allow_html=True)
    if st.button("🆘 مساعدة", key="help_btn"): st.session_state.open_help_dialog = True; st.rerun()
    if st.session_state.get("student_quiz_started"): show_student_quiz(db)
    elif not st.session_state.get("authenticated"): show_login_page(db, jwt_secret)
    else:
        if check_auto_logout(): return
        if not verify_token(st.session_state.token, jwt_secret): st.error("⏰ الصلاحية انتهت."); st.session_state.clear(); time.sleep(2); st.rerun(); return
        choice = show_sidebar_navigation(db) if st.session_state.get("show_sidebar") else st.session_state.get("menu_choice", "🏠 لوحة التحكم")
        st.markdown("<div class='content-area'>", unsafe_allow_html=True)
        if choice == "🏠 لوحة التحكم": show_dashboard(db)
        elif choice == "👥 إدارة المستخدمين": show_user_management(db) if st.session_state.user.get("role")=="System Admin" else st.error("🚫 غير مصرح")
        elif choice == "📊 التقارير": show_reports(db)
        elif choice == "📜 السجلات": show_logs(db) if st.session_state.user.get("role")=="System Admin" else st.error("🚫 غير مصرح")
        elif choice == "🔒 كلمة المرور": change_password(db)
        else: st.info(f"الصفحة: {choice}")
        st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state.get("open_help_dialog"): show_help_dialog()

if __name__ == "__main__":
    main()
