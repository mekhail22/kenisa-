
# Writing the complete fixed code - Part 1 (Imports and Setup)

part1 = '''import streamlit as st
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

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
CACHE_TTL_SECONDS = 120

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
'''

print("Part 1 written successfully")
print(f"Length: {len(part1)} chars")

# Part 2 - CSS Injection

part2 = '''
# =============================================================================
# CSS محسّن (الشريط الجانبي يفتح من اليمين كطبقة منزلقة)
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

        .timer-container { text-align: center; margin: 1rem 0; }
        .timer-box {
            display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2);
            color: white; padding: 0.8rem 2rem; border-radius: 15px;
            font-size: 1.8rem; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
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

        .quiz-review-card {
            background: white; border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 1rem;
            border-right: 5px solid #e74c3c;
        }
        .quiz-review-card.correct {
            border-right-color: #27ae60;
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
'''

print("Part 2 written successfully")
print(f"Length: {len(part2)} chars")

# Part 3 - SheetCache and Retry decorator

part3 = '''
# =============================================================================
# SheetCache
# =============================================================================
class SheetCache:
    def __init__(self):
        if 'sheet_cache' not in st.session_state:
            st.session_state.sheet_cache = {}
        if 'log_buffer' not in st.session_state:
            st.session_state.log_buffer = []

    def get(self, sheet_name):
        cache = st.session_state.sheet_cache
        if sheet_name in cache:
            entry = cache[sheet_name]
            if time.time() - entry['timestamp'] < CACHE_TTL_SECONDS:
                return entry['data']
        return None

    def set(self, sheet_name, data):
        st.session_state.sheet_cache[sheet_name] = {
            'data': data,
            'timestamp': time.time()
        }

    def invalidate(self, sheet_name):
        if sheet_name in st.session_state.sheet_cache:
            del st.session_state.sheet_cache[sheet_name]

    def clear_all(self):
        st.session_state.sheet_cache = {}

    def buffer_log(self, log_entry):
        st.session_state.log_buffer.append(log_entry)

    def flush_logs(self, db_instance):
        if st.session_state.log_buffer:
            logs = st.session_state.log_buffer.copy()
            st.session_state.log_buffer = []
            try:
                df = db_instance._sheet_to_df("Logs")
                if df.empty:
                    df = pd.DataFrame(columns=["log_id", "timestamp", "user_id", "action", "details"])
                new_rows = pd.DataFrame(logs)
                df = pd.concat([df, new_rows], ignore_index=True)
                db_instance._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])
            except Exception as e:
                st.warning(f"تعذر حفظ السجلات المؤقتة: {str(e)}")

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
'''

print("Part 3 written successfully")
print(f"Length: {len(part3)} chars")

# Part 4 - Database Class (FIXED with proper section name handling and Google Sheets fixes)

part4 = '''
# =============================================================================
# Database Class - FIXED
# =============================================================================
class Database:
    def __init__(self, creds, spreadsheet_id):
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        self.cache = SheetCache()

    @retry_operation(max_retries=5, base_delay=2)
    def _get_or_create_worksheet(self, name, columns):
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(columns), 1))
            if columns:
                ws.append_row(columns)
        return ws

    def _sheet_to_df(self, sheet_name):
        cached = self.cache.get(sheet_name)
        if cached is not None:
            return cached.copy()
        try:
            ws = self._get_or_create_worksheet(sheet_name, [])
            data = ws.get_all_records()
            if not data:
                df = pd.DataFrame()
            else:
                df = pd.DataFrame(data)
                df.dropna(how='all', axis=1, inplace=True)
                df = df.astype(object)
            self.cache.set(sheet_name, df.copy())
            return df
        except Exception as e:
            st.error(f"❌ فشل قراءة {sheet_name}: {str(e)}")
            return pd.DataFrame()

    def _df_to_sheet(self, sheet_name, df, columns):
        if not isinstance(df, pd.DataFrame):
            raise ValueError("df must be a DataFrame")
        if not isinstance(columns, list) or not columns:
            raise ValueError("columns must be a non-empty list")
        ws = self._get_or_create_worksheet(sheet_name, columns)
        ws.clear()
        if df.empty:
            ws.update([columns])
        else:
            for col in columns:
                if col not in df.columns:
                    df[col] = ""
            work_df = df[columns].copy()
            work_df.fillna("", inplace=True)
            work_df = work_df.astype(str)
            values = [columns] + work_df.values.tolist()
            ws.update(values)
        self.cache.invalidate(sheet_name)

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

    # --- Sections ---
    def get_sections(self):
        """قراءة الفصول مع التأكد من وجود الأعمدة الصحيحة"""
        df = self._sheet_to_df("Sections")
        if df.empty:
            return pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
        # التأكد من وجود الأعمدة المطلوبة
        required_cols = ["section_id", "section_name"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""
        return df

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
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, df.columns.tolist())

    # --- Students ---
    def get_students(self):
        df = self._sheet_to_df("Students")
        if df.empty:
            return pd.DataFrame(columns=["student_id", "full_name", "section_id", "teacher_id",
                                         "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])
        return df

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
        df = self._sheet_to_df("Quizzes")
        if df.empty:
            return pd.DataFrame(columns=["quiz_id", "title", "description", "created_by", "section_id",
                                         "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                         "quiz_code", "password", "is_active"])
        return df

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
                                               "score", "total_marks", "submission_time", "answers", "status"])

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

    # --- Quiz Results (مع حفظ تلقائي) ---
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
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            df = pd.DataFrame(columns=["result_id", "quiz_id", "student_id", "student_name",
                                       "score", "total_marks", "submission_time", "answers", "status"])
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "submission_time", "answers", "status"])
        return result_id

    def save_answers(self, result_id, answers_dict):
        """تحديث حقل الإجابات فقط"""
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

    # --- Logs ---
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
        self.cache.buffer_log(log)

    def delete_log(self, log_id):
        df = self.get_logs()
        df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])
'''

print("Part 4 written successfully")
print(f"Length: {len(part4)} chars")

# Part 5 - JWT, Session, Telegram, Help Dialog

part5 = '''
# =============================================================================
# JWT & Session Helpers
# =============================================================================
def generate_token(user: dict, secret: str) -> str:
    payload = {
        "user_id": user["user_id"],
        "role": user["role"],
        "full_name": user["full_name"],
        "section_id": user.get("section_id", ""),
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

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
        "quiz_answers": {},
        "quiz_submitted": False,
        "last_score": 0,
        "menu_choice": "🏠 لوحة التحكم",
        "show_sidebar": True,
        "open_help_dialog": False,
        "current_attempt_id": None,
        "last_saved_answers_str": "",
        "show_quiz_review": False,  # جديد: لعرض مراجعة الأخطاء
        "quiz_wrong_answers": []    # جديد: لتخزين الأخطاء
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout(db=None):
    if db and st.session_state.user:
        try:
            db.cache.flush_logs(db)
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

# =============================================================================
# Helper: الحصول على اسم الفصل من الـ ID
# =============================================================================
def get_section_name_by_id(db: Database, section_id: str) -> str:
    """ترجمة section_id إلى اسم الفصل"""
    if not section_id:
        return "غير محدد"
    sections = db.get_sections()
    if sections.empty:
        return str(section_id)
    match = sections[sections["section_id"] == section_id]
    if not match.empty:
        return str(match.iloc[0]["section_name"])
    return str(section_id)

def get_section_id_by_name(db: Database, section_name: str) -> str:
    """ترجمة اسم الفصل إلى section_id"""
    if not section_name:
        return ""
    sections = db.get_sections()
    if sections.empty:
        return ""
    match = sections[sections["section_name"] == section_name]
    if not match.empty:
        return str(match.iloc[0]["section_id"])
    return ""

def add_section_names_to_df(db: Database, df: pd.DataFrame, section_id_col: str = "section_id") -> pd.DataFrame:
    """إضافة عمود اسم الفصل إلى DataFrame"""
    if df.empty or section_id_col not in df.columns:
        return df
    sections = db.get_sections()
    if sections.empty or "section_name" not in sections.columns:
        df["اسم الفصل"] = df[section_id_col].apply(lambda x: str(x) if pd.notna(x) else "غير محدد")
        return df
    # دمج DataFrame مع جدول الفصول
    df = df.merge(sections[["section_id", "section_name"]], on=section_id_col, how="left")
    df["section_name"] = df["section_name"].fillna("غير محدد")
    df = df.rename(columns={"section_name": "اسم الفصل"})
    return df

# =============================================================================
# مركز المساعدة المحسّن
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
                if send_telegram_message(message):
                    st.success("✅ تم إرسال طلبك بنجاح! سنتواصل معك قريباً.")
                    st.balloons()
                else:
                    st.error("❌ فشل الإرسال، يرجى المحاولة لاحقاً أو التواصل مباشرة عبر الواتساب.")
'''

print("Part 5 written successfully")
print(f"Length: {len(part5)} chars")

# Part 6 - Initialization and Login (FIXED)

part6 = '''
# =============================================================================
# Initialization & Login
# =============================================================================
def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", type="primary", use_container_width=True, key="init_admin_btn"):
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

def show_login_page(db: Database, jwt_secret: str):
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
                                    st.session_state.show_quiz_review = False
                                    st.session_state.quiz_wrong_answers = []
                                    st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")
'''

print("Part 6 written successfully")
print(f"Length: {len(part6)} chars")

# Part 6 - Initialization and Login (FIXED)

part6 = '''
# =============================================================================
# Initialization & Login
# =============================================================================
def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", type="primary", use_container_width=True, key="init_admin_btn"):
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

def show_login_page(db: Database, jwt_secret: str):
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
                                    st.session_state.show_quiz_review = False
                                    st.session_state.quiz_wrong_answers = []
                                    st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")
'''

print("Part 6 written successfully")
print(f"Length: {len(part6)} chars")

# Part 8 - Sidebar Navigation

part8 = '''
# =============================================================================
# Sidebar Navigation (محتوى الشريط الجانبي)
# =============================================================================
def show_sidebar_navigation(db: Database):
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.user
        st.markdown(f"**👤 {user['full_name']}**")
        st.caption(f"الصلاحية: {user['role']}")
        
        # عرض اسم الفصل بدلاً من الـ ID
        section_id = user.get("section_id", "")
        if section_id:
            section_name = get_section_name_by_id(db, section_id)
            st.caption(f"الفصل: {section_name}")
        
        st.divider()

        role = user["role"]
        menus = {
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
'''

print("Part 8 written successfully")
print(f"Length: {len(part8)} chars")

# Part 9 - Dashboard (FIXED with section names and top section scores)

part9 = '''
# =============================================================================
# Dashboard - FIXED
# =============================================================================
def show_dashboard(db: Database):
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)

    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()
    quizzes = db.get_quizzes()
    results = db.get_quiz_results()
    sections = db.get_sections()

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

    st.markdown("---")
    
    # إضافة: أكثر فصل جايب درجات
    if role in ["System Admin", "Father Account"]:
        st.markdown("#### 🏆 أكثر الفصول تحصيلاً في الامتحانات")
        if not results.empty and not students.empty and not sections.empty:
            # دمج النتائج مع الطالبات للحصول على الفصل
            results_submitted = results[results["status"] == "submitted"] if "status" in results.columns else results
            if not results_submitted.empty:
                results_with_students = results_submitted.merge(
                    students[["student_id", "section_id"]], on="student_id", how="left"
                )
                results_with_students = results_with_students.merge(
                    sections[["section_id", "section_name"]], on="section_id", how="left"
                )
                results_with_students["score"] = pd.to_numeric(results_with_students["score"], errors="coerce").fillna(0)
                
                section_scores = results_with_students.groupby("section_name")["score"].agg(['sum', 'mean', 'count']).reset_index()
                section_scores.columns = ["اسم الفصل", "مجموع الدرجات", "متوسط الدرجة", "عدد الاختبارات"]
                section_scores = section_scores.sort_values("مجموع الدرجات", ascending=False)
                
                if not section_scores.empty:
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        fig = px.bar(section_scores, x="اسم الفصل", y="مجموع الدرجات", 
                                    color="متوسط الدرجة", title="درجات الفصول")
                        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True)
                    with c2:
                        st.dataframe(section_scores, use_container_width=True)
                else:
                    st.info("لا توجد نتائج اختبارات مسجلة بعد.")
            else:
                st.info("لا توجد نتائج اختبارات مسجلة بعد.")
        else:
            st.info("لا توجد بيانات كافية لعرض إحصائيات الفصول.")

    st.markdown("#### 📈 الحضور الأسبوعي")
    if not attendance.empty:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
        last_week = datetime.now() - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty:
            # إضافة اسم الفصل للعرض
            if not sections.empty:
                recent = recent.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
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
                absent_counts = absent_counts.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
                # إضافة اسم الفصل
                absent_counts = add_section_names_to_df(db, absent_counts, "section_id")
            st.dataframe(absent_counts[["full_name", "اسم الفصل", "أيام الغياب"]], use_container_width=True)
        else:
            st.info("لا يوجد غياب هذا الشهر.")

    st.markdown("#### 🔔 بنات بحاجة لافتقاد عاجل")
    urgent = followup[followup.regularity_status.isin(["منقطع", "متقطع"])] if not followup.empty else pd.DataFrame()
    if not urgent.empty:
        if not students.empty:
            urgent = urgent.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
            urgent = add_section_names_to_df(db, urgent, "section_id")
        st.dataframe(urgent[["full_name", "اسم الفصل", "followup_date", "notes"]], use_container_width=True)
    else:
        st.info("كل البنات منتظمات.")
'''

print("Part 9 written successfully")
print(f"Length: {len(part9)} chars")

# Part 10 - User Management (FIXED with section names instead of IDs)

part10 = '''
# =============================================================================
# إدارة المستخدمين - FIXED
# =============================================================================
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    students = db.get_students()
    
    # إضافة اسم الفصل لجدول المستخدمين
    if not users.empty and not sections.empty:
        users_display = users.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
        users_display["section_name"] = users_display["section_name"].fillna("غير محدد")
    else:
        users_display = users.copy() if not users.empty else pd.DataFrame()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول"])

    with tab1:
        st.subheader("قائمة المستخدمين (خدام)")
        if not users_display.empty:
            display_cols = ["user_id", "username", "full_name", "role", "section_name", "phone", "email"]
            available_cols = [c for c in display_cols if c in users_display.columns]
            rename_map = {"section_name": "الفصل"}
            st.dataframe(users_display[available_cols].rename(columns=rename_map), use_container_width=True)
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
                    section_options = ["None"] + sections["section_name"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, 
                        format_func=lambda x: x if x != "None" else "لا يوجد")
                    section_id = get_section_id_by_name(db, section_choice) if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف (اختياري)")
                email = st.text_input("البريد الإلكتروني (اختياري)")
                if st.form_submit_button("إضافة"):
                    if not username or not password or not full_name:
                        st.error("مطلوب اسم المستخدم وكلمة المرور والاسم الكامل")
                    elif not users.empty and not users[users.username == username].empty:
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
                # عرض الأسماء بدلاً من IDs
                user_options = dict(zip(users["user_id"], users["full_name"]))
                selected_user_id = st.selectbox("اختر المستخدم", options=list(user_options.keys()),
                                                format_func=lambda x: user_options[x], key="sel_user_edit")
                user_data = users[users.user_id == selected_user_id].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=user_data.get("full_name", ""), key="user_fullname")
                new_phone = st.text_input("رقم الهاتف", value=user_data.get("phone", ""), key="user_phone")
                new_email = st.text_input("البريد الإلكتروني", value=user_data.get("email", ""), key="user_email")
                roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher"]
                current_role = user_data.get("role", "Teacher")
                role_index = roles_list.index(current_role) if current_role in roles_list else 3
                new_role = st.selectbox("الصلاحية", roles_list, index=role_index, key="user_role")
                new_section_id = user_data.get("section_id", "")
                if new_role in ["Service Manager", "Teacher"]:
                    if not sections.empty:
                        section_options = ["None"] + sections["section_name"].tolist()
                        current_name = get_section_name_by_id(db, new_section_id)
                        current_idx = section_options.index(current_name) if current_name in section_options else 0
                        section_choice = st.selectbox("الفصل", section_options, index=current_idx, 
                            format_func=lambda x: x if x != "None" else "لا يوجد", key="user_section")
                        new_section_id = get_section_id_by_name(db, section_choice) if section_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات", key="update_user_btn"):
                    db.update_user(selected_user_id, {"full_name": new_full_name, "phone": new_phone, "email": new_email, "role": new_role, "section_id": new_section_id})
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المستخدم", key="delete_user_btn"):
                    if selected_user_id == st.session_state.user["user_id"]:
                        st.error("لا يمكنك حذف حسابك الحالي!")
                    else:
                        db.delete_user(selected_user_id)
                        st.success("تم الحذف")
                        time.sleep(1)
                        st.rerun()

    with tab2:
        st.subheader("قائمة المدرسات")
        teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
        if not teachers.empty:
            if not sections.empty:
                teachers_display = teachers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                teachers_display = teachers_display.rename(columns={"section_name": "الفصل"})
            else:
                teachers_display = teachers
                teachers_display["الفصل"] = "غير محدد"
            st.dataframe(teachers_display[["user_id", "username", "full_name", "الفصل", "phone", "email"]], use_container_width=True)
        else:
            st.info("لا توجد مدرسات مسجلات.")
        with st.expander("➕ إضافة مدرسة جديدة"):
            with st.form("add_teacher_form"):
                teacher_name = st.text_input("اسم المستخدم*")
                password = st.text_input("كلمة المرور*", type="password")
                section_id = ""
                if not sections.empty:
                    section_options = ["None"] + sections["section_name"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, 
                        format_func=lambda x: x if x != "None" else "لا يوجد")
                    section_id = get_section_id_by_name(db, section_choice) if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة"):
                    if not teacher_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif not users.empty and not users[users.username == teacher_name].empty:
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
                students_display = students_display.rename(columns={"section_name": "الفصل"})
            else:
                students_display = students
                students_display["الفصل"] = "غير محدد"
            display_cols = ["student_id", "full_name", "الفصل", "phone", "parent_phone", "birthdate", "school", "status"]
            available_cols = [c for c in display_cols if c in students_display.columns]
            st.dataframe(students_display[available_cols], use_container_width=True)
        else:
            st.info("لا توجد طالبات مسجلة.")
        with st.expander("➕ إضافة طالبة جديدة"):
            with st.form("add_student_form"):
                full_name = st.text_input("الاسم الكامل*")
                section_id = ""
                if not sections.empty:
                    section_options = sections["section_name"].tolist()
                    section_choice = st.selectbox("الفصل", section_options)
                    section_id = get_section_id_by_name(db, section_choice)
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
                student_options = dict(zip(students["student_id"], students["full_name"]))
                selected_student = st.selectbox("اختر طالبة", options=list(student_options.keys()),
                                                format_func=lambda x: student_options[x], key="sel_student_edit")
                student_row = students[students.student_id == selected_student].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""), key="student_fullname")
                new_section_id = student_row.get("section_id", "")
                if not sections.empty:
                    section_options = sections["section_name"].tolist()
                    current_name = get_section_name_by_id(db, new_section_id)
                    current_idx = section_options.index(current_name) if current_name in section_options else 0
                    section_choice = st.selectbox("الفصل", section_options, index=current_idx, key="student_section")
                    new_section_id = get_section_id_by_name(db, section_choice)
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
                delete_options = dict(zip(students["student_id"], students["full_name"]))
                delete_id = st.selectbox("اختر طالبة للحذف", options=list(delete_options.keys()),
                                        format_func=lambda x: delete_options[x], key="delete_student_sel")
                if st.button("تأكيد حذف الطالبة"):
                    db.delete_student(delete_id)
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()

    with tab4:
        st.subheader("قائمة أمناء الخدمة")
        managers = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
        if not managers.empty:
            if not sections.empty:
                mgr_display = managers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                mgr_display = mgr_display.rename(columns={"section_name": "الفصل"})
            else:
                mgr_display = managers
                mgr_display["الفصل"] = "غير محدد"
            st.dataframe(mgr_display[["user_id", "username", "full_name", "الفصل", "phone", "email"]], use_container_width=True)
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
                del_options = dict(zip(sections["section_id"], sections["section_name"]))
                del_sec = st.selectbox("اختر فصل", options=list(del_options.keys()),
                                      format_func=lambda x: del_options[x], key="del_section_sel")
                if st.button("تأكيد حذف الفصل"):
                    db.delete_section(del_sec)
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()
'''

print("Part 10 written successfully")
print(f"Length: {len(part10)} chars")
# =============================================================================
# Attendance - FIXED
# =============================================================================
def show_attendance(db: Database):
    user = st.session_state.user
    role = user["role"]
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
        section_name = get_section_name_by_id(db, section_id)
        st.write(f"**الفصل:** {section_name}")
    else:
        # عرض أسماء الفصول بدلاً من IDs
        section_options = dict(zip(sections["section_id"], sections["section_name"]))
        selected_section = st.selectbox("اختر الفصل", options=list(section_options.keys()),
                               format_func=lambda x: section_options[x])
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
                    "recorded_by": user["user_id"], "section_id": selected_section
                })
            db.batch_add_attendance(records)
            section_name = get_section_name_by_id(db, selected_section)
            db.add_log(user["user_id"], f"تسجيل حضور فصل {section_name} ليوم {date_str}")
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
# Follow-up - FIXED
# =============================================================================
def show_followup(db: Database):
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    students = db.get_students()
    followup = db.get_followup()

    if role == "Teacher" and section_id:
        responsible = students[students.section_id == section_id] if not students.empty else pd.DataFrame()
    elif role == "Service Manager" and section_id:
        responsible = students[students.section_id == section_id] if not students.empty else students
    else:
        responsible = students

    if responsible.empty:
        st.info("لا توجد طالبات مسؤولات عنك.")
        return

    # إضافة اسم الفصل
    responsible = add_section_names_to_df(db, responsible, "section_id")

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
            urgent_display = urgent.merge(responsible[["student_id", "full_name", "اسم الفصل"]], on="student_id", how="left")
            st.dataframe(urgent_display[["full_name", "اسم الفصل", "followup_date", "followup_type", "notes"]], use_container_width=True)
        else:
            st.info("كل البنات منتظمات حالياً.")
    else:
        st.info("لا توجد متابعات سابقة.")

    st.markdown("---")
    st.subheader("➕ إضافة متابعة جديدة")
    # عرض الطالبات بأسمائها وأسماء فصولها
    student_options = dict(zip(responsible["student_id"], 
                              responsible.apply(lambda r: f"{r['full_name']} (فصل: {r.get('اسم الفصل', 'غير محدد')})", axis=1)))
    student = st.selectbox("اختر الطالبة", options=list(student_options.keys()),
                           format_func=lambda x: student_options[x], key="followup_student")
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

# =============================================================================
# My Students - FIXED
# =============================================================================
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

    # إضافة اسم الفصل
    my_students = add_section_names_to_df(db, my_students, "section_id")

    if not followup.empty:
        latest_fup = followup.sort_values("followup_date").groupby("student_id").last().reset_index()
        my_students = my_students.merge(latest_fup[["student_id", "regularity_status"]], on="student_id", how="left")
        my_students["regularity_status"] = my_students["regularity_status"].fillna("غير معروف")
    else:
        my_students["regularity_status"] = "غير معروف"

    display_cols = ["full_name", "اسم الفصل", "phone", "regularity_status"]
    available_cols = [c for c in display_cols if c in my_students.columns]
    st.dataframe(my_students[available_cols], use_container_width=True)

    st.markdown("---")
    st.subheader("➕ إضافة متابعة سريعة")
    student_options = dict(zip(my_students["student_id"], my_students["full_name"]))
    selected = st.selectbox("اختر طالبة", options=list(student_options.keys()),
                            format_func=lambda x: student_options[x], key="my_students_fup")
    with st.expander("فتح نموذج المتابعة"):
        with st.form("quick_followup_form"):
            ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
            notes = st.text_area("ملاحظات")
            regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
            if st.form_submit_button("حفظ المتابعة"):
                db.add_followup_record({
                    "record_id": str(uuid.uuid4()), "student_id": selected,
                    "teacher_id": user["user_id"], "followup_date": datetime.now().strftime("%Y-%m-%d"),
                    "followup_type": ftype, "notes": notes, "regularity_status": regularity
                })
                st.success("✅ تمت المتابعة بنجاح")
                time.sleep(1)
                st.rerun()

# =============================================================================
# Class Competition Scores - FIXED (with section name and quiz filtering)
# =============================================================================
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
    sections = db.get_sections()

    section_students = students[students.section_id == section_id] if not students.empty else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات مسجلات في فصلك.")
        return

    section_student_ids = section_students["student_id"].tolist()
    section_name = get_section_name_by_id(db, section_id)

    if not results.empty and "student_id" in results.columns:
        class_results = results[results["student_id"].isin(section_student_ids)]
        if "status" in class_results.columns:
            class_results = class_results[class_results["status"] == "submitted"]
    else:
        class_results = pd.DataFrame()

    if not quizzes.empty and not class_results.empty and "quiz_id" in class_results.columns:
        class_results = class_results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
        class_results = class_results.rename(columns={"title": "اسم المسابقة"})
    else:
        class_results["اسم المسابقة"] = ""

    if not section_students.empty and not class_results.empty:
        class_results = class_results.merge(section_students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
        class_results = class_results.rename(columns={"full_name": "اسم الطالبة"})
        # إضافة اسم الفصل
        class_results = add_section_names_to_df(db, class_results, "section_id")
    else:
        class_results["اسم الطالبة"] = ""
        class_results["اسم الفصل"] = section_name

    if class_results.empty:
        st.info("لا توجد نتائج مسابقات مسجلة لطالبات فصلك بعد.")
        return

    display_cols = ["اسم المسابقة", "اسم الطالبة", "اسم الفصل", "score", "total_marks", "submission_time"]
    available_cols = [c for c in display_cols if c in class_results.columns]
    display_df = class_results[available_cols].copy()

    if "score" in display_df.columns:
        display_df["score"] = pd.to_numeric(display_df["score"], errors="coerce").fillna(0)
    if "total_marks" in display_df.columns:
        display_df["total_marks"] = pd.to_numeric(display_df["total_marks"], errors="coerce").fillna(20)

    st.markdown("---")
    st.subheader("🔍 بحث وتصفية")

    # فلترة حسب الامتحان
    if "اسم المسابقة" in display_df.columns:
        quiz_names = ["الكل"] + sorted(display_df["اسم المسابقة"].dropna().unique().tolist())
        filter_quiz = st.selectbox("تصفية حسب المسابقة", quiz_names)
    else:
        filter_quiz = "الكل"

    search_term = st.text_input("ابحث باسم الطالبة", placeholder="اكتب اسم الطالبة...")
    sort_by = st.selectbox("ترتيب حسب", ["التاريخ", "الدرجة (تنازلي)", "الدرجة (تصاعدي)", "اسم الطالبة"])

    filtered_df = display_df.copy()
    
    # فلترة حسب المسابقة
    if filter_quiz != "الكل" and "اسم المسابقة" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["اسم المسابقة"] == filter_quiz]

    if search_term:
        mask = False
        if "اسم الطالبة" in filtered_df.columns:
            mask = mask | filtered_df["اسم الطالبة"].astype(str).str.contains(search_term, na=False, case=False)
        filtered_df = filtered_df[mask] if mask is not False else filtered_df

    if sort_by == "التاريخ" and "submission_time" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("submission_time", ascending=False)
    elif sort_by == "الدرجة (تنازلي)" and "score" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("score", ascending=False)
    elif sort_by == "الدرجة (تصاعدي)" and "score" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("score", ascending=True)
    elif sort_by == "اسم الطالبة" and "اسم الطالبة" in filtered_df.columns:
        filtered_df = filtered_df.sort_values("اسم الطالبة", ascending=True)

    if "submission_time" in filtered_df.columns:
        filtered_df["submission_time"] = pd.to_datetime(filtered_df["submission_time"], errors="coerce")

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
# Quizzes - FIXED (separate quiz results, section names)
# =============================================================================
def show_quizzes(db: Database):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    quizzes = db.get_quizzes()
    sections = db.get_sections()

    if role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد")
        with st.form("quiz_form"):
            title = st.text_input("عنوان الاختبار*")
            num_questions = st.selectbox("عدد الأسئلة", [10, 20, 30], index=1)
            time_limit = st.number_input("الوقت (بالدقائق)", 1, 180, 15)
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
                        "total_marks": 20, "expiry_date": expiry.strftime("%Y-%m-%d"),
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
                quiz_options = dict(zip(active_quizzes["quiz_id"], active_quizzes["title"]))
                quiz_choice = st.selectbox("اختر اختباراً لإدارة أسئلته", options=list(quiz_options.keys()),
                                           format_func=lambda x: quiz_options[x])
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
                        del_options = dict(zip(questions["question_id"], questions["question_text"]))
                        del_q = st.selectbox("اختر سؤالاً لحذفه", options=list(del_options.keys()),
                                            format_func=lambda x: del_options[x])
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

    st.markdown("### 📊 نتائج الاختبارات - حسب الامتحان")
    results = db.get_quiz_results()
    students = db.get_students()
    
    if not results.empty:
        if "status" in results.columns:
            results = results[results["status"] == "submitted"]
        
        # فصل النتائج حسب الامتحان
        if not quizzes.empty:
            results = results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
            results = results.rename(columns={"title": "اسم الامتحان"})
        
        # إضافة اسم الفصل للطالبة
        if not students.empty:
            results = results.merge(students[["student_id", "section_id", "full_name"]], on="student_id", how="left")
            results = add_section_names_to_df(db, results, "section_id")
        
        if role == "Teacher" and section_id and not students.empty:
            section_student_ids = students[students.section_id == section_id]["student_id"].tolist()
            results = results[results.student_id.isin(section_student_ids)]
        
        # اختيار الامتحان للعرض
        if "اسم الامتحان" in results.columns:
            available_quizzes = sorted(results["اسم الامتحان"].dropna().unique().tolist())
            if available_quizzes:
                selected_quiz_name = st.selectbox("اختر الامتحان لعرض نتائجه", ["الكل"] + available_quizzes)
                if selected_quiz_name != "الكل":
                    results = results[results["اسم الامتحان"] == selected_quiz_name]
        
        display_cols = ["student_name", "اسم الامتحان", "اسم الفصل", "score", "total_marks", "submission_time"]
        available_cols = [c for c in display_cols if c in results.columns]
        if available_cols:
            st.dataframe(results[available_cols], use_container_width=True)
        
        if st.button("🏆 ترتيب الطالبات"):
            if "student_name" in results.columns and "score" in results.columns:
                top = results.groupby("student_name")["score"].sum().reset_index().sort_values("score", ascending=False)
                st.dataframe(top, use_container_width=True)
    else:
        st.info("لا توجد نتائج بعد.")

# =============================================================================
# Reports - FIXED
# =============================================================================
def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    attendance = db.get_attendance()
    students = db.get_students()
    sections = db.get_sections()

    if role == "Teacher" and section_id:
        attendance = attendance[attendance.section_id == section_id] if not attendance.empty else attendance
        if not students.empty:
            students = students[students.section_id == section_id]

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
            pivot = pivot.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
            pivot = add_section_names_to_df(db, pivot, "section_id")
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
            absent_counts = absent_counts.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
            absent_counts = add_section_names_to_df(db, absent_counts, "section_id")
        display_cols = ["full_name", "اسم الفصل", "أيام الغياب"]
        available_cols = [c for c in display_cols if c in absent_counts.columns]
        st.dataframe(absent_counts[available_cols], use_container_width=True)

# =============================================================================
# Logs & Change Password
# =============================================================================
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

def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    with st.form("change_password_form"):
        old = st.text_input("كلمة المرور الحالية", type="password")
        new = st.text_input("كلمة المرور الجديدة", type="password")
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
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
                st.success("✅ تم تغيير كلمة المرور بنجاح!")

# =============================================================================
# Main App (التحكم بانزلاق القائمة من اليمين)
# =============================================================================
def main():
    inject_css()
    init_session()
    try:
        creds = get_credentials()
        db = Database(creds, get_spreadsheet_id())
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال: {e}")
        st.stop()

    jwt_secret = get_jwt_secret()

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
                role = st.session_state.user["role"]
                menus = {
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
                menu_items = menus.get(role, [])
                if choice not in menu_items:
                    choice = menu_items[0] if menu_items else "🏠 لوحة التحكم"
                    st.session_state.menu_choice = choice
            else:
                if 'choice' not in locals():
                    choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")

            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            if choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "👥 إدارة المستخدمين":
                if st.session_state.user["role"] == "System Admin":
                    show_user_management(db)
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
                if st.session_state.user["role"] == "System Admin":
                    show_logs(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "🔒 تغيير كلمة المرور":
                change_password(db)
            st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("open_help_dialog"):
        show_help_dialog()
        st.session_state.open_help_dialog = False

    if st.session_state.authenticated:
        try:
            db.cache.flush_logs(db)
        except Exception:
            pass

if __name__ == "__main__":
    main()
