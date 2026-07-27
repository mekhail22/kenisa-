import streamlit as st
import streamlit.components.v1 as components
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
import hashlib
import hmac
import os
import io
import zipfile
from functools import wraps
import threading
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import base64
from io import BytesIO
import plotly.graph_objects as go
import plotly.io as pio

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
QUIZ_JWT_SECRET = "StDemianaChurch2025!QuizSecure#Key"
CACHE_TTL_SECONDS = 600
SESSION_TIMEOUT_HOURS = 8
CAIRO_TZ = timezone(timedelta(hours=3), name='Africa/Cairo')

# Password hashing
def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a random salt."""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + key.hex()

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash (or plaintext fallback)."""
    try:
        salt_hex, key_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        stored_key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hmac.compare_digest(new_key, stored_key)
    except (ValueError, AttributeError):
        return stored_hash == password


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
# Telegram & Support
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
# Credentials & IDs
# =============================================================================
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
    except Exception:
        return DEFAULT_JWT_SECRET


# =============================================================================
# get sections from users sheet (column "section_id")
# =============================================================================
@st.cache_data(ttl=600)
def get_sections_from_users():
    """
    قراءة قائمة الفصول الفريدة من ورقة Users (عمود section_id).
    ترجع قائمة مرتبة من الفصول غير الفارغة.
    """
    try:
        if 'db_instance' in st.session_state:
            db_local = st.session_state.db_instance
            users = db_local.get_users()
            if not users.empty and "section_id" in users.columns:
                sections = users["section_id"].dropna().unique().tolist()
                sections = [s.strip() for s in sections if s and str(s).strip() and str(s).strip().upper() != "N/A"]
                sections = sorted(set(sections))
                return sections
    except Exception:
        pass
    return []


# =============================================================================
# helpers: age and colors
# =============================================================================
def get_student_age(birthdate):
    if not birthdate:
        return None
    try:
        bd = pd.to_datetime(birthdate)
        now = datetime.now()
        return now.year - bd.year - ((now.month, now.day) < (bd.month, bd.day))
    except Exception:
        return None


STAGE_COLORS = {
    "إعدادي": "#28a745",
    "ثانوي": "#007bff",
    "جامعي": "#6f42c1",
    "KG1": "#fd7e14",
    "KG2": "#e83e8c",
    "الصف الأول": "#20c997",
    "default": "#667eea"
}


def get_stage_color(stage_name):
    for key, color in STAGE_COLORS.items():
        if key in str(stage_name):
            return color
    return STAGE_COLORS["default"]


# =============================================================================
# CSS
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
        section[data-testid="stSidebar"] {
            position: fixed !important; top: 0 !important; right: 0 !important;
            height: 100vh !important; width: 300px !important; z-index: 10000 !important;
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%) !important;
        }
        @media (max-width: 768px) { section[data-testid="stSidebar"] { width: 100vw !important; } }
        .nav-btn-container .stButton > button {
            width: 100% !important; text-align: right !important; justify-content: flex-start !important;
            padding: 0.7rem 1rem !important; font-size: 1rem !important; font-weight: 600 !important;
            border-radius: 10px !important; background: transparent !important; color: #1a1a2e !important;
            border: 1px solid transparent !important; direction: rtl !important;
        }
        .nav-btn-container .stButton > button:hover {
            background: rgba(102,126,234,0.08) !important; color: #667eea !important;
            border-color: rgba(102,126,234,0.15) !important;
        }
        .nav-btn-container .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border: none !important;
        }
        .floating-show-btn .stButton > button {
            position: fixed !important; top: 20px !important; right: 20px !important; z-index: 99999 !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; color: white !important;
            border: none !important; border-radius: 15px !important; width: 60px !important; height: 60px !important;
            font-size: 28px !important; font-weight: bold !important; box-shadow: 0 4px 15px rgba(102,126,234,0.4) !important;
        }
        .help-float-container .stButton > button {
            position: fixed !important; top: 20px !important; right: 100px !important; z-index: 99998 !important;
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important; color: white !important;
            font-weight: 700 !important; border-radius: 12px !important; padding: 12px 20px !important;
            font-size: 16px !important; border: none !important; white-space: nowrap !important;
        }
        .main-header {
            font-size: 2.2rem; font-weight: 700; color: #1a1a2e; text-align: center;
            margin-bottom: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.9);
            border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-top: 100px;
        }
        .user-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border-radius: 16px; padding: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            border: 1px solid rgba(0,0,0,0.05); transition: all 0.3s ease; position: relative; overflow: hidden;
        }
        .user-avatar {
            width: 70px; height: 70px; border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 1.8rem; font-weight: 700;
        }
        .profile-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px; padding: 2rem; color: white;
            box-shadow: 0 8px 25px rgba(102,126,234,0.3); margin-bottom: 2rem;
        }
        .profile-stat-card {
            background: white; border-radius: 12px; padding: 1rem; text-align: center;
            box-shadow: 0 3px 10px rgba(0,0,0,0.06); border: 1px solid rgba(0,0,0,0.04);
        }
        .profile-stat-card h3 { color: #667eea; font-size: 1.8rem; margin: 0; }
        .profile-stat-card p { color: #6c757d; font-size: 0.85rem; margin: 0; }
        .status-badge {
            display: inline-block; padding: 0.2rem 0.8rem; border-radius: 20px;
            font-size: 0.75rem; font-weight: 600;
        }
        .status-badge.active { background: #d4edda; color: #155724; }
        .status-badge.inactive { background: #e2e3e5; color: #383d41; }
        .role-badge {
            display: inline-block; padding: 0.2rem 0.8rem; border-radius: 20px;
            font-size: 0.75rem; font-weight: 600;
        }
        .role-badge.admin { background: #cce5ff; color: #004085; }
        .role-badge.priest { background: #d4edda; color: #155724; }
        .role-badge.leader { background: #fff3cd; color: #856404; }
        .role-badge.teacher { background: #e2e3e5; color: #383d41; }
        .content-area { padding: 0 1rem; }
        .stDataFrame { background: white; border-radius: 10px; }
        .streamlit-expanderHeader {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border-radius: 8px !important; font-weight: 600 !important;
        }
        .stSuccess { background: rgba(40,167,69,0.1); border: 1px solid rgba(40,167,69,0.2); color: #155724; border-radius: 10px; }
        .stError { background: rgba(220,53,69,0.1); border: 1px solid rgba(220,53,69,0.2); color: #721c24; border-radius: 10px; }
        @media (max-width: 768px) {
            .main-header { font-size: 1.6rem; margin-top: 110px; }
            .floating-show-btn .stButton > button { width: 50px !important; height: 50px !important; font-size: 24px !important; }
            .help-float-container .stButton > button { right: 80px !important; padding: 10px 16px !important; font-size: 14px !important; }
        }
    </style>
    """, unsafe_allow_html=True)


def inject_user_cards_css():
    st.markdown("""
    <style>
        .user-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.05);
        }
        .user-card .card-badge {
            position: absolute; top: 0; left: 0; padding: 0.3rem 1rem;
            border-radius: 0 0 16px 0; font-size: 0.7rem; font-weight: 700; color: white;
        }
        .user-card .card-badge.active { background: linear-gradient(135deg, #28a745, #20c997); }
        .user-card .card-badge.inactive { background: linear-gradient(135deg, #6c757d, #adb5bd); }
        .user-avatar {
            width: 70px; height: 70px; border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)


def inject_students_cards_css():
    st.markdown("""
    <style>
        .student-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.05);
            position: relative; overflow: hidden; transition: all 0.3s ease;
        }
        .student-card:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(0,0,0,0.12); }
        .student-avatar-large {
            width: 60px; height: 60px; border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 1.5rem; font-weight: 700;
        }
        .student-info-row {
            display: flex; align-items: center; gap: 0.5rem;
            margin: 0.4rem 0; font-size: 0.9rem; color: #333;
        }
        .student-badge {
            display: inline-block; padding: 0.25rem 0.75rem; border-radius: 20px;
            font-size: 0.75rem; font-weight: 600;
        }
        .student-badge.active { background: #d4edda; color: #155724; }
        .student-badge.inactive { background: #e2e3e5; color: #383d41; }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# Cache & Retry
# =============================================================================
def init_data_cache():
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
    if 'data_dirty' not in st.session_state:
        st.session_state.data_dirty = {}


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
# Database Class
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
        if not isinstance(columns, list) or not columns:
            raise ValueError("columns must be a non-empty list")
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

    # --- Users ---
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

    # --- Stages ---
    STAGE_COLUMNS = ["stage_id", "stage_name", "description", "display_order",
                     "status", "created_date", "created_by", "manager_user_id", "notes"]

    def get_stages(self):
        return self._sheet_to_df("Stages")

    def add_stage(self, stage_data):
        df = self.get_stages()
        if df.empty:
            df = pd.DataFrame(columns=self.STAGE_COLUMNS)
        new_row = {
            "stage_id": stage_data["stage_id"],
            "stage_name": stage_data.get("stage_name", ""),
            "description": stage_data.get("description", ""),
            "display_order": stage_data.get("display_order", ""),
            "status": stage_data.get("status", "active"),
            "created_date": stage_data.get("created_date", get_cairo_now().strftime("%Y-%m-%d")),
            "created_by": stage_data.get("created_by", ""),
            "manager_user_id": stage_data.get("manager_user_id", ""),
            "notes": stage_data.get("notes", "")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("Stages", df, self.STAGE_COLUMNS)

    def update_stage(self, stage_id, updates):
        df = self.get_stages()
        idx = df[df.stage_id == stage_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Stages", df, self.STAGE_COLUMNS)

    def delete_stage(self, stage_id):
        df = self.get_stages()
        df = df[df["stage_id"] != stage_id]
        self._df_to_sheet("Stages", df, self.STAGE_COLUMNS)

    # --- StageSupervisors (Many-to-Many) ---
    STAGE_SUPERVISOR_COLUMNS = ["assignment_id", "stage_id", "supervisor_id", "assigned_date"]

    def get_stage_supervisors(self):
        return self._sheet_to_df("StageSupervisors")

    def get_supervisors_for_stage(self, stage_id):
        df = self.get_stage_supervisors()
        if df.empty:
            return []
        assignments = df[df["stage_id"] == stage_id]
        if assignments.empty:
            return []
        return assignments["supervisor_id"].tolist()

    def get_supervisor_names_for_stage(self, stage_id, users_df=None):
        sup_ids = self.get_supervisors_for_stage(stage_id)
        if not sup_ids:
            return []
        if users_df is None or users_df.empty:
            return sup_ids
        names = []
        for sid in sup_ids:
            match = users_df[users_df["user_id"] == sid]
            if not match.empty:
                names.append(match.iloc[0].get("full_name", sid))
            else:
                names.append(sid)
        return names

    def add_stage_supervisor(self, stage_id, supervisor_id):
        df = self.get_stage_supervisors()
        if df.empty:
            df = pd.DataFrame(columns=self.STAGE_SUPERVISOR_COLUMNS)
        duplicate = df[(df["stage_id"] == stage_id) & (df["supervisor_id"] == supervisor_id)]
        if not duplicate.empty:
            return False
        new_row = {
            "assignment_id": str(uuid.uuid4()),
            "stage_id": stage_id,
            "supervisor_id": supervisor_id,
            "assigned_date": get_cairo_now().strftime("%Y-%m-%d")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("StageSupervisors", df, self.STAGE_SUPERVISOR_COLUMNS)
        return True

    def remove_stage_supervisor(self, stage_id, supervisor_id):
        df = self.get_stage_supervisors()
        if df.empty:
            return
        df = df[~((df["stage_id"] == stage_id) & (df["supervisor_id"] == supervisor_id))]
        self._df_to_sheet("StageSupervisors", df, self.STAGE_SUPERVISOR_COLUMNS)

    def clear_stage_supervisors(self, stage_id):
        df = self.get_stage_supervisors()
        if df.empty:
            return
        df = df[df["stage_id"] != stage_id]
        self._df_to_sheet("StageSupervisors", df, self.STAGE_SUPERVISOR_COLUMNS)

    def migrate_single_supervisors(self):
        stages = self.get_stages()
        if stages.empty or "manager_user_id" not in stages.columns:
            return 0
        existing_assignments = self.get_stage_supervisors()
        migrated = 0
        for _, row in stages.iterrows():
            stage_id = row.get("stage_id", "")
            mgr_id = row.get("manager_user_id", "")
            if not stage_id or not mgr_id:
                continue
            if existing_assignments.empty or (
                existing_assignments[(existing_assignments["stage_id"] == stage_id) &
                                     (existing_assignments["supervisor_id"] == mgr_id)].empty
            ):
                self.add_stage_supervisor(stage_id, mgr_id)
                migrated += 1
        return migrated

    def get_stages_for_supervisor(self, supervisor_id):
        df = self.get_stage_supervisors()
        if df.empty:
            return []
        assignments = df[df["supervisor_id"] == supervisor_id]
        if assignments.empty:
            return []
        return assignments["stage_id"].tolist()

    # --- SectionTeachers (Many-to-Many) ---
    SECTION_TEACHER_COLUMNS = ["assignment_id", "section_id", "teacher_id", "assigned_date"]

    def get_section_teachers(self):
        return self._sheet_to_df("SectionTeachers")

    def get_teachers_for_section(self, section_id):
        df = self.get_section_teachers()
        if df.empty:
            return []
        assignments = df[df["section_id"] == section_id]
        if assignments.empty:
            return []
        return assignments["teacher_id"].tolist()

    def get_teacher_names_for_section(self, section_id, users_df=None):
        t_ids = self.get_teachers_for_section(section_id)
        if not t_ids:
            return []
        if users_df is None or users_df.empty:
            return t_ids
        names = []
        for tid in t_ids:
            match = users_df[users_df["user_id"] == tid]
            if not match.empty:
                names.append(match.iloc[0].get("full_name", tid))
            else:
                names.append(tid)
        return names

    def add_section_teacher(self, section_id, teacher_id):
        df = self.get_section_teachers()
        if df.empty:
            df = pd.DataFrame(columns=self.SECTION_TEACHER_COLUMNS)
        duplicate = df[(df["section_id"] == section_id) & (df["teacher_id"] == teacher_id)]
        if not duplicate.empty:
            return False
        new_row = {
            "assignment_id": str(uuid.uuid4()),
            "section_id": section_id,
            "teacher_id": teacher_id,
            "assigned_date": get_cairo_now().strftime("%Y-%m-%d")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("SectionTeachers", df, self.SECTION_TEACHER_COLUMNS)
        return True

    def remove_section_teacher(self, section_id, teacher_id):
        df = self.get_section_teachers()
        if df.empty:
            return
        df = df[~((df["section_id"] == section_id) & (df["teacher_id"] == teacher_id))]
        self._df_to_sheet("SectionTeachers", df, self.SECTION_TEACHER_COLUMNS)

    def clear_section_teachers(self, section_id):
        df = self.get_section_teachers()
        if df.empty:
            return
        df = df[df["section_id"] != section_id]
        self._df_to_sheet("SectionTeachers", df, self.SECTION_TEACHER_COLUMNS)

    # --- Sections ---
    SECTION_COLUMNS = ["section_id", "section_name", "stage_id", "teacher_id", "leader_id",
                       "max_students", "room", "meeting_day", "meeting_time",
                       "status", "notes", "manager_user_id"]

    def get_sections(self):
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data):
        self._get_or_create_worksheet("Sections", self.SECTION_COLUMNS)
        df = self.get_sections()
        if df.empty:
            df = pd.DataFrame(columns=self.SECTION_COLUMNS)
        new_row = {
            "section_id": sec_data["section_id"],
            "section_name": sec_data.get("section_name", ""),
            "stage_id": sec_data.get("stage_id", ""),
            "teacher_id": sec_data.get("teacher_id", ""),
            "leader_id": sec_data.get("leader_id", ""),
            "max_students": sec_data.get("max_students", ""),
            "room": sec_data.get("room", ""),
            "meeting_day": sec_data.get("meeting_day", ""),
            "meeting_time": sec_data.get("meeting_time", ""),
            "status": sec_data.get("status", "active"),
            "notes": sec_data.get("notes", ""),
            "manager_user_id": sec_data.get("manager_user_id", "")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("Sections", df, self.SECTION_COLUMNS)

    def update_section(self, section_id, updates):
        df = self.get_sections()
        idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, self.SECTION_COLUMNS)

    def delete_section(self, section_id):
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, self.SECTION_COLUMNS)

    def get_sections_by_stage(self, stage_id):
        df = self.get_sections()
        if df.empty:
            return pd.DataFrame()
        return df[df.stage_id == stage_id]

    def get_sections_by_teacher(self, teacher_id):
        df = self.get_sections()
        if df.empty:
            return pd.DataFrame()
        return df[df.teacher_id == teacher_id]

    def get_sections_by_leader(self, leader_id):
        df = self.get_sections()
        if df.empty:
            return pd.DataFrame()
        return df[df.leader_id == leader_id]

    def get_section_student_count(self, section_id):
        students = self.get_students()
        if students.empty:
            return 0
        return len(students[students.section_id == section_id])

    def move_students_to_section(self, student_ids, new_section_id):
        students = self.get_students()
        if students.empty:
            return
        for sid in student_ids:
            idx = students[students.student_id == sid].index
            if len(idx) > 0:
                students.at[idx[0], "section_id"] = new_section_id
        self._df_to_sheet("Students", students, ["student_id", "full_name", "section_id", "teacher_id",
                                                 "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])

    # --- Students ---
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

    # --- Attendance ---
    ATTENDANCE_COLUMNS = ["record_id", "date", "time", "user_id", "name", "role", "section_id", "stage_id", "status", "notes", "recorded_by", "attendance_method"]

    def get_attendance(self):
        return self._sheet_to_df("Attendance")

    def batch_add_attendance(self, records_list):
        if not records_list:
            return
        df = self.get_attendance()
        if df.empty:
            df = pd.DataFrame(columns=self.ATTENDANCE_COLUMNS)
        existing_ids = set(df["record_id"].tolist()) if not df.empty else set()
        new_records = []
        for rec in records_list:
            if rec.get("record_id") in existing_ids:
                idx = df[df.record_id == rec["record_id"]].index[0]
                for k, v in rec.items():
                    if k in df.columns:
                        df.at[idx, k] = self._safe_str(v)
            else:
                new_records.append(rec)
        if new_records:
            new_df = pd.DataFrame(new_records)
            df = pd.concat([df, new_df], ignore_index=True)
        self._df_to_sheet("Attendance", df, self.ATTENDANCE_COLUMNS)

    def get_attendance_by_date_user(self, date_str, user_id):
        df = self.get_attendance()
        if df.empty:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.user_id == user_id)]

    def get_attendance_by_date_section(self, date_str, section_id):
        df = self.get_attendance()
        if df.empty:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    def delete_attendance_record(self, record_id):
        df = self.get_attendance()
        df = df[df.record_id != record_id]
        self._df_to_sheet("Attendance", df, self.ATTENDANCE_COLUMNS)

    # --- FollowUp ---
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

    # --- Quizzes ---
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

    # --- Quiz Results ---
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

    # --- Logs ---
    def get_logs(self):
        return self._sheet_to_df("Logs")

    def add_log(self, user_id, action, details=""):
        log = {
            "log_id": str(uuid.uuid4()), "timestamp": get_cairo_now().isoformat(),
            "user_id": user_id, "action": action, "details": details
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

    # --- Events ---
    EVENT_COLUMNS = ["event_id", "event_name", "event_type", "event_date", "event_time",
                     "location", "max_capacity", "description", "created_by", "status"]

    def get_events(self):
        return self._sheet_to_df("Events")

    def add_event(self, event_data):
        df = self.get_events()
        if df.empty:
            df = pd.DataFrame(columns=self.EVENT_COLUMNS)
        df = pd.concat([df, pd.DataFrame([event_data])], ignore_index=True)
        self._df_to_sheet("Events", df, self.EVENT_COLUMNS)

    def update_event(self, event_id, updates):
        df = self.get_events()
        idx = df[df.event_id == event_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Events", df, self.EVENT_COLUMNS)

    def delete_event(self, event_id):
        df = self.get_events()
        df = df[df.event_id != event_id]
        self._df_to_sheet("Events", df, self.EVENT_COLUMNS)

    # --- EventRSVP ---
    EVENT_RSVP_COLUMNS = ["rsvp_id", "event_id", "student_id", "student_name", "rsvp_status", "rsvp_date"]

    def get_event_rsvps(self, event_id=None):
        df = self._sheet_to_df("EventRSVP")
        if df.empty or not event_id:
            return df
        return df[df.event_id == event_id]

    def add_event_rsvp(self, rsvp_data):
        df = self.get_event_rsvps()
        if df.empty:
            df = pd.DataFrame(columns=self.EVENT_RSVP_COLUMNS)
        df = pd.concat([df, pd.DataFrame([rsvp_data])], ignore_index=True)
        self._df_to_sheet("EventRSVP", df, self.EVENT_RSVP_COLUMNS)

    def delete_event_rsvp(self, rsvp_id):
        df = self._sheet_to_df("EventRSVP")
        df = df[df.rsvp_id != rsvp_id]
        self._df_to_sheet("EventRSVP", df, self.EVENT_RSVP_COLUMNS)

    # --- EventAttendance ---
    EVENT_ATTENDANCE_COLUMNS = ["record_id", "event_id", "student_id", "status", "notes"]

    def get_event_attendance(self, event_id=None):
        df = self._sheet_to_df("EventAttendance")
        if df.empty or not event_id:
            return df
        return df[df.event_id == event_id]

    def add_event_attendance(self, attendance_data):
        df = self.get_event_attendance()
        if df.empty:
            df = pd.DataFrame(columns=self.EVENT_ATTENDANCE_COLUMNS)
        df = pd.concat([df, pd.DataFrame([attendance_data])], ignore_index=True)
        self._df_to_sheet("EventAttendance", df, self.EVENT_ATTENDANCE_COLUMNS)

    def delete_event_attendance(self, record_id):
        df = self._sheet_to_df("EventAttendance")
        df = df[df.record_id != record_id]
        self._df_to_sheet("EventAttendance", df, self.EVENT_ATTENDANCE_COLUMNS)


# =============================================================================
# JWT & Session Helpers
# =============================================================================
def generate_token(user: dict, secret: str) -> str:
    payload = {
        "user_id": user.get("user_id", ""), "role": user.get("role", ""),
        "full_name": user.get("full_name", ""), "section_id": user.get("section_id", ""),
        "status": user.get("status", "active"),
        "exp": datetime.utcnow() + timedelta(hours=SESSION_TIMEOUT_HOURS)
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def generate_quiz_token(quiz_id: str, student_id: str) -> str:
    payload = {"quiz_id": quiz_id, "student_id": student_id, "exp": datetime.utcnow() + timedelta(hours=48)}
    return jwt.encode(payload, QUIZ_JWT_SECRET, algorithm="HS256")


def verify_quiz_token(token: str):
    try:
        return jwt.decode(token, QUIZ_JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def verify_token(token: str, secret: str):
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def init_session():
    defaults = {
        "authenticated": False, "user": None, "token": None, "last_login_time": None,
        "student_quiz": None, "student_quiz_started": False, "quiz_phase": "enter_name",
        "student_name": "", "student_id": "", "quiz_start_time": None, "quiz_end_time": None,
        "quiz_submit_time": None, "quiz_token": None, "quiz_answers": {}, "quiz_submitted": False,
        "last_score": 0, "menu_choice": "🏠 لوحة التحكم", "show_sidebar": True,
        "open_help_dialog": False, "current_attempt_id": None, "last_saved_answers_str": "",
        "quiz_questions": None, "show_review": False, "data_errors": [], "data_validated": False,
        "quiz_load_failures": 0
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def logout(db=None):
    if db and st.session_state.user:
        try:
            db.add_log(st.session_state.user.get("user_id", ""), "تسجيل خروج", "تم تسجيل الخروج بنجاح")
        except Exception:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def send_telegram_message(message: str) -> bool:
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
    except Exception:
        return False


# =============================================================================
# مركز المساعدة
# =============================================================================
@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    hdr_col1, hdr_col2 = st.columns([0.85, 0.15])
    with hdr_col1:
        st.markdown("<h3 style='text-align:center; color:#667eea; margin:0; padding-top:0.5rem;'>📬 تواصل معنا</h3>", unsafe_allow_html=True)
    with hdr_col2:
        if st.button("✕ إغلاق", key="help_dialog_close_btn", use_container_width=True):
            st.session_state.open_help_dialog = False
            st.rerun()
    contact_name, contact_whatsapp = get_support_config()
    if contact_whatsapp:
        st.info(f"📞 للدعم المباشر: {contact_name} - {contact_whatsapp}")
    st.markdown("---")
    with st.form("help_form_enhanced", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("الاسم *", placeholder="أدخل اسمك الكامل")
            whatsapp = st.text_input("رقم الواتساب *", placeholder="01xxxxxxxxx")
        with col2:
            issue_type = st.selectbox("نوع المشكلة *", ["مشكلة تقنية", "مشكلة في البيانات", "طلب مساعدة", "اقتراح تحسين", "أخرى"])
            urgency = st.selectbox("الأولوية", ["عادي", "مستعجل", "طارئ جداً"], index=0)
        issue_desc = st.text_area("وصف المشكلة أو الطلب *", placeholder="اشرح المشكلة بالتفصيل...", height=150)
        uploaded_file = st.file_uploader("📎 إرفاق لقطة شاشة (اختياري)", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("🚀 إرسال الطلب", use_container_width=True)
        if submitted:
            if not name or not whatsapp or not issue_desc:
                st.error("⚠️ الرجاء ملء جميع الحقول المطلوبة")
            else:
                urgency_icon = {"عادي": "ℹ️", "مستعجل": "⚠️", "طارئ جداً": "🔴"}
                message = (
                    f"{urgency_icon.get(urgency, '')} بلاغ جديد من مركز المساعدة\n"
                    f"👤 الاسم: {name}\n📱 الواتساب: {whatsapp}\n📂 النوع: {issue_type}\n⚡ الأولوية: {urgency}\n📝 التفاصيل: {issue_desc}"
                )
                success = True
                if uploaded_file is not None:
                    if not send_telegram_photo(message, uploaded_file.getvalue(), uploaded_file.name):
                        success = False
                else:
                    if not send_telegram_message(message):
                        success = False
                if success:
                    st.success("✅ تم إرسال طلبك بنجاح! سنتواصل معك قريباً.")
                    st.balloons()
                else:
                    st.error("❌ فشل الإرسال، يرجى المحاولة لاحقاً أو التواصل مباشرة via الواتساب.")


# =============================================================================
# RBAC
# =============================================================================
VALID_ROLES = ["System Admin", "Father Account", "Service Manager", "Teacher", "Student"]
VALID_STATUSES = ["active", "inactive", "suspended"]
EVENT_TYPES = ["اجتماع", "خدمة", "رحلة", "احتفال"]
RSVP_STATUSES = ["سأحضر", "لن أحضر", "ربما"]

def require_role(required_roles):
    user = st.session_state.get("user")
    if not user:
        return False
    return user.get("role", "") in required_roles

def check_access(required_roles):
    if not require_role(required_roles):
        st.error("🚫 لا تملك الصلاحية للوصول إلى هذه الصفحة")
        st.stop()

def get_user_status(user_row):
    status = user_row.get("status", "active")
    if pd.isna(status) or str(status).strip() == "":
        return "active"
    return str(status).strip().lower()


# =============================================================================
# Helper Functions
# =============================================================================
def get_role_menu(role):
    menus = {
        "System Admin": [
            "🏠 لوحة التحكم", "👥 إدارة الأعضاء", "🏫 إدارة المراحل الدراسية", "📚 إدارة الفصول",
            "📋 الحضور", "💬 الافتقاد",
            "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات",
            "📅 إدارة الفعاليات", "📜 سجل العمليات", "🔒 تغيير كلمة المرور"
        ],
        "Father Account": ["🏠 لوحة التحكم", "👥 إدارة الأعضاء", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
    "Service Manager": [
        "🏠 لوحة التحكم", "👥 إدارة الأعضاء", "📋 الحضور", "💬 الافتقاد",
        "🏆 درجات المسابقات", "📝 المسابقات والاختبارات", "📅 إدارة الفعاليات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"
    ],
        "Teacher": [
            "🏠 لوحة التحكم", "👥 إدارة الأعضاء", "📋 الحضور", "💬 الافتقاد",
            "🏆 درجات المسابقات", "📅 إدارة الفعاليات", "🔒 تغيير كلمة المرور"
        ],
        "Student": ["🏠 لوحة التحكم", "📝 المسابقات والاختبارات", "📅 إدارة الفعاليات", "🔒 تغيير كلمة المرور"]
    }
    return menus.get(role, [])


def get_sections_for_supervisor(db, user_id):
    stage_ids = db.get_stages_for_supervisor(user_id)
    if not stage_ids:
        return []
    sections = db.get_sections()
    if sections.empty:
        return []
    section_ids = sections[sections.stage_id.isin(stage_ids)]["section_id"].tolist()
    return section_ids


def filter_students_by_role(students, role, section_id, db=None, user_id=None):
    if role == "Teacher" and section_id:
        return students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    elif role == "Service Manager":
        if db and user_id:
            section_ids = get_sections_for_supervisor(db, user_id)
            if section_ids and not students.empty and "section_id" in students.columns:
                return students[students.section_id.isin(section_ids)]
        return students
    else:
        return students


def filter_attendance_by_role(attendance, role, section_id, db=None, user_id=None):
    if role == "Teacher" and section_id:
        return attendance[attendance.section_id == section_id] if not attendance.empty and "section_id" in attendance.columns else pd.DataFrame()
    elif role == "Service Manager":
        if db and user_id:
            section_ids = get_sections_for_supervisor(db, user_id)
            if section_ids and not attendance.empty and "section_id" in attendance.columns:
                return attendance[attendance.section_id.isin(section_ids)]
        return attendance
    return attendance


def clear_quiz_session_keys():
    quiz_keys = [
        "student_quiz", "student_quiz_started", "quiz_phase", "student_name",
        "student_id", "quiz_start_time", "quiz_end_time", "quiz_submit_time",
        "quiz_token", "quiz_answers", "quiz_submitted", "last_score",
        "current_attempt_id", "last_saved_answers_str", "quiz_questions", "show_review"
    ]
    for key in quiz_keys:
        if key in st.session_state:
            del st.session_state[key]


# =============================================================================
# Validation
# =============================================================================
def validate_data_integrity(db):
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


def auto_fix_missing_sections(db):
    students = db.get_students()
    sections = db.get_sections()
    if students.empty:
        return False
    existing_ids = set(sections["section_id"].tolist()) if not sections.empty else set()
    student_section_ids = students["section_id"].dropna().unique().tolist()
    missing = [sid for sid in student_section_ids if sid and str(sid).strip() not in existing_ids]
    if missing:
        for sid in missing:
            db.add_section({"section_id": str(sid), "section_name": f"فصل (معرف {sid[:8]})"})
        return True
    return False


# =============================================================================
# Initialization & Login
# =============================================================================
def show_initialization(db):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", use_container_width=True, key="init_admin_btn"):
            admin_data = {
                "user_id": "admin-001", "username": "admin", "password": "admin123",
                "role": "System Admin", "full_name": "مدير النظام",
                "section_id": "", "phone": "0100000000", "email": "admin@church.com"
            }
            admin_data["password"] = hash_password(admin_data["password"])
            db.add_user(admin_data)
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.info("**اسم المستخدم:** `admin`\n\n**كلمة المرور:** `admin123`")
            time.sleep(2)
            st.rerun()
        st.stop()


def show_login_page(db, jwt_secret):
    st.markdown("<h1 class='main-header'>⛪ <br>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
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
                    with st.spinner("جاري التحقق..."):
                        users = db.get_users()
                        user_row = users[users.username == username]
                        if user_row.empty:
                            st.error("اسم المستخدم غير موجود")
                        else:
                            user = user_row.iloc[0].to_dict()
                            user_status = get_user_status(user)
                            if user_status != "active":
                                db.add_log(user.get("user_id", ""), "محاولة دخول فاشلة", f"الحساب غير نشط (الحالة: {user_status})")
                                st.error(f"🚫 هذا الحساب {user_status}. يرجى التواصل مع مسؤول النظام.")
                            elif verify_password(password, user.get("password", "")):
                                token = generate_token(user, jwt_secret)
                                st.session_state.token = token
                                st.session_state.user = user
                                st.session_state.authenticated = True
                                st.session_state.last_login_time = get_cairo_now().isoformat()
                                st.session_state.menu_choice = "🏠 لوحة التحكم"
                                st.session_state.show_sidebar = True
                                db.add_log(user["user_id"], "تسجيل دخول", "تم تسجيل الدخول بنجاح")
                                st.success("تم تسجيل الدخول بنجاح!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                db.add_log(user.get("user_id", ""), "محاولة دخول فاشلة", "كلمة مرور خاطئة")
                                st.error("كلمة المرور غير صحيحة")
    with tab2:
        st.subheader("دخول الاختبار الإلكتروني")
        with st.form("student_login_form"):
            code = st.text_input("كود الاختبار", placeholder="مثال: GEN123").strip()
            passwd = st.text_input("كلمة مرور الاختبار", type="password", placeholder="مثال: QUIZ99").strip()
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
                                expiry_naive = pd.to_datetime(quiz.get("expiry_date", "")).to_pydatetime()
                                expiry = expiry_naive.replace(tzinfo=CAIRO_TZ)
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
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")


# =============================================================================
# Student Quiz Interface
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
    score = round((correct_count / num_q) * 20, 1) if num_q > 0 else 0
    return score


def save_current_answers(db):
    if not st.session_state.current_attempt_id:
        return
    current_answers = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
    if current_answers != st.session_state.last_saved_answers_str:
        db.save_answers(st.session_state.current_attempt_id, st.session_state.quiz_answers)
        st.session_state.last_saved_answers_str = current_answers


def show_student_quiz(db):
    if st.session_state.quiz_phase in ["taking_quiz", "finished"]:
        if not st.session_state.get("quiz_token"):
            st.error("انتهت جلسة الاختبار. يرجى إعادة الدخول.")
            clear_quiz_session_keys()
            st.stop()
        token_data = verify_quiz_token(st.session_state.quiz_token)
        if token_data is None:
            st.error("انتهت صلاحية جلسة الاختبار. يرجى إعادة الدخول.")
            clear_quiz_session_keys()
            st.stop()

    quiz = st.session_state.student_quiz
    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz.get('title', '')}")
        st.markdown(f"**عدد الأسئلة:** {quiz.get('num_questions', '')} | **الدرجة الكلية:** 20 | **الوقت:** {quiz.get('time_limit_minutes', '')} دقيقة")
        st.markdown("---")
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
        if selected_id is not None:
            student_row = active_students[active_students.student_id == selected_id].iloc[0]
            sec_id = student_row.get("section_id", "")
            sections_df = db.get_sections()
            section_name = ""
            if not sections_df.empty and sec_id:
                sec_name = sections_df[sections_df.section_id == sec_id]["section_name"].values
                section_name = sec_name[0] if len(sec_name) > 0 else "لم يتم تعيين فصل"
            else:
                section_name = "لم يتم تعيين فصل"
            st.info(f"أنتِ في فصل: **{section_name}**")
        st.markdown("---")
        st.info("إذا لم تجد اسمك في القائمة، يرجى التواصل مع مشرف الخدمة لإضافتك.")
        if selected_id is not None:
            existing = db.get_quiz_results(quiz.get("quiz_id"))
            if not existing.empty:
                student_attempts = existing[existing["student_id"] == selected_id]
                if not student_attempts.empty:
                    attempt = student_attempts.iloc[0]
                    if attempt.get("status") == "started":
                        answers_str = attempt.get("answers", "{}")
                        try:
                            saved_answers = json.loads(answers_str) if answers_str else {}
                        except Exception:
                            saved_answers = {}
                        score = grade_attempt(db, quiz["quiz_id"], saved_answers)
                        db.submit_quiz_attempt(attempt["result_id"], score, json.dumps(saved_answers, ensure_ascii=False))
                        st.warning("تم تسليم محاولتك السابقة تلقائياً بناءً على ما قمت بحفظه.")
                        st.session_state.last_score = score
                        st.session_state.quiz_submit_time = get_cairo_now()
                        st.session_state.quiz_phase = "finished"
                        st.session_state.quiz_submitted = True
                        st.session_state.quiz_token = generate_quiz_token(quiz["quiz_id"], selected_id)
                        st.rerun()
                    else:
                        st.error("لقد قمت بتسليم هذا الاختبار بالفعل. لا يمكنك الدخول مرة أخرى.")
                        st.stop()
        if st.button("بدء الاختبار", use_container_width=True, disabled=(selected_id is None), key="start_quiz_btn"):
            selected_student = active_students[active_students["student_id"] == selected_id].iloc[0].to_dict()
            st.session_state.student_name = selected_student["full_name"]
            st.session_state.student_id = selected_id
            st.session_state.quiz_start_time = get_cairo_now()
            time_limit_seconds = int(quiz.get('time_limit_minutes', 15)) * 60
            st.session_state.quiz_end_time = st.session_state.quiz_start_time + timedelta(seconds=time_limit_seconds)
            attempt_id = db.start_quiz_attempt(quiz["quiz_id"], selected_id, st.session_state.student_name)
            st.session_state.current_attempt_id = attempt_id
            st.session_state.quiz_answers = {}
            st.session_state.last_saved_answers_str = ""
            st.session_state.quiz_questions = None
            st.session_state.show_review = False
            st.session_state.quiz_load_failures = 0
            st.session_state.quiz_token = generate_quiz_token(quiz["quiz_id"], selected_id)
            st.session_state.quiz_phase = "taking_quiz"
            st.rerun()
        return

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
            st.rerun()

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

        end_time_iso = st.session_state.quiz_end_time.isoformat()
        countdown_html = f"""
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><style>
        body {{ font-family: 'Cairo', sans-serif; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100%; background: transparent; }}
        #timer {{ font-size: 1.8rem; font-weight: bold; padding: 1rem 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; box-shadow: 0 4px 12px rgba(102,126,234,0.4); text-align: center; }}
        </style></head><body>
        <div id="timer">⏳ الوقت المتبقي: <span id="time"></span></div>
        <script>
        var endTime = new Date("{end_time_iso}").getTime();
        function update() {{ var now = new Date().getTime(); var dist = endTime - now;
            if (dist <= 0) {{ document.getElementById('time').innerHTML = "00:00"; parent.postMessage({{type: "QUIZ_TIME_UP"}}, "*"); clearInterval(intervalId); return; }}
            var mins = Math.floor((dist % (1000*60*60)) / (1000*60)); var secs = Math.floor((dist % (1000*60)) / 1000);
            document.getElementById('time').innerHTML = (mins<10?'0'+mins:mins) + ":" + (secs<10?'0'+secs:secs); }}
        update(); var intervalId = setInterval(update, 1000);
        </script></body></html>
        """
        st.components.v1.html(countdown_html, height=80, scrolling=False)
        st.title(f"📝 {quiz.get('title', '')}")
        st.markdown(f"الطالبة: **{st.session_state.student_name}** | الدرجة الكلية: 20")
        st.markdown("---")
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
            st.rerun()
        return

    elif st.session_state.quiz_phase == "finished":
        if not st.session_state.get("show_review", False):
            st.success("تم تسليم الاختبار بنجاح!")
            score = st.session_state.last_score
            score_display = int(score) if score.is_integer() else score
            st.info(f"نتيجتك: {score_display}/20")
            st.markdown("---")
            st.markdown("#### ⏱️ معلومات الوقت")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.write("**بداية الامتحان:**")
                st.write(format_cairo_time(st.session_state.quiz_start_time))
            with col_t2:
                st.write("**نهاية الامتحان (التسليم):**")
                st.write(format_cairo_time(st.session_state.quiz_submit_time))
            col_btn, _ = st.columns([2, 3])
            if col_btn.button("عرض الإجابات والأخطاء", use_container_width=True, key="show_review_btn"):
                st.session_state.show_review = True
                st.rerun()
            if st.button("إنهاء والعودة إلى الرئيسية", use_container_width=True, key="finish_no_review_btn"):
                clear_quiz_session_keys()
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
                if st.button("إنهاء المراجعة والعودة إلى الرئيسية", use_container_width=True, key="finish_review_btn"):
                    clear_quiz_session_keys()
                    st.rerun()
        return


# =============================================================================
# Sidebar Navigation
# =============================================================================
def show_sidebar_navigation(db):
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.user
        st.markdown(f"**👤 {user.get('full_name', '')}**")
        st.caption(f"الصلاحية: {user.get('role', '')}")
        st.divider()
        role = user.get("role", "")
        menu_items = get_role_menu(role)
        if not menu_items:
            st.warning("صلاحية غير معروفة")
            return None
        current_choice = st.session_state.get("menu_choice", menu_items[0])
        if current_choice not in menu_items:
            current_choice = menu_items[0]
            st.session_state.menu_choice = current_choice
        if st.button("✕ إخفاء القائمة", key="hide_sidebar_btn", use_container_width=True):
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
        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout_btn"):
            logout(db)
    return current_choice


# =============================================================================
# Dashboard
# =============================================================================
def show_dashboard(db):
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
    if role in ["System Admin", "Service Manager"] and st.session_state.get("data_errors"):
        with st.expander("⚠️ تنبيهات هامة - أخطاء في البيانات", expanded=True):
            for err in st.session_state.data_errors:
                st.warning(err)
            if st.button("🔧 إصلاح تلقائي (إنشاء الفصول الناقصة)", key="auto_fix_btn"):
                if auto_fix_missing_sections(db):
                    st.session_state.data_errors = validate_data_integrity(db)
                    st.success("تم إنشاء الفصول الناقصة. سيتم تحديث الصفحة...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("لا توجد فصول ناقصة لإصلاحها.")
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()
    if role in ["Teacher", "Service Manager"] and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
        if not attendance.empty and "section_id" in attendance.columns:
            attendance = attendance[attendance.section_id == section_id]
        if not followup.empty and not students.empty and "student_id" in followup.columns and "student_id" in students.columns:
            followup = followup[followup.student_id.isin(students["student_id"])]
    if not attendance.empty and "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    total_students = len(students)
    today_str = get_cairo_now().strftime("%Y-%m-%d")
    present_today = len(attendance[(attendance.date == today_str) & (attendance.status == "حاضر")]) if not attendance.empty and "status" in attendance.columns else 0
    absent_today = len(attendance[(attendance.date == today_str) & (attendance.status == "غائب")]) if not attendance.empty and "status" in attendance.columns else 0
    need_follow = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty and "regularity_status" in followup.columns else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("عدد الطالبات", total_students)
    col2.metric("الحضور اليوم", present_today)
    col3.metric("الغياب اليوم", absent_today)
    col4.metric("منقطعات", need_follow)
    st.markdown("#### 📈 الحضور الأسبوعي")
    if not attendance.empty and "date" in attendance.columns and "status" in attendance.columns:
        last_week = get_cairo_now().replace(tzinfo=None) - timedelta(days=7)
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
    if not attendance.empty and "date" in attendance.columns and "status" in attendance.columns:
        month_start = get_cairo_now().replace(day=1).strftime("%Y-%m-%d")
        month_att = attendance[(attendance.date >= month_start) & (attendance.status == "غائب")]
        if not month_att.empty:
            absent_counts = month_att.groupby("student_id").size().reset_index(name="أيام الغياب")
            absent_counts = absent_counts.sort_values("أيام الغياب", ascending=False).head(5)
            if not students.empty and "student_id" in students.columns and "full_name" in students.columns:
                absent_counts = absent_counts.merge(students[["student_id", "full_name"]], on="student_id", how="left")
            st.dataframe(absent_counts[["full_name", "أيام الغياب"]], use_container_width=True)
        else:
            st.info("لا يوجد غياب هذا الشهر.")
    st.markdown("#### 🔔 بنات بحاجة لافتقاد عاجل")
    urgent = followup[followup.regularity_status.isin(["منقطع", "متقطع"])] if not followup.empty and "regularity_status" in followup.columns else pd.DataFrame()
    if not urgent.empty:
        if not students.empty and "student_id" in students.columns and "full_name" in students.columns:
            urgent = urgent.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(urgent[["full_name", "followup_date", "notes"]], use_container_width=True)
    else:
        st.info("كل البنات منتظمات.")
    if role in ["System Admin", "Father Account", "Service Manager"]:
        st.markdown("---")
        st.subheader("🏆 أفضل فصل درجات في المسابقات")
        results = db.get_quiz_results()
        students_all = db.get_students()
        sections_all = db.get_sections()
        if not results.empty and "status" in results.columns and not students_all.empty and not sections_all.empty:
            submitted = results[results.status == "submitted"]
            if not submitted.empty:
                merged = submitted.merge(students_all[["student_id", "section_id"]], on="student_id", how="left")
                merged["score"] = pd.to_numeric(merged["score"], errors="coerce").fillna(0)
                if "section_id" in merged.columns:
                    section_scores = merged.groupby("section_id")["score"].mean().reset_index()
                    section_scores = section_scores.merge(sections_all[["section_id", "section_name"]], on="section_id", how="left")
                    if not section_scores.empty:
                        top_section = section_scores.sort_values("score", ascending=False).iloc[0]
                        st.metric(f"أفضل فصل: {top_section.get('section_name', '')}", f"{top_section.get('score', 0):.1f} / 20 متوسط")
                        st.dataframe(section_scores.rename(columns={"section_name": "الفصل", "score": "متوسط الدرجات"}).set_index("الفصل"), use_container_width=True)


# =============================================================================
# Members Cards Page (Unified)
# =============================================================================
def show_members_cards_page(db):
    inject_user_cards_css()
    st.markdown("<h2 class='main-header'>👥 إدارة الأعضاء</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")
    section_id = user.get("section_id", "")

    if role not in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
        st.error("🚫 غير مصرح")
        return

    users = db.get_users()
    students = db.get_students()
    sections = db.get_sections()

    # Build unified members list (exclude System Admin and Father Account)
    members = []
    if not users.empty:
        for _, u in users.iterrows():
            u_role = u.get("role", "")
            if u_role in ["System Admin", "Father Account"]:
                continue
            # Teacher cannot see other teachers
            if role == "Teacher" and u_role == "Teacher" and u.get("user_id", "") != user_id:
                continue
            members.append({
                "member_id": u.get("user_id", ""),
                "full_name": u.get("full_name", ""),
                "role": u_role,
                "section_id": u.get("section_id", ""),
                "phone": u.get("phone", ""),
                "email": u.get("email", ""),
                "status": u.get("status", "active"),
                "type": "user",
                "created_by": u.get("created_by", "")
            })
    if not students.empty:
        for _, s in students.iterrows():
            # Teacher can only see students in their section
            if role == "Teacher" and section_id:
                if s.get("section_id", "") != section_id:
                    continue
            members.append({
                "member_id": s.get("student_id", ""),
                "full_name": s.get("full_name", ""),
                "role": "Student",
                "section_id": s.get("section_id", ""),
                "phone": s.get("phone", ""),
                "email": "",
                "status": s.get("status", "active"),
                "type": "student",
                "parent_phone": s.get("parent_phone", ""),
                "birthdate": s.get("birthdate", ""),
                "address": s.get("address", ""),
                "school": s.get("school", ""),
                "notes": s.get("notes", ""),
                "created_by": s.get("created_by", "")
            })

    members_df = pd.DataFrame(members) if members else pd.DataFrame(columns=["member_id", "full_name", "role", "section_id", "phone", "email", "status", "type"])

    # RBAC filtering based on stages for Service Manager
    if role == "Teacher" and user.get("section_id"):
        if not members_df.empty:
            members_df = members_df[members_df["section_id"] == user.get("section_id")]
    elif role == "Service Manager":
        section_ids = get_sections_for_supervisor(db, user_id)
        if section_ids and not members_df.empty:
            members_df = members_df[members_df["section_id"].isin(section_ids)]

    # Search
    search_term = st.text_input("🔍 بحث", placeholder="ابحث في الاسم والتليفون...", label_visibility="collapsed")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        role_options = ["الكل", "Student", "Service Manager", "Teacher"]
        role_filter = st.selectbox("نوع العضو", role_options)
    with col2:
        status_options = ["الكل", "active", "inactive"]
        status_filter = st.selectbox("الحالة", status_options)
    with col3:
        section_options = ["الكل"] + sections["section_id"].tolist() if not sections.empty else ["الكل"]
        section_filter = st.selectbox("الفصل", section_options, format_func=lambda x: "الكل" if x == "الكل" else sections[sections.section_id == x]["section_name"].values[0] if not sections.empty else x)

    filtered = members_df.copy()
    if search_term and not filtered.empty:
        mask = pd.Series(False, index=filtered.index)
        for col in ["full_name", "phone"]:
            if col in filtered.columns:
                mask |= filtered[col].astype(str).str.contains(search_term, na=False, case=False)
        filtered = filtered[mask]
    if role_filter != "الكل" and not filtered.empty and "role" in filtered.columns:
        filtered = filtered[filtered["role"] == role_filter]
    if status_filter != "الكل" and not filtered.empty and "status" in filtered.columns:
        filtered = filtered[filtered["status"] == status_filter]
    if section_filter != "الكل" and not filtered.empty and "section_id" in filtered.columns:
        filtered = filtered[filtered["section_id"] == section_filter]

    st.markdown(f"<p style='text-align:left; color:#666;'>عدد الأعضاء: {len(filtered)}</p>", unsafe_allow_html=True)

    if not filtered.empty:
        cols = st.columns(3)
        for idx, (_, m) in enumerate(filtered.iterrows()):
            col = cols[idx % 3]
            with col:
                mid = m.get("member_id", "")
                full_name = m.get("full_name", "غير معروف")
                member_role = m.get("role", "")
                sec_id = m.get("section_id", "")
                phone = m.get("phone", "")
                status = m.get("status", "active")
                member_type = m.get("type", "user")
                initials = get_initials(full_name)
                role_class = get_role_css_class(member_role)
                status_class = get_status_css_class(status)

                section_name = ""
                if not sections.empty and sec_id:
                    sec_match = sections[sections["section_id"] == sec_id]
                    if not sec_match.empty:
                        section_name = sec_match.iloc[0].get("section_name", "")

                role_label = {"Service Manager": "أمين خدمة", "Teacher": "مدرسة", "Student": "طالبة"}.get(member_role, member_role)
                status_label = {"active": "نشط", "inactive": "غير نشط"}.get(status, "نشط")

                if member_type == "student":
                    # Student card - show only name, phone, status, section
                    parent_phone = m.get("parent_phone", "")
                    birthdate = m.get("birthdate", "")
                    address = m.get("address", "")
                    school = m.get("school", "")
                    student_notes = m.get("notes", "")
                    
                    st.markdown(f"""
                    <div class='user-card' id='card-{mid}'>
                        <div class='card-badge {status_class}'>{status_label}</div>
                        <div style='display:flex; gap:1rem; align-items:center;'>
                            <div class='user-avatar'>{initials}</div>
                            <div>
                                <h3 style='margin:0;'>{full_name}</h3>
                                <span class='role-badge {role_class}'>{role_label}</span>
                                <span class='status-badge {status_class}'>{status_label}</span>
                            </div>
                        </div>
                        <div class='student-info-row' style='margin-top:0.8rem;'>
                            <span>📱 {phone if phone else '—'}</span>
                        </div>
                        <div class='student-info-row'>
                            <span>🏫 {section_name if section_name else '—'}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # User card - show name, phone, section
                    email = m.get("email", "")
                    st.markdown(f"""
                    <div class='user-card' id='card-{mid}'>
                        <div class='card-badge {status_class}'>{status_label}</div>
                        <div style='display:flex; gap:1rem; align-items:center;'>
                            <div class='user-avatar'>{initials}</div>
                            <div>
                                <h3 style='margin:0;'>{full_name}</h3>
                                <span class='role-badge {role_class}'>{role_label}</span>
                                <span class='status-badge {status_class}'>{status_label}</span>
                            </div>
                        </div>
                        <div class='student-info-row' style='margin-top:0.8rem;'>
                            <span>📱 {phone if phone else '—'}</span>
                        </div>
                        <div class='student-info-row'>
                            <span>🏫 {section_name if section_name else '—'}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # Action buttons
                action_cols = st.columns(5)
                with action_cols[0]:
                    if st.button("📋", key=f"view_{mid}"):
                        st.session_state.profile_user_id = mid
                        st.rerun()
                
                # Check if teacher can edit/delete
                can_edit_delete = True
                is_own_data = True
                if role == "Teacher":
                    if member_type == "student":
                        created_by = m.get("created_by", "")
                        is_own_data = (created_by == user_id)
                        can_edit_delete = is_own_data
                    else:
                        # Teacher cannot edit other teachers
                        can_edit_delete = False
                        st.warning("⛔ لا يمكنك التعديل على بيانات شخص آخر. هذه البيانات تخص مستخدم آخر.")
                
                if role == "System Admin" and can_edit_delete:
                    with action_cols[1]:
                        if status == "active":
                            if st.button("⏸️", key=f"deact_{mid}"):
                                if member_type == "student":
                                    db.update_student(mid, {"status": "inactive"})
                                else:
                                    db.update_user(mid, {"status": "inactive"})
                                db.add_log(user.get("user_id", ""), "تعطيل عضو", f"تم تعطيل {full_name}")
                                st.success("✅ تم التعطيل")
                                time.sleep(1)
                                st.rerun()
                        else:
                            if st.button("▶️", key=f"act_{mid}"):
                                if member_type == "student":
                                    db.update_student(mid, {"status": "active"})
                                else:
                                    db.update_user(mid, {"status": "active"})
                                db.add_log(user.get("user_id", ""), "تفعيل عضو", f"تم تفعيل {full_name}")
                                st.success("✅ تم التفعيل")
                                time.sleep(1)
                                st.rerun()
                    with action_cols[2]:
                        if st.button("✏️", key=f"edit_{mid}"):
                            st.session_state[f"edit_mode_{mid}"] = True
                    with action_cols[3]:
                        if st.button("🗑️", key=f"del_{mid}"):
                            confirm = st.checkbox(f"تأكيد الحذف؟", key=f"confirm_del_{mid}")
                            if confirm:
                                if member_type == "student":
                                    db.delete_student(mid)
                                else:
                                    db.delete_user(mid)
                                db.add_log(user.get("user_id", ""), "حذف عضو", f"تم حذف {full_name}")
                                st.success("✅ تم الحذف")
                                time.sleep(1)
                                st.rerun()
                elif role == "Teacher" and can_edit_delete and member_type == "student":
                    with action_cols[2]:
                        if st.button("✏️", key=f"edit_{mid}"):
                            st.session_state[f"edit_mode_{mid}"] = True
                    with action_cols[3]:
                        if st.button("🗑️", key=f"del_{mid}"):
                            confirm = st.checkbox(f"تأكيد الحذف؟", key=f"confirm_del_{mid}")
                            if confirm:
                                db.delete_student(mid)
                                db.add_log(user.get("user_id", ""), "حذف طالبة", f"تم حذف {full_name}")
                                st.success("✅ تم الحذف")
                                time.sleep(1)
                                st.rerun()

                # Edit form
                if st.session_state.get(f"edit_mode_{mid}", False):
                    with st.expander("✏️ تعديل البيانات", expanded=True):
                        with st.form(f"edit_member_form_{mid}"):
                            edit_name = st.text_input("الاسم الكامل*", value=full_name)
                            edit_phone = st.text_input("الهاتف", value=phone)
                            edit_email = st.text_input("البريد الإلكتروني", value=phone if member_role in ["Service Manager", "Teacher"] else "")
                            sec_options = sections["section_id"].tolist() if not sections.empty else []
                            current_sec = sec_id if sec_id in sec_options else (sec_options[0] if sec_options else "")
                            edit_section = st.selectbox("الفصل", sec_options, index=sec_options.index(current_sec) if current_sec in sec_options else 0, format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0]) if sec_options else ""
                            
                            # Student specific fields
                            edit_parent_phone = ""
                            edit_birthdate = None
                            edit_address = ""
                            edit_school = ""
                            edit_notes = ""
                            edit_status = "active"
                            if member_type == "student":
                                edit_parent_phone = st.text_input("رقم ولي الأمر", value=m.get("parent_phone", ""))
                                bd_value = pd.to_datetime(m.get("birthdate", "")).date() if m.get("birthdate") else None
                                edit_birthdate = st.date_input("تاريخ الميلاد", value=bd_value)
                                edit_address = st.text_input("العنوان", value=m.get("address", ""))
                                edit_school = st.text_input("المدرسة", value=m.get("school", ""))
                                edit_notes = st.text_area("ملاحظات", value=m.get("notes", ""))
                                edit_status = st.selectbox("الحالة", ["نشطة", "غير نشطة"], index=0 if m.get("status", "active") == "active" else 1)
                            
                            if st.form_submit_button("💾 حفظ"):
                                if member_type == "student":
                                    db.update_student(mid, {
                                        "full_name": edit_name,
                                        "phone": edit_phone,
                                        "section_id": edit_section,
                                        "parent_phone": edit_parent_phone,
                                        "birthdate": edit_birthdate.strftime("%Y-%m-%d") if edit_birthdate else "",
                                        "address": edit_address,
                                        "school": edit_school,
                                        "notes": edit_notes,
                                        "status": "active" if edit_status == "نشطة" else "inactive"
                                    })
                                else:
                                    db.update_user(mid, {"full_name": edit_name, "phone": edit_phone, "email": edit_email, "section_id": edit_section})
                                db.add_log(user.get("user_id", ""), "تعديل عضو", f"تم تعديل {edit_name}")
                                st.session_state[f"edit_mode_{mid}"] = False
                                st.success("✅ تم التحديث")
                                time.sleep(1)
                                st.rerun()
                st.markdown("---")

    # Add new member
    with st.expander("➕ إضافة عضو جديد"):
        with st.form("add_member_form"):
            member_type = st.selectbox("نوع العضو", ["طالبة", "أمين خدمة", "مدرسة"])
            new_name = st.text_input("الاسم الكامل*")
            new_phone = st.text_input("الهاتف")
            new_section_id = ""
            if not sections.empty:
                new_section_id = st.selectbox("الفصل", sections["section_id"], format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0])
            
            # Student specific fields
            new_parent_phone = ""
            new_birthdate = None
            new_address = ""
            new_school = ""
            new_notes = ""
            new_status = "نشطة"
            if member_type == "طالبة":
                new_parent_phone = st.text_input("رقم ولي الأمر")
                new_birthdate = st.date_input("تاريخ الميلاد", value=None)
                new_address = st.text_input("العنوان")
                new_school = st.text_input("المدرسة")
                new_notes = st.text_area("ملاحظات")
                new_status = st.selectbox("الحالة", ["نشطة", "غير نشطة"], index=0)

            submitted = st.form_submit_button("إضافة عضو")
            if submitted:
                if not new_name:
                    st.error("الاسم الكامل مطلوب")
                else:
                    if member_type == "طالبة":
                        student_data = {
                            "student_id": str(uuid.uuid4()),
                            "full_name": new_name.strip(),
                            "section_id": new_section_id,
                            "phone": new_phone,
                            "parent_phone": new_parent_phone,
                            "birthdate": new_birthdate.strftime("%Y-%m-%d") if new_birthdate else "",
                            "address": new_address,
                            "school": new_school,
                            "notes": new_notes,
                            "status": "active" if new_status == "نشطة" else "inactive",
                            "created_by": user_id
                        }
                        db.add_student(student_data)
                    else:
                        role_map = {"أمين خدمة": "Service Manager", "مدرسة": "Teacher"}
                        db.add_user({
                            "user_id": str(uuid.uuid4()),
                            "username": new_name.strip(),
                            "password": hash_password("1234"),
                            "role": role_map.get(member_type, "Teacher"),
                            "full_name": new_name.strip(),
                            "section_id": new_section_id,
                            "phone": new_phone,
                            "email": ""
                        })
                    db.add_log(user.get("user_id", ""), "إضافة عضو", f"تمت إضافة {new_name}")
                    st.success("✅ تمت الإضافة بنجاح")
                    time.sleep(1)
                    st.rerun()


# =============================================================================
# User Management (Deprecated)
# =============================================================================
# DEPRECATED - replaced by show_members_cards_page
def show_user_management(db):
    st.warning("⚠️ هذه الصفحة تم استبدالها بصفحة إدارة الأعضاء الموحدة")
    st.info("يرجى استخدام صفحة 👥 إدارة الأعضاء من القائمة الجانبية")


# =============================================================================
# Students Management (Cards) (Deprecated)
# =============================================================================
# DEPRECATED - replaced by show_members_cards_page
def show_students_cards_page(db):
    st.warning("⚠️ هذه الصفحة تم استبدالها بصفحة إدارة الأعضاء الموحدة")
    st.info("يرجى استخدام صفحة 👥 إدارة الأعضاء من القائمة الجانبية")


# =============================================================================
# Stages Management Page (Standalone)
# =============================================================================
def show_stages_page(db):
    inject_user_cards_css()
    st.markdown("<h2 class='main-header'>🏫 إدارة المراحل الدراسية</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    users = db.get_users()
    stages = db.get_stages()
    sections = db.get_sections()
    students = db.get_students()

    if role == "Father Account":
        st.info("👁️ وضع العرض فقط - يمكنك مراجعة المراحل")
    elif role not in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
        st.error("🚫 غير مصرح")
        return

    if not stages.empty:
        stage_view = stages.copy()
        if "stage_id" in stage_view.columns:
            stage_view["num_sections"] = stage_view["stage_id"].apply(
                lambda sid: len(sections[sections["stage_id"] == sid]) if not sections.empty and "stage_id" in sections.columns else 0
            )
            stage_view["num_students"] = stage_view["stage_id"].apply(
                lambda sid: len(students[students["section_id"].isin(sections[sections["stage_id"] == sid]["section_id"])]) if not sections.empty and not students.empty and "stage_id" in sections.columns else 0
            )
        else:
            stage_view["num_sections"] = 0
            stage_view["num_students"] = 0
        if not users.empty:
            stage_view["supervisors"] = stage_view["stage_id"].apply(
                lambda sid: ", ".join(db.get_supervisor_names_for_stage(sid, users)) if not stages.empty else ""
            )
        else:
            stage_view["supervisors"] = ""
        view_cols = ["stage_name", "status", "num_sections", "num_students", "supervisors"]
        available_cols = [c for c in view_cols if c in stage_view.columns]
        st.dataframe(stage_view[available_cols].rename(columns={"stage_name": "المرحلة", "status": "الحالة", "num_sections": "عدد الفصول", "num_students": "عدد الطلاب", "supervisors": "المشرفون"}), use_container_width=True)
    else:
        st.info("لا توجد مراحل مسجلة.")

    with st.expander("➕ إضافة مرحلة جديدة"):
        with st.form("add_stage_page_form"):
            new_name = st.text_input("اسم المرحلة*")
            new_desc = st.text_area("الوصف")
            new_order = st.number_input("ترتيب العرض", 1, 100, 1)
            new_status = st.selectbox("الحالة", ["active", "inactive"], index=0)
            new_notes = st.text_area("ملاحظات")
            if st.form_submit_button("إضافة المرحلة"):
                if not new_name:
                    st.error("اسم المرحلة مطلوب")
                elif not stages.empty and "stage_name" in stages.columns and not stages[stages.stage_name == new_name.strip()].empty:
                    st.error("⛔ اسم المرحلة موجود مسبقاً!")
                else:
                    db.add_stage({
                        "stage_id": str(uuid.uuid4()), "stage_name": new_name.strip(),
                        "description": new_desc, "display_order": new_order,
                        "status": new_status, "created_date": get_cairo_now().strftime("%Y-%m-%d"),
                        "created_by": user.get("user_id", ""), "manager_user_id": "",
                        "notes": new_notes
                    })
                    st.success("✅ تمت إضافة المرحلة بنجاح")
                    time.sleep(1)
                    st.rerun()

    if not stages.empty:
        with st.expander("✏️ تعديل / حذف مرحلة"):
            stage_sel = st.selectbox("اختر مرحلة", stages["stage_id"],
                                     format_func=lambda x: stages[stages.stage_id == x]["stage_name"].values[0])
            stage_row = stages[stages.stage_id == stage_sel].iloc[0].to_dict()
            edit_name = st.text_input("اسم المرحلة", value=stage_row.get("stage_name", ""), key="page_edit_stage_name")
            edit_desc = st.text_area("الوصف", value=stage_row.get("description", ""), key="page_edit_stage_desc")
            edit_order = st.number_input("ترتيب العرض", 1, 100, int(stage_row.get("display_order", 1) or 1), key="page_edit_stage_order")
            edit_status = st.selectbox("الحالة", ["active", "inactive"], index=0 if stage_row.get("status", "active") == "active" else 1, key="page_edit_stage_status")
            edit_notes = st.text_area("ملاحظات", value=stage_row.get("notes", ""), key="page_edit_stage_notes")

            st.markdown("#### 👥 المشرفون على المرحلة")
            current_supervisors = db.get_supervisors_for_stage(stage_sel)
            eligible_users = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
            if not eligible_users.empty:
                supervisor_options = eligible_users["user_id"].tolist()
                # Filter default to only include IDs that exist in options
                valid_supervisors = [s for s in current_supervisors if s in supervisor_options]
                selected_supervisors = st.multiselect("اختر المشرفين", supervisor_options,
                                                      default=valid_supervisors,
                                                      format_func=lambda x: eligible_users[eligible_users.user_id == x]["full_name"].values[0] if not eligible_users.empty and x in eligible_users["user_id"].values else str(x),
                                                      key="page_stage_supervisors")
            else:
                selected_supervisors = []
                st.info("لا يوجد مستخدمون مؤهلون")

            col1, col2 = st.columns(2)
            if col1.button("تحديث المرحلة"):
                db.update_stage(stage_sel, {"stage_name": edit_name, "description": edit_desc,
                                            "display_order": edit_order, "status": edit_status, "notes": edit_notes})
                db.clear_stage_supervisors(stage_sel)
                for sup_id in selected_supervisors:
                    db.add_stage_supervisor(stage_sel, sup_id)
                st.success("تم التحديث")
                time.sleep(1)
                st.rerun()
            if col2.button("حذف المرحلة"):
                sections_in_stage = sections[sections["stage_id"] == stage_sel] if not sections.empty and "stage_id" in sections.columns else pd.DataFrame()
                if not sections_in_stage.empty:
                    st.error("❌ لا يمكن حذف المرحلة لأنها تحتوي على فصول. قم بحذف الفصول أولاً.")
                else:
                    db.delete_stage(stage_sel)
                    db.clear_stage_supervisors(stage_sel)
                    st.success("تم حذف المرحلة")
                    time.sleep(1)
                    st.rerun()


# =============================================================================
# Sections Management Page (Standalone)
# =============================================================================
def show_sections_page(db):
    inject_user_cards_css()
    st.markdown("<h2 class='main-header'>📚 إدارة الفصول</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    users = db.get_users()
    stages = db.get_stages()
    sections = db.get_sections()
    students = db.get_students()

    if role == "Father Account":
        st.info("👁️ وضع العرض فقط - يمكنك مراجعة الفصول")
    elif role in ["Service Manager", "Teacher"] and not sections.empty:
        assigned = db.get_sections_by_teacher(user.get("user_id", "")) if role == "Teacher" else db.get_sections_by_leader(user.get("user_id", ""))
        if assigned.empty:
            assigned = db.get_sections_by_teacher(user.get("user_id", ""))
        sections = assigned if not assigned.empty else sections
    elif role not in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
        st.error("🚫 غير مصرح")
        return

    def get_names_from_ids(id_string, users_df, role_name):
        if not id_string or users_df.empty:
            return f"غير محدد{role_name}"
        ids = [x.strip() for x in str(id_string).split(",") if x.strip()]
        names = []
        for uid in ids:
            match = users_df[users_df["user_id"] == uid]
            if not match.empty:
                names.append(match.iloc[0].get("full_name", uid))
        return "، ".join(names) if names else f"غير محدد{role_name}"

    search_term = st.text_input("🔍 بحث", placeholder="ابحث باسم الفصل...", label_visibility="collapsed")
    col1, col2, col3 = st.columns(3)
    with col1:
        stage_options = ["الكل"] + stages["stage_id"].tolist() if not stages.empty else ["الكل"]
        stage_filter = st.selectbox("المرحلة", stage_options,
                                    format_func=lambda x: "الكل" if x == "الكل" else stages[stages.stage_id == x]["stage_name"].values[0] if not stages.empty else x)
    with col2:
        teacher_options = ["الكل"] + users["user_id"].tolist() if not users.empty else ["الكل"]
        teacher_filter = st.selectbox("المدرس", teacher_options,
                                      format_func=lambda x: "الكل" if x == "الكل" else users[users.user_id == x]["full_name"].values[0] if not users.empty else x)
    with col3:
        status_filter = st.selectbox("الحالة", ["الكل", "active", "inactive"])

    filtered = sections.copy() if not sections.empty else pd.DataFrame()
    if search_term and not filtered.empty:
        mask = pd.Series(False, index=filtered.index)
        for col in ["section_name"]:
            if col in filtered.columns:
                mask |= filtered[col].astype(str).str.contains(search_term, na=False, case=False)
        filtered = filtered[mask]
    if stage_filter != "الكل" and not filtered.empty and "stage_id" in filtered.columns:
        filtered = filtered[filtered["stage_id"] == stage_filter]
    if teacher_filter != "الكل" and not filtered.empty and "teacher_id" in filtered.columns:
        filtered = filtered[filtered["teacher_id"] == teacher_filter]
    if status_filter != "الكل" and not filtered.empty and "status" in filtered.columns:
        filtered = filtered[filtered["status"] == status_filter]

    if not filtered.empty:
        for _, sec in filtered.iterrows():
            sec_id = sec.get("section_id", "")
            sec_name = sec.get("section_name", "")
            sec_stage = sec.get("stage_id", "")
            sec_teacher = sec.get("teacher_id", "")
            sec_leader = sec.get("leader_id", "")
            sec_status = sec.get("status", "active")
            sec_notes = sec.get("notes", "")

            if not stages.empty and sec_stage:
                matched_stage = stages[stages["stage_id"] == sec_stage]["stage_name"]
                stage_name = matched_stage.values[0] if not matched_stage.empty else "—"
            else:
                stage_name = "—"
            teacher_name = get_names_from_ids(sec_teacher, users, "")
            leader_name = get_names_from_ids(sec_leader, users, "ة")
            student_count = db.get_section_student_count(sec_id)

            with st.expander(f"🏫 {sec_name} ({stage_name}) - {student_count} طالبة"):
                st.markdown(f"**المرحلة:** {stage_name} | **الحالة:** {sec_status}")
                st.markdown(f"**المدرس:** {teacher_name} | **أمين الخدمة:** {leader_name}")
                st.markdown(f"**عدد الطلاب:** {student_count}")
                st.markdown(f"**ملاحظات:** {sec_notes or '—'}")

                if role == "System Admin":
                    st.markdown("#### 🏫 نقل الفصل بين المراحل")
                    if not stages.empty:
                        new_stage = st.selectbox("نقل إلى مرحلة", stages["stage_id"],
                                                 format_func=lambda x: "—" if x not in stages["stage_id"].values else stages[stages.stage_id == x]["stage_name"].values[0],
                                                 key=f"move_stage_{sec_id}")
                        if st.button("نقل الفصل", key=f"move_sec_{sec_id}"):
                            db.update_section(sec_id, {"stage_id": new_stage})
                            st.success("✅ تم نقل الفصل")
                            time.sleep(1)
                            st.rerun()

                    st.markdown("#### 🔗 التعيينات")
                    eligible_teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
                    eligible_leaders = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
                    current_teachers_raw = str(sec_teacher).split(",") if sec_teacher else []
                    current_leaders_raw = str(sec_leader).split(",") if sec_leader else []
                    valid_teacher_ids = eligible_teachers["user_id"].tolist() if not eligible_teachers.empty else []
                    valid_leader_ids = eligible_leaders["user_id"].tolist() if not eligible_leaders.empty else []
                    # Filter defaults to only include IDs that still exist in the options
                    current_teachers = [t.strip() for t in current_teachers_raw if t.strip() and t.strip() in valid_teacher_ids]
                    current_leaders = [l.strip() for l in current_leaders_raw if l.strip() and l.strip() in valid_leader_ids]

                    selected_teachers = st.multiselect("المدرسات", valid_teacher_ids,
                                                       default=current_teachers,
                                                       format_func=lambda x: eligible_teachers[eligible_teachers.user_id == x]["full_name"].values[0] if not eligible_teachers.empty and x in eligible_teachers["user_id"].values else str(x),
                                                       key=f"teacher_{sec_id}")
                    selected_leaders = st.multiselect("أمناء الخدمة", valid_leader_ids,
                                                      default=current_leaders,
                                                      format_func=lambda x: eligible_leaders[eligible_leaders.user_id == x]["full_name"].values[0] if not eligible_leaders.empty and x in eligible_leaders["user_id"].values else str(x),
                                                      key=f"leader_{sec_id}")
                    if st.button("💾 حفظ التعيينات", key=f"save_assign_{sec_id}"):
                        db.update_section(sec_id, {"teacher_id": ",".join(selected_teachers), "leader_id": ",".join(selected_leaders)})
                        st.success("✅ تم تحديث التعيينات")
                        time.sleep(1)
                        st.rerun()

                    if role == "System Admin":
                        st.markdown("#### ✏️ تعديل / حذف الفصل")
                        new_name = st.text_input("اسم الفصل", value=sec_name, key=f"edit_name_{sec_id}")
                        new_status = st.selectbox("الحالة", ["active", "inactive"], index=0 if sec_status == "active" else 1, key=f"edit_status_{sec_id}")
                        new_notes = st.text_area("ملاحظات", value=sec_notes, key=f"edit_notes_{sec_id}")
                        c1, c2 = st.columns(2)
                        if c1.button("تحديث الفصل", key=f"update_sec_{sec_id}"):
                            db.update_section(sec_id, {"section_name": new_name, "notes": new_notes, "status": new_status})
                            st.success("✅ تم التحديث")
                            time.sleep(1)
                            st.rerun()
                        if c2.button("حذف الفصل", key=f"delete_sec_{sec_id}"):
                            section_students = students[students["section_id"] == sec_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
                            if not section_students.empty:
                                st.error("❌ لا يمكن حذف الفصل لأنه يحتوي على طالبات. قم بنقل الطالبات أولاً.")
                            else:
                                db.delete_section(sec_id)
                                st.success("✅ تم الحذف")
                                time.sleep(1)
                                st.rerun()
                    else:
                        st.info("👁️ يمكنك فقط مشاهدة بيانات الفصل - لا يمكنك تعديلها أو حذفها")
    else:
        st.info("🔍 لا توجد فصول مطابقة.")

    if role == "System Admin":
        with st.expander("➕ إضافة فصل جديد"):
            with st.form("add_section_page_form"):
                sec_name = st.text_input("اسم الفصل*")
                sec_stage = st.selectbox("المرحلة", stages["stage_id"],
                                         format_func=lambda x: "—" if not stages.empty and x not in stages["stage_id"].values else stages[stages.stage_id == x]["stage_name"].values[0]) if not stages.empty else ""
                eligible_teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
                eligible_leaders = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
                teacher_opts = eligible_teachers["user_id"].tolist() if not eligible_teachers.empty else []
                selected_teachers = st.multiselect("المدرسات", teacher_opts,
                                                   format_func=lambda x: eligible_teachers[eligible_teachers.user_id == x]["full_name"].values[0] if not eligible_teachers.empty and x in eligible_teachers["user_id"].values and not eligible_teachers[eligible_teachers.user_id == x].empty else str(x)) if teacher_opts else []
                leader_opts = eligible_leaders["user_id"].tolist() if not eligible_leaders.empty else []
                selected_leaders = st.multiselect("أمناء الخدمة", leader_opts,
                                                  format_func=lambda x: eligible_leaders[eligible_leaders.user_id == x]["full_name"].values[0] if not eligible_leaders.empty and x in eligible_leaders["user_id"].values and not eligible_leaders[eligible_leaders.user_id == x].empty else str(x)) if leader_opts else []
                sec_notes = st.text_area("ملاحظات")
                if st.form_submit_button("إضافة الفصل"):
                    if not sec_name:
                        st.error("اسم الفصل مطلوب")
                    elif not sections.empty and "section_name" in sections.columns and sec_stage and not sections[sections.section_name == sec_name.strip()].empty:
                        st.error("⛔ اسم الفصل موجود مسبقاً!")
                    else:
                        teacher_ids_str = ",".join(selected_teachers) if selected_teachers else ""
                        leader_ids_str = ",".join(selected_leaders) if selected_leaders else ""
                        db.add_section({
                            "section_id": str(uuid.uuid4()), "section_name": sec_name.strip(),
                            "stage_id": sec_stage, "teacher_id": teacher_ids_str, "leader_id": leader_ids_str,
                            "max_students": "", "room": "",
                            "meeting_day": "", "meeting_time": "",
                            "status": "active", "notes": sec_notes,
                            "manager_user_id": user.get("user_id", "")
                        })
                        st.success("✅ تمت إضافة الفصل بنجاح")
                        time.sleep(1)
                        st.rerun()


# =============================================================================
# Attendance
# =============================================================================
def show_attendance(db):
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")
    st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
    
    # Service Manager can view attendance for their sections but not edit
    if role == "Service Manager":
        section_ids = get_sections_for_supervisor(db, user_id)
        if not section_ids:
            st.info("لا توجد فصول معينة لك.")
            return
        sections = db.get_sections()
        if sections.empty:
            st.warning("لا توجد فصول.")
            return
        supervised_sections = sections[sections.section_id.isin(section_ids)]
        if supervised_sections.empty:
            st.info("لا توجد فصول معينة لك.")
            return
        
        st.subheader("📊 عرض الحضور (للقراءة فقط)")
        selected_section = st.selectbox("اختر الفصل", supervised_sections["section_id"],
                                        format_func=lambda x: "—" if x not in supervised_sections["section_id"].values else supervised_sections[supervised_sections.section_id == x]["section_name"].values[0])
        date = st.date_input("التاريخ", get_cairo_now().date())
        date_str = date.strftime("%Y-%m-%d")
        students = db.get_students()
        section_students = students[students.section_id == selected_section] if not students.empty and "section_id" in students.columns else pd.DataFrame()
        if section_students.empty:
            st.info("لا توجد طالبات في هذا الفصل.")
            return
        existing = db.get_attendance_by_date_section(date_str, selected_section)
        if existing.empty:
            st.info("لا يوجد سجل حضور لهذا اليوم.")
            return
        # Merge student names
        display = existing.merge(section_students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(display[["full_name", "status", "notes"]], use_container_width=True)
        return
    
    # Teacher and System Admin flow continues below
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
                                        format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0])
    date = st.date_input("التاريخ", get_cairo_now().date())
    date_str = date.strftime("%Y-%m-%d")
    students = db.get_students()
    section_students = students[students.section_id == selected_section] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات في هذا الفصل.")
        return
    existing = db.get_attendance_by_date_section(date_str, selected_section)
    already_filled = not existing.empty
    if already_filled:
        st.warning("⚠️ يوجد تسجيل حضور سابق.")
    statuses = {}
    notes_dict = {}
    st.markdown("<div class='card'>", unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("💾 حفظ الحضور", use_container_width=True, key="save_attendance_btn"):
        with st.spinner("جاري حفظ الحضور..."):
            records = []
            for sid, status in statuses.items():
                prev_record = existing[existing.student_id == sid] if already_filled else pd.DataFrame()
                record_id = prev_record.iloc[0]["record_id"] if not prev_record.empty else str(uuid.uuid4())
                records.append({
                    "record_id": record_id, "date": date_str, "student_id": sid,
                    "status": status, "notes": notes_dict.get(sid, ""),
                    "recorded_by": user.get("user_id", ""), "section_id": selected_section
                })
            db.batch_add_attendance(records)
            db.add_log(user.get("user_id", ""), f"تسجيل حضور فصل {selected_section} ليوم {date_str}")
            st.success("✅ تم تسجيل الحضور بنجاح")
            time.sleep(1)
            st.rerun()
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
        
        # Teacher can only delete attendance records they created
        can_delete_attendance = True
        if role == "Teacher":
            can_delete_attendance = False
            st.warning("⛔ لا يمكنك حذف سجل حضور سجلته مدرسة أخرى.")
        
        if role == "System Admin" and can_delete_attendance:
            del_id = st.selectbox("اختر سجل حضور لحذفه", rec["record_id"], key="del_att_sel")
            if st.button("حذف سجل الحضور"):
                db.delete_attendance_record(del_id)
                st.success("تم الحذف")
                time.sleep(1)
                st.rerun()


# =============================================================================
# Follow-up
# =============================================================================
def show_followup(db):
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")
    students = db.get_students()
    followup = db.get_followup()
    
    # Service Manager filtering by stages
    if role == "Service Manager" and db and user_id:
        section_ids = get_sections_for_supervisor(db, user_id)
        if section_ids:
            responsible = students[students.section_id.isin(section_ids)] if not students.empty and "section_id" in students.columns else pd.DataFrame()
        else:
            responsible = pd.DataFrame()
    else:
        section_id = user.get("section_id", "")
        responsible = filter_students_by_role(students, role, section_id)
    if responsible.empty:
        st.info("لا توجد طالبات مسؤولات عنك.")
        return
    if not followup.empty and "student_id" in followup.columns and "regularity_status" in followup.columns:
        student_ids = responsible["student_id"].tolist() if "student_id" in responsible.columns else []
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
    if not followup.empty and "regularity_status" in followup.columns and "student_id" in followup.columns:
        urgent = followup[(followup.regularity_status.isin(["متقطع", "منقطع"])) & (followup.student_id.isin(responsible["student_id"]))]
        if not urgent.empty:
            urgent_display = urgent.merge(responsible[["student_id", "full_name"]], on="student_id", how="left")
            st.dataframe(urgent_display[["full_name", "followup_date", "notes"]], use_container_width=True)
        else:
            st.info("كل البنات منتظمات حالياً.")
    else:
        st.info("لا توجد متابعات سابقة.")
    st.markdown("---")
    st.subheader("➕ إضافة متابعة جديدة")
    if "student_id" in responsible.columns:
        student = st.selectbox("اختر الطالبة", responsible["student_id"],
                               format_func=lambda x: responsible[responsible.student_id == x]["full_name"].values[0], key="followup_student")
        with st.form("followup_form"):
            ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
            notes = st.text_area("ملاحظات")
            regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
            if st.form_submit_button("حفظ المتابعة"):
                try:
                    db.add_followup_record({
                        "record_id": str(uuid.uuid4()), "student_id": student,
                        "teacher_id": user.get("user_id", ""), "followup_date": get_cairo_now().strftime("%Y-%m-%d"),
                        "followup_type": ftype, "notes": notes, "regularity_status": regularity
                    })
                    st.success("✅ تم تسجيل الافتقاد بنجاح")
                    time.sleep(1)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    
    # Show existing followup records with delete option for admin
    if not followup.empty and role == "System Admin":
        st.markdown("---")
        st.subheader("🗑️ إدارة سجلات الافتقاد")
        followup_display = followup.merge(
            students[["student_id", "full_name"]] if not students.empty else pd.DataFrame(),
            on="student_id", how="left"
        )
        if not followup_display.empty:
            followup_display = followup_display[["record_id", "full_name", "followup_type", "regularity_status"]]
            st.dataframe(followup_display, use_container_width=True)
            del_followup_id = st.selectbox("اختر سجل افتقاد لحذفه", followup_display["record_id"], key="del_followup_sel")
            if st.button("حذف سجل الافتقاد"):
                db.delete_followup_record(del_followup_id)
                st.success("تم الحذف")
                time.sleep(1)
                st.rerun()


# =============================================================================
# Class Competition Scores
# =============================================================================
def show_class_competition_scores(db):
    st.markdown("<h2 class='main-header'>🏆 درجات مسابقات الفصل</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")
    
    # Service Manager can view competition scores for their stages
    if role == "Service Manager":
        section_ids = get_sections_for_supervisor(db, user_id)
        if not section_ids:
            st.info("لا توجد فصول معينة لك.")
            return
        students = db.get_students()
        quizzes = db.get_quizzes()
        results = db.get_quiz_results()
        section_students = students[students.section_id.isin(section_ids)] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    elif role == "Teacher":
        section_id = user.get("section_id", "")
        if not section_id:
            st.error("🚫 لم يتم تعيين فصل لك.")
            return
        students = db.get_students()
        quizzes = db.get_quizzes()
        results = db.get_quiz_results()
        section_students = students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    else:
        st.error("🚫 هذه الصفحة متاحة للمدرسات وأمناء الخدمة فقط.")
        return
    if section_students.empty:
        st.info("لا توجد طالبات مسجلات في فصلك.")
        return
    section_student_ids = section_students["student_id"].tolist()
    if not results.empty and "student_id" in results.columns:
        class_results = results[results["student_id"].isin(section_student_ids)]
        if "status" in class_results.columns:
            class_results = class_results[class_results["status"] == "submitted"]
    else:
        class_results = pd.DataFrame()
    if not quizzes.empty and not class_results.empty:
        class_results = class_results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
        class_results = class_results.rename(columns={"title": "اسم المسابقة"})
    else:
        class_results["اسم المسابقة"] = ""
    if not section_students.empty and not class_results.empty:
        class_results = class_results.merge(section_students[["student_id", "full_name"]], on="student_id", how="left")
        class_results = class_results.rename(columns={"full_name": "اسم الطالبة"})
    else:
        class_results["اسم الطالبة"] = ""
    if class_results.empty:
        st.info("لا توجد نتائج مسابقات مسجلة لطالبات فصلك بعد.")
        return
    display_cols = ["اسم المسابقة", "اسم الطالبة", "score", "total_marks", "submission_time"]
    available_cols = [c for c in display_cols if c in class_results.columns]
    display_df = class_results[available_cols].copy()
    if "score" in display_df.columns:
        display_df["score"] = pd.to_numeric(display_df["score"], errors="coerce").fillna(0)
    if "total_marks" in display_df.columns:
        display_df["total_marks"] = pd.to_numeric(display_df["total_marks"], errors="coerce").fillna(20)
    st.markdown("---")
    st.subheader("🔍 بحث وتصفية")
    search_term = st.text_input("ابحث باسم الطالبة أو المسابقة", placeholder="اكتب اسم الطالبة أو المسابقة...")
    if "اسم المسابقة" in display_df.columns:
        quiz_names = ["الكل"] + sorted(display_df["اسم المسابقة"].dropna().unique().tolist())
        filter_quiz = st.selectbox("تصفية حسب المسابقة", quiz_names)
    else:
        filter_quiz = "الكل"
    sort_by = st.selectbox("ترتيب حسب", ["التاريخ", "الدرجة (تنازلي)", "الدرجة (تصاعدي)", "اسم الطالبة"])
    filtered_df = display_df.copy()
    if search_term:
        mask = pd.Series(False, index=filtered_df.index)
        if "اسم الطالبة" in filtered_df.columns:
            mask = mask | filtered_df["اسم الطالبة"].astype(str).str.contains(search_term, na=False, case=False)
        if "اسم المسابقة" in filtered_df.columns:
            mask = mask | filtered_df["اسم المسابقة"].astype(str).str.contains(search_term, na=False, case=False)
        filtered_df = filtered_df[mask]
    if filter_quiz != "الكل" and "اسم المسابقة" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["اسم المسابقة"] == filter_quiz]
    if sort_by == "التاريخ" and "submission_time" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("submission_time", ascending=False)
    elif sort_by == "الدرجة (تنازلي)" and "score" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("score", ascending=False)
    elif sort_by == "الدرجة (تصاعدي)" and "score" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("score", ascending=True)
    elif sort_by == "اسم الطالبة" and "اسم الطالبة" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("اسم الطالبة", ascending=True)
    st.markdown("---")
    st.subheader("📋 النتائج")
    if not filtered_df.empty:
        filtered_df = filtered_df.reset_index(drop=True)
        filtered_df.index = filtered_df.index + 1
        # Rename English columns to Arabic
        display_final = filtered_df.rename(columns={
            "score": "الدرجة",
            "total_marks": "الدرجة الكلية",
            "submission_time": "وقت التسليم"
        })
        available_cols = [c for c in display_final.columns if c in ["اسم المسابقة", "اسم الطالبة", "الدرجة", "الدرجة الكلية", "وقت التسليم"]]
        st.dataframe(display_final[available_cols], use_container_width=True)
        if "score" in filtered_df.columns and "total_marks" in filtered_df.columns:
            st.markdown("---")
            st.subheader("📊 إحصائيات الفصل")
            avg_score = filtered_df["score"].mean()
            max_score = filtered_df["score"].max()
            min_score = filtered_df["score"].min()
            c1, c2, c3 = st.columns(3)
            c1.metric("متوسط الدرجات", f"{avg_score:.1f}")
            c2.metric("أعلى درجة", f"{max_score:.1f}")
            c3.metric("أقل درجة", f"{min_score:.1f}")
            if "اسم الطالبة" in filtered_df.columns:
                st.markdown("---")
                st.subheader("🏆 ترتيب الطالبات")
                ranking = filtered_df.groupby("اسم الطالبة")["score"].sum().reset_index().sort_values("score", ascending=False)
                ranking.index = range(1, len(ranking) + 1)
                st.dataframe(ranking.rename(columns={"score": "المجموع"}), use_container_width=True)
    else:
        st.info("لا توجد نتائج مطابقة للبحث.")


# =============================================================================
# Quizzes
# =============================================================================
def show_quizzes(db):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")
    section_id = user.get("section_id", "")
    quizzes = db.get_quizzes()
    if role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد")
        with st.form("quiz_form"):
            title = st.text_input("عنوان الاختبار*")
            num_questions = st.selectbox("عدد الأسئلة", [10, 20, 30], index=1)
            time_limit = st.number_input("الوقت (بالدقائق)", 1, 180, 15)
            expiry = st.date_input("تاريخ الانتهاء", get_cairo_now().date() + timedelta(days=7))
            if st.form_submit_button("إنشاء"):
                if not title:
                    st.error("يرجى إدخال عنوان الاختبار")
                else:
                    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    pwd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    quiz_id = str(uuid.uuid4())
                    db.add_quiz({
                        "quiz_id": quiz_id, "title": title, "description": "",
                        "created_by": user.get("user_id", ""), "section_id": "",
                        "num_questions": num_questions, "time_limit_minutes": time_limit,
                        "total_marks": 20, "expiry_date": expiry.strftime("%Y-%m-%d"),
                        "quiz_code": code, "password": pwd, "is_active": "True"
                    })
                    st.success(f"✅ تم إنشاء الاختبار! الكود: {code}")
                    time.sleep(2)
                    st.rerun()
        st.markdown("---")
        st.subheader("📝 إدارة الأسئلة")
        if not quizzes.empty and "is_active" in quizzes.columns:
            active_quizzes = quizzes[quizzes.is_active == "True"]
            if not active_quizzes.empty:
                quiz_choice = st.selectbox("اختر اختباراً لإدارة أسئلته", active_quizzes["quiz_id"],
                                           format_func=lambda x: active_quizzes[active_quizzes.quiz_id == x]["title"].values[0])
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
                            opts["option1"] = "صح"
                            opts["option2"] = "خطأ"
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
                qid = q.get("quiz_id", "")
                title = q.get("title", "")
                active = q.get("is_active", "True") == "True"
                code = q.get("quiz_code", "")
                expiry = q.get("expiry_date", "")
                created_by = q.get("created_by", "")
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                col1.write(f"**{title}**")
                col2.write(f"الكود: {code}")
                col3.write("حالة: " + ("🟢 نشط" if active else "🔴 مغلق"))
                col4.write(f"ينتهي: {expiry}")
                
                # Check if teacher can modify this quiz
                can_manage_quiz = True
                if role == "Teacher" and created_by != user_id:
                    can_manage_quiz = False
                
                col_actions = st.columns(4)
                if can_manage_quiz:
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
                if role == "System Admin" and can_manage_quiz:
                    if col_actions[1].button("حذف (النتائج تبقى)", key=f"del_keep_{qid}"):
                        db.delete_quiz_keep_results(qid)
                        st.success(f"تم حذف الاختبار '{title}' مع الاحتفاظ بالنتائج.")
                        time.sleep(1)
                        st.rerun()
                
                if role == "Teacher" and not can_manage_quiz:
                    st.warning("⛔ لا يمكنك التعديل على مسابقة أنشأها شخص آخر.")
                
                st.markdown("---")
    st.markdown("### 📊 نتائج الاختبارات")
    results = db.get_quiz_results()
    students = db.get_students()
    sections_all = db.get_sections()
    if not results.empty:
        if "status" in results.columns:
            results = results[results["status"] == "submitted"]
        if role == "Teacher" and section_id and not students.empty and "student_id" in results.columns and "section_id" in students.columns:
            section_student_ids = students[students.section_id == section_id]["student_id"].tolist()
            results = results[results.student_id.isin(section_student_ids)]
        elif role == "Service Manager" and not students.empty and "student_id" in results.columns and "section_id" in students.columns:
            section_ids = get_sections_for_supervisor(db, user_id)
            if section_ids:
                section_student_ids = students[students.section_id.isin(section_ids)]["student_id"].tolist()
                results = results[results.student_id.isin(section_student_ids)]
        if not students.empty:
            if "student_id" in results.columns:
                results = results.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
                results.rename(columns={"full_name": "اسم الطالبة"}, inplace=True)
        if not sections_all.empty:
            if "section_id" in results.columns:
                results = results.merge(sections_all[["section_id", "section_name"]], on="section_id", how="left")
                results.rename(columns={"section_name": "الفصل"}, inplace=True)
        else:
            results["الفصل"] = ""
        if not quizzes.empty:
            if "quiz_id" in results.columns:
                results = results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
                results.rename(columns={"title": "المسابقة"}, inplace=True)
        if "score" in results.columns:
            results["score"] = pd.to_numeric(results["score"], errors="coerce").fillna(0)
        if "quiz_id" in results.columns:
            quiz_ids = results["quiz_id"].unique().tolist()
            if quiz_ids and not quizzes.empty:
                quiz_titles = quizzes[quizzes["quiz_id"].isin(quiz_ids)][["quiz_id", "title"]].drop_duplicates()
                quiz_options = ["الكل"] + quiz_titles["quiz_id"].tolist()
                selected_quiz_filter = st.selectbox("اختر الاختبار لعرض نتائجه فقط", quiz_options,
                                                    format_func=lambda x: "الكل" if x == "الكل" else quiz_titles[quiz_titles.quiz_id == x]["title"].values[0])
                if selected_quiz_filter != "الكل":
                    results = results[results.quiz_id == selected_quiz_filter]
        if results.empty:
            st.info("لا توجد نتائج مطابقة للاختبار المحدد.")
        else:
            base_cols = ["اسم الطالبة", "الفصل", "المسابقة", "score", "total_marks"]
            if "submission_time" in results.columns:
                base_cols.append("submission_time")
            if st.session_state.user.get("role") == "System Admin":
                time_cols = []
                if "start_time" in results.columns:
                    try:
                        results["بداية الاختبار"] = pd.to_datetime(results["start_time"]).apply(
                            lambda x: format_cairo_time(x.replace(tzinfo=CAIRO_TZ)) if pd.notna(x) else ""
                        )
                        time_cols.append("بداية الاختبار")
                    except Exception:
                        pass
                if "submission_time" in results.columns:
                    try:
                        results["تسليم الاختبار"] = pd.to_datetime(results["submission_time"]).apply(
                            lambda x: format_cairo_time(x.replace(tzinfo=CAIRO_TZ)) if pd.notna(x) else ""
                        )
                        time_cols.append("تسليم الاختبار")
                    except Exception:
                        pass
                display_cols = base_cols + time_cols
            else:
                display_cols = base_cols
            display_cols = list(dict.fromkeys(display_cols))
            available = [c for c in display_cols if c in results.columns]
            st.dataframe(results[available], use_container_width=True)
            if st.button("🏆 ترتيب الطالبات حسب المجموع") and "اسم الطالبة" in results.columns and "score" in results.columns:
                top = results.groupby("اسم الطالبة")["score"].sum().reset_index().sort_values("score", ascending=False)
                st.dataframe(top, use_container_width=True)
    else:
        st.info("لا توجد نتائج بعد.")


# =============================================================================
# Reports - Advanced Reports & Statistics Page
# =============================================================================
def _export_to_csv_bytes(df):
    """Convert DataFrame to CSV bytes for download."""
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding='utf-8-sig')
    buf.seek(0)
    return buf.getvalue()


def _export_to_excel_with_charts(report_title, df, charts_list=None):
    """
    إنشاء ملف Excel (.xlsx) يحتوي على التقرير + الرسوم البيانية كصور داخل الملف.
    charts_list: list of (plotly_figure, sheet_name) tuples
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Write data sheet
        df.to_excel(writer, sheet_name='التقرير', index=False)
        workbook = writer.book
        ws = writer.sheets['التقرير']
        
        # Style header
        header_font = Font(name='Cairo', bold=True, color='FFFFFF', size=12)
        header_fill = PatternFill(start_color='667EEA', end_color='764BA2', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for col_idx, col in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # Auto-adjust column widths
        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(
                df[col].astype(str).map(len).max() if not df.empty else 0,
                len(str(col))
            )
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 50)
        
        # Add charts as images if provided
        if charts_list:
            for fig, sheet_name in charts_list:
                img_bytes = pio.to_image(fig, format='png', width=1200, height=500, scale=2)
                img_stream = io.BytesIO(img_bytes)
                from openpyxl.drawing.image import Image as XLImage
                img = XLImage(img_stream)
                img.width = 800
                img.height = 350
                
                # Create new sheet for chart
                ws_chart = workbook.create_sheet(title=sheet_name)
                ws_chart.add_image(img, 'A1')
    
    output.seek(0)
    return output.getvalue()


def show_reports_page(db):
    """صفحة التقارير والإحصائيات المتقدمة"""
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")
    user_section_id = user.get("section_id", "")
    
    # Load data
    attendance = db.get_attendance()
    students = db.get_students()
    sections = db.get_sections()
    stages = db.get_stages()
    events = db.get_events()
    
    # RBAC filtering
    if role == "Service Manager" and db and user_id:
        section_ids = get_sections_for_supervisor(db, user_id)
        if section_ids:
            if not students.empty and "section_id" in students.columns:
                students = students[students.section_id.isin(section_ids)]
            if not attendance.empty and "section_id" in attendance.columns:
                attendance = attendance[attendance.section_id.isin(section_ids)]
        else:
            st.info("لا توجد فصول معينة لك.")
            return
    elif role == "Teacher":
        if user_section_id:
            if not students.empty and "section_id" in students.columns:
                students = students[students.section_id == user_section_id]
            if not attendance.empty and "section_id" in attendance.columns:
                attendance = attendance[attendance.section_id == user_section_id]
    
    if attendance.empty:
        st.info("لا توجد بيانات حضور كافية لإنشاء التقارير.")
        return
    
    # Parse dates
    if "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    if "student_id" in attendance.columns and not students.empty and "student_id" in students.columns:
        attendance = attendance.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
    
    # =========================================================================
    # FILTERS
    # =========================================================================
    st.markdown("### 🔍 الفلاتر")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        # Date range filter
        min_date = attendance["date"].min().date() if not attendance.empty and "date" in attendance.columns else get_cairo_now().date() - timedelta(days=30)
        max_date = attendance["date"].max().date() if not attendance.empty and "date" in attendance.columns else get_cairo_now().date()
        date_from = st.date_input("من تاريخ", min_date)
        date_to = st.date_input("إلى تاريخ", max_date)
    
    with col_f2:
        # Section filter
        section_options = ["الكل"]
        if not sections.empty and "section_id" in sections.columns:
            section_options += sections["section_id"].tolist()
        section_filter = st.selectbox(
            "الفصل", section_options,
            format_func=lambda x: "الكل" if x == "الكل" else (
                sections[sections.section_id == x]["section_name"].values[0] if not sections.empty and x in sections["section_id"].values else x
            )
        )
    
    with col_f3:
        # Event type filter (for event reports)
        event_type_filter = st.selectbox("نوع الحدث", ["الكل"] + EVENT_TYPES)
    
    with col_f4:
        # Report type selector
        report_type = st.selectbox(
            "نوع التقرير",
            [
                "تقرير الحضور الأسبوعي (آخر 7 أيام)",
                "تقرير الحضور الشهري (شهر محدد)",
                "تقرير الأعضاء الجدد (آخر 30 يوم)",
                "تقرير الأعضاء الغائبين (أكثر من 3 أيام)"
            ]
        )
    
    # Apply date filter
    filtered_attendance = attendance.copy()
    if "date" in filtered_attendance.columns:
        filtered_attendance = filtered_attendance[
            (filtered_attendance["date"].dt.date >= date_from) &
            (filtered_attendance["date"].dt.date <= date_to)
        ]
    
    # Apply section filter
    if section_filter != "الكل" and "section_id" in filtered_attendance.columns:
        filtered_attendance = filtered_attendance[filtered_attendance["section_id"] == section_filter]
    
    # Apply event type filter (for events)
    filtered_events = events.copy() if not events.empty else pd.DataFrame()
    if event_type_filter != "الكل" and not filtered_events.empty and "event_type" in filtered_events.columns:
        filtered_events = filtered_events[filtered_events["event_type"] == event_type_filter]
    
    # =========================================================================
    # REPORT GENERATION
    # =========================================================================
    st.markdown("---")
    st.markdown("### 📋 التقرير")
    
    report_df = pd.DataFrame()
    report_title = ""
    charts_to_export = []
    
    if report_type == "تقرير الحضور الأسبوعي (آخر 7 أيام)":
        report_title = "تقرير الحضور الأسبوعي"
        week_ago = get_cairo_now().date() - timedelta(days=7)
        weekly = filtered_attendance[filtered_attendance["date"].dt.date >= week_ago].copy()
        
        if not weekly.empty:
            # Summary by day
            daily_summary = weekly.groupby([weekly["date"].dt.date, "status"]).size().reset_index(name="العدد")
            daily_pivot = daily_summary.pivot(index="date", columns="status", values="العدد").fillna(0).reset_index()
            daily_pivot.columns.name = None
            daily_pivot["date"] = pd.to_datetime(daily_pivot["date"]).dt.strftime("%Y-%m-%d")
            daily_pivot = daily_pivot.rename(columns={"date": "التاريخ"})
            
            # Add total
            status_cols = [c for c in daily_pivot.columns if c != "التاريخ"]
            if status_cols:
                daily_pivot["الإجمالي"] = daily_pivot[status_cols].sum(axis=1)
            
            report_df = daily_pivot
            
            # Line chart for weekly attendance
            fig_line = px.line(
                weekly.groupby([weekly["date"].dt.date, "status"]).size().reset_index(name="العدد"),
                x="date", y="العدد", color="status",
                title="الحضور اليومي - آخر 7 أيام",
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"}
            )
            fig_line.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title="التاريخ", yaxis_title="العدد",
                font=dict(family="Cairo")
            )
            st.plotly_chart(fig_line, use_container_width=True)
            charts_to_export.append((fig_line, "الحضور اليومي"))
            
            # Pie chart for status distribution
            status_counts = weekly["status"].value_counts().reset_index()
            status_counts.columns = ["الحالة", "العدد"]
            fig_pie = px.pie(
                status_counts, names="الحالة", values="العدد",
                title="توزيع الحالات - آخر 7 أيام",
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"}
            )
            fig_pie.update_layout(font=dict(family="Cairo"))
            st.plotly_chart(fig_pie, use_container_width=True)
            charts_to_export.append((fig_pie, "توزيع الحالات"))
        else:
            st.info("لا توجد بيانات للأيام السبعة الماضية.")
    
    elif report_type == "تقرير الحضور الشهري (شهر محدد)":
        report_title = "تقرير الحضور الشهري"
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            month = st.selectbox("الشهر", range(1, 13), index=get_cairo_now().month - 1)
        with col_m2:
            year = st.number_input("السنة", value=get_cairo_now().year, min_value=2020, max_value=2100)
        
        monthly = filtered_attendance[
            (filtered_attendance["date"].dt.month == month) &
            (filtered_attendance["date"].dt.year == year)
        ].copy()
        
        if not monthly.empty:
            # Student-level summary
            student_summary = monthly.groupby(["student_id", "full_name", "status"]).size().reset_index(name="عدد الأيام")
            student_pivot = student_summary.pivot(index=["student_id", "full_name"], columns="status", values="عدد الأيام").fillna(0).reset_index()
            student_pivot.columns.name = None
            
            # Rename columns
            student_pivot = student_pivot.rename(columns={"full_name": "اسم الطالبة"})
            if "student_id" in student_pivot.columns:
                student_pivot = student_pivot.drop(columns=["student_id"])
            
            # Add total
            status_cols = [c for c in student_pivot.columns if c != "اسم الطالبة"]
            if status_cols:
                student_pivot["إجمالي الأيام"] = student_pivot[status_cols].sum(axis=1)
            
            report_df = student_pivot
            
            # Bar chart comparing sections
            if "section_id" in monthly.columns:
                section_attendance = monthly.groupby(["section_id", "status"]).size().reset_index(name="العدد")
                section_pivot = section_attendance.pivot(index="section_id", columns="status", values="العدد").fillna(0).reset_index()
                section_pivot.columns.name = None
                
                if not sections.empty and "section_id" in sections.columns:
                    section_pivot = section_pivot.merge(
                        sections[["section_id", "section_name"]], on="section_id", how="left"
                    )
                    section_pivot["section_id"] = section_pivot["section_name"].fillna(section_pivot["section_id"])
                
                fig_bar = px.bar(
                    section_pivot, x="section_id",
                    y=[c for c in ["حاضر", "غائب", "متأخر"] if c in section_pivot.columns],
                    title=f"مقارنة بين الفصول - شهر {month}/{year}",
                    barmode="group",
                    color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"}
                )
                fig_bar.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    xaxis_title="الفصل", yaxis_title="العدد",
                    font=dict(family="Cairo")
                )
                st.plotly_chart(fig_bar, use_container_width=True)
                charts_to_export.append((fig_bar, "مقارنة الفصول"))
            
            # Pie chart
            status_counts = monthly["status"].value_counts().reset_index()
            status_counts.columns = ["الحالة", "العدد"]
            fig_pie = px.pie(
                status_counts, names="الحالة", values="العدد",
                title=f"توزيع الحالات - شهر {month}/{year}",
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"}
            )
            fig_pie.update_layout(font=dict(family="Cairo"))
            st.plotly_chart(fig_pie, use_container_width=True)
            charts_to_export.append((fig_pie, "توزيع الحالات"))
        else:
            st.info(f"لا توجد بيانات للشهر {month}/{year}.")
    
    elif report_type == "تقرير الأعضاء الجدد (آخر 30 يوم)":
        report_title = "تقرير الأعضاء الجدد"
        thirty_days_ago = get_cairo_now().date() - timedelta(days=30)
        
        # New students
        new_students = pd.DataFrame()
        if not students.empty:
            if "created_by" in students.columns:
                # Try to find creation date from attendance first record
                student_ids = students["student_id"].tolist()
                first_attendance = attendance[attendance["student_id"].isin(student_ids)].copy()
                if not first_attendance.empty:
                    first_dates = first_attendance.groupby("student_id")["date"].min().reset_index()
                    first_dates.columns = ["student_id", "first_date"]
                    new_students = students.merge(first_dates, on="student_id", how="inner")
                    new_students = new_students[new_students["first_date"].dt.date >= thirty_days_ago]
                else:
                    # No attendance records, show all students as new
                    new_students = students.copy()
                    new_students["first_date"] = get_cairo_now()
            else:
                # No created_by column, use first attendance date
                student_ids = students["student_id"].tolist()
                first_attendance = attendance[attendance["student_id"].isin(student_ids)].copy()
                if not first_attendance.empty:
                    first_dates = first_attendance.groupby("student_id")["date"].min().reset_index()
                    first_dates.columns = ["student_id", "first_date"]
                    new_students = students.merge(first_dates, on="student_id", how="inner")
                    new_students = new_students[new_students["first_date"].dt.date >= thirty_days_ago]
        
        if not new_students.empty:
            new_students["first_date_str"] = new_students["first_date"].dt.strftime("%Y-%m-%d")
            report_df = new_students[["full_name", "phone", "section_id", "first_date_str"]].rename(
                columns={"full_name": "الاسم", "phone": "الهاتف", "section_id": "الفصل", "first_date_str": "تاريخ أول حضور"}
            )
            
            # Add section names
            if not sections.empty and "section_id" in sections.columns:
                report_df = report_df.merge(
                    sections[["section_id", "section_name"]],
                    left_on="الفصل", right_on="section_id", how="left"
                )
                report_df["الفصل"] = report_df["section_name"].fillna(report_df["الفصل"])
                report_df = report_df.drop(columns=["section_id"], errors="ignore")
            
            st.success(f"✅ تم إضافة {len(new_students)} أعضاء جدد في آخر 30 يوم")
            
            # Bar chart for new members by section
            if not report_df.empty and "الفصل" in report_df.columns:
                section_counts = report_df["الفصل"].value_counts().reset_index()
                section_counts.columns = ["الفصل", "العدد"]
                fig_bar = px.bar(
                    section_counts, x="الفصل", y="العدد",
                    title="الأعضاء الجدد حسب الفصل",
                    color="العدد", color_continuous_scale="Viridis"
                )
                fig_bar.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(family="Cairo")
                )
                st.plotly_chart(fig_bar, use_container_width=True)
                charts_to_export.append((fig_bar, "أعضاء جدد حسب الفصل"))
        else:
            st.info("لا يوجد أعضاء جدد في آخر 30 يوم.")
    
    elif report_type == "تقرير الأعضاء الغائبين (أكثر من 3 أيام)":
        report_title = "تقرير الأعضاء الغائبين"
        month_start = get_cairo_now().replace(day=1).date()
        month_attendance = filtered_attendance[filtered_attendance["date"].dt.date >= month_start].copy()
        
        if not month_attendance.empty and "status" in month_attendance.columns:
            # Count absences per student
            absent_counts = month_attendance[month_attendance["status"] == "غائب"].groupby(
                ["student_id", "full_name"]
            ).size().reset_index(name="أيام الغياب")
            
            absent_counts = absent_counts[absent_counts["أيام الغياب"] > 3].sort_values("أيام الغياب", ascending=False)
            
            if not absent_counts.empty:
                report_df = absent_counts.rename(columns={"full_name": "اسم الطالبة", "أيام الغياب": "أيام الغياب"})
                
                # Add section info
                if not students.empty and "section_id" in students.columns:
                    report_df = report_df.merge(
                        students[["student_id", "section_id"]], on="student_id", how="left"
                    )
                    if not sections.empty and "section_id" in sections.columns:
                        report_df = report_df.merge(
                            sections[["section_id", "section_name"]], on="section_id", how="left"
                        )
                        report_df["الفصل"] = report_df["section_name"].fillna("")
                        report_df = report_df.drop(columns=["section_id", "section_name"], errors="ignore")
                    else:
                        report_df["الفصل"] = report_df.get("section_id", "")
                        report_df = report_df.drop(columns=["section_id"], errors="ignore")
                
                report_df = report_df.drop(columns=["student_id"], errors="ignore")
                
                st.warning(f"⚠️ يوجد {len(absent_counts)} طالبة غائبة أكثر من 3 أيام هذا الشهر")
                
                # Bar chart
                fig_bar = px.bar(
                    absent_counts.head(15), x="full_name", y="أيام الغياب",
                    title="أكثر الطالبات غياباً (أكثر من 3 أيام)",
                    color="أيام الغياب", color_continuous_scale="Reds"
                )
                fig_bar.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    xaxis_title="الطالبة", yaxis_title="أيام الغياب",
                    font=dict(family="Cairo")
                )
                st.plotly_chart(fig_bar, use_container_width=True)
                charts_to_export.append((fig_bar, "الطالبات الغائبات"))
            else:
                st.success("✅ لا توجد طالبات غائبات أكثر من 3 أيام هذا الشهر.")
        else:
            st.info("لا توجد بيانات كافية.")
    
    # =========================================================================
    # DISPLAY REPORT TABLE
    # =========================================================================
    if not report_df.empty:
        st.markdown("#### 📊 بيانات التقرير")
        st.dataframe(report_df, use_container_width=True)
    
    # =========================================================================
    # INTERACTIVE CHARTS SECTION
    # =========================================================================
    st.markdown("---")
    st.markdown("### 📈 الرسوم البيانية التفاعلية")
    
    tab_chart1, tab_chart2, tab_chart3 = st.tabs([
        "📈 الحضور عبر الزمن", "📊 مقارنة بين الفصول", "🥧 توزيع الحالات"
    ])
    
    with tab_chart1:
        # Line chart: attendance over time (last 30 days)
        thirty_days_ago = get_cairo_now().date() - timedelta(days=30)
        last_30 = filtered_attendance[filtered_attendance["date"].dt.date >= thirty_days_ago].copy()
        
        if not last_30.empty:
            daily = last_30.groupby([last_30["date"].dt.date, "status"]).size().reset_index(name="العدد")
            fig_line = px.line(
                daily, x="date", y="العدد", color="status",
                title="الحضور عبر الزمن - آخر 30 يوم",
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"},
                markers=True
            )
            fig_line.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title="التاريخ", yaxis_title="العدد",
                font=dict(family="Cairo"),
                hovermode="x unified"
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية لآخر 30 يوم.")
    
    with tab_chart2:
        # Bar chart: compare sections
        if not filtered_attendance.empty and "section_id" in filtered_attendance.columns:
            section_comp = filtered_attendance.groupby(["section_id", "status"]).size().reset_index(name="العدد")
            section_pivot = section_comp.pivot(index="section_id", columns="status", values="العدد").fillna(0).reset_index()
            section_pivot.columns.name = None
            
            if not sections.empty and "section_id" in sections.columns:
                section_pivot = section_pivot.merge(
                    sections[["section_id", "section_name"]], on="section_id", how="left"
                )
                section_pivot["الفصل"] = section_pivot["section_name"].fillna(section_pivot["section_id"])
            else:
                section_pivot["الفصل"] = section_pivot["section_id"]
            
            fig_bar = px.bar(
                section_pivot, x="الفصل",
                y=[c for c in ["حاضر", "غائب", "متأخر"] if c in section_pivot.columns],
                title="مقارنة الحضور بين الفصول",
                barmode="group",
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"}
            )
            fig_bar.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title="الفصل", yaxis_title="العدد",
                font=dict(family="Cairo"),
                legend_title="الحالة"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية للمقارنة بين الفصول.")
    
    with tab_chart3:
        # Pie chart: status distribution
        if not filtered_attendance.empty and "status" in filtered_attendance.columns:
            status_counts = filtered_attendance["status"].value_counts().reset_index()
            status_counts.columns = ["الحالة", "العدد"]
            
            fig_pie = px.pie(
                status_counts, names="الحالة", values="العدد",
                title="توزيع الحالات (حاضر / غائب / متأخر)",
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"},
                hole=0.3
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(font=dict(family="Cairo"))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية لتوزيع الحالات.")
    
    # =========================================================================
    # EXPORT BUTTONS
    # =========================================================================
    if not report_df.empty:
        st.markdown("---")
        st.markdown("### 📥 تصدير التقرير")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            # CSV Export
            csv_bytes = _export_to_csv_bytes(report_df)
            st.download_button(
                label="📄 تصدير CSV",
                data=csv_bytes,
                file_name=f"{report_title}_{get_cairo_now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="export_csv_btn"
            )
        
        with col_exp2:
            # Excel Export
            excel_bytes = _export_to_excel_with_charts(report_title, report_df, charts_to_export)
            st.download_button(
                label="📗 تصدير Excel مع الرسوم البيانية",
                data=excel_bytes,
                file_name=f"{report_title}_{get_cairo_now().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="export_excel_btn"
            )
    
    # =========================================================================
    # EVENT REPORT (if events data available)
    # =========================================================================
    if not filtered_events.empty and event_type_filter != "الكل":
        st.markdown("---")
        st.markdown("### 📅 تقرير الفعاليات")
        st.dataframe(filtered_events[["event_name", "event_type", "event_date", "location", "status"]].rename(
            columns={
                "event_name": "اسم الفعالية", "event_type": "النوع",
                "event_date": "التاريخ", "location": "المكان", "status": "الحالة"
            }
        ), use_container_width=True)


# =============================================================================
# Events Management
# ==============================================================================
def inject_events_css():
    st.markdown("""
    <style>
        .event-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.05);
            position: relative; overflow: hidden; transition: all 0.3s ease;
        }
        .event-card:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(0,0,0,0.12); }
        .event-badge {
            display: inline-block; padding: 0.25rem 0.75rem; border-radius: 20px;
            font-size: 0.75rem; font-weight: 600;
        }
        .event-badge.meeting { background: #cce5ff; color: #004085; }
        .event-badge.service { background: #d4edda; color: #155724; }
        .event-badge.trip { background: #fff3cd; color: #856404; }
        .event-badge.celebration { background: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_html=True)


def get_event_type_label(event_type):
    labels = {"اجتماع": "اجتماع", "خدمة": "خدمة", "رحلة": "رحلة", "احتفال": "احتفال"}
    return labels.get(event_type, event_type)


def get_event_type_css(event_type):
    css_map = {"اجتماع": "meeting", "خدمة": "service", "رحلة": "trip", "احتفال": "celebration"}
    return css_map.get(event_type, "meeting")


def show_upcoming_events(db, user, role):
    """عرض الفعاليات القادمة مع خيار التسجيل (RSVP)"""
    events = db.get_events()
    if events.empty or "event_date" not in events.columns:
        st.info("لا توجد فعاليات مسجلة.")
        return pd.DataFrame()

    today_str = get_cairo_now().strftime("%Y-%m-%d")
    events["event_date_clean"] = pd.to_datetime(events["event_date"], errors="coerce").dt.date
    upcoming = events[events["event_date_clean"] >= pd.to_datetime(today_str).date()].copy()

    if upcoming.empty:
        st.info("لا توجد فعاليات قادمة.")
        return pd.DataFrame()

    event_type_filter = st.selectbox("تصفية حسب النوع", ["الكل"] + EVENT_TYPES)
    if event_type_filter != "الكل" and "event_type" in upcoming.columns:
        upcoming = upcoming[upcoming.event_type == event_type_filter]

    if upcoming.empty:
        st.info("لا توجد فعاليات مطابقة.")
        return pd.DataFrame()

    for _, ev in upcoming.iterrows():
        ev_id = ev.get("event_id", "")
        ev_name = ev.get("event_name", "بدون اسم")
        ev_type = ev.get("event_type", "")
        ev_date = ev.get("event_date", "")
        ev_time = ev.get("event_time", "")
        ev_location = ev.get("location", "")
        ev_capacity = ev.get("max_capacity", "")
        ev_desc = ev.get("description", "")

        type_label = get_event_type_label(ev_type)
        type_css = get_event_type_css(ev_type)

        st.markdown(f"""
        <div class='event-card'>
            <span class='event-badge {type_css}'>{type_label}</span>
            <h3 style='margin-top:0.5rem;'>{ev_name}</h3>
            <p>📅 {ev_date} | ⏰ {ev_time}</p>
            <p>📍 {ev_location}</p>
            <p>👥 السعة القصوى: {ev_capacity}</p>
            <p>📝 {ev_desc}</p>
        </div>
        """, unsafe_allow_html=True)

        # RSVP for non-admin users
        if role not in ["System Admin", "Father Account"]:
            rsvp_df = db.get_event_rsvps(ev_id)
            already_rsvped = False
            if not rsvp_df.empty and "student_id" in rsvp_df.columns:
                student_id = user.get("user_id", "")
                already_rsvped = not rsvp_df[rsvp_df.student_id == student_id].empty

            if already_rsvped:
                rsvp_row = rsvp_df[rsvp_df.student_id == user.get("user_id", "")]
                rsvp_status = rsvp_row.iloc[0].get("rsvp_status", "") if not rsvp_row.empty else ""
                st.success(f"✅ تم تسجيل حضورك المتوقع: {rsvp_status}")
            else:
                if st.button("📝 تسجيل حضور متوقع", key=f"rsvp_{ev_id}", use_container_width=True):
                    st.session_state[f"rsvp_event_{ev_id}"] = True
                    st.rerun()

            if st.session_state.get(f"rsvp_event_{ev_id}", False):
                with st.form(f"rsvp_form_{ev_id}"):
                    rsvp_status = st.selectbox("حالة الحضور", RSVP_STATUSES)
                    submitted = st.form_submit_button("حفظ", use_container_width=True)
                    if submitted:
                        db.add_event_rsvp({
                            "rsvp_id": str(uuid.uuid4()),
                            "event_id": ev_id,
                            "student_id": user.get("user_id", ""),
                            "student_name": user.get("full_name", ""),
                            "rsvp_status": rsvp_status,
                            "rsvp_date": get_cairo_now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        st.success("✅ تم تسجيل الحضور المتوقع")
                        st.session_state[f"rsvp_event_{ev_id}"] = False
                        time.sleep(1)
                        st.rerun()

        st.markdown("---")

    return upcoming


def add_event_form(db, user):
    """نموذج إضافة فعالية جديدة"""
    st.subheader("➕ إضافة فعالية جديدة")
    with st.form("add_event_form"):
        col1, col2 = st.columns(2)
        with col1:
            event_name = st.text_input("اسم الفعالية*")
            event_type = st.selectbox("نوع الفعالية", EVENT_TYPES)
            event_date = st.date_input("التاريخ", get_cairo_now().date())
            event_time = st.text_input("الوقت", placeholder="مثال: 05:00 م")
        with col2:
            location = st.text_input("المكان*")
            max_capacity = st.number_input("السعة القصوى", min_value=1, value=50)
        description = st.text_area("الوصف")
        submitted = st.form_submit_button("💾 حفظ الفعالية", use_container_width=True)
        if submitted:
            if not event_name or not location:
                st.error("يرجى ملء اسم الفعالية والمكان")
            else:
                event_id = str(uuid.uuid4())
                db.add_event({
                    "event_id": event_id,
                    "event_name": event_name.strip(),
                    "event_type": event_type,
                    "event_date": event_date.strftime("%Y-%m-%d"),
                    "event_time": event_time,
                    "location": location.strip(),
                    "max_capacity": str(max_capacity),
                    "description": description.strip(),
                    "created_by": user.get("user_id", ""),
                    "status": "upcoming"
                })
                st.success("✅ تمت إضافة الفعالية بنجاح")
                time.sleep(1)
                st.rerun()


def show_event_actual_attendance(db, user):
    """تسجيل الحضور الفعلي للفعاليات المنتهية مع ملخص إحصائي"""
    st.subheader("📊 تسجيل الحضور الفعلي")
    events = db.get_events()
    if events.empty or "event_date" not in events.columns:
        st.info("لا توجد فعاليات مسجلة.")
        return

    today_str = get_cairo_now().strftime("%Y-%m-%d")
    events["event_date_clean"] = pd.to_datetime(events["event_date"], errors="coerce").dt.date
    past = events[events["event_date_clean"] < pd.to_datetime(today_str).date()].copy()

    if past.empty:
        st.info("لا توجد فعاليات منتهية لتسجيل الحضور الفعلي.")
        return

    event_options = past["event_id"].tolist()
    selected_event = st.selectbox(
        "اختر الفعالية", event_options,
        format_func=lambda x: past[past.event_id == x]["event_name"].values[0]
    )

    if not selected_event:
        return

    # Get RSVPs and students
    rsvp_df = db.get_event_rsvps(selected_event)
    existing_attendance = db.get_event_attendance(selected_event)
    students = db.get_students()

    already_recorded = not existing_attendance.empty
    if already_recorded:
        st.warning("⚠️ تم تسجيل الحضور الفعلي مسبقاً")
        st.info("سيتم إعادة حفظ الحضور الجديد محل القديم.")

    st.markdown("#### اختر الحاضرات فعلياً")

    # Build options from RSVP list or all students
    options = []
    labels = []
    if not rsvp_df.empty and not students.empty:
        merged = rsvp_df.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        options = merged["student_id"].tolist()
        labels = merged.apply(
            lambda row: f"{row['full_name']} ({row['rsvp_status']})" if row['full_name'] else row['student_id'],
            axis=1
        ).tolist()

    if not options:
        st.info("لا توجد تسجيلات حضور متوقع لهذه الفعالية.")
        return

    selected = st.multiselect(
        "الطالبات الحاضرات",
        options=options,
        format_func=lambda x: labels[options.index(x)] if x in options else x
    )

    if st.button("💾 حفظ الحضور الفعلي", use_container_width=True):
        # Remove old records if any
        if already_recorded:
            for _, rec in existing_attendance.iterrows():
                db.delete_event_attendance(rec["record_id"])

        for sid in selected:
            db.add_event_attendance({
                "record_id": str(uuid.uuid4()),
                "event_id": selected_event,
                "student_id": sid,
                "status": "حاضر",
                "notes": ""
            })
        # Add absent records for RSVPed but not present
        for _, row in rsvp_df.iterrows():
            sid = row["student_id"]
            if sid not in selected:
                db.add_event_attendance({
                    "record_id": str(uuid.uuid4()),
                    "event_id": selected_event,
                    "student_id": sid,
                    "status": "غائب",
                    "notes": ""
                })
        st.success(f"✅ تم تسجيل حضور {len(selected)} طالبة")
        time.sleep(1)
        st.rerun()

    st.markdown("---")
    st.subheader("📈 ملخص إحصائي")
    event_row = past[past.event_id == selected_event].iloc[0].to_dict()
    max_cap = int(event_row.get("max_capacity", 0) or 0)
    total_rsvp = len(rsvp_df)

    # Reload attendance records for summary
    attendance_df = db.get_event_attendance(selected_event)
    total_present = len(attendance_df[attendance_df["status"] == "حاضر"]) if not attendance_df.empty else 0
    total_absent = len(attendance_df[attendance_df["status"] == "غائب"]) if not attendance_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("المسجلين (RSVP)", total_rsvp)
    c2.metric("الحاضرين فعلياً", total_present)
    c3.metric("الغائبين", total_absent)
    c4.metric("السعة القصوى", max_cap)

    # Show detailed table
    if not attendance_df.empty and not students.empty:
        detail = attendance_df.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(detail[["full_name", "status", "notes"]].rename(
            columns={"full_name": "الاسم", "status": "الحالة", "notes": "ملاحظات"}
        ), use_container_width=True)


def show_events_page(db):
    """الصفحة الرئيسية لإدارة الفعاليات"""
    inject_events_css()
    st.markdown("<h2 class='main-header'>📅 إدارة الفعاليات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    user_id = user.get("user_id", "")

    if role not in ["System Admin", "Father Account", "Service Manager", "Teacher", "Student"]:
        st.error("🚫 غير مصرح")
        return

    tab1, tab2, tab3 = st.tabs(["📋 الفعاليات القادمة", "➕ إضافة فعالية", "📊 سجل الحضور الفعلي"])

    with tab1:
        show_upcoming_events(db, user, role)

    with tab2:
        if role in ["System Admin", "Service Manager", "Teacher"]:
            add_event_form(db, user)
        else:
            st.info("👁️ يمكنك فقط مشاهدة الفعاليات")

    with tab3:
        show_event_actual_attendance(db, user)


# =============================================================================
# User Card Helpers
# ==============================================================================
def get_role_css_class(role):
    role_map = {"System Admin": "admin", "Father Account": "priest", "Service Manager": "leader", "Teacher": "teacher", "Student": "student"}
    return role_map.get(role, "")

def get_status_css_class(status):
    return "active" if status in ["active", ""] else str(status).lower()

def get_initials(name):
    if not name or pd.isna(name):
        return "❓"
    parts = str(name).strip().split()
    if len(parts) >= 2:
        return parts[0][0] + parts[1][0]
    return parts[0][0] if parts[0] else "❓"

def render_user_card(user, sections_df=None, stages_df=None, is_selected=False, db=None):
    user_id = user.get("user_id", "")
    full_name = user.get("full_name", "غير معروف")
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    phone = user.get("phone", "")
    email = user.get("email", "")
    status = get_user_status(user)
    initials = get_initials(full_name)
    role_css = get_role_css_class(role)
    status_css = get_status_css_class(status)
    section_name = ""
    if sections_df is not None and not sections_df.empty and section_id:
        sec = sections_df[sections_df.section_id == section_id]
        if not sec.empty:
            section_name = sec.iloc[0].get("section_name", "")
    stage_name = ""
    if stages_df is not None and not stages_df.empty and section_id:
        sec = sections_df[sections_df.section_id == section_id] if sections_df is not None else pd.DataFrame()
        if not sec.empty:
            stage_id = sec.iloc[0].get("stage_id", "")
            if stage_id:
                stage = stages_df[stages_df.stage_id == stage_id]
                if not stage.empty:
                    stage_name = stage.iloc[0].get("stage_name", "")
    role_label = {"System Admin": "مدير النظام", "Father Account": "أب كاهن", "Service Manager": "أمين الخدمة", "Teacher": "مدرسة", "Student": "طالبة"}.get(role, role)
    status_label = {"active": "نشط", "inactive": "غير نشط", "suspended": "موقوف", "archived": "مؤرشف"}.get(status, "نشط")
    border = "2px solid #667eea" if is_selected else "1px solid rgba(0,0,0,0.05)"
    reg_date = user.get("registration_date", "")
    if reg_date:
        try:
            reg_date = pd.to_datetime(reg_date).strftime("%Y-%m-%d")
        except:
            reg_date = ""
    last_login = user.get("last_login", "")
    if last_login:
        try:
            last_login = pd.to_datetime(last_login).strftime("%Y-%m-%d %I:%M %p")
        except:
            last_login = ""
    return f"""
    <div class="user-card" style="border: {border};" data-user-id="{user_id}">
        <div class="card-badge {status_css}">{status_label}</div>
        <div style="display:flex; align-items:center; gap:1rem; margin-top:1.5rem;">
            <div class="user-avatar">{initials}</div>
            <div style="flex:1;">
                <div style="font-weight:700; font-size:1.1rem;">{full_name}</div>
                <span class="role-badge {role_css}">{role_label}</span>
                <div style="font-size:0.8rem; color:#6c757d; margin-top:0.3rem;">📞 {phone if phone else '—'}</div>
            </div>
        </div>
        <div style="margin-top:1rem; padding:0.8rem; background:rgba(102,126,234,0.05); border-radius:10px;">
            {('<div style="font-size:0.85rem; margin-bottom:0.3rem;">📚 <strong>المرحلة:</strong> ' + stage_name + '</div>') if stage_name else ''}
            {('<div style="font-size:0.85rem; margin-bottom:0.3rem;">🏫 <strong>الفصل:</strong> ' + section_name + '</div>') if section_name else ''}
            <div style="font-size:0.8rem; color:#6c757d;">📅 التسجيل: {reg_date if reg_date else 'غير متاح'}</div>
            <div style="font-size:0.8rem; color:#6c757d;">⏰ آخر دخول: {last_login if last_login else 'غير متاح'}</div>
        </div>
        <div style="display:flex; gap:0.5rem; margin-top:0.8rem; flex-wrap:wrap; align-items:center;">
            <span style="font-size:0.75rem; background:#f8f9fa; padding:0.2rem 0.6rem; border-radius:8px;">🆔 {user_id[:12]}...</span>
            {('<span style="font-size:0.75rem; background:#f8f9fa; padding:0.2rem 0.6rem; border-radius:8px;">📧 ' + email[:25] + '</span>') if email else ''}
        </div>
    </div>
    """

def filter_users_df(df, search_term="", role_filter="الكل", status_filter="الكل", section_filter="الكل"):
    filtered = df.copy()
    if search_term:
        search_mask = pd.Series(False, index=filtered.index)
        for col in ["full_name", "username", "phone", "email"]:
            if col in filtered.columns:
                search_mask |= filtered[col].astype(str).str.contains(search_term, na=False, case=False)
        filtered = filtered[search_mask]
    if role_filter != "الكل" and "role" in filtered.columns:
        filtered = filtered[filtered["role"] == role_filter]
    if status_filter != "الكل":
        if "status" in filtered.columns:
            st_map = {"نشط": "active", "غير نشط": "inactive", "موقوف": "suspended", "مؤرشف": "archived"}
            eng_status = st_map.get(status_filter, status_filter)
            filtered = filtered[filtered["status"] == eng_status]
        else:
            eng_status = "active" if status_filter == "نشط" else "inactive"
            filtered = filtered[filtered.get("status", "active") == eng_status]
    if section_filter != "الكل" and "section_id" in filtered.columns:
        filtered = filtered[filtered["section_id"] == section_filter]
    return filtered


# =============================================================================
# Student Profile Page
# ==============================================================================
def show_student_profile(db, student_id):
    students_df = db.get_students()
    student_row = students_df[students_df.student_id == student_id]
    if student_row.empty:
        st.error("لم يتم العثور على الطالبة")
        if st.button("🔙 العودة"):
            st.session_state.profile_user_id = None
            st.rerun()
        return
    
    student = student_row.iloc[0].to_dict()
    sections = db.get_sections()
    user = st.session_state.user
    role = user.get("role", "")
    
    # Get section name
    section_name = ""
    sec_id = student.get("section_id", "")
    if not sections.empty and sec_id:
        sec_match = sections[sections["section_id"] == sec_id]
        if not sec_match.empty:
            section_name = sec_match.iloc[0].get("section_name", "")
    
    full_name = student.get("full_name", "غير معروف")
    initials = get_initials(full_name)
    status = student.get("status", "active")
    status_label = {"active": "نشطة", "inactive": "غير نشطة"}.get(status, "نشطة")
    
    st.markdown(f"""
    <div class="profile-header">
        <div style="display:flex; align-items:center; gap:2rem;">
            <div style="width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,0.2); display:flex;align-items:center;justify-content:center;font-size:2.5rem;font-weight:700;">{initials}</div>
            <div>
                <h1 style="margin:0;font-size:1.8rem;">{full_name}</h1>
                <p style="margin:0.3rem 0;opacity:0.9;">طالبة</p>
                <p style="margin:0;opacity:0.8;font-size:0.85rem;">🆔 {student_id[:12]}...</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown('<div class="profile-stat-card">', unsafe_allow_html=True)
        st.markdown(f"<h3>{status_label}</h3>", unsafe_allow_html=True)
        st.markdown("<p>📌 الحالة</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="profile-stat-card">', unsafe_allow_html=True)
        birthdate = student.get("birthdate", "")
        age = get_student_age(birthdate)
        st.markdown(f"<h3>{age if age else '—'}</h3>", unsafe_allow_html=True)
        st.markdown("<p>🎂 العمر</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="profile-stat-card">', unsafe_allow_html=True)
        st.markdown(f"<h3>{section_name or '—'}</h3>", unsafe_allow_html=True)
        st.markdown("<p>🏫 الفصل</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with st.expander("📋 المعلومات الشخصية", expanded=True):
        info_cols = st.columns(2)
        with info_cols[0]:
            st.markdown(f"**👤 الاسم الكامل:** {full_name}")
            st.markdown(f"**📱 الهاتف:** {student.get('phone', '—') or '—'}")
            st.markdown(f"**📱 رقم ولي الأمر:** {student.get('parent_phone', '—') or '—'}")
            st.markdown(f"**🎂 تاريخ الميلاد:** {birthdate or '—'}")
        with info_cols[1]:
            st.markdown(f"**🏫 الفصل:** {section_name or '—'}")
            st.markdown(f"**🏫 المدرسة:** {student.get('school', '—') or '—'}")
            st.markdown(f"**📍 العنوان:** {student.get('address', '—') or '—'}")
            st.markdown(f"**📌 الحالة:** {status_label}")
    
    if student.get("notes"):
        with st.expander("📝 ملاحظات"):
            st.write(student.get("notes", ""))
    
    st.markdown("---")
    
    # Action buttons based on role
    if role in ["System Admin", "Service Manager"]:
        act_col1, act_col2, act_col3 = st.columns(3)
        with act_col1:
            if st.button("✏️ تعديل", use_container_width=True):
                st.session_state.edit_student_id = student_id
                st.session_state.profile_user_id = None
                st.rerun()
        with act_col2:
            if status == "active":
                if st.button("⏸️ تعطيل", use_container_width=True):
                    db.update_student(student_id, {"status": "inactive"})
                    db.add_log(user.get("user_id", ""), f"تعطيل طالبة {student_id}", f"تم تعطيل {full_name}")
                    st.success("✅ تم التعطيل")
                    time.sleep(1)
                    st.rerun()
            else:
                if st.button("▶️ تفعيل", use_container_width=True):
                    db.update_student(student_id, {"status": "active"})
                    db.add_log(user.get("user_id", ""), f"تفعيل طالبة {student_id}", f"تم تفعيل {full_name}")
                    st.success("✅ تم التفعيل")
                    time.sleep(1)
                    st.rerun()
        with act_col3:
            if st.button("🗑️ حذف", use_container_width=True):
                db.delete_student(student_id)
                db.add_log(user.get("user_id", ""), f"حذف طالبة {student_id}", f"تم حذف {full_name}")
                st.success("✅ تم الحذف")
                st.session_state.profile_user_id = None
                time.sleep(1)
                st.rerun()
    elif role == "Teacher":
        st.info("👁️ وضع العرض فقط - لا يمكنك التعديل على بيانات الطالبات")
    
    if st.button("🔙 العودة", use_container_width=True):
        st.session_state.profile_user_id = None
        st.rerun()
    
    # Edit form for System Admin and Service Manager
    if role in ["System Admin", "Service Manager"] and st.session_state.get("edit_student_id") == student_id:
        st.markdown("---")
        with st.expander("✏️ تعديل بيانات الطالبة", expanded=True):
            with st.form("edit_student_profile_form"):
                edit_name = st.text_input("الاسم الكامل*", value=full_name)
                edit_phone = st.text_input("الهاتف", value=student.get("phone", ""))
                edit_parent_phone = st.text_input("رقم ولي الأمر", value=student.get("parent_phone", ""))
                bd_value = pd.to_datetime(birthdate).date() if birthdate else None
                edit_birthdate = st.date_input("تاريخ الميلاد", value=bd_value)
                edit_address = st.text_input("العنوان", value=student.get("address", ""))
                edit_school = st.text_input("المدرسة", value=student.get("school", ""))
                edit_notes = st.text_area("ملاحظات", value=student.get("notes", ""))
                
                sec_options = sections["section_id"].tolist() if not sections.empty else []
                current_sec = sec_id if sec_id in sec_options else (sec_options[0] if sec_options else "")
                edit_section = st.selectbox("الفصل", sec_options, 
                                           index=sec_options.index(current_sec) if current_sec in sec_options else 0,
                                           format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0]) if sec_options else ""
                
                edit_status = st.selectbox("الحالة", ["نشطة", "غير نشطة"], index=0 if status == "active" else 1)
                
                if st.form_submit_button("💾 حفظ التعديلات"):
                    db.update_student(student_id, {
                        "full_name": edit_name,
                        "phone": edit_phone,
                        "section_id": edit_section,
                        "parent_phone": edit_parent_phone,
                        "birthdate": edit_birthdate.strftime("%Y-%m-%d") if edit_birthdate else "",
                        "address": edit_address,
                        "school": edit_school,
                        "notes": edit_notes,
                        "status": "active" if edit_status == "نشطة" else "inactive"
                    })
                    db.add_log(user.get("user_id", ""), "تعديل طالبة", f"تم تعديل {edit_name}")
                    st.session_state.edit_student_id = None
                    st.success("✅ تم التحديث")
                    time.sleep(1)
                    st.rerun()


# =============================================================================
# User Profile Page
# =============================================================================
def show_user_profile(db, user_id):
    users_df = db.get_users()
    user_row = users_df[users_df.user_id == user_id]
    if user_row.empty:
        st.error("لم يتم العثور على المستخدم")
        if st.button("🔙 العودة"):
            st.session_state.profile_user_id = None
            st.rerun()
        return
    user = user_row.iloc[0].to_dict()
    sections = db.get_sections()
    stages = db.get_stages()
    logs = db.get_logs()
    user_logs = logs[logs.user_id == user_id] if not logs.empty and "user_id" in logs.columns else pd.DataFrame()
    section_name = ""
    if not sections.empty:
        sec = sections[sections.section_id == user.get("section_id", "")]
        section_name = sec.iloc[0]["section_name"] if not sec.empty else ""
    initials = get_initials(user.get("full_name", ""))
    role = user.get("role", "")
    role_label = {"System Admin": "مدير النظام", "Father Account": "أب كاهن", "Service Manager": "أمين الخدمة", "Teacher": "مدرسة"}.get(role, role)
    status = get_user_status(user)
    status_label = {"active": "نشط", "inactive": "غير نشط", "suspended": "موقوف", "archived": "مؤرشف"}.get(status, "نشط")
    st.markdown(f"""
    <div class="profile-header">
        <div style="display:flex; align-items:center; gap:2rem;">
            <div style="width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,0.2); display:flex;align-items:center;justify-content:center;font-size:2.5rem;font-weight:700;">{initials}</div>
            <div>
                <h1 style="margin:0;font-size:1.8rem;">{user.get('full_name', '')}</h1>
                <p style="margin:0.3rem 0;opacity:0.9;">{role_label}</p>
                <p style="margin:0;opacity:0.8;font-size:0.85rem;">🆔 {user.get('user_id', '')[:12]}... | 📅 تاريخ التسجيل: {user.get('registration_date', get_cairo_now().strftime('%Y-%m-%d'))[:10]}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown('<div class="profile-stat-card">', unsafe_allow_html=True)
        st.markdown(f"<h3>{len(user_logs)}</h3>", unsafe_allow_html=True)
        st.markdown("<p>📋 نشاطات</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="profile-stat-card">', unsafe_allow_html=True)
        now = get_cairo_now()
        if user.get("birthdate"):
            try:
                age = now.year - pd.to_datetime(user["birthdate"]).year
                st.markdown(f"<h3>{age}</h3>", unsafe_allow_html=True)
                st.markdown("<p>🎂 العمر</p>", unsafe_allow_html=True)
            except:
                st.markdown("<h3>—</h3>", unsafe_allow_html=True)
                st.markdown("<p>🎂 العمر</p>", unsafe_allow_html=True)
        else:
            st.markdown("<h3>—</h3>", unsafe_allow_html=True)
            st.markdown("<p>🎂 العمر</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="profile-stat-card">', unsafe_allow_html=True)
        st.markdown(f'<h3><span class="status-badge {status}">{status_label}</span></h3>', unsafe_allow_html=True)
        st.markdown("<p>📌 الحالة</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with st.expander("📋 المعلومات الشخصية", expanded=True):
        info_cols = st.columns(2)
        with info_cols[0]:
            st.markdown(f"**👤 الاسم الكامل:** {user.get('full_name', '')}")
            st.markdown(f"**👤 اسم المستخدم:** {user.get('username', '')}")
            st.markdown(f"**📱 الهاتف:** {user.get('phone', '—')}")
            st.markdown(f"**📧 البريد:** {user.get('email', '—')}")
        with info_cols[1]:
            st.markdown(f"**🎭 الدور:** {role_label}")
            st.markdown(f"**📚 الفصل:** {section_name or '—'}")
            st.markdown(f"**📌 الحالة:** {status_label}")
            st.markdown(f"**🆔 المعرف:** {user.get('user_id', '')}")
    with st.expander("📜 سجل النشاطات"):
        if not user_logs.empty:
            display_logs = user_logs.sort_values("timestamp", ascending=False).head(20)
            for _, log_row in display_logs.iterrows():
                ts = log_row.get("timestamp", "")
                action = log_row.get("action", "")
                details = log_row.get("details", "")
                st.markdown(f"- **{str(ts)[:19]}** — {action} {('(' + details + ')') if details else ''}")
        else:
            st.info("لا توجد نشاطات مسجلة لهذا المستخدم.")
    st.markdown("---")
    act_col1, act_col2, act_col3, act_col4 = st.columns(4)
    with act_col1:
        if st.button("✏️ تعديل", use_container_width=True):
            st.session_state.edit_user_id = user_id
            st.session_state.profile_user_id = None
            st.rerun()
    with act_col2:
        if status == "active":
            if st.button("⏸️ تعطيل", use_container_width=True):
                db.update_user(user_id, {"status": "inactive"})
                db.add_log(st.session_state.user.get("user_id", ""), f"تعطيل مستخدم {user_id}", f"تم تعطيل {user.get('full_name', '')}")
                st.rerun()
        else:
            if st.button("▶️ تفعيل", use_container_width=True):
                db.update_user(user_id, {"status": "active"})
                db.add_log(st.session_state.user.get("user_id", ""), f"تفعيل مستخدم {user_id}", f"تم تفعيل {user.get('full_name', '')}")
                st.rerun()
    with act_col3:
        if st.button("🗑️ حذف", use_container_width=True):
            if user_id == st.session_state.user.get("user_id"):
                st.error("لا يمكنك حذف حسابك الحالي!")
            else:
                db.delete_user(user_id)
                db.add_log(st.session_state.user.get("user_id", ""), f"حذف مستخدم {user_id}", f"تم حذف {user.get('full_name', '')}")
                st.success("✅ تم حذف المستخدم")
                st.session_state.profile_user_id = None
                time.sleep(1)
                st.rerun()
    with act_col4:
        if st.button("🔙 العودة للقائمة", use_container_width=True):
            st.session_state.profile_user_id = None
            st.rerun()


# =============================================================================
# Logs
# =============================================================================
def show_logs(db):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db.get_logs()
    if not logs.empty:
        if "timestamp" in logs.columns:
            logs["timestamp"] = pd.to_datetime(logs["timestamp"])
        st.dataframe(logs.sort_values("timestamp", ascending=False), use_container_width=True)
        if "log_id" in logs.columns:
            del_id = st.selectbox("اختر سجلاً لحذفه", logs["log_id"], key="del_log_sel")
            if st.button("حذف السجل"):
                db.delete_log(del_id)
                st.success("تم الحذف")
                time.sleep(1)
                st.rerun()


# =============================================================================
# Change Password
# =============================================================================
def change_password(db):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    with st.form("change_password_form"):
        old = st.text_input("كلمة المرور الحالية", type="password").strip()
        new = st.text_input("كلمة المرور الجديدة", type="password").strip()
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password").strip()
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old or not new or not confirm:
                st.error("الرجاء ملء جميع الحقول")
            elif not verify_password(old, st.session_state.user.get("password", "")):
                st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new) < 4:
                st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
            elif new != confirm:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                hashed = hash_password(new)
                db.update_user(st.session_state.user["user_id"], {"password": hashed})
                st.session_state.user["password"] = hashed
                db.add_log(st.session_state.user["user_id"], "تغيير كلمة المرور", "تم تغيير كلمة المرور بنجاح")
                st.success("✅ تم تغيير كلمة المرور بنجاح!")


# =============================================================================
# Main App
# =============================================================================
def main():
    inject_css()
    init_session()
    init_data_cache()
    if 'db_instance' not in st.session_state:
        try:
            creds = get_credentials()
            st.session_state.db_instance = Database(creds, get_spreadsheet_id())
        except Exception as e:
            st.error(f"❌ خطأ في الاتصال: {e}")
            st.stop()
    db = st.session_state.db_instance
    jwt_secret = get_jwt_secret()
    if st.session_state.get("authenticated"):
        try:
            migrated = db.migrate_single_supervisors()
            if migrated and migrated > 0:
                st.caption(f"تم نقل {migrated} تعيين من مسؤول المرحلة القديم إلى نظام المشرفين المتعددين.")
        except Exception:
            pass
    st.markdown('<div class="help-float-container"></div>', unsafe_allow_html=True)
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
                return
            if not st.session_state.get("data_validated"):
                errors = validate_data_integrity(db)
                st.session_state.data_errors = errors
                st.session_state.data_validated = True
            if not st.session_state.show_sidebar:
                st.markdown("""<style>section[data-testid="stSidebar"] { transform: translateX(100%) !important; }</style>""", unsafe_allow_html=True)
                st.markdown('<div class="floating-show-btn"></div>', unsafe_allow_html=True)
                if st.button("القائمه", key="show_sidebar_btn"):
                    st.session_state.show_sidebar = True
                    st.rerun()
            else:
                st.markdown("""<style>section[data-testid="stSidebar"] { transform: translateX(0) !important; }</style>""", unsafe_allow_html=True)
                choice = show_sidebar_navigation(db)
            if not st.session_state.show_sidebar:
                choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
                role = st.session_state.user.get("role", "")
                menu_items = get_role_menu(role)
                if choice not in menu_items:
                    choice = menu_items[0] if menu_items else "🏠 لوحة التحكم"
                    st.session_state.menu_choice = choice
            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            if st.session_state.get("profile_user_id"):
                profile_id = st.session_state.profile_user_id
                # Check if this ID exists in Students sheet first
                students_df = db.get_students()
                if not students_df.empty and "student_id" in students_df.columns:
                    student_match = students_df[students_df["student_id"] == profile_id]
                    if not student_match.empty:
                        show_student_profile(db, profile_id)
                    else:
                        show_user_profile(db, profile_id)
                else:
                    show_user_profile(db, profile_id)
            elif choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "🏫 إدارة المراحل الدراسية":
                if st.session_state.user.get("role") in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
                    show_stages_page(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "📚 إدارة الفصول":
                if st.session_state.user.get("role") in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
                    show_sections_page(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "👥 إدارة الأعضاء":
                if st.session_state.user.get("role") in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
                    show_members_cards_page(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "📋 الحضور":
                show_attendance(db)
            elif choice == "💬 الافتقاد":
                show_followup(db)
            elif choice == "📝 المسابقات والاختبارات":
                show_quizzes(db)
            elif choice == "📊 التقارير والإحصائيات":
                show_reports_page(db)
            elif choice == "📅 إدارة الفعاليات":
                show_events_page(db)
            elif choice == "📜 سجل العمليات":
                if st.session_state.user.get("role") == "System Admin":
                    show_logs(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "🔒 تغيير كلمة المرور":
                change_password(db)
            st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state.get("open_help_dialog"):
        show_help_dialog()
        st.session_state.open_help_dialog = False


if __name__ == "__main__":
    main()
