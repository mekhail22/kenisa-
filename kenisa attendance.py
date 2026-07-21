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
import qrcode
from io import BytesIO
from PIL import Image
import base64
import hashlib
import hmac

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

# =============================================================================
# نظام الصلاحيات والتفويض (RBAC)
# =============================================================================
PERMISSIONS = {
    "System Admin": {
        "pages": ["🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", "📋 حضور المدرسين", "📱 حضور الطالبات QR", "📱 حضور المدرسين QR", "📋 الحضور", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية",
                  "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "📜 سجل العمليات", "🔒 تغيير كلمة المرور"],
        "actions": ["manage_users", "manage_teachers", "manage_students", "manage_sections", "manage_stages",
                    "register_attendance", "manage_followup", "manage_quizzes", "view_reports", "view_logs",
                    "change_password", "manage_settings", "security_access", "view_followup_dashboard"]
    },
    "Father Account": {
        "pages": ["🏠 لوحة التحكم", "📋 حضور المدرسين", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
        "actions": ["view_dashboard", "view_reports", "change_password", "view_followup_dashboard"]
    },
    "Service Manager": {
        "pages": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📱 حضور الطالبات QR", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية", "📋 حضور المدرسين",
                  "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
        "actions": ["view_dashboard", "manage_followup", "manage_quizzes", "view_reports", "change_password", "view_followup_dashboard"]
    },
    "Teacher": {
        "pages": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "📱 حضور الطالبات QR", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية", "📋 حضور المدرسين",
                  "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"],
        "actions": ["view_dashboard", "view_own_class", "register_attendance", "manage_followup", "view_quiz_scores", "change_password", "view_followup_dashboard"]
    }
}

def check_permission(action: str) -> bool:
    """Check if current user has permission for the given action."""
    if not st.session_state.get("authenticated"):
        return False
    user = st.session_state.get("user")
    if not user:
        return False
    role = user.get("role", "")
    if role not in PERMISSIONS:
        return False
    return action in PERMISSIONS[role].get("actions", [])

def check_page_access(page: str) -> bool:
    """Check if current user can access the given page."""
    if not st.session_state.get("authenticated"):
        return False
    user = st.session_state.get("user")
    if not user:
        return False
    role = user.get("role", "")
    if role not in PERMISSIONS:
        return False
    return page in PERMISSIONS[role].get("pages", [])

def require_permission(action: str, show_error: bool = True):
    """Decorator/context manager for permission checking - call at start of protected functions."""
    if not check_permission(action):
        if show_error:
            st.error("🚫 غير مصرح لك بالوصول إلى هذه الصفحة.")
        return False
    return True

def get_user_status() -> str:
    """Get current user's status (active/inactive)."""
    user = st.session_state.get("user")
    if user:
        # Handle missing or None status - default to active
        status = user.get("status", "active")
        if status is None or status == "" or status == "None":
            return "active"
        return status
    return "active"  # Default to active if no user (will be caught elsewhere)

def is_user_active() -> bool:
    """Check if current user account is active."""
    # Consider user active by default for backwards compatibility
    return True

def get_user_role() -> str:
    """Get current authenticated user's role."""
    user = st.session_state.get("user")
    if user:
        return user.get("role", "")
    return ""

def get_user_section() -> str:
    """Get current user's assigned section."""
    user = st.session_state.get("user")
    if user:
        return user.get("section_id", "")
    return ""

def get_user_stage() -> str:
    """Get current user's assigned stage."""
    user = st.session_state.get("user")
    if user:
        return user.get("stage_id", "")
    return ""

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
# CSS محسّن مع تثبيت المظهر الفاتح
# =============================================================================
def inject_css():
    st.markdown("""
    <style>
        html, body, .stApp {
            color-scheme: light !important;
        }
        @media (prefers-color-scheme: dark) {
            html, body, .stApp {
                background-color: #f0f2f6 !important;
                color: #1a1a2e !important;
            }
        }

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
            pointer-events: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            width: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            position: absolute !important;
            z-index: -9999 !important;
            overflow: hidden !important;
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
            margin: 0 !important;
            padding-top: 1rem !important;
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%) !important;
            border-left: 1px solid rgba(0,0,0,0.08) !important;
            transform: translateX(0);
        }

        @media (max-width: 768px) {
            section[data-testid="stSidebar"] {
                width: 100vw !important;
            }
        }

        [data-testid="stSidebarOverlay"] {
            display: none !important;
        }

        [data-testid="stAppViewContainer"] > [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            max-width: 100% !important;
            width: 100% !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
        }

        .nav-btn-container .stButton > button {
            width: 100% !important;
            text-align: right !important;
            justify-content: flex-start !important;
            padding: 0.7rem 1rem !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            background: transparent !important;
            color: #1a1a2e !important;
            border: 1px solid transparent !important;
            box-shadow: none !important;
            transition: all 0.2s ease !important;
            direction: rtl !important;
        }
        .nav-btn-container .stButton > button:hover {
            background: rgba(102,126,234,0.08) !important;
            color: #667eea !important;
            border-color: rgba(102,126,234,0.15) !important;
            transform: translateX(-2px) !important;
        }
        .nav-btn-container .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 2px 8px rgba(102,126,234,0.3) !important;
        }
        .nav-btn-container .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%) !important;
            color: white !important;
            transform: translateX(-2px) !important;
        }

        .floating-show-btn .stButton > button {
            position: fixed !important;
            top: 20px !important;
            right: 20px !important;
            z-index: 99999 !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 15px !important;
            width: 60px !important;
            height: 60px !important;
            font-size: 28px !important;
            font-weight: bold !important;
            box-shadow: 0 4px 15px rgba(102,126,234,0.4) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            cursor: pointer !important;
            padding: 0 !important;
            min-height: 60px !important;
            transition: all 0.2s ease !important;
        }
        .floating-show-btn .stButton > button:hover {
            transform: scale(1.08) !important;
            box-shadow: 0 6px 20px rgba(102,126,234,0.6) !important;
        }

        .help-float-container .stButton > button {
            position: fixed !important;
            top: 20px !important;
            right: 100px !important;
            z-index: 99998 !important;
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important;
            color: white !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            padding: 12px 20px !important;
            font-size: 16px !important;
            border: none !important;
            box-shadow: 0 4px 15px rgba(243,156,18,0.4) !important;
            white-space: nowrap !important;
            min-height: 48px !important;
            transition: all 0.2s ease !important;
        }
        .help-float-container .stButton > button:hover {
            transform: scale(1.04) !important;
            box-shadow: 0 6px 20px rgba(243,156,18,0.5) !important;
        }

        .main-header {
            font-size: 2.2rem; font-weight: 700; color: #1a1a2e; text-align: center;
            margin-bottom: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.9);
            border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            backdrop-filter: blur(5px); border: 1px solid rgba(0,0,0,0.05);
            margin-top: 100px;
        }
        .card { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 1rem; transition: transform 0.2s; color: #1a1a2e; border: 1px solid rgba(0,0,0,0.05); }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 8px; font-weight: 600;
            transition: all 0.2s; box-shadow: 0 2px 8px rgba(102,126,234,0.3);
        }
        .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(102,126,234,0.4); }
        .stRadio > div, .stSelectbox > div, .stMultiSelect > div { direction: rtl; }
        .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput { text-align: right; }
        .content-area { padding: 0 1rem; }

        .stDataFrame { background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .streamlit-expanderHeader {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important; border-radius: 8px; font-weight: 600;
        }
        .stForm { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            background: rgba(102,126,234,0.1); border-radius: 8px 8px 0 0;
            padding: 10px 20px; font-weight: 600; color: #667eea;
            border: 1px solid rgba(102,126,234,0.2); border-bottom: none;
        }
        .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; color: white !important; }
        .stSuccess { background: rgba(40,167,69,0.1); border: 1px solid rgba(40,167,69,0.2); color: #155724; border-radius: 10px; }
        .stError { background: rgba(220,53,69,0.1); border: 1px solid rgba(220,53,69,0.2); color: #721c24; border-radius: 10px; }

        iframe[title="st_components.html"] {
            border: none !important;
            background: transparent !important;
        }

        @media (max-width: 768px) {
            .floating-show-btn .stButton > button {
                width: 50px !important;
                height: 50px !important;
                font-size: 24px !important;
                top: 14px !important;
                right: 14px !important;
            }
            .help-float-container .stButton > button {
                right: 80px !important;
                top: 14px !important;
                padding: 10px 16px !important;
                font-size: 14px !important;
            }
            .main-header { font-size: 1.6rem; margin-top: 110px; }
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# تحسين الأداء: كاش مركزي داخل session_state
# =============================================================================
def init_data_cache():
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
    if 'data_dirty' not in st.session_state:
        st.session_state.data_dirty = {}

# =============================================================================
# Retry decorator
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
# Database Class مع نظام كاش متقدم
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

    @staticmethod
    def _get_default_user_columns():
        """Return default user table columns."""
        return ["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email", "status"]

    def add_user(self, user_data):
        df = self.get_users()
        cols = self._get_default_user_columns()
        if df.empty:
            df = pd.DataFrame(columns=cols)
        # Ensure status is set
        if "status" not in user_data:
            user_data["status"] = "active"
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        self._df_to_sheet("Users", df, cols)

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

    # --- Stages (جديد) ---
    def get_stages(self):
        return self._sheet_to_df("Stages")

    def add_stage(self, stage_data):
        df = self.get_stages()
        if df.empty:
            df = pd.DataFrame(columns=["stage_id", "stage_name", "manager_user_id"])
        new_row = {
            "stage_id": stage_data["stage_id"],
            "stage_name": stage_data["stage_name"],
            "manager_user_id": stage_data.get("manager_user_id", "")
        }
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

    # --- Sections ---
    def get_sections(self):
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data):
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
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, df.columns.tolist())

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
        """
        Return quizzes from Quizzes worksheet with proper column structure.
        Falls back to Exams worksheet for backward compatibility.
        Merges data from both worksheets if both exist.
        """
        # Try reading from Quizzes sheet first
        df_quizzes = self._sheet_to_df("Quizzes")
        
        # Also try reading from Exams sheet for backward compatibility
        df_exams = pd.DataFrame()
        try:
            Database._rate_limit()
            ws = self.spreadsheet.worksheet("Exams")
            df_exams = self._read_sheet_raw("Exams")
        except (gspread.WorksheetNotFound, Exception):
            pass
        
        # Merge both dataframes if both have data
        if df_quizzes.empty and not df_exams.empty:
            # Only Exams data exists - map columns
            df = df_exams.copy()
            column_mapping = {
                "exam_id": "quiz_id",
                "exam_code": "quiz_code",
                "class_id": "section_id",
                "end_date": "expiry_date"
            }
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns and v not in df.columns})
            return df
        elif not df_quizzes.empty and not df_exams.empty:
            # Both exist - merge with Quizzes taking priority
            df = df_quizzes.copy()
            exam_cols_mapped = df_exams.copy()
            column_mapping = {
                "exam_id": "quiz_id",
                "exam_code": "quiz_code",
                "class_id": "section_id",
                "end_date": "expiry_date"
            }
            exam_cols_mapped = exam_cols_mapped.rename(columns={k: v for k, v in column_mapping.items() if k in exam_cols_mapped.columns and v not in exam_cols_mapped.columns})
            # Merge missing rows from Exams that are not already in Quizzes
            if "quiz_id" in exam_cols_mapped.columns and "quiz_id" in df.columns:
                existing_ids = set(df["quiz_id"].tolist())
                new_rows = exam_cols_mapped[~exam_cols_mapped["quiz_id"].isin(existing_ids)]
                if not new_rows.empty:
                    df = pd.concat([df, new_rows], ignore_index=True)
            return df
        elif df_quizzes.empty and df_exams.empty:
            return pd.DataFrame()
        
        # Only Quizzes data exists - map columns for backwards compatibility and return
        df = df_quizzes.copy()
        column_mapping = {
            "exam_id": "quiz_id",
            "exam_code": "quiz_code",
            "class_id": "section_id",
            "end_date": "expiry_date"
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns and v not in df.columns})
        return df

    @staticmethod
    def _get_default_quiz_columns():
        """Return default quiz table columns as per specification."""
        return ["quiz_id", "title", "description", "created_by", "section_id",
                "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                "quiz_code", "password", "is_active"]

    @staticmethod
    def _get_default_exam_columns():
        """Return default exam table columns for Exams worksheet."""
        return ["exam_id", "quiz_id", "title", "description", "category", "exam_type",
                "class_id", "section_id", "stage_id", "start_date", "end_date",
                "expiry_date", "time_limit_minutes", "total_marks", "passing_score",
                "random_question_order", "random_answer_order", "max_attempts",
                "visibility", "is_active", "auto_publish", "auto_close",
                "instructions", "created_by", "password", "num_questions",
                "question_count", "created_at", "updated_at"]

    def add_exam(self, exam_data):
        """Add a new exam/quiz with enhanced fields.
        Writes to both Quizzes sheet (for student access) and Exams sheet (for enhanced fields).
        """
        # Prepare quiz columns data (Quizzes sheet)
        quiz_cols = ["quiz_id", "title", "description", "created_by", "section_id",
                     "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                     "quiz_code", "password", "is_active"]
        
        quiz_row = {
            "quiz_id": exam_data.get("quiz_id", str(uuid.uuid4())),
            "title": exam_data.get("title", ""),
            "description": exam_data.get("description", ""),
            "created_by": exam_data.get("created_by", ""),
            "section_id": exam_data.get("section_id", ""),
            "num_questions": exam_data.get("num_questions", 0),
            "time_limit_minutes": exam_data.get("time_limit_minutes", 15),
            "total_marks": exam_data.get("total_marks", 20),
            "expiry_date": exam_data.get("expiry_date", ""),
            "quiz_code": exam_data.get("exam_code", ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))),
            "password": exam_data.get("password", ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))),
            "is_active": "True"
        }
        
        # Write to Quizzes sheet
        df_quizzes = self._sheet_to_df("Quizzes")
        if df_quizzes.empty:
            df_quizzes = pd.DataFrame(columns=quiz_cols)
        df_quizzes = pd.concat([df_quizzes, pd.DataFrame([quiz_row])], ignore_index=True)
        self._df_to_sheet("Quizzes", df_quizzes, quiz_cols)
        
        # Also write to Exams sheet for enhanced fields (backward compatibility)
        df = self.get_quizzes()
        cols = self._get_default_exam_columns()
        if df.empty:
            df = pd.DataFrame(columns=cols)
        # Set defaults
        exam_data.setdefault("exam_code", quiz_row["quiz_code"])
        exam_data.setdefault("visibility", "public")
        exam_data.setdefault("is_active", "True")
        exam_data.setdefault("auto_publish", "False")
        exam_data.setdefault("auto_close", "False")
        exam_data.setdefault("random_question_order", "True")
        exam_data.setdefault("random_answer_order", "True")
        exam_data.setdefault("max_attempts", 1)
        exam_data.setdefault("total_marks", 20)
        exam_data.setdefault("passing_score", 10)
        exam_data.setdefault("quiz_code", quiz_row["quiz_code"])
        exam_data.setdefault("password", quiz_row["password"])
        exam_data.setdefault("quiz_id", quiz_row["quiz_id"])
        exam_data.setdefault("created_at", get_cairo_now().isoformat())
        exam_data.setdefault("updated_at", get_cairo_now().isoformat())
        df = pd.concat([df, pd.DataFrame([exam_data])], ignore_index=True)
        self._df_to_sheet("Exams", df, cols)
        
        # Return the generated quiz code and password for display
        return quiz_row["quiz_code"], quiz_row["password"]

    def update_exam(self, exam_id, updates):
        """Update an existing exam."""
        df = self.get_quizzes()
        idx = df[df.exam_id == exam_id].index
        if len(idx) > 0:
            updates["updated_at"] = get_cairo_now().isoformat()
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Exams", df, df.columns.tolist())
        else:
            idx = df[df.quiz_id == exam_id].index
            if len(idx) > 0:
                updates["updated_at"] = get_cairo_now().isoformat()
                for k, v in updates.items():
                    df.at[idx[0], k] = self._safe_str(v)
                self._df_to_sheet("Exams", df, df.columns.tolist())

    def update_quiz(self, quiz_id, updates):
        """Update a quiz in the Quizzes sheet by quiz_id."""
        df = self._sheet_to_df("Quizzes")
        if df.empty:
            return
        idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            quiz_cols = ["quiz_id", "title", "description", "created_by", "section_id",
                         "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                         "quiz_code", "password", "is_active"]
            self._df_to_sheet("Quizzes", df, quiz_cols)
        # Also update in Exams sheet for backward compatibility
        try:
            df_exams = self._read_sheet_raw("Exams")
            if not df_exams.empty:
                idx_exam = df_exams[df_exams.quiz_id == quiz_id].index
                if len(idx_exam) > 0:
                    for k, v in updates.items():
                        if k in df_exams.columns:
                            df_exams.at[idx_exam[0], k] = self._safe_str(v)
                    self._df_to_sheet("Exams", df_exams, df_exams.columns.tolist())
        except Exception:
            pass

    def delete_exam(self, exam_id):
        """Delete an exam and its questions."""
        df = self.get_quizzes()
        df = df[df.exam_id != exam_id]
        if "exam_id" not in df.columns and "quiz_id" in df.columns:
            df = df[df.quiz_id != exam_id]
        self._df_to_sheet("Exams", df, self._get_default_exam_columns())
        # Delete all questions for this exam
        qdf = self.get_exam_questions(exam_id)
        if not qdf.empty and "exam_id" in qdf.columns:
            qdf = self._sheet_to_df("ExamQuestions")
            qdf = qdf[qdf.exam_id != exam_id]
            self._df_to_sheet("ExamQuestions", qdf, ["question_id", "exam_id", "question_text", 
                                                    "question_type", "option1", "option2", "option3", "option4",
                                                    "option5", "option6", "correct_answer", "category",
                                                    "difficulty", "image_url", "points"])

    def add_quiz(self, quiz_data):
        """Legacy support - redirects to add_exam."""
        self.add_exam(quiz_data)

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
        """Get questions for a quiz - supports both quiz_id and exam_id."""
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            return pd.DataFrame()
        # Support both quiz_id and exam_id columns for flexibility
        if "quiz_id" in df.columns:
            return df[df.quiz_id == quiz_id]
        elif "exam_id" in df.columns:
            return df[df.exam_id == quiz_id]
        return pd.DataFrame()

    def get_exam_questions(self, exam_id):
        """Get questions for an exam by exam_id."""
        df = self._sheet_to_df("ExamQuestions")
        if df.empty:
            # Fallback to QuizQuestions
            df = self._sheet_to_df("QuizQuestions")
            if df.empty:
                return pd.DataFrame()
            # Try matching by quiz_id or exam_id
            if "exam_id" in df.columns:
                return df[df.exam_id == exam_id]
            elif "quiz_id" in df.columns:
                return df[df.quiz_id == exam_id]
        return df[df.exam_id == exam_id] if "exam_id" in df.columns else pd.DataFrame()

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
            "result_id": result_id,
            "quiz_id": quiz_id,
            "student_id": student_id,
            "student_name": student_name,
            "score": "",
            "total_marks": "20",
            "start_time": now_iso,
            "submission_time": now_iso,
            "answers": "{}",
            "status": "started"
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
            "log_id": str(uuid.uuid4()),
            "timestamp": get_cairo_now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details
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

    # --- Teacher Attendance ---
    def get_teacher_attendance(self):
        """Get all teacher attendance records from Google Sheets."""
        return self._sheet_to_df("Teacher Attendance")

    def add_teacher_attendance(self, record: dict):
        """Add or update a teacher attendance record."""
        df = self.get_teacher_attendance()
        cols = ["id", "teacher_id", "teacher_name", "date", "status", "check_in_time",
                "check_out_time", "method", "recorded_by", "recorded_by_name", "notes",
                "is_deleted", "deleted_at", "deleted_by", "restored_at", "restored_by",
                "created_at", "updated_at", "ip_address", "user_agent", "sync_status",
                "synced_at", "qr_code_data", "session_id"]
        if df.empty:
            df = pd.DataFrame(columns=cols)
        # Set defaults
        record.setdefault("is_deleted", "0")
        record.setdefault("sync_status", "pending")
        record.setdefault("created_at", get_cairo_now().isoformat())
        record.setdefault("updated_at", get_cairo_now().isoformat())
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("Teacher Attendance", df, cols)

    def update_teacher_attendance(self, record_id: str, updates: dict):
        """Update an existing teacher attendance record."""
        df = self.get_teacher_attendance()
        idx = df[df.id == record_id].index
        if len(idx) > 0:
            updates["updated_at"] = get_cairo_now().isoformat()
            updates["sync_status"] = "pending"
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Teacher Attendance", df, df.columns.tolist())

    def soft_delete_teacher_attendance(self, record_id: str, user_id: str):
        """Soft delete a teacher attendance record."""
        df = self.get_teacher_attendance()
        idx = df[df.id == record_id].index
        if len(idx) > 0:
            df.at[idx[0], "is_deleted"] = "1"
            df.at[idx[0], "deleted_at"] = get_cairo_now().isoformat()
            df.at[idx[0], "deleted_by"] = user_id
            df.at[idx[0], "updated_at"] = get_cairo_now().isoformat()
            self._df_to_sheet("Teacher Attendance", df, df.columns.tolist())

    def restore_teacher_attendance(self, record_id: str, user_id: str):
        """Restore a soft-deleted teacher attendance record."""
        df = self.get_teacher_attendance()
        idx = df[df.id == record_id].index
        if len(idx) > 0:
            df.at[idx[0], "is_deleted"] = "0"
            df.at[idx[0], "restored_at"] = get_cairo_now().isoformat()
            df.at[idx[0], "restored_by"] = user_id
            df.at[idx[0], "updated_at"] = get_cairo_now().isoformat()
            self._df_to_sheet("Teacher Attendance", df, df.columns.tolist())

    def get_teacher_attendance_by_date(self, date_str: str, teacher_id: str = None):
        """Get attendance records for a specific date, optionally for a specific teacher."""
        df = self.get_teacher_attendance()
        if df.empty:
            return pd.DataFrame()
        result = df[(df.date == date_str) & (df.is_deleted == "0")]
        if teacher_id and "teacher_id" in result.columns:
            result = result[result.teacher_id == teacher_id]
        return result

    def get_teacher_attendance_by_id(self, record_id: str):
        """Get a specific teacher attendance record by ID."""
        df = self.get_teacher_attendance()
        if df.empty:
            return None
        result = df[df.id == record_id]
        return result.iloc[0].to_dict() if not result.empty else None

    def batch_add_teacher_attendance(self, records: list):
        """Batch add/update multiple teacher attendance records."""
        df = self.get_teacher_attendance()
        cols = ["id", "teacher_id", "teacher_name", "date", "status", "check_in_time",
                "check_out_time", "method", "recorded_by", "recorded_by_name", "notes",
                "is_deleted", "deleted_at", "deleted_by", "restored_at", "restored_by",
                "created_at", "updated_at", "ip_address", "user_agent", "sync_status",
                "synced_at", "qr_code_data", "session_id"]
        if df.empty:
            df = pd.DataFrame(columns=cols)
        for rec in records:
            rec.setdefault("is_deleted", "0")
            rec.setdefault("sync_status", "pending")
            rec.setdefault("created_at", get_cairo_now().isoformat())
            rec.setdefault("updated_at", get_cairo_now().isoformat())
            df = pd.concat([df, pd.DataFrame([rec])], ignore_index=True)
        self._df_to_sheet("Teacher Attendance", df, cols)

    def get_pending_attendance_sync(self):
        """Get attendance records pending sync to Google Sheets."""
        df = self.get_teacher_attendance()
        if df.empty or "sync_status" not in df.columns:
            return pd.DataFrame()
        return df[df.sync_status == "pending"]

# =============================================================================
# JWT & Session Helpers
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
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
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
            # يمكن حفظ أي شيء قبل الخروج
            pass
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
# مركز المساعدة مع إمكانية إرفاق الصور
# =============================================================================
@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    hdr_col1, hdr_col2 = st.columns([0.85, 0.15])
    with hdr_col1:
        st.markdown("<h3 style='text-align:center; color:#667eea; margin:0; padding-top:0.5rem;'>📬 تواصل معنا</h3>", unsafe_allow_html=True)
    with hdr_col2:
        if st.button("✕ إغلاق", key="help_dialog_close_btn", help="إغلاق مركز المساعدة", use_container_width=True):
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
                    f"👤 الاسم: {name}\n"
                    f"📱 الواتساب: {whatsapp}\n"
                    f"📂 النوع: {issue_type}\n"
                    f"⚡ الأولوية: {urgency}\n"
                    f"📝 التفاصيل: {issue_desc}"
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
# QR Code Generation Functions
# =============================================================================
def generate_qr_code(data: str, size: int = 200) -> bytes:
    """Generate a secure QR code as PNG bytes."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

def get_qr_for_user(user_id: str, user_type: str = "user") -> str:
    """Get or generate QR code data URL for a user/teacher/student."""
    # Create unique, secure identifier
    qr_data = f"{user_type}:{user_id}:{hashlib.sha256(user_id.encode()).hexdigest()[:8]}"
    qr_bytes = generate_qr_code(qr_data)
    return f"data:image/png;base64,{base64.b64encode(qr_bytes).decode()}"

def generate_student_qr_data(student_id: str, section_id: str) -> bytes:
    """
    Generate a student QR code containing JSON with ONLY student_id and section_id.
    No sensitive information is stored in the QR code.
    Format: {"student_id": "STU000125", "section_id": "SEC003"}
    """
    qr_json = json.dumps({
        "student_id": student_id,
        "section_id": section_id
    }, ensure_ascii=False)
    return generate_qr_code(qr_json)

# =============================================================================
# Pagination Helper
# =============================================================================
def paginate_df(df: pd.DataFrame, page_key: str, page_size: int = 10):
    """Paginate a dataframe with session state support."""
    if df.empty:
        return df, 1, 1
    
    total_items = len(df)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    current_page = min(max(1, st.session_state[page_key]), total_pages)
    
    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    
    paginated_df = df.iloc[start_idx:end_idx].reset_index(drop=True)
    return paginated_df, current_page, total_pages

# =============================================================================
# Search & Filter Helpers
# =============================================================================
def search_users(users: pd.DataFrame, search_term: str):
    """Intelligent search for users with Arabic/English support and partial matching."""
    if users.empty or not search_term:
        return users
    
    search_lower = search_term.lower().strip()
    
    mask = pd.Series([False] * len(users))
    search_cols = ["full_name", "username", "phone", "email"]
    
    for col in search_cols:
        if col in users.columns:
            mask |= users[col].astype(str).str.lower().str.contains(search_lower, na=False)
    
    return users[mask]

def search_students(students: pd.DataFrame, search_term: str):
    """Intelligent search for students with Arabic/English support."""
    if students.empty or not search_term:
        return students
    
    search_lower = search_term.lower().strip()
    mask = pd.Series([False] * len(students))
    
    search_cols = ["full_name", "phone", "parent_phone", "school"]
    for col in search_cols:
        if col in students.columns:
            mask |= students[col].astype(str).str.lower().str.contains(search_lower, na=False)
    
    return students[mask]

def filter_users(users: pd.DataFrame, role_filter: str = None, status_filter: str = None, section_filter: str = None):
    """Advanced filtering for users."""
    filtered = users.copy()
    
    if role_filter and role_filter != "الكل" and "role" in filtered.columns:
        filtered = filtered[filtered["role"] == role_filter]
    
    if status_filter and status_filter != "الكل" and "status" in filtered.columns:
        filtered = filtered[filtered["status"] == status_filter]
    
    if section_filter and section_filter != "الكل" and "section_id" in filtered.columns:
        filtered = filtered[filtered["section_id"] == section_filter]
    
    return filtered

def calculate_age(birthdate_str: str) -> int:
    """Calculate age from birthdate string."""
    try:
        birthdate = pd.to_datetime(birthdate_str)
        today = get_cairo_now()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return age
    except Exception:
        return 0

# =============================================================================
# Member Card UI Component
# =============================================================================
def render_member_card(record: pd.Series, member_type: str = "user"):
    """Render a premium member card with avatar, status, and quick actions."""
    full_name = record.get("full_name", "غير محدد")
    status = record.get("status", "active")
    phone = record.get("phone", "")
    
    # Status badge styling
    status_colors = {
        "active": "linear-gradient(135deg, #2ecc71 0%, #27ae60 100%)",
        "inactive": "linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)"
    }
    status_bg = status_colors.get(status, "#95a5a6")
    status_text = "نشط" if status == "active" else "معطل"
    
    # Generate avatar from name
    avatar_letter = full_name[0].upper() if full_name else "?"
    avatar_colors = ["#667eea", "#764ba2", "#3498db", "#2ecc71", "#f39c12", "#e74c3c"]
    avatar_color = avatar_colors[hash(full_name) % len(avatar_colors)] if full_name else avatar_colors[0]
    
    col_avatar, col_info, col_actions = st.columns([1, 4, 2])
    
    with col_avatar:
        st.markdown(f"""
        <div style="
            width: 60px; height: 60px; border-radius: 50%; 
            background: {avatar_color}; color: white; 
            display: flex; align-items: center; justify-content: center;
            font-size: 24px; font-weight: bold; margin: 5px auto;
        ">{avatar_letter}</div>
        """, unsafe_allow_html=True)
    
    with col_info:
        st.markdown(f"**{full_name}**")
        if member_type == "user":
            role = record.get("role", "")
            section = record.get("section_id", "")
            st.caption(f"الدور: {role} | الهاتف: {phone}")
        elif member_type == "student":
            section = record.get("section_id", "")
            school = record.get("school", "")
            st.caption(f"الفصل: {section} | المدرسة: {school}")
    
    with col_actions:
        st.markdown(f"""
        <span style="background: {status_bg}; color: white; 
            padding: 4px 12px; border-radius: 12px; 
            font-size: 0.85rem; font-weight: 600;">{status_text}</span>
        """, unsafe_allow_html=True)

# =============================================================================
# Export Functions
# =============================================================================
def export_to_csv(df: pd.DataFrame, filename: str = "data.csv"):
    """Export dataframe to CSV."""
    if df.empty:
        return None
    return df.to_csv(index=False).encode('utf-8')

def export_to_excel(df: pd.DataFrame, filename: str = "data.xlsx"):
    """Export dataframe to Excel."""
    if df.empty:
        return None
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    return buffer.getvalue()

# =============================================================================
# Validation Function
# =============================================================================
def validate_data_integrity(db: Database):
    errors = []
    students = db.get_students()
    sections = db.get_sections()
    users = db.get_users()

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
    if missing:
        for sid in missing:
            db.add_section({"section_id": str(sid), "section_name": f"فصل (معرف {sid[:8]})"})
        return True
    return False

# =============================================================================
# Initialization & Login
# =============================================================================
def show_initialization(db: Database):
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
            db.add_user(admin_data)
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.info("**اسم المستخدم:** `admin`\n\n**كلمة المرور:** `admin123`")
            time.sleep(2)
            st.rerun()
        st.stop()

def ensure_all_users_active(db: Database):
    """Ensure all existing users have active status."""
    try:
        users = db.get_users()
        if not users.empty:
            for _, user in users.iterrows():
                current_status = user.get("status", "")
                if current_status != "active":
                    db.update_user(user.get("user_id", ""), {"status": "active"})
    except Exception:
        pass

def show_login_page(db: Database, jwt_secret: str):
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
                            if password == user.get("password", ""):
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
# Student Quiz Interface (مؤقت بدون تحديث)
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

def show_student_quiz(db: Database):
    if st.session_state.quiz_phase in ["taking_quiz", "finished"]:
        if not st.session_state.get("quiz_token"):
            st.error("انتهت جلسة الاختبار. يرجى إعادة الدخول.")
            for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                        "student_id", "quiz_start_time", "quiz_end_time", "quiz_submit_time",
                        "quiz_token", "quiz_answers", "quiz_submitted", "last_score",
                        "current_attempt_id", "last_saved_answers_str", "quiz_questions", "show_review"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.stop()
        else:
            token_data = verify_quiz_token(st.session_state.quiz_token)
            if token_data is None:
                st.error("انتهت صلاحية جلسة الاختبار. يرجى إعادة الدخول.")
                for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                            "student_id", "quiz_start_time", "quiz_end_time", "quiz_submit_time",
                            "quiz_token", "quiz_answers", "quiz_submitted", "last_score",
                            "current_attempt_id", "last_saved_answers_str", "quiz_questions", "show_review"]:
                    if key in st.session_state:
                        del st.session_state[key]
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
            section_id = student_row.get("section_id", "")
            sections_df = db.get_sections()
            if not sections_df.empty:
                sec_name = sections_df[sections_df.section_id == section_id]["section_name"].values
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
                        except json.JSONDecodeError:
                            saved_answers = {}
                        score = grade_attempt(db, quiz["quiz_id"], saved_answers)
                        db.submit_quiz_attempt(attempt["result_id"], score, json.dumps(saved_answers, ensure_ascii=False))
                        st.warning("تم تسليم محاولتك السابقة تلقائياً بناءً على ما قمت بحفظه.")
                        st.session_state.last_score = score
                        st.session_state.quiz_submit_time = get_cairo_now()
                        st.session_state.quiz_phase = "finished"
                        st.session_state.quiz_submitted = True
                        token = generate_quiz_token(quiz["quiz_id"], selected_id)
                        st.session_state.quiz_token = token
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
            token = generate_quiz_token(quiz["quiz_id"], selected_id)
            st.session_state.quiz_token = token
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

        # JavaScript لاستقبال إشارة انتهاء الوقت
        st.markdown("""
        <script>
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'QUIZ_TIME_UP') {
                var buttons = document.querySelectorAll('button');
                for (var i=0; i<buttons.length; i++) {
                    if (buttons[i].innerText.includes('تسليم الاختبار')) {
                        buttons[i].click();
                        break;
                    }
                }
            }
        });
        </script>
        """, unsafe_allow_html=True)

        # مؤقت HTML بدون تحديث الصفحة
        end_time_iso = st.session_state.quiz_end_time.isoformat()
        countdown_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
        body {{
            font-family: 'Cairo', sans-serif;
            margin: 0; padding: 0;
            display: flex; justify-content: center; align-items: center;
            height: 100%; background: transparent;
        }}
        #timer {{
            font-size: 1.8rem; font-weight: bold;
            padding: 1rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border-radius: 15px;
            box-shadow: 0 4px 12px rgba(102,126,234,0.4);
            text-align: center;
        }}
        </style>
        </head>
        <body>
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
        </script>
        </body>
        </html>
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
            if score.is_integer():
                score_display = int(score)
            else:
                score_display = score
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
                if st.button("إنهاء المراجعة والعودة إلى الرئيسية", use_container_width=True, key="finish_review_btn"):
                    for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                                "student_id", "quiz_start_time", "quiz_end_time", "quiz_submit_time",
                                "quiz_token", "quiz_answers", "quiz_submitted", "last_score",
                                "current_attempt_id", "last_saved_answers_str", "quiz_questions", "show_review"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
        return

# =============================================================================
# Sidebar Navigation
# =============================================================================
def get_role_badge(role: str) -> str:
    """Return styled role badge HTML."""
    badges = {
        "System Admin": "<span style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>🛡️ مدير النظام</span>",
        "Father Account": "<span style='background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>✝️ أبونا</span>",
        "Service Manager": "<span style='background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>📋 أمين خدمة</span>",
        "Teacher": "<span style='background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>👩‍🏫 مدرسة</span>"
    }
    return badges.get(role, "<span style='background: #95a5a6; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600;'>❓ غير معروف</span>")

def show_sidebar_navigation(db: Database):
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.user
        st.markdown(f"**👤 {user.get('full_name', '')}**")
        st.markdown(get_role_badge(user.get('role', '')), unsafe_allow_html=True)
        
        # Show section/stage assignment for Teacher/Service Manager
        section_id = user.get('section_id', '')
        if section_id:
            sections = db.get_sections()
            if not sections.empty:
                sec_name = sections[sections.section_id == section_id]['section_name'].values
                if len(sec_name) > 0:
                    st.caption(f"📍 الفصل: {sec_name[0]}")
        st.divider()

        role = user.get("role", "")
        menus = {
            "System Admin": [
                "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", 
                "📋 حضور المدرسين", "📱 حضور الطالبات QR", "📱 حضور المدرسين QR", "📋 الحضور", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية",
                "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات",
                "📜 سجل العمليات", "🔒 تغيير كلمة المرور"
            ],
            "Father Account": [
                "🏠 لوحة التحكم", "📋 حضور المدرسين", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"
            ],
            "Service Manager": [
                "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📱 حضور الطالبات QR", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية", "📋 حضور المدرسين",
                "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"
            ],
            "Teacher": [
                "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "📱 حضور الطالبات QR", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية",
                "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"
            ]
        }
        menu_items = menus.get(role, [])
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
def show_dashboard(db: Database):
    """
    Enhanced dashboard with KPI cards, interactive charts, and analytics.
    """
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم متقدمة</h2>", unsafe_allow_html=True)

    # Show data integrity warnings for admins
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

    # Get all data sources
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()
    teacher_attendance = db.get_teacher_attendance()
    users = db.get_users()
    sections = db.get_sections()
    stages = db.get_stages()

    # Filter by role
    if role in ["Teacher", "Service Manager"] and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
        if not attendance.empty and "section_id" in attendance.columns:
            attendance = attendance[attendance.section_id == section_id]
        if not followup.empty and not students.empty and "student_id" in followup.columns and "student_id" in students.columns:
            followup = followup[followup.student_id.isin(students["student_id"])]

    # Convert dates
    if not attendance.empty and "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    if not teacher_attendance.empty and "date" in teacher_attendance.columns:
        teacher_attendance["date"] = pd.to_datetime(teacher_attendance["date"], errors="coerce")

    # Today's date
    today = get_cairo_now()
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Calculate KPIs
    total_students = len(students) if not students.empty else 0
    total_teachers = len(users[users.role == "Teacher"]) if not users.empty and "role" in users.columns else 0
    total_classes = len(sections) if not sections.empty else 0
    total_stages = len(stages) if not stages.empty else 0

    # Student attendance today
    present_today = len(attendance[(attendance.date == today_str) & (attendance.status == "حاضر")]) if not attendance.empty and "status" in attendance.columns else 0
    absent_today = len(attendance[(attendance.date == today_str) & (attendance.status == "غائب")]) if not attendance.empty and "status" in attendance.columns else 0
    late_today = len(attendance[(attendance.date == today_str) & (attendance.status == "متأخر")]) if not attendance.empty and "status" in attendance.columns else 0
    excused_today = len(attendance[(attendance.date == today_str) & (attendance.status == "معفي")]) if not attendance.empty and "status" in attendance.columns else 0

    # Teacher attendance today
    teacher_present = len(teacher_attendance[(teacher_attendance.date == today_str) & (teacher_attendance.status == "present")]) if not teacher_attendance.empty and "status" in teacher_attendance.columns else 0
    teacher_absent = len(teacher_attendance[(teacher_attendance.date == today_str) & (teacher_attendance.status == "absent")]) if not teacher_attendance.empty and "status" in teacher_attendance.columns else 0
    teacher_late = len(teacher_attendance[(teacher_attendance.date == today_str) & (teacher_attendance.status == "late")]) if not teacher_attendance.empty and "status" in teacher_attendance.columns else 0

    # Active/Inactive members
    active_students = len(students[students.status == "active"]) if not students.empty and "status" in students.columns else 0
    inactive_students = len(students[students.status == "inactive"]) if not students.empty and "status" in students.columns else 0

    # Follow-up candidates
    followup_candidates = len(followup[followup.regularity_status.isin(["منقطع", "متقطع"])]) if not followup.empty and "regularity_status" in followup.columns else 0

    # Attendance percentage
    total_att_records = len(attendance[attendance.is_deleted == "0"]) if "is_deleted" in attendance.columns else len(attendance)
    attendance_pct = round((present_today / total_students * 100), 1) if total_students > 0 and present_today > 0 else 0

    # KPI Row 1 - Main Statistics
    st.markdown("### 📊 الإحصائيات الرئيسية")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 إجمالي الطالبات", total_students, delta=f"{active_students - inactive_students}")
    col2.metric("✅ حضور اليوم", present_today, delta=f"-{absent_today}" if absent_today > 0 else "0")
    col3.metric("❌ غياب اليوم", absent_today, delta=f"+{late_today}" if late_today > 0 else "0")
    col4.metric("⏰ متأخرون اليوم", late_today)

    # KPI Row 2 - Teacher & Follow-up Stats
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("👩‍🏫 إجمالي المدرسين", total_teachers)
    col6.metric("☕ حضور المدرسين", teacher_present, delta=f"-{teacher_absent}" if teacher_absent > 0 else "0")
    col7.metric("⚠️ بحاجة متابعة", followup_candidates)
    col8.metric("📊 نسبة الحضور", f"{attendance_pct}%")

    st.markdown("---")
    st.markdown("### 📊 تحليلات متقدمة")

    # Weekly Attendance Trend Chart
    if not attendance.empty and "date" in attendance.columns and "status" in attendance.columns:
        last_week = get_cairo_now().replace(tzinfo=None) - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty:
            st.markdown("#### 📈 اتجاهات الحضور الأسبوعية")
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
                        st.dataframe(section_scores.rename(columns={"section_name":"الفصل", "score":"متوسط الدرجات"}).set_index("الفصل"), use_container_width=True)

# =============================================================================
# إدارة المستخدمين (بما في ذلك إدارة المراحل)
# =============================================================================
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    stages = db.get_stages()
    students = db.get_students()
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول", "إدارة المراحل"])

    with tab1:
        st.subheader("قائمة المستخدمين (خدام)")
        
        # Advanced Search and Filter
        col_search, col_filter, col_export = st.columns([2, 1, 1])
        with col_search:
            search_term = st.text_input("🔍 بحث بالاسم أو الهاتف أو البريد", key="user_search")
        with col_filter:
            role_filter = st.selectbox("تصفية حسب الصلاحية", ["الكل", "System Admin", "Father Account", "Service Manager", "Teacher"], key="user_role_filter")
        with col_filter:
            status_filter = st.selectbox("تصفية حسب الحالة", ["الكل", "active", "inactive"], key="user_status_filter")
        with col_export:
            st.markdown("<br>", unsafe_allow_html=True)
            if not users.empty:
                csv_data = export_to_csv(users)
                if csv_data:
                    st.download_button("📥 تصدير CSV", csv_data, "users.csv", "text/csv")
        
        # Apply search and filter
        filtered_users = search_users(users, search_term)
        filtered_users = filter_users(filtered_users, role_filter if role_filter != "الكل" else None, 
                                    status_filter if status_filter != "الكل" else None)
        
        if not filtered_users.empty:
            # Pagination
            paginated, current_page, total_pages = paginate_df(filtered_users, "users_page", 10)
            display_cols = [c for c in ["user_id", "username", "full_name", "role", "section_id", "phone", "email", "status"] if c in paginated.columns]
            
            # Render as Member Cards
            for _, row in paginated.iterrows():
                with st.container():
                    col_img, col_info, col_qr = st.columns([1, 4, 1])
                    with col_info:
                        render_member_card(row, "user")
                    with col_qr:
                        if st.button(" QR", key=f"qr_{row['user_id']}"):
                            qr_data = get_qr_for_user(row['user_id'], "user")
                            st.image(qr_data, caption="رمز الاستجابة السريعة", width=80)
            st.caption(f"الصفحة {current_page} من {total_pages}")
        else:
            st.info("لا توجد نتائج مطابقة للبحث.")
        with st.expander("➕ إضافة مستخدم جديد"):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                username = col1.text_input("اسم المستخدم*").strip()
                full_name = col2.text_input("الاسم الكامل*")
                password = col1.text_input("كلمة المرور*", type="password").strip()
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
                    elif "username" in users.columns and not users[users.username == username].empty:
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
                new_full_name = st.text_input("الاسم الكامل", value=user_data.get("full_name", ""), key="user_fullname")
                new_phone = st.text_input("رقم الهاتف", value=user_data.get("phone", ""), key="user_phone")
                new_email = st.text_input("البريد الإلكتروني", value=user_data.get("email", ""), key="user_email")
                roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher"]
                current_role = user_data.get("role", "Teacher")
                role_index = roles_list.index(current_role) if current_role in roles_list else 3
                new_role = st.selectbox("الصلاحية", roles_list, index=role_index, key="user_role")
                new_section_id = user_data.get("section_id", "")
                if new_role in ["Service Manager", "Teacher"] and not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    section_choice = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد", key="user_section")
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
            with st.form("add_teacher_form"):
                teacher_name = st.text_input("اسم المستخدم*").strip()
                password = st.text_input("كلمة المرور*", type="password").strip()
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
                new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""), key="student_fullname")
                sections_local = sections
                new_section_id = student_row.get("section_id", "")
                if not sections_local.empty:
                    section_options = sections_local["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    new_section_id = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections_local[sections_local.section_id==x]["section_name"].values[0], key="student_section")
                new_phone = st.text_input("رقم الهاتف", value=student_row.get("phone", ""), key="student_phone")
                new_parent = st.text_input("رقم ولي الأمر", value=student_row.get("parent_phone", ""), key="student_parent")
                existing_birthdate = student_row.get("birthdate", "")
                if existing_birthdate:
                    try: birth_date_val = pd.to_datetime(existing_birthdate).date()
                    except (ValueError, TypeError): birth_date_val = None
                else: birth_date_val = None
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

    with tab6:
        st.subheader("🏫 إدارة المراحل الدراسية")
        if not stages.empty:
            if not users.empty and "user_id" in users.columns and "full_name" in users.columns:
                stages_display = stages.merge(users[["user_id", "full_name"]].rename(columns={"user_id":"manager_user_id", "full_name":"المسؤول"}), on="manager_user_id", how="left")
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
                                                  format_func=lambda x: "بدون" if x == "None" else eligible_users[eligible_users.user_id==x]["full_name"].values[0])
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
                                         format_func=lambda x: stages[stages.stage_id==x]["stage_name"].values[0])
                stage_row = stages[stages.stage_id == stage_sel].iloc[0].to_dict()
                new_stage_name = st.text_input("اسم المرحلة", value=stage_row["stage_name"])
                eligible_users = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
                current_mgr = stage_row.get("manager_user_id", "")
                if not eligible_users.empty:
                    mgr_options = ["None"] + eligible_users["user_id"].tolist()
                    current_idx = mgr_options.index(current_mgr) if current_mgr in mgr_options else 0
                    new_manager = st.selectbox("مسؤول المرحلة", mgr_options, index=current_idx,
                                               format_func=lambda x: "بدون" if x == "None" else eligible_users[eligible_users.user_id==x]["full_name"].values[0])
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
# Attendance, Follow-up, My Students, etc.
# =============================================================================
def show_attendance(db: Database):
    user = st.session_state.user
    role = user.get("role", "")
    if role not in ["System Admin", "Service Manager", "Teacher"]:
        st.error("🚫 غير مصرح لك بتسجيل الحضور.")
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
                               format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
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

def show_followup(db: Database):
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()

    if role == "Teacher" and section_id:
        responsible = students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    elif role == "Service Manager" and section_id:
        responsible = students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else students
    else:
        responsible = students

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
            st.dataframe(urgent_display[["full_name", "followup_date", "followup_type", "notes"]], use_container_width=True)
        else:
            st.info("كل البنات منتظمات حالياً.")
    else:
        st.info("لا توجد متابعات سابقة.")

    st.markdown("---")
    st.subheader("➕ إضافة متابعة جديدة")
    if "student_id" in responsible.columns:
        student = st.selectbox("اختر الطالبة", responsible["student_id"],
                               format_func=lambda x: responsible[responsible.student_id==x]["full_name"].values[0], key="followup_student")
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

def show_my_students(db: Database):
    st.markdown("<h2 class='main-header'>👩‍🎓 طالباتي</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()

    if role == "Teacher" and section_id:
        my_students = students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    elif role == "Service Manager" and section_id:
        my_students = students[students.section_id == section_id] if not students.empty and "section_id" in students.columns else students
    else:
        my_students = students

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
                                format_func=lambda x: my_students[my_students.student_id==x]["full_name"].values[0], key="my_students_fup")
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

def show_class_competition_scores(db: Database):
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
        mask = False
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

def show_quizzes(db: Database):
    """Complete Online Examination and Competition System."""
    st.markdown("<h2 class='main-header'>📝 نظام الاختبارات والمسابقات الإلكترونية</h2>", unsafe_allow_html=True)
    
    # Check permissions
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    
    # Tab interface for comprehensive exam system
    tab_create, tab_questions, tab_results, tab_analytics = st.tabs([
        "➕ إنشاء اختبار", "📝 أسئلة الاختبار", "📊 النتائج", "📈 التحليلات"
    ])
    
    with tab_create:
        _show_exam_creation(db, role, section_id)
    
    with tab_questions:
        _show_question_management(db, role, section_id)
    
    with tab_results:
        _show_exam_results(db, role, section_id)
    
    with tab_analytics:
        _show_exam_analytics(db, role, section_id)

def _show_exam_creation(db: Database, role: str, section_id: str):
    """Enhanced exam creation with all required fields."""
    st.markdown("### ➕ إنشاء اختبار إلكتروني جديد")
    
    user = st.session_state.get("user", {})
    
    if role not in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
        st.warning("⚠️ لا تملك صلاحية إنشاء اختبارات.")
        return
    
    sections = db.get_sections()
    stages = db.get_stages()
    
    with st.form("create_exam_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("🏷️ عنوان الاختبار *", placeholder="مثال: اختبار الرياضيات الشهر الأول")
            description = st.text_area("📄 الوصف", placeholder="وصف مختصر للاختبار...")
            exam_type = st.selectbox("📋 نوع الاختبار", ["اختبار", "مسابقة", "واجب منزل", "محفظة"])
            category = st.selectbox("📂 الفئة", ["دين", "رياضيات", "علوم", "لغة عربى", "لغة إنجليزية", "ثقافة عامة", "أخرى"])
        
        with col2:
            class_id = ""
            if role in ["Teacher", "Service Manager", "Father Account"] and not sections.empty:
                class_options = ["None"] + sections["section_id"].tolist()
                class_choice = st.selectbox("👥 الفصل", class_options, 
                    format_func=lambda x: "بدون فصل" if x == "None" else sections[sections.section_id==x]["section_name"].values[0])
                class_id = class_choice if class_choice != "None" else ""
            
            stage_id = ""
            if not stages.empty:
                stage_options = ["None"] + stages["stage_id"].tolist()
                stage_choice = st.selectbox("🏫 المرحلة", stage_options,
                    format_func=lambda x: "بدون مرحلة" if x == "None" else stages[stages.stage_id==x]["stage_name"].values[0])
                stage_id = stage_choice if stage_choice != "None" else ""
            
            start_date = st.date_input("📅 تاريخ البدء", value=get_cairo_now().date())
            end_date = st.date_input("📅 تاريخ الانتهاء", value=get_cairo_now().date() + timedelta(days=7))
        
        col3, col4 = st.columns(2)
        
        with col3:
            time_limit = st.number_input("⏱️ الوقت (بالدقائق)", min_value=1, max_value=180, value=15)
            total_marks = st.number_input("🏆 الدرجة الكلية", min_value=1, max_value=100, value=20)
            passing_score = st.number_input("✅ درجة النجاة", min_value=0, max_value=total_marks, value=10)
        
        with col4:
            max_attempts = st.number_input("🔄 عدد المحاولات المسموحة", min_value=1, max_value=10, value=1)
            visibility = st.selectbox("👁️ الظهور", ["عام", "خاص", "مخفي"])
            random_order = st.checkbox("🔀 ترتيب عشوائي للأسئلة والإجابات", value=True)
        
        instructions = st.text_area("📝 تعليمات الاختبار", 
            placeholder="اكتب تعليمات للطالبات قبل بدء الاختبار...", height=100)
        
        if st.form_submit_button("✨ إنشاء الاختبار", use_container_width=True):
            if not title:
                st.error("⚠️ عنوان الاختبار مطلوب")
            elif end_date < start_date:
                st.error("⚠️ تاريخ الانتهاء لا يمكن أن يكون قبل تاريخ البدء")
            else:
                exam_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                exam_password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                exam_data = {
                    "exam_id": str(uuid.uuid4()),
                    "quiz_id": str(uuid.uuid4()),
                    "exam_code": exam_code,
                    "quiz_code": exam_code,
                    "title": title.strip(),
                    "description": description,
                    "category": category,
                    "exam_type": exam_type,
                    "class_id": class_id,
                    "section_id": class_id,
                    "stage_id": stage_id,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "expiry_date": end_date.strftime("%Y-%m-%d"),
                    "time_limit_minutes": time_limit,
                    "total_marks": total_marks,
                    "passing_score": passing_score,
                    "random_question_order": "True" if random_order else "False",
                    "random_answer_order": "True" if random_order else "False",
                    "max_attempts": max_attempts,
                    "visibility": visibility,
                    "is_active": "True",
                    "auto_publish": "False",
                    "auto_close": "False",
                    "instructions": instructions,
                    "created_by": user.get("user_id", ""),
                    "password": exam_password,
                    "num_questions": 0,
                    "question_count": 0
                }
                
                try:
                    db.add_exam(exam_data)
                    db.add_log(user.get("user_id", ""), f"إنشاء اختبار جديد: {title} ({exam_code})")
                    st.success(f"✅ تم إنشاء الاختبار بنجاح!")
                    st.info(f"**كود الاختبار:** `{exam_code}`")
                    st.info(f"**كلمة المرور:** `{exam_password}`")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ خطأ في إنشاء الاختبار: {str(e)}")

def _show_question_management(db: Database, role: str, section_id: str):
    """Enhanced question management with all question types."""
    st.markdown("### 📝 إدارة أسئلة الاختبار")
    
    quizzes = db.get_quizzes()
    if quizzes.empty:
        st.info("لا توجد اختبارات متاحة. يرجى إنشاء اختبار أولاً.")
        return
    
    exam_col = "exam_id" if "exam_id" in quizzes.columns else "quiz_id"
    title_col = "title"
    
    if role in ["Teacher", "Service Manager"] and section_id:
        if "class_id" in quizzes.columns:
            quizzes = quizzes[quizzes["class_id"] == section_id]
        elif "section_id" in quizzes.columns:
            quizzes = quizzes[quizzes["section_id"] == section_id]
    
    if quizzes.empty:
        st.info("لا توجد اختبارات في فصلك.")
        return
    
    exam_choice = st.selectbox("اختر الاختبار", quizzes[exam_col].unique(),
        format_func=lambda x: quizzes[quizzes[exam_col]==x][title_col].values[0])
    
    if exam_choice:
        questions = db.get_quiz_questions(exam_choice)
        st.markdown(f"#### 📊 عدد الأسئلة: {len(questions) if not questions.empty else 0}")
        
        st.markdown("---")
        st.subheader("➕ إضافة سؤال جديد")
        
        question_types = ["اختيار من متعدد", "صح وخطأ", "أكمل", "إجابة قصيرة", "مقال", "مطابقة", "ترتيب"]
        qtype = st.selectbox("نوع السؤال", question_types)
        
        with st.form(f"add_question_form_{exam_choice}", clear_on_submit=True):
            qtext = st.text_area("📝 نص السؤال *")
            
            col1, col2 = st.columns(2)
            with col1:
                points = st.number_input("🏆 النقاط", min_value=1, max_value=10, value=1)
                q_category = st.selectbox("📂 فئة السؤال", ["سهل", "متوسط", "صعب"])
            
            with col2:
                image_url = st.text_input("🖼️ رابط صورة (اختياري)", placeholder="https://...")
            
            opts = {}
            if qtype == "اختيار من متعدد":
                st.markdown("**الخيارات:**")
                cols = st.columns(2)
                for i in range(1, 5):
                    opts[f"option{i}"] = cols[(i-1)%2].text_input(f"الخيار {i}")
                correct = st.text_input("✅ الإجابة الصحيحة (اكتب حرف الخيار A, B, C, أو D)")
            
            elif qtype == "صح وخطأ":
                opts["option1"] = "صح"
                opts["option2"] = "خطأ"
                correct = st.selectbox("✅ الإجابة الصحيحة", ["صح", "خطأ"])
            
            elif qtype == "مطابقة":
                st.markdown("**العناصر للمطابقة (كل سطر من فرادين مفصولة بسطر جديد):**")
                left_items = st.text_area("العناصر اليسار", placeholder="عنصر 1\nعنصر 2\nعنصر 3")
                right_items = st.text_area("العناصر اليمين", placeholder="عنصر أ\nعنصر ب\nعنصر ج")
                opts["option1"] = left_items.replace("\n", "|")
                opts["option2"] = right_items.replace("\n", "|")
                correct = st.text_input("✅ الإجابة (مثال: 1-a, 2-b, 3-c)")
            
            elif qtype == "ترتيب":
                items = st.text_area("📋 العناصر (كل عنصر في سطر):", placeholder="عنصر 1\nعنصر 2\nعنصر 3")
                opts["option1"] = items.replace("\n", "|")
                correct = st.text_input("✅ الترتيب الصحيح (أرقام مفصولة بفواصل):", placeholder="1, 3, 2")
            
            else:
                opts["option1"] = opts["option2"] = opts["option3"] = opts["option4"] = ""
                correct = st.text_area("✅ إجابة نموذجية")
            
            if st.form_submit_button("💾 حفظ السؤال"):
                if not qtext:
                    st.error("نص السؤال مطلوب")
                else:
                    user_obj = st.session_state.get("user", {})
                    q_data = {
                        "question_id": str(uuid.uuid4()),
                        "exam_id": exam_choice,
                        "quiz_id": exam_choice,
                        "question_text": qtext,
                        "question_type": qtype,
                        "option1": opts.get("option1", ""),
                        "option2": opts.get("option2", ""),
                        "option3": opts.get("option3", ""),
                        "option4": opts.get("option4", ""),
                        "correct_answer": correct,
                        "category": q_category,
                        "difficulty": q_category,
                        "image_url": image_url,
                        "points": points
                    }
                    db.add_question(q_data)
                    db.add_log(user_obj.get("user_id", ""), f"إضافة سؤال للاختبار {exam_choice}")
                    
                    questions = db.get_quiz_questions(exam_choice)
                    db.update_exam(exam_choice, {"question_count": len(questions) + 1})
                    
                    st.success("✅ تم حفظ السؤال")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")
        st.subheader("📋 الأسئلة الحالية")
        
        if questions.empty:
            st.info("لا توجد أسئلة مضافة لهذا الاختبار بعد.")
        else:
            for idx, q in questions.iterrows():
                with st.expander(f"سؤال {idx + 1}: {q.get('question_text', '')[:50]}..."):
                    st.markdown(f"**النوع:** {q.get('question_type', '')}")
                    st.markdown(f"**النقاط:** {q.get('points', 1)}")
                    st.markdown(f"**الإجابة الصحيحة:** {q.get('correct_answer', '')}")
                    
                    col1, col2 = st.columns(2)
                    if col1.button("✏️ تعديل", key=f"edit_q_{q.get('question_id')}"):
                        st.session_state[f"editing_question_{q.get('question_id')}"] = True
                    if col2.button("🗑️ حذف", key=f"del_q_{q.get('question_id')}"):
                        db.delete_question(q.get('question_id'))
                        st.success("✅ تم حذف السؤال")
                        time.sleep(1)
                        st.rerun()

def _show_exam_results(db: Database, role: str, section_id: str):
    """Display comprehensive exam results with search and filters."""
    st.markdown("### 📊 نتائج الاختبارات")
    
    results = db.get_quiz_results()
    quizzes = db.get_quizzes()
    students = db.get_students()
    
    if results.empty:
        st.info("لا توجد نتائج اختبارات مسجلة بعد.")
        return
    
    if "status" in results.columns:
        results = results[results["status"] == "submitted"]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_term = st.text_input("🔍 بحث بالطالبة أو الاختبار", placeholder="اكتب اسم...")
    
    with col2:
        status_filter = st.selectbox("📊 التصفية", ["الكل", "ناجح", "راسب"])
    
    with col3:
        quiz_filter = "الكل"
        if not quizzes.empty:
            if "exam_id" in quizzes.columns:
                quiz_options = ["الكل"] + quizzes["exam_id"].tolist()
                quiz_filter = st.selectbox("📋 الاختبار", quiz_options,
                    format_func=lambda x: "الكل" if x == "الكل" else quizzes[quizzes["exam_id"]==x]["title"].values[0])
            elif "quiz_id" in quizzes.columns:
                quiz_options = ["الكل"] + quizzes["quiz_id"].tolist()
                quiz_filter = st.selectbox("📋 الاختبار", quiz_options,
                    format_func=lambda x: "الكل" if x == "الكل" else quizzes[quizzes["quiz_id"]==x]["title"].values[0])
    
    filtered = results.copy()
    
    if search_term:
        st.markdown("---")
        st.markdown("📊 تحليل النتائج:")
    
    if quiz_filter != "الكل" and "quiz_id" in filtered.columns:
        filtered = filtered[filtered["quiz_id"] == quiz_filter]
    
    if status_filter == "ناجح" and "score" in filtered.columns:
        passing = 10
        if not quizzes.empty and quiz_filter != "الكل":
            quiz_row = quizzes[quizzes.quiz_id == quiz_filter] if "quiz_id" in quizzes.columns else pd.DataFrame()
            if not quiz_row.empty:
                passing = int(quiz_row.iloc[0].get("passing_score", 10))
            filtered = filtered[filtered["score"] >= passing]
    elif status_filter == "راسب" and "score" in filtered.columns:
        passing = 10
        if not quizzes.empty and quiz_filter != "الكل":
            quiz_row = quizzes[quizzes.quiz_id == quiz_filter] if "quiz_id" in quizzes.columns else pd.DataFrame()
            if not quiz_row.empty:
                passing = int(quiz_row.iloc[0].get("passing_score", 10))
            filtered = filtered[filtered["score"] < passing]
    
    if "score" in filtered.columns:
        filtered["score"] = pd.to_numeric(filtered["score"], errors="coerce").fillna(0)
    
    if not filtered.empty:
        st.markdown("---")
        display_cols = ["student_name", "quiz_id", "score", "submission_time"]
        available = [c for c in display_cols if c in filtered.columns]
        st.dataframe(filtered[available], use_container_width=True)
    else:
        st.info("لا توجد نتائج مطابقة للبحث.")

def _show_exam_analytics(db: Database, role: str, section_id: str):
    """Display exam analytics and statistics."""
    st.markdown("### 📈 تحليلات الاختبارات")
    
    quizzes = db.get_quizzes()
    results = db.get_quiz_results()
    students = db.get_students()
    
    if quizzes.empty:
        st.info("لا توجد اختبارات لعرض التحليلات.")
        return
    
    if not results.empty and "status" in results.columns:
        results = results[results["status"] == "submitted"]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📚 إجمالي الاختبارات", len(quizzes))
    col2.metric("📊 إجمالي النتائج", len(results) if not results.empty else 0)
    col3.metric("✅ متوسط الدرجات", f"{results['score'].mean():.1f}" if not results.empty and "score" in results.columns else "0")
    col4.metric("👥 الطالبات المشاركات", len(results['student_id'].unique()) if not results.empty and "student_id" in results.columns else 0)
    
    st.markdown("---")
    
    if not results.empty and not quizzes.empty:
        st.markdown("#### 📊 توزيع الدرجات حسب الاختبارات")
        if "quiz_id" in results.columns and "score" in results.columns:
            score_summary = results.groupby("quiz_id")["score"].mean().reset_index()
            score_summary = score_summary.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
            if not score_summary.empty:
                fig = px.bar(score_summary, x="title", y="score", title="متوسط الدرجات حسب الاختبار")
                fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("#### 🏆 أفضل 10 طالبات")
    if not results.empty and "student_id" in results.columns and "score" in results.columns and not students.empty:
        top_students = results.groupby("student_id")["score"].sum().reset_index()
        top_students = top_students.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        top_students = top_students.sort_values("score", ascending=False).head(10)
        st.dataframe(top_students[["full_name", "score"]], use_container_width=True)

def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    attendance = db.get_attendance()
    students = db.get_students()

    if role == "Teacher" and section_id:
        if not attendance.empty and "section_id" in attendance.columns:
            attendance = attendance[attendance.section_id == section_id]
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]

    if attendance.empty:
        st.info("لا توجد بيانات حضور.")
        return
    if "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    st.subheader("📅 تقرير الغياب الشهري")
    col1, col2 = st.columns(2)
    month = col1.selectbox("الشهر", range(1,13), index=get_cairo_now().month-1)
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

def change_password(db: Database):
    """Allow user to change their password."""
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    
    with st.form("change_password_form"):
        old = st.text_input("كلمة المرور الحالية", type="password").strip()
        new = st.text_input("كلمة المرور الجديدة", type="password").strip()
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password").strip()
        
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old or not new or not confirm:
                st.error("الرجاء ملء جميع الحقول")
            elif old != user.get("password", ""):
                st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new) < 4:
                st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
            elif new != confirm:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                db.update_user(user["user_id"], {"password": new})
                st.session_state.user["password"] = new
                db.add_log(user.get("user_id", ""), "تغيير كلمة المرور")
                st.success("✅ تم تغيير كلمة المرور بنجاح!")

def show_logs(db: Database):
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
# Teacher Attendance Management System
# =============================================================================

def validate_teacher_qr_code(qr_data: str, secret: str) -> tuple:
    """
    Validate teacher QR code data.
    
    Args:
        qr_data: Raw QR code data string (JSON format)
        secret: Secret key for HMAC validation
        
    Returns:
        Tuple of (is_valid, teacher_id, teacher_name, error_message)
    """
    try:
        data = json.loads(qr_data)
        if not all(k in data for k in ["teacher_id", "teacher_name", "timestamp", "checksum"]):
            return False, None, None, "بيانات QR غير مكتملة"
        
        # Validate checksum
        expected_checksum = hmac.new(
            secret.encode(), 
            f"{data['teacher_id']}:{data['timestamp']}".encode(), 
            hashlib.sha256
        ).hexdigest()[:8]
        
        if data["checksum"] != expected_checksum:
            return False, None, None, "تحقق من صحة QR غير ناجح"
        
        # Validate timestamp (5 minutes expiry)
        qr_time = pd.to_datetime(data["timestamp"])
        now = get_cairo_now()
        if (now - qr_time.replace(tzinfo=CAIRO_TZ)).total_seconds() > 300:
            return False, None, None, "انتهت صلاحية رمز QR (أكثر من 5 دقائق)"
        
        return True, data["teacher_id"], data["teacher_name"], None
    except json.JSONDecodeError:
        return False, None, None, "تنسيق QR غير صالح"
    except Exception as e:
        return False, None, None, f"خطأ في التحقق: {str(e)}"

def get_client_info() -> tuple:
    """Get client IP address and user agent for audit logging."""
    try:
        ip_address = st.session_state.get("client_ip", "")
    except Exception:
        ip_address = ""
    user_agent = st.session_state.get("user_agent", "")
    return ip_address, user_agent

def show_teacher_attendance(db: Database):
    """
    Main function for Teacher Attendance Management System.
    Displays QR scanner, manual entry, history, and statistics tabs.
    """
    st.markdown("<h2 class='main-header'>📋 حضور المدرسين</h2>", unsafe_allow_html=True)
    
    # Check permissions
    user = st.session_state.user
    role = user.get("role", "")
    
    if role not in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
        st.error("🚫 غير مصرح لك بالوصول إلى هذه الصفحة.")
        return
    
    tab_qr, tab_manual, tab_history, tab_stats, tab_export = st.tabs([
        "📱 مسح QR", "✍️ إدخال يدوي", "📊 السجلات", "📈 الإحصائيات", "📥 تصدير"
    ])
    
    with tab_qr:
        _show_qr_attendance(db)
    
    with tab_manual:
        _show_manual_teacher_attendance(db)
    
    with tab_history:
        _show_teacher_attendance_history(db)
    
    with tab_stats:
        _show_teacher_attendance_stats(db)
    
    with tab_export:
        _show_teacher_attendance_export(db)

def _show_qr_attendance(db: Database):
    """Display QR code scanning interface for teacher attendance."""
    st.markdown("### 📱 مسح رمز الاستجابة السريعة")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 محاولة مرة أخرى", use_container_width=True):
            st.session_state.qr_scan_result = None
            st.session_state.qr_processing = False
    
    # QR scanner placeholder with fallback
    st.markdown("""
    <div style="
        border: 2px dashed #667eea; 
        border-radius: 15px; 
        padding: 2rem; 
        text-align: center;
        background: rgba(102, 126, 234, 0.05);
        margin: 1rem 0;
    ">
        <h3>📷 كاميرا مسح QR</h3>
        <p>ضع كاميرا هاتفك أمام رمز QR المدرس</p>
        <p style="color: #666; font-size: 0.9rem;">(إذا كانت الكاميرا غير متاحة، استخدم الإدخال اليدوي أدناه)</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Manual QR input fallback
    st.markdown("#### إدخال QR يدوياً (إذا كانت الكاميرا غير متاحة)")
    qr_input = st.text_area("الصق بيانات QR هنا", height=100, key="qr_manual_input")
    
    if st.button("معالجة QR", key="process_qr_btn"):
        if qr_input.strip():
            _process_teacher_qr(db, qr_input.strip())
        else:
            st.error("يرجى إدخال بيانات QR")

def _process_teacher_qr(db: Database, qr_data: str):
    """Process scanned teacher QR code and mark attendance."""
    secret = st.secrets.get("qr_secret", "default-teacher-qr-secret")
    is_valid, teacher_id, teacher_name, error = validate_teacher_qr_code(qr_data, secret)
    
    if not is_valid:
        st.error(f"❌ {error}")
        db.add_log(st.session_state.user.get("user_id", ""), f"QR scan failed: {error}")
        return
    
    # Check if teacher exists and is active
    users = db.get_users()
    teacher = users[(users.user_id == teacher_id) & (users.role == "Teacher")]
    
    if teacher.empty:
        st.error("❌ المدرس غير موجود في النظام")
        return
    
    if teacher.iloc[0].get("status", "active") != "active":
        st.error("❌ حساب المدرس غير مفعّل")
        return
    
    # Check for duplicate within session
    today = get_cairo_now().strftime("%Y-%m-%d")
    existing = db.get_teacher_attendance_by_date(today, teacher_id)
    
    if not existing.empty:
        st.info(f"ℹ️ حضور المدرس تم تسجيله مسبقاً اليوم")
        st.markdown(f"**الاسم:** {teacher_name}")
        st.markdown(f"**الوقت:** {existing.iloc[0].get('check_in_time', 'غير مسجل')}")
    else:
        # Create attendance record
        record = {
            "id": str(uuid.uuid4()),
            "teacher_id": teacher_id,
            "teacher_name": teacher_name,
            "date": today,
            "status": "present",
            "check_in_time": get_cairo_now().strftime("%H:%M:%S"),
            "method": "qr",
            "recorded_by": st.session_state.user.get("user_id", ""),
            "recorded_by_name": st.session_state.user.get("full_name", ""),
            "ip_address": get_client_info()[0],
            "session_id": st.session_state.get("session_id", str(uuid.uuid4()))
        }
        db.add_teacher_attendance(record)
        db.add_log(st.session_state.user.get("user_id", ""), f"تم تسجيل حضور مدرس {teacher_name} عبر QR")
        st.success(f"✅ تم تسجيل حضور المدرس: {teacher_name}")

def _show_manual_teacher_attendance(db: Database):
    """Display manual teacher attendance marking interface."""
    st.markdown("### ✍️ تسليم حضور المدرس يدوياً")
    
    # Search teachers
    users = db.get_users()
    teachers = users[users.role == "Teacher"] if not users.empty and "role" in users.columns else pd.DataFrame()
    
    if teachers.empty:
        st.info("لا توجد مدرسين مسجلين في النظام.")
        return
    
    search_term = st.text_input("ابحث عن مدرس", key="teacher_search_manual")
    
    if search_term:
        teachers_list = teachers[
            teachers.full_name.astype(str).str.contains(search_term, case=False, na=False) |
            teachers.user_id.astype(str).str.contains(search_term, case=False, na=False)
        ]
    else:
        teachers_list = teachers
    
    if teachers_list.empty:
        st.info("لا توجد مدرسين مطابقين للبحث.")
        return
    
    today = get_cairo_now().strftime("%Y-%m-%d")
    
    # Quick action buttons for each teacher
    for _, teacher in teachers_list.iterrows():
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            status = teacher.get("status", "active")
            status_icon = "✅" if status == "active" else "⚠️"
            st.markdown(f"{status_icon} **{teacher.get('full_name', '')}**")
        
        # Check if already marked today
        existing = db.get_teacher_attendance_by_date(today, teacher.get("user_id"))
        
        if not existing.empty:
            with col2:
                st.markdown("🟢 مسجل")
        else:
            with col2:
                if st.button("حاضر", key=f"mark_present_{teacher.get('user_id')}"):
                    _mark_teacher_attendance(db, teacher.get("user_id"), teacher.get("full_name"), "present")
            with col3:
                if st.button("متأخر", key=f"mark_late_{teacher.get('user_id')}"):
                    _mark_teacher_attendance(db, teacher.get("user_id"), teacher.get("full_name"), "late")
            with col4:
                if st.button("غائب", key=f"mark_absent_{teacher.get('user_id')}"):
                    _mark_teacher_attendance(db, teacher.get("user_id"), teacher.get("full_name"), "absent")

def _mark_teacher_attendance(db: Database, teacher_id: str, teacher_name: str, status: str):
    """Mark attendance for a specific teacher."""
    today = get_cairo_now().strftime("%Y-%m-%d")
    now_time = get_cairo_now().strftime("%H:%M:%S")
    
    record = {
        "id": str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "teacher_name": teacher_name,
        "date": today,
        "status": status,
        "check_in_time": now_time if status in ["present", "late"] else "",
        "method": "manual",
        "recorded_by": st.session_state.user.get("user_id", ""),
        "recorded_by_name": st.session_state.user.get("full_name", ""),
        "ip_address": get_client_info()[0],
        "session_id": st.session_state.get("session_id", str(uuid.uuid4()))
    }
    db.add_teacher_attendance(record)
    db.add_log(st.session_state.user.get("user_id", ""), f"تم تسجيل حضور مدرس {teacher_name} ({status})")
    st.success(f"✅ تم تسجيل حضور المدرس: {teacher_name} - الحالة: {status}")

def _show_teacher_attendance_history(db: Database):
    """Display teacher attendance history with filtering and editing."""
    st.markdown("### 📊 سجلات حضور المدرسين")
    
    attendance = db.get_teacher_attendance()
    users = db.get_users()
    
    if attendance.empty:
        st.info("لا توجد سجلات حضور مدرسين بعد.")
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_filter = st.date_input("تاريخ محدد", value=get_cairo_now().date())
    
    with col2:
        status_options = ["الكل", "present", "absent", "late", "excused"]
        status_filter = st.selectbox("حالة الحضور", status_options)
    
    with col3:
        if not users.empty:
            teacher_options = ["الكل"] + users[users.role == "Teacher"]["user_id"].tolist()
            teacher_filter = st.selectbox("المدرس", teacher_options)
        else:
            teacher_filter = "الكل"
    
    # Apply filters
    filtered = attendance[(attendance.date == date_filter.strftime("%Y-%m-%d")) & 
                         (attendance.is_deleted == "0")]
    
    if status_filter != "الكل" and "status" in filtered.columns:
        filtered = filtered[filtered.status == status_filter]
    
    if teacher_filter != "الكل" and "teacher_id" in filtered.columns:
        filtered = filtered[filtered.teacher_id == teacher_filter]
    
    if filtered.empty:
        st.info("لا توجد سجلات مطابقة للفلاتر.")
    else:
        # Display records
        display_cols = ["teacher_name", "date", "status", "check_in_time", "method"]
        available_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(filtered[available_cols], use_container_width=True)
        
        # Edit/Delete options
        if st.session_state.user.get("role") in ["System Admin", "Father Account", "Service Manager"]:
            record_id = st.selectbox("اختر سجل لتعديله", filtered["id"], key="edit_teacher_att")
            if record_id:
                _show_edit_teacher_attendance(db, record_id)

def _show_edit_teacher_attendance(db: Database, record_id: str):
    """Show edit dialog for teacher attendance record."""
    record = db.get_teacher_attendance_by_id(record_id)
    if not record:
        return
    
    with st.expander("✏️ تعديل السجل"):
        status_options = ["present", "absent", "late", "excused"]
        current_status = record.get("status", "present")
        status_index = status_options.index(current_status) if current_status in status_options else 0
        
        new_status = st.selectbox("الحالة", status_options, index=status_index)
        new_notes = st.text_area("ملاحظات", value=record.get("notes", ""))
        
        if st.button("💾 حفظ التعديل"):
            updates = {
                "status": new_status,
                "notes": new_notes,
                "updated_at": get_cairo_now().isoformat()
            }
            db.update_teacher_attendance(record_id, updates)
            db.add_log(st.session_state.user.get("user_id", ""), 
                      f"تم تعديل سجل حضور المدرس {record.get('teacher_name')} (قبل: {current_status}, بعد: {new_status})")
            st.success("✅ تم تحديث السجل")

def _show_teacher_attendance_stats(db: Database):
    """Display teacher attendance statistics."""
    st.markdown("### 📈 إحصائيات حضور المدرسين")
    
    attendance = db.get_teacher_attendance()
    users = db.get_users()
    
    if attendance.empty:
        st.info("لا توجد بيانات إحصائية.")
        return
    
    # Daily summary
    today = get_cairo_now().strftime("%Y-%m-%d")
    today_records = attendance[attendance.date == today]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("إجمالي المدرسين", len(users[users.role == "Teacher"]) if not users.empty else 0)
    col2.metric("حاضرون اليوم", len(today_records[today_records.status == "present"]))
    col3.metric("متأخرون اليوم", len(today_records[today_records.status == "late"]))
    col4.metric("غائبون اليوم", len(today_records[today_records.status == "absent"]))
    
    # Period summary
    st.markdown("---")
    st.subheader("📊 ملخص فترة")
    
    start_date = st.date_input("من تاريخ", value=get_cairo_now().date() - timedelta(days=7))
    end_date = st.date_input("إلى تاريخ", value=get_cairo_now().date())
    
    period_records = attendance[(attendance.date >= start_date.strftime("%Y-%m-%d")) & 
                              (attendance.date <= end_date.strftime("%Y-%m-%d")) &
                              (attendance.is_deleted == "0")]
    
    if not period_records.empty:
        total_days = (end_date - start_date).days + 1
        attendance_rate = len(period_records[period_records.status.isin(["present", "late"])]) / (len(users[users.role == "Teacher"]) * total_days) * 100
        
        st.metric("معدل الحضور", f"{attendance_rate:.1f}%")

def _show_teacher_attendance_export(db: Database):
    """Display teacher attendance export interface."""
    st.markdown("### 📥 تصدير سجلات حضور المدرسين")
    
    attendance = db.get_teacher_attendance()
    
    if attendance.empty:
        st.info("لا توجد سجلات للتصدير.")
        return
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("من تاريخ", value=get_cairo_now().date() - timedelta(days=30), key="export_start")
    with col2:
        end_date = st.date_input("إلى تاريخ", value=get_cairo_now().date(), key="export_end")
    
    filtered = attendance[(attendance.date >= start_date.strftime("%Y-%m-%d")) & 
                         (attendance.date <= end_date.strftime("%Y-%m-%d")) &
                         (attendance.is_deleted == "0")]
    
    if filtered.empty:
        st.info("لا توجد سجلات في الفترة المحددة.")
        return
    
    # Display preview
    st.markdown("#### معاينة البيانات")
    display_cols = ["teacher_name", "date", "status", "check_in_time"]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available].head(20), use_container_width=True)
    
    # Export options
    col1, col2 = st.columns(2)
    with col1:
        csv_data = export_to_csv(filtered)
        if csv_data:
            st.download_button("📥 تصدير CSV", csv_data, "teacher_attendance.csv", "text/csv", use_container_width=True)
    with col2:
        excel_data = export_to_excel(filtered)
        if excel_data:
            st.download_button("📥 تصدير Excel", excel_data, "teacher_attendance.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

def calculate_followup_status(student_id: str, attendance: pd.DataFrame) -> str:
    """
    Calculate follow-up status based on attendance history.
    Returns: Regular, Occasionally Absent, Needs Follow-up, Inactive
    """
    if attendance.empty or "student_id" not in attendance.columns:
        return "Regular"
    
    student_att = attendance[attendance["student_id"] == student_id]
    if student_att.empty:
        return "Regular"
    
    # Check for recent absence (last 30 days)
    today = get_cairo_now()
    month_ago = today - timedelta(days=30)
    
    if "date" in student_att.columns:
        recent_att = student_att[pd.to_datetime(student_att["date"], errors="coerce") >= month_ago]
        if not recent_att.empty:
            absent_count = len(recent_att[recent_att["status"] == "غائب"])
            if absent_count >= 5:
                return "Needs Follow-up"
            elif absent_count >= 3:
                return "Occasionally Absent"
    
    return "Regular"

def get_priority_level(absent_count: int, consecutive_absences: int) -> str:
    """Determine priority level based on absence count."""
    if absent_count >= 10 or consecutive_absences >= 5:
        return "Critical"
    elif absent_count >= 5 or consecutive_absences >= 3:
        return "High"
    elif absent_count >= 3:
        return "Medium"
    else:
        return "Low"

def show_followup_dashboard(db: Database):
    """Enhanced Follow-up Management Dashboard with smart alerts."""
    st.markdown("<h2 class='main-header'>💬 لوحة متابعة الافتقاد الذكية</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    
    # Check permissions
    if role not in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
        st.error("🚫 غير مصرح لك بالوصول إلى هذه الصفحة.")
        return
    
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()
    
    # Filter by role
    if role in ["Teacher", "Service Manager"] and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
    
    # Calculate follow-up statistics
    total_students = len(students) if not students.empty else 0
    
    # Students needing follow-up
    if not attendance.empty:
        if "date" in attendance.columns:
            attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
        
        today = get_cairo_now()
        month_ago = today - timedelta(days=30)
        
        # High priority (absent 5+ times)
        if "date" in attendance.columns:
            recent_month = attendance[pd.to_datetime(attendance["date"], errors="coerce") >= month_ago]
            high_priority = len(recent_month[recent_month["status"] == "غائب"].groupby("student_id").filter(lambda x: len(x) >= 5))
        else:
            high_priority = 0
        
        # Critical (absent 10+ times)
        critical = len(recent_month[recent_month["status"] == "غائب"].groupby("student_id").filter(lambda x: len(x) >= 10))
        
        # Pending follow-up
        if not followup.empty and "regularity_status" in followup.columns:
            pending = len(followup[followup.regularity_status.isin(["متقطع", "منقطع"])])
            completed = len(followup[followup.regularity_status == "منتظم"])
        else:
            pending = 0
            completed = 0
    else:
        high_priority = critical = pending = completed = 0
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 إجمالي الطالبات", total_students)
    col2.metric("⚠️ متابقة معلقة", pending)
    col3.metric("🔴 أولوية عالية", high_priority)
    col4.metric("🔴 أولوية حرجة", critical)
    
    st.markdown("---")
    
    # Tab interface
    tab1, tab2, tab3, tab4 = st.tabs(["📋 قائمة المتابعة", "➕ إضافة متابعة", "📊 التحليل الذكي", "📅 الجدول الزمني"])
    
    with tab1:
        _show_followup_list(db, students, followup)
    
    with tab2:
        _add_followup_record(db, students, section_id)
    
    with tab3:
        _show_smart_analysis(db, students, attendance)
    
    with tab4:
        _show_followup_timeline(db, students, followup)

def _show_followup_list(db: Database, students: pd.DataFrame, followup: pd.DataFrame):
    """Display follow-up records with filters."""
    st.markdown("### 📋 سجلات المتابعة")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox("الحالة", ["الكل", "منتظم", "متقطع", "منقطع"])
    
    with col2:
        priority_filter = st.selectbox("الأولوية", ["الكل", "Low", "Medium", "High", "Critical"])
    
    with col3:
        type_filter = st.selectbox("نوع الافتقاد", ["الكل", "زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
    
    if not followup.empty:
        filtered = followup.copy()
        
        if status_filter != "الكل" and "regularity_status" in filtered.columns:
            filtered = filtered[filtered["regularity_status"] == status_filter]
        
        # Merge with student names
        if not students.empty and "student_id" in students.columns:
            filtered = filtered.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        
        display_cols = ["full_name", "followup_date", "followup_type", "notes", "regularity_status"]
        available = [c for c in display_cols if c in filtered.columns]
        
        if available:
            st.dataframe(filtered[available], use_container_width=True)
    else:
        st.info("لا توجد سجلات متابعة.")

def _add_followup_record(db: Database, students: pd.DataFrame, section_id: str):
    """Add new follow-up record with enhanced fields."""
    st.markdown("### ➕ إضافة متابعة جديدة")
    
    if students.empty:
        st.info("لا توجد طالبات مسجلة.")
        return
    
    # Student selection
    if "student_id" in students.columns:
        student = st.selectbox(
            "اختر الطالبة", 
            students["student_id"].tolist(),
            format_func=lambda x: students[students["student_id"] == x]["full_name"].values[0] if x in students["student_id"].values else x
        )
    else:
        return
    
    with st.form("add_followup_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي", "اجتماع أهل", "واتساب", "رسائل نصية", "أخرى"])
            priority = st.selectbox("الأولوية", ["Low", "Medium", "High", "Critical"])
            regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
        
        with col2:
            notes = st.text_area("ملاحظات")
        
        if st.form_submit_button("حفظ المتابعة"):
            try:
                db.add_followup_record({
                    "record_id": str(uuid.uuid4()),
                    "student_id": student,
                    "teacher_id": st.session_state.user.get("user_id", ""),
                    "followup_date": get_cairo_now().strftime("%Y-%m-%d"),
                    "followup_type": ftype,
                    "notes": notes,
                    "regularity_status": regularity
                })
                db.add_log(st.session_state.user.get("user_id", ""), f"إضافة متابعة للطالبة {student}")
                st.success("✅ تم حفظ المتابعة بنجاح")
                time.sleep(1)
                st.rerun()
            except ValueError as e:
                st.error(str(e))

def _show_smart_analysis(db: Database, students: pd.DataFrame, attendance: pd.DataFrame):
    """Display smart absence analysis and alerts."""
    st.markdown("### 📊 التحليل الذكي للغياب")
    
    if attendance.empty or students.empty:
        st.info("لا توجد بيانات للتحليل.")
        return
    
    today = get_cairo_now()
    month_ago = today - timedelta(days=30)
    
    if "date" in attendance.columns:
        recent_month = attendance[pd.to_datetime(attendance["date"], errors="coerce") >= month_ago]
    
    # Find problematic students
    absent_counts = recent_month[recent_month["status"] == "غائب"].groupby("student_id").size().reset_index(name="absent_count")
    
    if not absent_counts.empty and not students.empty:
        merged = absent_counts.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
        merged["Priority"] = merged["absent_count"].apply(
            lambda x: "Critical" if x >= 10 else ("High" if x >= 5 else ("Medium" if x >= 3 else "Low"))
        )
        
        st.markdown("#### 🔴 الطالبات ذات الغياب المتكرر")
        st.dataframe(merged[["full_name", "absent_count", "Priority"]], use_container_width=True)
        
        # Alerts
        st.markdown("---")
        st.markdown("#### ⚠️ تنبيهات النظام")
        
        critical = merged[merged["Priority"] == "Critical"]
        high = merged[merged["Priority"] == "High"]
        
        if not critical.empty:
            st.error(f"🔴 {len(critical)} طالبات بحاجة متابعة حرجة (غياب 10+ مرات)")
        
        if not high.empty:
            st.warning(f"🟠 {len(high)} طالبات بحاجة متابعة عالية (غياب 5+ مرات)")

def _show_followup_timeline(db: Database, students: pd.DataFrame, followup: pd.DataFrame):
    """Display chronological follow-up timeline."""
    st.markdown("### 📅 الجدول الزمني للمتابعة")
    
    if followup.empty:
        st.info("لا توجد سجلات متابعة.")
        return
    
    if "followup_date" in followup.columns:
        sorted_fu = followup.sort_values("followup_date", ascending=False).head(20)
        
        if not students.empty and "student_id" in students.columns:
            sorted_fu = sorted_fu.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        
        for _, row in sorted_fu.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    st.markdown(f"**{row.get('followup_date', '')}**")
                with col2:
                    st.markdown(f"**{row.get('full_name', '')}** - {row.get('followup_type', '')}")
                    st.caption(row.get('notes', ''))
                with col3:
                    status = row.get('regularity_status', '')
                    if status == 'منتظم':
                        st.success(status)
                    elif status == 'متقطع':
                        st.warning(status)
                    else:
                        st.error(status)

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
    ensure_all_users_active(db)

    # Session validation and user status check
    if st.session_state.authenticated and st.session_state.user:
        # Verify token validity
        token_data = verify_token(st.session_state.token, jwt_secret)
        if not token_data:
            st.error("⏰ انتهت صلاحية الجلسة أو انتهت صلاحية التوكن.")
            st.session_state.clear()
            time.sleep(2)
            st.rerun()

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
                st.markdown("""
                <style>
                section[data-testid="stSidebar"] {
                    transform: translateX(100%) !important;
                }
                </style>
                """, unsafe_allow_html=True)

                st.markdown('<div class="floating-show-btn"></div>', unsafe_allow_html=True)
                if st.button("☰", key="show_sidebar_btn"):
                    st.session_state.show_sidebar = True
                    st.rerun()
            else:
                st.markdown("""
                <style>
                section[data-testid="stSidebar"] {
                    transform: translateX(0) !important;
                }
                </style>
                """, unsafe_allow_html=True)

                choice = show_sidebar_navigation(db)

            if not st.session_state.show_sidebar:
                choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
                role = st.session_state.user.get("role", "")
                menus = {
                    "System Admin": [
                        "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", "📋 حضور المدرسين", "📱 حضور الطالبات QR", "📱 حضور المدرسين QR", "📋 الحضور", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية",
                        "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات",
                        "📜 سجل العمليات", "🔒 تغيير كلمة المرور"
                    ],
                    "Father Account": ["🏠 لوحة التحكم", "📋 حضور المدرسين", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                    "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📱 حضور الطالبات QR", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية", "📋 حضور المدرسين",
                                        "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                    "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "📱 حضور الطالبات QR", "💬 الافتقاد", "💬 لوحة متابعة الافتقاد الذكية", "📋 حضور المدرسين",
                                "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"]
                }
                menu_items = menus.get(role, [])
                if choice not in menu_items:
                    choice = menu_items[0] if menu_items else "🏠 لوحة التحكم"
                    st.session_state.menu_choice = choice

            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            if choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "📋 حضور المدرسين":
                show_teacher_attendance(db)
            elif choice == "📱 حضور الطالبات QR":
                show_student_qr_attendance(db)
            elif choice == "📱 حضور المدرسين QR":
                show_teacher_qr_attendance(db)
            elif choice == "👥 إدارة المستخدمين":
                if st.session_state.user.get("role") == "System Admin":
                    show_user_management(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "🏫 إدارة المراحل":
                if st.session_state.user.get("role") == "System Admin":
                    show_user_management(db)  # ستفتح التبويب السادس الخاص بالمراحل
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "👩‍🎓 طالباتي":
                show_my_students(db)
            elif choice == "📋 الحضور":
                show_attendance(db)
            elif choice == "💬 الافتقاد":
                show_followup(db)
            elif choice == "💬 لوحة متابعة الافتقاد الذكية":
                if check_permission("view_followup_dashboard"):
                    show_followup_dashboard(db)
                else:
                    st.error("🚫 غير مصرح")
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

# =============================================================================
# QR ATTENDANCE - Students & Teachers
# =============================================================================

def show_student_qr_attendance(db: Database):
    """Student QR attendance - scan QR to record attendance with camera permission handling."""
    st.markdown("<h2 class='main-header'>📱 حضور الطالبات بالرمز الثنائي</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    if not user:
        st.error("يجب تسجيل الدخول أولاً")
        st.stop()
    
    # Check permission
    if not check_permission("register_attendance"):
        st.error("🚫 غير مصرح لك بتسجيل الحضور")
        st.stop()
    
    # Initialize QR scanning state with camera availability check
    if 'qr_scanning_active' not in st.session_state:
        st.session_state.qr_scanning_active = True
    if 'qr_scan_success' not in st.session_state:
        st.session_state.qr_scan_success = False
    if 'qr_scan_result' not in st.session_state:
        st.session_state.qr_scan_result = None
    if 'qr_permission_denied' not in st.session_state:
        st.session_state.qr_permission_denied = False
    if 'qr_camera_check_done' not in st.session_state:
        st.session_state.qr_camera_check_done = False
    
    # Camera permission denied dialog
    if st.session_state.get("qr_permission_denied"):
        st.error("📷 **وصول الكاميرا مطلوب لمسح رموز QR**")
        st.markdown("""
        <div style="
            text-align: center; 
            padding: 2rem; 
            border: 2px solid #e74c3c; 
            border-radius: 15px; 
            background: rgba(231, 76, 60, 0.05);
            margin: 1rem 0;
        ">
            <h3 style="color: #e74c3c;">⚠️ إذن الكاميرا مطلوب</h3>
            <p>يجب السماح باستخدام الكاميرا لمسح رموز الاستجابة السريعة.</p>
            <p style="font-size: 0.9rem; color: #666;">اضغط على "سماح" أو "Allow" عند طلب الإذن في المتصفح.</p>
        </div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 إعادة المحاولة", use_container_width=True, key="qr_retry_btn"):
                st.session_state.qr_permission_denied = False
                st.session_state.qr_scanning_active = True
                st.session_state.qr_scan_success = False
                st.session_state.qr_camera_check_done = False
                st.rerun()
        with col2:
            if st.button("❌ إلغاء", use_container_width=True, key="qr_cancel_btn"):
                st.session_state.qr_permission_denied = False
                st.session_state.qr_scanning_active = False
                st.session_state.qr_scan_success = False
                st.rerun()
        return
    
    # Show result message if we have a result stored
    if st.session_state.get("qr_scan_result_message"):
        msg = st.session_state.qr_scan_result_message
        if msg["type"] == "success":
            st.success(msg["text"])
            st.balloons()
        elif msg["type"] == "warning":
            st.warning(msg["text"])
        elif msg["type"] == "error":
            st.error(msg["text"])
        
        # Show student info if available
        if msg.get("student_name"):
            st.markdown(f"**الاسم:** {msg['student_name']}")
        if msg.get("section_name"):
            st.markdown(f"**الفصل:** {msg['section_name']}")
        if msg.get("time"):
            st.markdown(f"**الوقت:** {msg['time']}")
        
        # Reset button
        if st.button("📱 مسح QR جديد", use_container_width=True, key="new_qr_scan_btn"):
            st.session_state.qr_scan_result_message = None
            st.session_state.qr_scanning_active = True
            st.session_state.qr_scan_success = False
            st.rerun()
        return
    
    # QR scanner with automatic camera permission request and improved detection
    if st.session_state.qr_scanning_active and not st.session_state.qr_scan_success:
        # Unique ID for this scanner instance to avoid conflicts on rerun
        scanner_id = f"qr-reader-{user.get('user_id', 'default')}"
        
        st.components.v1.html(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; padding: 0; font-family: 'Cairo', sans-serif; background: transparent; }}
                #{scanner_id} {{ 
                    width: 100%; 
                    min-height: 300px; 
                    border-radius: 15px; 
                    overflow: hidden;
                    background: #000;
                }}
                #qr-status {{ 
                    text-align: center; 
                    padding: 1rem; 
                    color: #667eea;
                    font-weight: 600;
                    direction: rtl;
                }}
                .scan-line {{
                    width: 100%;
                    height: 3px;
                    background: linear-gradient(90deg, transparent, #667eea, #764ba2, transparent);
                    position: absolute;
                    top: 0;
                    left: 0;
                    animation: scanMove 2s ease-in-out infinite;
                    pointer-events: none;
                }}
                @keyframes scanMove {{
                    0%, 100% {{ top: 0; }}
                    50% {{ top: 100%; }}
                }}
                #qr-reader-container {{
                    position: relative;
                    overflow: hidden;
                }}
            </style>
        </head>
        <body>
            <div id="qr-status">📱 جاري طلب إذن الكاميرا...</div>
            <div id="qr-reader-container">
                <div id="{scanner_id}"></div>
                <div class="scan-line"></div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
            <script>
                let html5QrCode = null;
                let scanningActive = false;
                const scannerId = "{scanner_id}";
                const statusEl = document.getElementById('qr-status');
                
                function startScanner() {{
                    try {{
                        html5QrCode = new Html5Qrcode(scannerId);
                        
                        html5QrCode.start(
                            {{ facingMode: "environment" }},
                            {{
                                fps: 30,
                                qrbox: {{ width: 280, height: 280 }},
                                aspectRatio: 1.0,
                                disableFlip: false
                            }},
                            function(decodedText) {{
                                if (!scanningActive) {{
                                    scanningActive = true;
                                    statusEl.innerHTML = '✅ تم المسح بنجاح! جاري المعالجة...';
                                    
                                    // Stop scanner immediately after success
                                    if (html5QrCode) {{
                                        html5QrCode.stop().catch(() => {{}});
                                    }}
                                    
                                    parent.postMessage({{
                                        type: 'QR_SCANNED',
                                        data: decodedText
                                    }}, '*');
                                }}
                            }},
                            function(error) {{
                                // Silent - no error spam for better UX
                            }}
                        ).catch(function(err) {{
                            statusEl.innerHTML = '❌ خطأ في فتح الكاميرا: ' + err;
                            parent.postMessage({{
                                type: 'CAMERA_ERROR',
                                error: err.toString()
                            }}, '*');
                        }});
                    }} catch(e) {{
                        statusEl.innerHTML = '❌ خطأ في تهيئة الماسح: ' + e.message;
                        parent.postMessage({{
                            type: 'CAMERA_ERROR',
                            error: e.message
                        }}, '*');
                    }}
                }}
                
                // Request camera permission with proper error handling
                function requestCamera() {{
                    statusEl.innerHTML = '📱 جاري طلب إذن الكاميرا...';
                    
                    // First check if mediaDevices is supported
                    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
                        statusEl.innerHTML = '❌ المتصفح لا يدعم الوصول للكاميرا';
                        parent.postMessage({{
                            type: 'CAMERA_ERROR',
                            error: 'المتصفح لا يدعم الوصول للكاميرا'
                        }}, '*');
                        return;
                    }}
                    
                    // Request camera permission
                    navigator.mediaDevices.getUserMedia({{ 
                        video: {{ 
                            facingMode: "environment",
                            width: {{ ideal: 1280 }},
                            height: {{ ideal: 720 }}
                        }} 
                    }})
                    .then(function(stream) {{
                        // Stop the test stream immediately
                        stream.getTracks().forEach(track => track.stop());
                        statusEl.innerHTML = '✅ تم الحصول على الإذن - ضع رمز QR أمام الكاميرا';
                        // Start the actual scanner
                        startScanner();
                    }})
                    .catch(function(err) {{
                        let errorMsg = '❌ رفض الإذن بالكاميرا';
                        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {{
                            errorMsg = '❌ تم رفض إذن الكاميرا. يرجى السماح بالوصول من إعدادات المتصفح.';
                        }} else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {{
                            errorMsg = '❌ لم يتم العثور على كاميرا. تأكد من توصيل الكاميرا.';
                        }} else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {{
                            errorMsg = '❌ الكاميرا قيد الاستخدام من تطبيق آخر.';
                        }}
                        statusEl.innerHTML = errorMsg;
                        parent.postMessage({{
                            type: 'CAMERA_PERMISSION_DENIED',
                            error: err.toString()
                        }}, '*');
                    }});
                }}
                
                // Request camera immediately when page loads
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', requestCamera);
                }} else {{
                    requestCamera();
                }}
                
                // Listen for stop command
                window.addEventListener('message', function(event) {{
                    if (event.data && event.data.type === 'STOP_SCANNER') {{
                        if (html5QrCode && scanningActive) {{
                            html5QrCode.stop().catch(() => {{}});
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """, height=420)
    
    # Process QR scan results from the HTML component
    qr_result = st.session_state.get("qr_scan_result")
    if qr_result and not st.session_state.get("qr_scan_result_message"):
        st.session_state.qr_scanning_active = False
        result = _process_student_qr_attendance(db, qr_result)
        if result and isinstance(result, dict):
            st.session_state.qr_scan_result_message = result
            st.session_state.qr_scan_success = True
            # Stop scanner in iframe
            try:
                st.components.v1.html("<script>parent.postMessage({type: 'STOP_SCANNER'}, '*');</script>", height=0)
            except Exception:
                pass
        elif result and result is True:
            st.session_state.qr_scan_success = True
        st.rerun()
    
    # Manual QR input fallback (shown only when no success yet)
    if not st.session_state.qr_scan_success and not st.session_state.get("qr_scan_result_message"):
        st.markdown("---")
        st.markdown("#### 💻 إدخال QR يدوياً")
        qr_input = st.text_area("الصق بيانات QR هنا (نص JSON)", height=80, key="student_qr_manual_input")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔍 معالجة QR", key="process_student_qr_btn", use_container_width=True):
                if qr_input and qr_input.strip():
                    result = _process_student_qr_attendance(db, qr_input.strip())
                    if result and isinstance(result, dict):
                        st.session_state.qr_scan_result_message = result
                        st.session_state.qr_scan_success = True
                        st.rerun()
                    elif result is True:
                        st.session_state.qr_scan_success = True
                        st.rerun()
                else:
                    st.error("يرجى إدخال نص QR أولاً")
        with col_btn2:
            if st.button("🔄 إعادة مسح الكاميرا", key="rescan_btn", use_container_width=True):
                st.session_state.qr_scanning_active = True
                st.session_state.qr_scan_success = False
                st.session_state.qr_scan_result_message = None
                st.session_state.qr_camera_check_done = False
                st.rerun()

def _process_student_qr_attendance(db: Database, qr_data: str):
    """
    Process student QR code and record attendance.
    
    QR Format (JSON):
    {
        "student_id": "STU000125",
        "section_id": "SEC003"
    }
    
    Flow:
    1. Parse JSON → extract student_id, section_id
    2. Find student in Students sheet
    3. Verify student exists
    4. Verify student status = ACTIVE
    5. Verify QR section_id matches student's section_id
    6. Check Attendance sheet for duplicate (same student_id + same date)
    7. If duplicate → return warning
    8. Insert new row into Attendance sheet
    """
    students = db.get_students()
    if students.empty:
        return {"type": "error", "text": "❌ لا توجد طالبات مسجلات في النظام"}
    
    # Parse JSON from QR code
    try:
        qr_json = json.loads(qr_data)
    except json.JSONDecodeError:
        # Try legacy format: "student:{student_id}:{checksum}"
        if qr_data.startswith("student:"):
            try:
                parts = qr_data.split(":")
                if len(parts) >= 2:
                    student_id = parts[1]
                    student_row = students[students.student_id == student_id]
                    if student_row.empty:
                        return {"type": "error", "text": "❌ الطالبة غير موجودة في النظام"}
                    student = student_row.iloc[0].to_dict()
                    # Legacy: skip strict section validation, just record
                    return _save_qr_attendance(db, student, student_id, student.get("section_id", ""))
            except Exception:
                pass
        return {"type": "error", "text": "❌ رمز QR غير صالح - يجب أن يكون بصيغة JSON"}
    
    # Validate required fields
    if "student_id" not in qr_json or "section_id" not in qr_json:
        return {"type": "error", "text": "❌ رمز QR غير مكتمل - يجب أن يحتوي على student_id و section_id"}
    
    student_id = str(qr_json["student_id"]).strip()
    qr_section_id = str(qr_json["section_id"]).strip()
    
    if not student_id or not qr_section_id:
        return {"type": "error", "text": "❌ رمز QR غير صالح - student_id أو section_id فارغ"}
    
    # Find student in database
    student_row = students[students.student_id == student_id]
    if student_row.empty:
        return {"type": "error", "text": f"❌ الطالبة برقم {student_id} غير موجودة في النظام"}
    
    student = student_row.iloc[0].to_dict()
    
    # Verify student status = ACTIVE
    student_status = str(student.get("status", "active")).strip().lower()
    if student_status != "active":
        return {"type": "error", "text": f"❌ حساب الطالبة {student.get('full_name', '')} غير نشط"}
    
    # Verify section_id matches between QR and student record
    student_section_id = str(student.get("section_id", "")).strip()
    if student_section_id and student_section_id != qr_section_id:
        return {
            "type": "error",
            "text": f"❌ رمز QR لا يخص طالبة في هذا الفصل. الفصل المسجل: {student_section_id}"
        }
    
    # All validations passed - save attendance
    return _save_qr_attendance(db, student, student_id, qr_section_id)

def _save_qr_attendance(db: Database, student: dict, student_id: str, section_id: str):
    """
    Save QR attendance record to Attendance sheet.
    Uses existing Attendance worksheet columns:
    record_id, date, student_id, status, notes, recorded_by, section_id
    
    Duplicate protection: Same student_id + Same date → reject
    """
    today = get_cairo_now().strftime("%Y-%m-%d")
    now_time = get_cairo_now().strftime("%H:%M:%S")
    user = st.session_state.get("user", {})
    recorded_by = user.get("user_id", "") if user else ""
    
    # --- DUPLICATE PROTECTION ---
    # Check Attendance sheet for existing record with same student_id AND same date
    attendance = db.get_attendance()
    if not attendance.empty:
        existing = attendance[
            (attendance.student_id == student_id) & 
            (attendance.date == today)
        ]
        if not existing.empty:
            section_name = ""
            sections = db.get_sections()
            if not sections.empty and section_id:
                sec = sections[sections.section_id == section_id]
                if not sec.empty:
                    section_name = sec.iloc[0].get("section_name", "")
            
            return {
                "type": "warning",
                "text": "⚠️ **تم تسجيل الحضور مسبقاً اليوم**",
                "student_name": student.get("full_name", ""),
                "section_name": section_name,
                "time": now_time
            }
    
    # --- CREATE NEW ATTENDANCE RECORD ---
    record = {
        "record_id": str(uuid.uuid4()),
        "date": today,
        "student_id": student_id,
        "status": "Present",
        "notes": "QR Attendance",
        "recorded_by": recorded_by,
        "section_id": section_id
    }
    
    # Insert into existing Attendance sheet using existing columns
    df = db.get_attendance()
    if df.empty:
        df = pd.DataFrame(columns=["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    db._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
    
    # Get section name for display
    section_name = ""
    sections = db.get_sections()
    if not sections.empty and section_id:
        sec = sections[sections.section_id == section_id]
        if not sec.empty:
            section_name = sec.iloc[0].get("section_name", "")
    
    # Log the action
    db.add_log(recorded_by, f"QR Attendance: {student.get('full_name', '')} - {today}")
    
    return {
        "type": "success",
        "text": f"✅ **تم تسجيل حضور الطالبة بنجاح**",
        "student_name": student.get("full_name", ""),
        "section_name": section_name,
        "time": now_time
    }

def show_teacher_qr_attendance(db: Database):
    """Teacher QR attendance - scan QR to record teacher attendance with camera permission handling."""
    st.markdown("<h2 class='main-header'>📱 حضور المدرسين بالرمز الثنائي</h2>", unsafe_allow_html=True)
    
    # Initialize QR scanning state
    if 'qr_teacher_scanning_active' not in st.session_state:
        st.session_state.qr_teacher_scanning_active = True
    if 'qr_teacher_scan_success' not in st.session_state:
        st.session_state.qr_teacher_scan_success = False
    if 'qr_teacher_scan_result' not in st.session_state:
        st.session_state.qr_teacher_scan_result = None
    
    # Camera permission check with professional dialog
    if st.session_state.get("qr_camera_error"):
        st.markdown("""
        <style>
        .qr-permission-dialog {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            z-index: 99999;
            max-width: 400px;
            width: 90%;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="qr-permission-dialog">
            <h3 style="color: #e74c3c; text-align: center;">⚠️ إذن الكاميرا مطلوب</h3>
            <p style="text-align: center; margin: 1rem 0;">
                يرجى السماح باستخدام الكاميرا لمسح رموز الاستجابة السريعة.<br>
                اضغط على "سماح" أو "Allow" عند طلب الإذن.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 إعادة المحاولة", use_container_width=True):
                st.session_state.qr_camera_error = False
                st.session_state.qr_teacher_scanning_active = True
                st.rerun()
        with col2:
            if st.button("❌ إلغاء", use_container_width=True):
                st.session_state.qr_camera_error = False
                st.session_state.qr_teacher_scanning_active = False
                st.rerun()
        return
    
    # QR scanner with automatic camera permission request
    if st.session_state.qr_teacher_scanning_active and not st.session_state.qr_teacher_scan_success:
        st.components.v1.html("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body { margin: 0; padding: 0; font-family: 'Cairo', sans-serif; background: transparent; }
                #qr-reader { width: 100%; min-height: 300px; border-radius: 15px; overflow: hidden; }
                #qr-status { text-align: center; padding: 1rem; color: #667eea; }
                .scanning-animation {
                    width: 100%;
                    height: 4px;
                    background: linear-gradient(90deg, #667eea, #764ba2, #667eea);
                    animation: scanning 2s infinite;
                    margin-top: 1rem;
                }
                @keyframes scanning {
                    0% { transform: translateX(-100%); }
                    100% { transform: translateX(100%); }
                }
            </style>
        </head>
        <body>
            <div id="qr-status">📱 طلب إذن الكاميرا... يرجى السماح</div>
            <div id="qr-reader"></div>
            <div class="scanning-animation"></div>
            <script src="https://cdn.jsdelivr.net/npm/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
            <script>
                let html5QrCode;
                let scanning = false;
                
                // Request camera permission immediately on page load
                navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
                    .then(function(stream) {
                        stream.getTracks().forEach(track => track.stop());
                        document.getElementById('qr-status').innerHTML = '✅ تم الحصول على إذن الكاميرا - ضع رمز QR أمام الكاميرا';
                        
                        html5QrCode = new Html5Qrcode("qr-reader");
                        html5QrCode.start(
                            { facingMode: "environment" },
                            {
                                fps: 15,
                                qrbox: { width: 250, height: 250 },
                                aspectRatio: 1.0,
                                disableFlip: false
                            },
                            function(decodedText) {
                                if (!scanning) {
                                    scanning = true;
                                    document.getElementById('qr-status').innerHTML = '✅ تم المسح بنجاح! جاري المعالجة...';
                                    parent.postMessage({type: 'QR_SCANNED', data: decodedText}, '*');
                                }
                            },
                            function(error) {
                                // Silent scanning - no error display for better UX
                            }
                        ).catch(function(err) {
                            document.getElementById('qr-status').innerHTML = '❌ خطأ في فتح الكاميرا: ' + err;
                            parent.postMessage({type: 'CAMERA_ERROR', error: err}, '*');
                        });
                    })
                    .catch(function(err) {
                        document.getElementById('qr-status').innerHTML = '❌ إذن الكاميرا مرفوض أو غير متاح';
                        parent.postMessage({type: 'CAMERA_PERMISSION_DENIED', error: err}, '*');
                    });
                
                window.addEventListener('message', function(event) {
                    if (event.data && event.data.type === 'STOP_SCANNER') {
                        if (html5QrCode && scanning) {
                            html5QrCode.stop().catch(() => {});
                        }
                    }
                });
            </script>
        </body>
        </html>
        """, height=400)
        
        # Stop scanning after successful attendance
        if st.session_state.qr_teacher_scan_success:
            st.components.v1.html("""
            <script>
                parent.postMessage({type: 'STOP_SCANNER'}, '*');
            </script>
            """, height=0)
    
    # Show QR input or success message
    if st.session_state.qr_teacher_scan_success:
        st.success(f"✅ تم تسجيل الحضور بنجاح!")
        st.session_state.qr_teacher_scanning_active = False
    else:
        st.markdown("#### إدخال QR يدوياً (إذا كانت الكاميرا غير متاحة)")
        qr_input = st.text_area("الصق بيانات QR هنا أو امسح بالكاميرا", height=100, key="teacher_qr_manual_input")
        
        if st.button("معالجة QR", key="process_teacher_qr_btn"):
            if qr_input and qr_input.strip():
                result = _process_teacher_qr_attendance(db, qr_input.strip())
                if result:
                    st.session_state.qr_teacher_scan_success = True
                    st.rerun()
            else:
                st.error("يرجى إدخال أو مسح رمز QR أولاً")

def _process_teacher_qr_attendance(db: Database, qr_data: str):
    """Process teacher QR code and record attendance."""
    users = db.get_users()
    if users.empty:
        st.error("لا يوجد مستخدمون في النظام")
        return
    
    if not qr_data.startswith("user:"):
        st.error("❌ رمز QR غير صالح - يجب أن يكون للمدرس")
        return
    
    try:
        parts = qr_data.split(":")
        if len(parts) < 2:
            st.error("❌ تنسيق رمز QR غير صحيح")
            return
        
        teacher_id = parts[1]
        teachers = users[users.role == "Teacher"]
        teacher_row = teachers[teachers.user_id == teacher_id]
        
        if teacher_row.empty:
            st.error("❌ المدرس غير موجود أو غير مدرس في النظام")
            return
        
        teacher = teacher_row.iloc[0].to_dict()
        
        # Check for duplicate attendance today
        today = get_cairo_now().strftime("%Y-%m-%d")
        ta = db.get_teacher_attendance()
        if not ta.empty:
            existing = ta[(ta.teacher_id == teacher_id) & (ta.date == today)]
            if not existing.empty:
                st.warning(f"⚠️ تم تسجيل حضور هذا المدرس مسبقاً اليوم")
                st.markdown(f"**الاسم:** {teacher.get('full_name', '')}")
                return
        
        # Record attendance
        record = {
            "id": str(uuid.uuid4()),
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("full_name", ""),
            "date": today,
            "status": "present",
            "check_in_time": get_cairo_now().strftime("%H:%M:%S"),
            "method": "qr",
            "recorded_by": st.session_state.user.get("user_id", "")
        }
        
        db.add_teacher_attendance(record)
        st.success(f"✅ تم تسجيل حضور المدرس: {teacher.get('full_name', '')}")
        st.balloons()
        
        sections = db.get_sections()
        if not sections.empty and teacher.get("section_id"):
            sec = sections[sections.section_id == teacher.get("section_id")]
            if not sec.empty:
                st.markdown(f"**الفصل:** {sec.iloc[0].get('section_name', '')}")
        st.markdown(f"**الوقت:** {get_cairo_now().strftime('%H:%M:%S')}")
        
        db.add_log("", f"QR Teacher Attendance: {teacher.get('full_name', '')}")
        
    except Exception as e:
        st.error(f"❌ خطأ في معالجة الرمز: {str(e)}")

def generate_qr_for_all_users(db: Database):
    """Generate QR codes for authorized users only (Service Managers, Teachers, and Students)."""
    users = db.get_users()
    if users.empty:
        return {}
    
    # Authorized roles for QR code generation
    authorized_roles = ["Service Manager", "Teacher"]
    
    qr_codes = {}
    for _, user in users.iterrows():
        user_id = user.get("user_id", "")
        role = user.get("role", "")
        
        # Only generate QR codes for authorized roles
        if role not in authorized_roles:
            continue
        
        user_type = "user"
        qr_codes[user_id] = get_qr_for_user(user_id, user_type)
    return qr_codes

if __name__ == "__main__":
    main()
