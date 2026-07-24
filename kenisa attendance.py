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
# CSS
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
                    st.error("❌ فشل الإرسال، يرجى المحاولة لاحقاً أو التواصل مباشرة عبر الواتساب.")


# =============================================================================
# RBAC
# =============================================================================
VALID_ROLES = ["System Admin", "Father Account", "Service Manager", "Teacher", "Student"]
VALID_STATUSES = ["active", "inactive", "suspended"]

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
            "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل الدراسية", "📚 إدارة الفصول",
            "📋 الحضور", "💬 الافتقاد",
            "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات",
            "📜 سجل العمليات", "🔒 تغيير كلمة المرور"
        ],
        "Father Account": ["🏠 لوحة التحكم", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
        "Service Manager": [
            "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد",
            "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"
        ],
        "Teacher": [
            "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد",
            "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"
        ],
        "Student": ["🏠 لوحة التحكم", "📝 المسابقات والاختبارات", "🔒 تغيير كلمة المرور"]
    }
    return menus.get(role, [])


def filter_students_by_role(students, role, section_id):
    if role == "Teacher" and section_id:
        return students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    elif role == "Service Manager" and section_id:
        return students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else students
    else:
        return students


def filter_attendance_by_role(attendance, role, section_id):
    if role == "Teacher" and section_id:
        return attendance[attendance.section_id == section_id] if not attendance.empty and "section_id" in attendance.columns else pd.DataFrame()
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
            time_limit_seconds = int(quiz.get("time_limit_minutes", 15)) * 60
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
        function update() {{
            var now = new Date().getTime(); var dist = endTime - now;
            if (dist <= 0) {{ document.getElementById('time').innerHTML = "00:00"; parent.postMessage({{type: "QUIZ_TIME_UP"}}, "*"); clearInterval(intervalId); return; }}
            var mins = Math.floor((dist % (1000*60*60)) / (1000*60));
            var secs = Math.floor((dist % (1000*60)) / 1000);
            document.getElementById('time').innerHTML = (mins<10?'0'+mins:mins) + ":" + (secs<10?'0'+secs:secs);
        }}
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
# User Card Helpers
# =============================================================================
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
# User Management
# =============================================================================
def show_user_management(db):
    inject_user_cards_css()
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    stages = db.get_stages()
    students = db.get_students()
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["مدير النظام", "المدرسات", "الطالبات", "أمناء الخدمة", "خدم الكنيسة", "إدارة الفصول", "إدارة المراحل"])
    with tab1:
        st.subheader("👨‍💼 قائمة مديري النظام")
        admins = users[users.role == "System Admin"] if not users.empty and "role" in users.columns else pd.DataFrame()
        if not admins.empty:
            display_cols = [c for c in ["user_id", "username", "full_name", "phone", "email"] if c in admins.columns]
            st.dataframe(admins[display_cols], use_container_width=True)
        else:
            st.info("لا يوجد مديري نظام مسجلين.")
        with st.expander("➕ إضافة مدير نظام جديد"):
            with st.form("add_admin_form"):
                admin_name = st.text_input("اسم المستخدم*").strip()
                password = st.text_input("كلمة المرور*", type="password").strip()
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة"):
                    if not admin_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif "username" in users.columns and not users[users.username == admin_name].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({
                            "user_id": str(uuid.uuid4()), "username": admin_name, "password": password,
                            "role": "System Admin", "full_name": admin_name,
                            "section_id": "", "phone": phone, "email": email
                        })
                        st.success("تمت إضافة مدير النظام بنجاح")
                        time.sleep(1)
                        st.rerun()
    with tab2:
        st.subheader("قائمة المدرسات")
        teachers = users[users.role == "Teacher"] if not users.empty and "role" in users.columns else pd.DataFrame()
        if not teachers.empty:
            if not sections.empty:
                teachers_display = teachers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                teachers_display = teachers_display.rename(columns={"section_name": "الفصل"})
            else:
                teachers_display = teachers
                teachers_display["الفصل"] = ""
            display_cols = [c for c in ["user_id", "username", "full_name", "الفصل", "phone", "email"] if c in teachers_display.columns]
            st.dataframe(teachers_display[display_cols], use_container_width=True)
        else:
            st.info("لا توجد مدرسات مسجلات.")
        with st.expander("➕ إضافة مدرسة جديدة"):
            with st.form("add_teacher_form_2"):
                teacher_name = st.text_input("اسم المستخدم*").strip()
                password = st.text_input("كلمة المرور*", type="password").strip()
                section_id = ""
                if not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة"):
                    if not teacher_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif "username" in users.columns and not users[users.username == teacher_name].empty:
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
        with st.expander("➕ إضافة مستخدم جديد"):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                username = col1.text_input("اسم المستخدم*").strip()
                full_name = col2.text_input("الاسم الكامل*")
                password = col1.text_input("كلمة المرور*", type="password").strip()
                role = col2.selectbox("الصلاحية", ["System Admin", "Father Account", "Service Manager", "Teacher", "Student"])
                section_id = ""
                if role in ["Service Manager", "Teacher", "Student"] and not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف (اختياري)")
                email = st.text_input("البريد الإلكتروني (اختياري)")
                if st.form_submit_button("إضافة"):
                    if not username or not password or not full_name:
                        st.error("مطلوب اسم المستخدم وكلمة المرور والاسم الكامل")
                    elif "username" in users.columns and not users[users.username == username].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({
                            "user_id": str(uuid.uuid4()), "username": username, "password": hash_password(password),
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
                new_full_name = st.text_input("الاسم الكامل", value=user_data.get("full_name", ""), key="user_fullname")
                new_phone = st.text_input("رقم الهاتف", value=user_data.get("phone", ""), key="user_phone")
                new_email = st.text_input("البريد الإلكتروني", value=user_data.get("email", ""), key="user_email")
                roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher", "Student"]
                current_role = user_data.get("role", "Teacher")
                role_index = roles_list.index(current_role) if current_role in roles_list else 3
                new_role = st.selectbox("الصلاحية", roles_list, index=role_index, key="user_role")
                new_section_id = user_data.get("section_id", "")
                if new_role in ["Service Manager", "Teacher", "Student"] and not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    section_choice = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0] if x != "None" else "لا يوجد", key="user_section")
                    new_section_id = section_choice if section_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات", key="update_user_btn"):
                    db.update_user(selected_user_id, {"full_name": new_full_name, "phone": new_phone, "email": new_email, "role": new_role, "section_id": new_section_id})
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المستخدم", key="delete_user_btn"):
                    if selected_user_id == st.session_state.user.get("user_id"):
                        st.error("لا يمكنك حذف حسابك الحالي!")
                    else:
                        db.delete_user(selected_user_id)
                        st.success("تم الحذف")
                        time.sleep(1)
                        st.rerun()
    with tab3:
        st.subheader("قائمة الطالبات")
        if not students.empty:
            if not sections.empty:
                students_display = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
            else:
                students_display = students
                students_display["section_name"] = ""
            display_cols = [c for c in ["student_id", "full_name", "section_name", "phone", "parent_phone", "birthdate", "school", "status"] if c in students_display.columns]
            st.dataframe(students_display[display_cols], use_container_width=True)
        else:
            st.info("لا توجد طالبات مسجلة.")
        with st.expander("➕ إضافة طالبة جديدة"):
            with st.form("add_student_form_unique"):
                full_name = st.text_input("الاسم الكامل*")
                section_id = ""
                if not sections.empty:
                    section_id = st.selectbox("الفصل", sections["section_id"], format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0])
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
                new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""), key="student_fullname")
                sections_local = sections
                new_section_id = student_row.get("section_id", "")
                if not sections_local.empty:
                    section_options = sections_local["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    new_section_id = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections_local[sections_local.section_id == x]["section_name"].values[0], key="student_section")
                new_phone = st.text_input("رقم الهاتف", value=student_row.get("phone", ""), key="student_phone")
                new_parent = st.text_input("رقم ولي الأمر", value=student_row.get("parent_phone", ""), key="student_parent")
                existing_birthdate = student_row.get("birthdate", "")
                if existing_birthdate:
                    try:
                        birth_date_val = pd.to_datetime(existing_birthdate).date()
                    except Exception:
                        birth_date_val = None
                else:
                    birth_date_val = None
                new_birthdate = st.date_input("تاريخ الميلاد", value=birth_date_val, key="student_birthdate")
                new_school = st.text_input("المدرسة", value=student_row.get("school", ""), key="student_school")
                new_notes = st.text_area("ملاحظات", value=student_row.get("notes", ""), key="student_notes")
                status_list = ["active", "inactive"]
                current_status = student_row.get("status", "active")
                status_index = 0 if current_status == "active" else 1
                new_status = st.selectbox("الحالة", status_list, index=status_index, key="student_status")
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
    with tab4:
        st.subheader("قائمة أمناء الخدمة")
        managers = users[users.role == "Service Manager"] if not users.empty and "role" in users.columns else pd.DataFrame()
        if not managers.empty:
            if not sections.empty:
                mgr_display = managers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                mgr_display = mgr_display.rename(columns={"section_name": "الفصل"})
            else:
                mgr_display = managers
                mgr_display["الفصل"] = ""
            display_cols = [c for c in ["user_id", "username", "full_name", "الفصل", "phone", "email"] if c in mgr_display.columns]
            st.dataframe(mgr_display[display_cols], use_container_width=True)
        else:
            st.info("لا يوجد أمناء خدمة.")
    with tab5:
        st.subheader("👔 قائمة خدمات الكنيسة (Priests)")
        priests = users[users.role == "Father Account"] if not users.empty and "role" in users.columns else pd.DataFrame()
        if not priests.empty:
            display_cols = [c for c in ["user_id", "username", "full_name", "phone", "email"] if c in priests.columns]
            st.dataframe(priests[display_cols], use_container_width=True)
        else:
            st.info("لا يوجد خدم مسجلون.")
        with st.expander("➕ إضافة خدم جديد"):
            with st.form("add_priest_form"):
                priest_name = st.text_input("اسم المستخدم*").strip()
                password = st.text_input("كلمة المرور*", type="password").strip()
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة"):
                    if not priest_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif "username" in users.columns and not users[users.username == priest_name].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        db.add_user({
                            "user_id": str(uuid.uuid4()), "username": priest_name, "password": password,
                            "role": "Father Account", "full_name": priest_name,
                            "section_id": "", "phone": phone, "email": email
                        })
                        st.success("تمت إضافة الخدم بنجاح")
                        time.sleep(1)
                        st.rerun()
    with tab6:
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
    with tab7:
        st.subheader("🏫 إدارة المراحل الدراسية")
        if not stages.empty:
            if not users.empty and "user_id" in users.columns and "full_name" in users.columns:
                stages_display = stages.merge(users[["user_id", "full_name"]].rename(columns={"user_id": "manager_user_id", "full_name": "المسؤول"}), on="manager_user_id", how="left")
            else:
                stages_display = stages
                stages_display["المسؤول"] = ""
            st.dataframe(stages_display[["stage_id", "stage_name", "المسؤول"]], use_container_width=True)
        else:
            st.info("لا توجد مراحل مسجلة بعد.")
        with st.expander("➕ إضافة مرحلة جديدة"):
            with st.form("add_stage_form"):
                stage_name = st.text_input("اسم المرحلة*", placeholder="مثال: KG1, KG2, الصف الأول...")
                eligible_users = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
                manager_id = ""
                if not eligible_users.empty:
                    manager_choice = st.selectbox("مسؤول المرحلة (اختياري)", ["None"] + eligible_users["user_id"].tolist(),
                                                  format_func=lambda x: "بدون" if x == "None" else eligible_users[eligible_users.user_id == x]["full_name"].values[0])
                    manager_id = manager_choice if manager_choice != "None" else ""
                else:
                    st.info("لا يوجد مستخدمون مؤهلون لإدارة المرحلة.")
                if st.form_submit_button("إضافة"):
                    if not stage_name:
                        st.error("يرجى إدخال اسم المرحلة")
                    else:
                        db.add_stage({
                            "stage_id": str(uuid.uuid4()),
                            "stage_name": stage_name.strip(),
                            "manager_user_id": manager_id
                        })
                        st.success("✅ تمت إضافة المرحلة بنجاح")
                        time.sleep(1)
                        st.rerun()
        if not stages.empty:
            with st.expander("✏️ تعديل / حذف مرحلة"):
                stage_sel = st.selectbox("اختر مرحلة", stages["stage_id"],
                                         format_func=lambda x: stages[stages.stage_id == x]["stage_name"].values[0])
                stage_row = stages[stages.stage_id == stage_sel].iloc[0].to_dict()
                new_stage_name = st.text_input("اسم المرحلة", value=stage_row["stage_name"])
                eligible_users = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
                current_mgr = stage_row.get("manager_user_id", "")
                if not eligible_users.empty:
                    mgr_options = ["None"] + eligible_users["user_id"].tolist()
                    current_idx = mgr_options.index(current_mgr) if current_mgr in mgr_options else 0
                    new_manager = st.selectbox("مسؤول المرحلة", mgr_options, index=current_idx,
                                               format_func=lambda x: "بدون" if x == "None" else eligible_users[eligible_users.user_id == x]["full_name"].values[0])
                    new_mgr_id = new_manager if new_manager != "None" else ""
                else:
                    new_mgr_id = ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث المرحلة"):
                    db.update_stage(stage_sel, {"stage_name": new_stage_name, "manager_user_id": new_mgr_id})
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المرحلة"):
                    db.delete_stage(stage_sel)
                    st.success("تم حذف المرحلة")
                    time.sleep(1)
                    st.rerun()


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
                selected_supervisors = st.multiselect("اختر المشرفين", supervisor_options,
                                                      default=current_supervisors,
                                                      format_func=lambda x: eligible_users[eligible_users.user_id == x]["full_name"].values[0] if x in eligible_users["user_id"].values else x,
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

    search_term = st.text_input("🔍 بحث", placeholder="ابحث باسم الفصل، الغرفة، اليوم...", label_visibility="collapsed")
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
        for col in ["section_name", "room", "meeting_day"]:
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
            sec_max = sec.get("max_students", "")
            sec_room = sec.get("room", "")
            sec_day = sec.get("meeting_day", "")
            sec_time = sec.get("meeting_time", "")
            sec_status = sec.get("status", "active")
            sec_notes = sec.get("notes", "")

            stage_name = stages[stages["stage_id"] == sec_stage]["stage_name"].values[0] if not stages.empty and sec_stage else "—"
            teacher_name = users[users["user_id"] == sec_teacher]["full_name"].values[0] if not users.empty and sec_teacher else "غير محدد"
            leader_name = users[users["user_id"] == sec_leader]["full_name"].values[0] if not users.empty and sec_leader else "غير محددة"
            student_count = db.get_section_student_count(sec_id)

            with st.expander(f"🏫 {sec_name} ({stage_name}) - {student_count} طالبة"):
                st.markdown(f"**المرحلة:** {stage_name} | **الحالة:** {sec_status}")
                st.markdown(f"**المدرس:** {teacher_name} | **أمين الخدمة:** {leader_name}")
                st.markdown(f"**الغرفة:** {sec_room or '—'} | **الحد الأقصى:** {sec_max or '—'}")
                st.markdown(f"**اليوم:** {sec_day or '—'} | **الوقت:** {sec_time or '—'}")
                st.markdown(f"**عدد الطلاب:** {student_count}")
                st.markdown(f"**ملاحظات:** {sec_notes or '—'}")

                if role == "System Admin":
                    st.markdown("#### 🏫 نقل الفصل بين المراحل")
                    if not stages.empty:
                        new_stage = st.selectbox("نقل إلى مرحلة", stages["stage_id"],
                                                 format_func=lambda x: stages[stages.stage_id == x]["stage_name"].values[0],
                                                 key=f"move_stage_{sec_id}")
                        if st.button("نقل الفصل", key=f"move_sec_{sec_id}"):
                            db.update_section(sec_id, {"stage_id": new_stage})
                            st.success("✅ تم نقل الفصل")
                            time.sleep(1)
                            st.rerun()

                    st.markdown("#### 🔗 التعيينات")
                    eligible_teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
                    eligible_leaders = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
                    t_opts = ["None"] + eligible_teachers["user_id"].tolist() if not eligible_teachers.empty else ["None"]
                    l_opts = ["None"] + eligible_leaders["user_id"].tolist() if not eligible_leaders.empty else ["None"]
                    t_idx = t_opts.index(sec_teacher) if sec_teacher in t_opts else 0
                    l_idx = t_opts.index(sec_leader) if sec_leader in l_opts else 0
                    new_teacher = st.selectbox("المدرس", t_opts, index=t_idx,
                                                format_func=lambda x: "بدون" if x == "None" else eligible_teachers[eligible_teachers.user_id == x]["full_name"].values[0],
                                                key=f"teacher_{sec_id}")
                    new_leader = st.selectbox("أمين الخدمة", l_opts, index=l_idx,
                                                format_func=lambda x: "بدون" if x == "None" else eligible_leaders[eligible_leaders.user_id == x]["full_name"].values[0],
                                                key=f"leader_{sec_id}")
                    if st.button("💾 حفظ التعيينات", key=f"save_assign_{sec_id}"):
                        db.update_section(sec_id, {"teacher_id": new_teacher if new_teacher != "None" else "", "leader_id": new_leader if new_leader != "None" else ""})
                        st.success("✅ تم تحديث التعيينات")
                        time.sleep(1)
                        st.rerun()

                    st.markdown("#### ✏️ تعديل / حذف الفصل")
                    new_name = st.text_input("اسم الفصل", value=sec_name, key=f"edit_name_{sec_id}")
                    new_max = st.number_input("الحد الأقصى للطلاب", 0, 500, int(sec_max) if sec_max else 0, key=f"edit_max_{sec_id}")
                    new_room = st.text_input("الغرفة", value=sec_room, key=f"edit_room_{sec_id}")
                    new_day = st.text_input("يوم الاجتماع", value=sec_day, key=f"edit_day_{sec_id}")
                    new_time = st.text_input("وقت الاجتماع", value=sec_time, key=f"edit_time_{sec_id}")
                    new_notes = st.text_area("ملاحظات", value=sec_notes, key=f"edit_notes_{sec_id}")
                    new_status = st.selectbox("الحالة", ["active", "inactive"], index=0 if sec_status == "active" else 1, key=f"edit_status_{sec_id}")
                    c1, c2 = st.columns(2)
                    if c1.button("تحديث الفصل", key=f"update_sec_{sec_id}"):
                        db.update_section(sec_id, {"section_name": new_name, "max_students": new_max, "room": new_room,
                                                   "meeting_day": new_day, "meeting_time": new_time, "notes": new_notes, "status": new_status})
                        st.success("✅ تم التحديث")
                        time.sleep(1)
                        st.rerun()
                    if c2.button("حذف الفصل", key=f"delete_sec_{sec_id}"):
                        db.delete_section(sec_id)
                        st.success("✅ تم الحذف")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("🔍 لا توجد فصول مطابقة.")

    if role == "System Admin":
        with st.expander("➕ إضافة فصل جديد"):
            with st.form("add_section_page_form"):
                sec_name = st.text_input("اسم الفصل*")
                sec_stage = st.selectbox("المرحلة", stages["stage_id"],
                                         format_func=lambda x: stages[stages.stage_id == x]["stage_name"].values[0]) if not stages.empty else ""
                sec_teacher = st.selectbox("المدرس", ["None"] + users[users.role == "Teacher"]["user_id"].tolist(),
                                           format_func=lambda x: "بدون" if x == "None" else users[users.user_id == x]["full_name"].values[0]) if not users.empty else "None"
                sec_teacher = sec_teacher if sec_teacher != "None" else ""
                sec_leader = st.selectbox("أمين الخدمة", ["None"] + users[users.role == "Service Manager"]["user_id"].tolist(),
                                          format_func=lambda x: "بدون" if x == "None" else users[users.user_id == x]["full_name"].values[0]) if not users.empty else "None"
                sec_leader = sec_leader if sec_leader != "None" else ""
                sec_max = st.number_input("الحد الأقصى للطلاب", 0, 500, 0)
                sec_room = st.text_input("الغرفة")
                sec_day = st.text_input("يوم الاجتماع")
                sec_time = st.text_input("وقت الاجتماع")
                sec_notes = st.text_area("ملاحظات")
                if st.form_submit_button("إضافة الفصل"):
                    if not sec_name:
                        st.error("اسم الفصل مطلوب")
                    elif not sections.empty and "section_name" in sections.columns and sec_stage and not sections[sections.section_name == sec_name.strip()].empty:
                        st.error("⛔ اسم الفصل موجود مسبقاً!")
                    else:
                        db.add_section({
                            "section_id": str(uuid.uuid4()), "section_name": sec_name.strip(),
                            "stage_id": sec_stage, "teacher_id": sec_teacher, "leader_id": sec_leader,
                            "max_students": sec_max, "room": sec_room, "meeting_day": sec_day,
                            "meeting_time": sec_time, "status": "active", "notes": sec_notes,
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
    if role == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور، هذه المهمة خاصة بالمدرسات فقط.")
        if st.button("🔙 العودة إلى لوحة التحكم"):
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
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()
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


# =============================================================================
# My Students
# =============================================================================
def show_my_students(db):
    st.markdown("<h2 class='main-header'>👩‍🎓 طالباتي</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()
    my_students = filter_students_by_role(students, role, section_id)
    if my_students.empty:
        st.info("لا توجد طالبات مسجلات في فصلك.")
        return
    if not followup.empty and "student_id" in followup.columns and "regularity_status" in followup.columns:
        latest_fup = followup.sort_values("followup_date").groupby("student_id").last().reset_index()
        my_students = my_students.merge(latest_fup[["student_id", "regularity_status"]], on="student_id", how="left")
        my_students["regularity_status"] = my_students["regularity_status"].fillna("غير معروف")
    else:
        my_students["regularity_status"] = "غير معروف"
    display_cols = [c for c in ["full_name", "phone", "regularity_status"] if c in my_students.columns]
    st.dataframe(my_students[display_cols], use_container_width=True)
    st.markdown("---")
    st.subheader("➕ إضافة متابعة سريعة")
    if "student_id" in my_students.columns:
        selected = st.selectbox("اختر طالبة", my_students["student_id"],
                                format_func=lambda x: my_students[my_students.student_id == x]["full_name"].values[0], key="my_students_fup")
        with st.expander("فتح نموذج المتابعة"):
            with st.form("quick_followup_form"):
                ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
                notes = st.text_area("ملاحظات")
                regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
                if st.form_submit_button("حفظ المتابعة"):
                    try:
                        db.add_followup_record({
                            "record_id": str(uuid.uuid4()), "student_id": selected,
                            "teacher_id": user.get("user_id", ""), "followup_date": get_cairo_now().strftime("%Y-%m-%d"),
                            "followup_type": ftype, "notes": notes, "regularity_status": regularity
                        })
                        st.success("✅ تمت المتابعة بنجاح")
                        time.sleep(1)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


# =============================================================================
# Class Competition Scores
# =============================================================================
def show_class_competition_scores(db):
    st.markdown("<h2 class='main-header'>🏆 درجات مسابقات الفصل</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    if role != "Teacher" or not section_id:
        st.error("🚫 هذه الصفحة متاحة للمدرسات فقط.")
        return
    students = db.get_students()
    quizzes = db.get_quizzes()
    results = db.get_quiz_results()
    section_students = students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
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
        st.dataframe(filtered_df, use_container_width=True)
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
                st.dataframe(ranking, use_container_width=True)
    else:
        st.info("لا توجد نتائج مطابقة للبحث.")


# =============================================================================
# Quizzes
# =============================================================================
def show_quizzes(db):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
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
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
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
    students = db.get_students()
    sections_all = db.get_sections()
    if not results.empty:
        if "status" in results.columns:
            results = results[results["status"] == "submitted"]
        if role == "Teacher" and section_id and not students.empty and "student_id" in results.columns and "section_id" in students.columns:
            section_student_ids = students[students.section_id == section_id]["student_id"].tolist()
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
# Reports
# =============================================================================
def show_reports(db):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    attendance = db.get_attendance()
    students = db.get_students()
    attendance = filter_attendance_by_role(attendance, role, section_id)
    if role == "Teacher" and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
    if attendance.empty:
        st.info("لا توجد بيانات حضور.")
        return
    if "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    st.subheader("📅 تقرير الغياب الشهري")
    col1, col2 = st.columns(2)
    month = col1.selectbox("الشهر", range(1, 13), index=get_cairo_now().month - 1)
    year = col2.number_input("السنة", value=get_cairo_now().year, min_value=2020)
    if "date" in attendance.columns:
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
    if not attendance.empty and "status" in attendance.columns and "student_id" in attendance.columns:
        absent_counts = attendance[attendance.status == "غائب"].groupby("student_id").size().reset_index(name="أيام الغياب")
        absent_counts = absent_counts.sort_values("أيام الغياب", ascending=False).head(10)
        if not students.empty:
            absent_counts = absent_counts.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(absent_counts[["full_name", "أيام الغياب"]], use_container_width=True)


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
                show_user_profile(db, st.session_state.profile_user_id)
            elif choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "👥 إدارة المستخدمين":
                if st.session_state.user.get("role") == "System Admin":
                    show_user_management(db)
                else:
                    st.error("🚫 غير مصرح")
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
