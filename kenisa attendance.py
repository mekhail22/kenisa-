import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import uuid
import json
import random
import string
import jwt
import time
import requests
import traceback
from functools import wraps

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
APP_VERSION = "5.3.0"
CACHE_TTL_SECONDS = 120  # مدة صلاحية الكاش: دقيقتين

st.set_page_config(
    page_title="نظام الغياب والافتقاد - كنيسة الشهيدة دميانة",
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
    except:
        return DEFAULT_JWT_SECRET

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
        [data-testid="stSidebarNavToggle"], [data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"],
        button[aria-label="Close sidebar"], [data-testid="stSidebar"] > button,
        [data-testid="stSidebar"] > div:first-child > button, [data-testid="stSidebarResizer"],
        section[data-testid="stSidebar"] .st-emotion-cache-1oe5cao { display: none !important; }
        .main-header {
            font-size: 2.2rem; font-weight: 700; color: #1a1a2e; text-align: center;
            margin-bottom: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.9);
            border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            backdrop-filter: blur(5px); border: 1px solid rgba(0,0,0,0.05);
            margin-top: 60px;
        }
        .card { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 1rem; transition: transform 0.2s; color: #1a1a2e; border: 1px solid rgba(0,0,0,0.05); }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
        .stat-card {
            background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.2rem;
            text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            color: #1a1a2e; border: 1px solid rgba(0,0,0,0.05);
        }
        .stat-card .value { font-size: 2.2rem; font-weight: 700; color: #667eea; margin: 0.5rem 0; }
        .stat-card .label { font-size: 1rem; color: #555; font-weight: 600; }
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 8px; font-weight: 600;
            transition: all 0.2s; box-shadow: 0 2px 8px rgba(102,126,234,0.3);
        }
        .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(102,126,234,0.4); }
        .stRadio > div, .stSelectbox > div, .stMultiSelect > div { direction: rtl; }
        .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput { text-align: right; }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
            border-left: 1px solid rgba(0,0,0,0.08); padding-top: 1rem;
        }
        section[data-testid="stSidebar"] .stRadio label { font-weight: 600; color: #1a1a2e; font-size: 1rem; }
        .hide-sidebar-btn button { background: #667eea !important; color: white !important; font-weight: bold; border-radius: 8px; margin-bottom: 1rem; }
        .floating-show-btn { position: fixed; top: 20px; left: 20px; z-index: 99999; }
        .floating-show-btn button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border: none !important; border-radius: 14px !important;
            width: 65px !important; height: 65px !important; font-size: 28px !important;
            font-weight: bold !important; box-shadow: 0 4px 20px rgba(102,126,234,0.5) !important;
        }
        .help-float-container { position: fixed; top: 20px; left: 20px; z-index: 99998; }
        .help-float-container button {
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important;
            color: white !important; font-weight: 700 !important; border-radius: 8px !important;
        }
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
        .content-area { padding: 0 1rem; }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# SheetCache: تخزين مؤقت لتقليل استهلاك API
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
# Helper: Retry decorator
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
# Database Class
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

    # --- Attendance (batch) ---
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

    # --- Quizzes (extended with new fields) ---
    def get_quizzes(self):
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data):
        df = self.get_quizzes()
        if df.empty:
            df = pd.DataFrame(columns=["quiz_id", "title", "description", "created_by", "section_id",
                                       "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                       "quiz_code", "password", "is_active",
                                       "expiry_type", "expiry_hours", "start_time", "end_time"])
        df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active",
                                          "expiry_type", "expiry_hours", "start_time", "end_time"])

    def update_quiz(self, quiz_id, updates):
        df = self.get_quizzes()
        idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def delete_quiz(self, quiz_id):
        df = self.get_quizzes()
        df = df[df.quiz_id != quiz_id]
        self._df_to_sheet("Quizzes", df, df.columns.tolist())
        qdf = self._sheet_to_df("QuizQuestions")
        qdf = qdf[qdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizQuestions", qdf, ["question_id", "quiz_id", "question_text", "question_type",
                                                 "option1", "option2", "option3", "option4", "correct_answer"])
        rdf = self._sheet_to_df("QuizResults")
        rdf = rdf[rdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizResults", rdf, ["result_id", "quiz_id", "student_id", "student_name",
                                               "score", "total_marks", "submission_time", "answers"])

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
        self._df_to_sheet("QuizQuestions", df, df.columns.tolist())

    def get_quiz_results(self, quiz_id=None):
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return pd.DataFrame()
        if quiz_id:
            return df[df.quiz_id == quiz_id]
        return df

    def save_quiz_result(self, result):
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            df = pd.DataFrame(columns=["result_id", "quiz_id", "student_id", "student_name",
                                       "score", "total_marks", "submission_time", "answers"])
        df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "submission_time", "answers"])

    def delete_quiz_result(self, result_id):
        df = self._sheet_to_df("QuizResults")
        df = df[df.result_id != result_id]
        self._df_to_sheet("QuizResults", df, df.columns.tolist())

    # --- Logs (buffered) ---
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
    except:
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
        "correct_count": 0,
        "total_questions": 0,
        "submission_time": "",
        "login_attempted": False,
        "menu_choice": "🏠 لوحة التحكم",
        "show_sidebar": True,
        "open_help_dialog": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout(db=None):
    if db and st.session_state.user:
        try:
            db.cache.flush_logs(db)
        except:
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

@st.dialog("🆘 مركز المساعدة والدعم الفني")
def show_help_dialog():
    contact_name, contact_whatsapp = get_support_config()
    st.markdown("<h3>📬 الإبلاغ عن مشكلة أو خطأ</h3>", unsafe_allow_html=True)
    if contact_whatsapp:
        st.info(f"📞 تواصل مع {contact_name}: {contact_whatsapp}")
    with st.form("help_form_dialog"):
        name = st.text_input("الاسم *")
        whatsapp = st.text_input("رقم الواتساب *")
        issue_desc = st.text_area("وصف المشكلة *")
        if st.form_submit_button("إرسال"):
            if not name or not whatsapp or not issue_desc:
                st.error("جميع الحقول مطلوبة")
                return
            message = f"🆘 بلاغ من {name}\n📱 {whatsapp}\n📝 {issue_desc}"
            if send_telegram_message(message):
                st.success("تم الإرسال")
            else:
                st.error("فشل الإرسال")

# =============================================================================
# Initialization & Login
# =============================================================================
def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", type="primary", use_container_width=True):
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
    st.markdown("<h1 class='main-header'>⛪ نظام الغياب والافتقاد<br>الكنيسة الشهيدة دميانة بأسيوط</h1>", unsafe_allow_html=True)
    show_initialization(db)
    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم", placeholder="admin")
            password = st.text_input("كلمة المرور", type="password", placeholder="admin123")
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
                                    st.session_state.correct_count = 0
                                    st.session_state.total_questions = 0
                                    st.session_state.submission_time = ""
                                    st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")

# =============================================================================
# Student Quiz Interface - محسن بالكامل
# =============================================================================
def show_student_quiz(db: Database):
    quiz = st.session_state.student_quiz

    # ---------- مرحلة اختيار الاسم ----------
    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz['title']}")
        st.markdown(f"**عدد الأسئلة:** {quiz['num_questions']} | **الدرجة الكلية:** 20")
        expiry_type = quiz.get("expiry_type", "minutes")
        if expiry_type == "end_of_day":
            st.markdown("⏰ الامتحان متاح حتى نهاية اليوم (11:59 PM)")
        elif expiry_type == "hours":
            st.markdown(f"⏰ مدة الامتحان {quiz.get('expiry_hours', '1')} ساعات من وقت البدء")
        else:
            st.markdown(f"⏰ مدة الامتحان {quiz['time_limit_minutes']} دقيقة")
        st.markdown("---")
        students_df = db.get_students()
        active_students = students_df[students_df["status"] == "active"] if not students_df.empty else pd.DataFrame()
        if active_students.empty:
            st.warning("لا توجد طالبات مسجلات حالياً.")
            st.stop()
        options_dict = dict(zip(active_students["student_id"], active_students["full_name"]))
        selected_id = st.selectbox(
            "اختر اسمك من القائمة", options=list(options_dict.keys()),
            format_func=lambda x: options_dict[x], index=None, placeholder="اختر اسمك..."
        )
        st.info("إذا لم تجد اسمك في القائمة، يرجى التواصل مع مشرف الخدمة.")
        if selected_id is not None:
            existing_results = db.get_quiz_results(quiz["quiz_id"])
            if not existing_results.empty and "student_id" in existing_results.columns:
                if not existing_results[existing_results["student_id"] == selected_id].empty:
                    st.error("لقد قمت بتسليم هذا الاختبار بالفعل. لا يمكنك تكرار المحاولة.")
                    st.stop()
        if st.button("بدء الاختبار", use_container_width=True, type="primary", disabled=(selected_id is None)):
            selected_student = active_students[active_students["student_id"] == selected_id].iloc[0].to_dict()
            st.session_state.student_name = selected_student["full_name"]
            st.session_state.student_id = selected_id
            now = datetime.now()
            st.session_state.quiz_start_time = now

            # حساب وقت النهاية حسب نوع الامتحان
            expiry_type = quiz.get("expiry_type", "minutes")
            if expiry_type == "end_of_day":
                end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
                st.session_state.quiz_end_time = end_of_day
            elif expiry_type == "hours":
                hours = int(quiz.get("expiry_hours", 1))
                st.session_state.quiz_end_time = now + timedelta(hours=hours)
            else:  # minutes
                limit = int(quiz.get("time_limit_minutes", 15))
                st.session_state.quiz_end_time = now + timedelta(minutes=limit)

            st.session_state.quiz_phase = "taking_quiz"
            st.rerun()
        return

    # ---------- صفحة النتيجة (بعد التسليم) ----------
    if st.session_state.quiz_submitted or st.session_state.quiz_phase == "finished":
        st.markdown("<h2 style='text-align:center; color:green;'>✅ تم تسليم الاختبار بنجاح!</h2>", unsafe_allow_html=True)
        st.markdown(f"**الطالبة:** {st.session_state.student_name}")
        st.markdown(f"**عنوان الاختبار:** {quiz['title']}")
        st.markdown(f"### 🎯 نتيجتك: {st.session_state.last_score} من 20")
        st.markdown(f"- عدد الإجابات الصحيحة: {st.session_state.correct_count} من {st.session_state.total_questions}")
        st.markdown(f"- عدد الإجابات الخاطئة: {st.session_state.total_questions - st.session_state.correct_count}")
        if st.session_state.submission_time:
            st.markdown(f"- وقت التسليم: {st.session_state.submission_time}")
        if st.button("🏠 العودة للرئيسية", use_container_width=True, type="primary"):
            # مسح كل مفاتيح الاختبار
            keys_to_clear = ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                             "student_id", "quiz_start_time", "quiz_end_time", "quiz_answers",
                             "quiz_submitted", "last_score", "correct_count", "total_questions", "submission_time"]
            for k in keys_to_clear:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()
        return

    # ---------- أثناء الامتحان (مؤقت + أسئلة) ----------
    # التايمر (يظهر فقط أثناء الامتحان)
    end_timestamp = st.session_state.quiz_end_time.timestamp() * 1000
    timer_html = f"""
    <div class="timer-container" id="timer-container">
        <span id="quiz-timer" class="timer-box" data-end="{end_timestamp}">⏳ الوقت المتبقي: --:--</span>
    </div>
    <script>
        (function() {{
            const timerSpan = document.getElementById('quiz-timer');
            const timerContainer = document.getElementById('timer-container');
            if (!timerSpan) return;
            const endMillis = parseInt(timerSpan.dataset.end, 10);
            if (isNaN(endMillis)) return;
            function updateTimer() {{
                const now = Date.now();
                const diff = endMillis - now;
                if (diff <= 0) {{
                    timerSpan.textContent = '⏳ الوقت المتبقي: 00:00';
                    const btn = document.getElementById('timeout-submit-btn');
                    if (btn) btn.click();
                    return;
                }}
                const mins = Math.floor(diff / 60000);
                const secs = Math.floor((diff % 60000) / 1000);
                timerSpan.textContent = `⏳ الوقت المتبقي: ${{mins.toString().padStart(2,'0')}}:${{secs.toString().padStart(2,'0')}}`;
            }}
            updateTimer();
            setInterval(updateTimer, 1000);
        }})();
    </script>
    """
    st.markdown(timer_html, unsafe_allow_html=True)

    st.title(f"📝 {quiz['title']}")
    st.markdown(f"الطالبة: **{st.session_state.student_name}** | الدرجة الكلية: 20")
    st.markdown("---")
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
                st.session_state.quiz_answers[q_id] = ans if ans else ""
        else:
            ans = st.text_input("الإجابة", key=f"q_{q_id}", value=prev_answer)
            st.session_state.quiz_answers[q_id] = ans
        st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📩 تسليم الاختبار", use_container_width=True, key="submit_quiz_btn"):
            auto_submit_quiz(db, quiz)
            st.session_state.quiz_phase = "finished"
            st.rerun()
    with col2:
        if st.button("🛑 إنهاء الامتحان", use_container_width=True, key="finish_early_btn"):
            st.session_state.confirm_finish_early = True
            st.rerun()

    # مربع تأكيد الإنهاء المبكر
    if st.session_state.get("confirm_finish_early"):
        st.warning("⚠️ هل أنتي متأكدة من إنهاء الامتحان؟ الدرجة هتحسب على الأسئلة اللي اتجابت بس.")
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("✅ تأكيد الإنهاء", use_container_width=True):
                st.session_state.confirm_finish_early = False
                auto_submit_quiz(db, quiz)
                st.session_state.quiz_phase = "finished"
                st.rerun()
        with col_cancel:
            if st.button("❌ إلغاء", use_container_width=True):
                st.session_state.confirm_finish_early = False
                st.rerun()

    # زر خفي للتسليم التلقائي عند انتهاء الوقت
    st.markdown('<div style="display:none">', unsafe_allow_html=True)
    if st.button("", key="timeout_submit_btn"):
        if not st.session_state.quiz_submitted:
            auto_submit_quiz(db, quiz)
            st.session_state.quiz_phase = "finished"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def auto_submit_quiz(db, quiz):
    questions = db.get_quiz_questions(quiz["quiz_id"])
    if questions.empty:
        return
    correct_count = 0
    answers_dict = dict(st.session_state.quiz_answers)
    for _, q_row in questions.iterrows():
        q = q_row.to_dict()
        if str(q["correct_answer"]).strip().lower() == str(answers_dict.get(q["question_id"], "")).strip().lower():
            correct_count += 1
    total_q = len(questions)
    score = round((correct_count / total_q) * 20, 1) if total_q > 0 else 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {
        "result_id": str(uuid.uuid4()), "quiz_id": quiz["quiz_id"],
        "student_id": st.session_state.student_id, "student_name": st.session_state.student_name,
        "score": score, "total_marks": 20,
        "submission_time": now_str,
        "answers": json.dumps(answers_dict, ensure_ascii=False)
    }
    db.save_quiz_result(result)
    st.session_state.quiz_submitted = True
    st.session_state.last_score = score
    st.session_state.correct_count = correct_count
    st.session_state.total_questions = total_q
    st.session_state.submission_time = now_str

# =============================================================================
# Sidebar
# =============================================================================
def show_sidebar(db: Database):
    with st.sidebar:
        st.markdown('<div class="hide-sidebar-btn">', unsafe_allow_html=True)
        if st.button("◀ إخفاء القائمة", key="hide_sidebar_btn", use_container_width=True):
            st.session_state.show_sidebar = False
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.user
        st.markdown(f"**👤 {user['full_name']}**")
        st.caption(f"الصلاحية: {user['role']}")
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
                "🔒 تغيير كلمة المرور"
            ]
        }
        menu_items = menus.get(role, [])
        if not menu_items:
            st.warning("صلاحية غير معروفة")
            return None
        current_choice = st.session_state.get("menu_choice", menu_items[0])
        if current_choice not in menu_items:
            current_choice = menu_items[0]
        choice = st.radio(
            "القائمة الرئيسية", menu_items,
            index=menu_items.index(current_choice),
            key="nav_radio", label_visibility="collapsed"
        )
        if choice != current_choice:
            st.session_state.menu_choice = choice
            st.rerun()
        st.divider()
        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout_btn"):
            logout(db)
        return choice

# =============================================================================
# Dashboard
# =============================================================================
def show_dashboard(db: Database):
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)

    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()

    if role in ["Teacher", "Service Manager"] and section_id:
        students = students[students.section_id == section_id] if not students.empty else students
        if not attendance.empty:
            attendance = attendance[attendance.section_id == section_id]
        if not followup.empty and not students.empty:
            followup = followup[followup.student_id.isin(students["student_id"])]

    total = len(students)
    today = datetime.now().strftime("%Y-%m-%d")
    present = len(attendance[(attendance.date == today) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent = len(attendance[(attendance.date == today) & (attendance.status == "غائب")]) if not attendance.empty else 0
    disconnected = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("عدد الطالبات", total)
    c2.metric("الحضور اليوم", present)
    c3.metric("الغياب اليوم", absent)
    c4.metric("منقطعات", disconnected)

    st.markdown("#### 📈 الحضور الأسبوعي")
    if not attendance.empty:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
        last_week = datetime.now() - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty:
            fig = px.histogram(recent, x="date", color="status", barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا بيانات.")
    st.markdown("#### 🏅 أكثر 5 غياباً هذا الشهر")
    if not attendance.empty:
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_att = attendance[(attendance.date >= month_start) & (attendance.status == "غائب")]
        if not month_att.empty:
            top5 = month_att.groupby("student_id").size().reset_index(name="أيام الغياب").nlargest(5, "أيام الغياب")
            if not students.empty:
                top5 = top5.merge(students[["student_id", "full_name"]], on="student_id", how="left")
            st.dataframe(top5[["full_name", "أيام الغياب"]], use_container_width=True)
    st.markdown("#### 🔔 بنات بحاجة لافتقاد عاجل")
    urgent = followup[followup.regularity_status.isin(["منقطع", "متقطع"])] if not followup.empty else pd.DataFrame()
    if not urgent.empty:
        if not students.empty:
            urgent = urgent.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(urgent[["full_name", "followup_date", "notes"]], use_container_width=True)

# =============================================================================
# إدارة المستخدمين (Admin)
# =============================================================================
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    students = db.get_students()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول"])

    # Tab1 Users
    with tab1:
        st.subheader("قائمة المستخدمين")
        if not users.empty:
            st.dataframe(users[["user_id", "username", "full_name", "role", "section_id"]], use_container_width=True)
        with st.expander("➕ إضافة مستخدم"):
            with st.form("add_user"):
                uname = st.text_input("اسم المستخدم*")
                fname = st.text_input("الاسم الكامل*")
                pwd = st.text_input("كلمة المرور*", type="password")
                role = st.selectbox("الصلاحية", ["System Admin", "Father Account", "Service Manager", "Teacher"])
                sec_id = ""
                if role in ["Service Manager", "Teacher"] and not sections.empty:
                    sec_choice = st.selectbox("الفصل", ["None"] + sections["section_id"].tolist(),
                                              format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x!="None" else "لا يوجد")
                    sec_id = sec_choice if sec_choice!="None" else ""
                if st.form_submit_button("إضافة"):
                    if not uname or not pwd or not fname:
                        st.error("جميع الحقول مطلوبة")
                    elif not users[users.username == uname].empty:
                        st.error("اسم المستخدم موجود")
                    else:
                        db.add_user({"user_id": str(uuid.uuid4()), "username": uname, "password": pwd,
                                     "role": role, "full_name": fname, "section_id": sec_id, "phone": "", "email": ""})
                        st.success("تمت الإضافة")
                        time.sleep(1)
                        st.rerun()

    # Tab3 Students (مع تاريخ الميلاد)
    with tab3:
        st.subheader("الطالبات")
        if not students.empty:
            st.dataframe(students[["student_id", "full_name", "section_id", "birthdate"]], use_container_width=True)
        with st.expander("➕ إضافة طالبة"):
            with st.form("add_student"):
                name = st.text_input("الاسم*")
                sec = st.selectbox("الفصل", sections["section_id"].tolist()) if not sections.empty else ""
                phone = st.text_input("الهاتف")
                parent = st.text_input("ولي الأمر")
                birth = st.date_input("تاريخ الميلاد", value=None)
                if st.form_submit_button("إضافة"):
                    if not name: st.error("الاسم مطلوب")
                    else:
                        db.add_student({"student_id": str(uuid.uuid4()), "full_name": name, "section_id": sec,
                                        "phone": phone, "parent_phone": parent,
                                        "birthdate": birth.strftime("%Y-%m-%d") if birth else "",
                                        "address": "", "school": "", "notes": "", "status": "active"})
                        st.success("تمت الإضافة")
                        time.sleep(1)
                        st.rerun()
        with st.expander("✏️ تعديل طالبة"):
            if not students.empty:
                sid = st.selectbox("اختر طالبة", students["student_id"], key="edit_student")
                srow = students[students.student_id == sid].iloc[0]
                new_name = st.text_input("الاسم", value=srow.get("full_name",""))
                birth_val = None
                if srow.get("birthdate"):
                    try: birth_val = pd.to_datetime(srow["birthdate"]).date()
                    except: pass
                new_birth = st.date_input("تاريخ الميلاد", value=birth_val)
                if st.button("حفظ التعديلات"):
                    db.update_student(sid, {"full_name": new_name, "birthdate": new_birth.strftime("%Y-%m-%d") if new_birth else ""})
                    st.success("تم التحديث")
                    time.sleep(1)
                    st.rerun()

# =============================================================================
# Attendance
# =============================================================================
def show_attendance(db: Database):
    user = st.session_state.user
    if user["role"] == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور.")
        if st.button("🔙 العودة"):
            st.session_state.menu_choice = "🏠 لوحة التحكم"
            st.rerun()
        return
    st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
    sections = db.get_sections()
    if sections.empty:
        st.warning("لا توجد فصول.")
        return
    section = user.get("section_id", "")
    if not section or user["role"] == "System Admin":
        section = st.selectbox("اختر الفصل", sections["section_id"],
                               format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
    date_str = st.date_input("التاريخ", datetime.now()).strftime("%Y-%m-%d")
    students = db.get_students()
    section_students = students[students.section_id == section] if not students.empty else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات.")
        return
    existing = db.get_attendance_by_date_section(date_str, section)
    st.markdown("<div class='card'>", True)
    statuses, notes = {}, {}
    for _, s in section_students.iterrows():
        sid = s["student_id"]
        prev = existing[existing.student_id == sid]
        ps = prev.iloc[0]["status"] if not prev.empty else "حاضر"
        pn = prev.iloc[0]["notes"] if not prev.empty else ""
        c = st.columns([3,2,2])
        c[0].write(s["full_name"])
        status = c[1].radio("", ["حاضر","غائب","متأخر"], index=["حاضر","غائب","متأخر"].index(ps) if ps in ["حاضر","غائب","متأخر"] else 0, key=f"att_{sid}", horizontal=True)
        note = c[2].text_input("ملاحظة", value=pn, key=f"note_{sid}", label_visibility="collapsed")
        statuses[sid] = status
        notes[sid] = note
    st.markdown("</div>", True)
    if st.button("💾 حفظ الحضور"):
        records = []
        for sid, st_val in statuses.items():
            rid = existing[existing.student_id==sid]["record_id"].values[0] if not existing[existing.student_id==sid].empty else str(uuid.uuid4())
            records.append({"record_id": rid, "date": date_str, "student_id": sid, "status": st_val,
                            "notes": notes.get(sid,""), "recorded_by": user["user_id"], "section_id": section})
        db.batch_add_attendance(records)
        db.add_log(user["user_id"], f"تسجيل حضور فصل {section} ليوم {date_str}")
        st.success("تم تسجيل الحضور")
        time.sleep(1)
        st.rerun()

# =============================================================================
# Follow-up
# =============================================================================
def show_followup(db: Database):
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    students = db.get_students()
    followup = db.get_followup()
    if user["role"] == "Teacher" and user.get("section_id"):
        students = students[students.section_id == user["section_id"]] if not students.empty else students
    if students.empty:
        st.info("لا توجد طالبات.")
        return
    # كروت
    if not followup.empty:
        f_rel = followup[followup.student_id.isin(students["student_id"])]
        reg = len(f_rel[f_rel.regularity_status=="منتظم"])
        intm = len(f_rel[f_rel.regularity_status=="متقطع"])
        disc = len(f_rel[f_rel.regularity_status=="منقطع"])
    else:
        reg=intm=disc=0
    c1,c2,c3 = st.columns(3)
    c1.metric("منتظمات", reg)
    c2.metric("متقطعات", intm)
    c3.metric("منقطعات", disc)
    st.subheader("⚠️ بنات بحاجة لافتقاد")
    urgent = followup[(followup.regularity_status.isin(["متقطع","منقطع"])) & (followup.student_id.isin(students["student_id"]))] if not followup.empty else pd.DataFrame()
    if not urgent.empty:
        st.dataframe(urgent.merge(students[["student_id","full_name"]], on="student_id", how="left")[["full_name","followup_date","notes"]], use_container_width=True)
    with st.form("followup"):
        student = st.selectbox("اختر الطالبة", students["student_id"], format_func=lambda x: students[students.student_id==x]["full_name"].values[0])
        ftype = st.selectbox("النوع", ["زيارة","اتصال","رسالة","لقاء"])
        notes = st.text_area("ملاحظات")
        regularity = st.selectbox("الحالة", ["منتظم","متقطع","منقطع"])
        if st.form_submit_button("حفظ"):
            db.add_followup_record({"record_id": str(uuid.uuid4()), "student_id": student, "teacher_id": user["user_id"],
                                    "followup_date": datetime.now().strftime("%Y-%m-%d"), "followup_type": ftype,
                                    "notes": notes, "regularity_status": regularity})
            st.success("تم الحفظ")
            time.sleep(1)
            st.rerun()

# =============================================================================
# My Students
# =============================================================================
def show_my_students(db: Database):
    st.markdown("<h2 class='main-header'>👩‍🎓 طالباتي</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    students = db.get_students()
    if user["role"] == "Teacher" and user.get("section_id"):
        students = students[students.section_id == user["section_id"]] if not students.empty else students
    if students.empty:
        st.info("لا توجد طالبات.")
        return
    followup = db.get_followup()
    if not followup.empty:
        latest = followup.sort_values("followup_date").groupby("student_id").last().reset_index()
        students = students.merge(latest[["student_id","regularity_status"]], on="student_id", how="left")
        students["regularity_status"] = students["regularity_status"].fillna("غير معروف")
    else:
        students["regularity_status"] = "غير معروف"
    st.dataframe(students[["full_name","regularity_status"]], use_container_width=True)

# =============================================================================
# Quizzes - مع التعديلات الجديدة (إنشاء، تعديل، إدارة)
# =============================================================================
def show_quizzes(db: Database):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user["role"]
    section_id = user.get("section_id", "")

    # إنشاء اختبار (لأدمن وأمين خدمة)
    if role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد")
        with st.form("create_quiz"):
            title = st.text_input("عنوان الاختبار*")
            num_q = st.selectbox("عدد الأسئلة", [10,20,30], index=1)
            total_marks = st.number_input("الدرجة الكلية", value=20, min_value=1)
            expiry_date = st.date_input("تاريخ انتهاء الصلاحية", datetime.now()+timedelta(days=7))

            st.markdown("**⏱️ نوع الوقت**")
            time_type = st.radio("اختر طريقة انتهاء الوقت",
                                 ["⏱️ وقت محدد بالدقائق", "📅 ينتهي بنهاية اليوم", "⏰ ينتهي بعد عدد ساعات"],
                                 index=0, key="time_type_radio")
            time_limit = 15
            expiry_hours = 1
            if time_type.startswith("⏱️"):
                time_limit = st.number_input("الوقت بالدقائق", 1, 180, 15)
                expiry_type = "minutes"
            elif time_type.startswith("📅"):
                expiry_type = "end_of_day"
                time_limit = 0
            else:
                expiry_type = "hours"
                expiry_hours = st.number_input("عدد الساعات", 1, 24, 1)
                time_limit = 0

            quiz_code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
            quiz_pass = ''.join(random.choices(string.ascii_uppercase+string.digits, k=5))
            if st.form_submit_button("إنشاء الاختبار"):
                if not title:
                    st.error("العنوان مطلوب")
                else:
                    quiz_id = str(uuid.uuid4())
                    db.add_quiz({
                        "quiz_id": quiz_id, "title": title, "description": "",
                        "created_by": user["user_id"], "section_id": "",
                        "num_questions": num_q, "time_limit_minutes": time_limit,
                        "total_marks": total_marks, "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "quiz_code": quiz_code, "password": quiz_pass, "is_active": "True",
                        "expiry_type": expiry_type, "expiry_hours": expiry_hours,
                        "start_time": "", "end_time": ""
                    })
                    st.success(f"✅ تم إنشاء الاختبار! الكود: {quiz_code}")
                    time.sleep(2)
                    st.rerun()

        # إدارة الامتحانات الحالية
        st.markdown("---")
        st.subheader("📋 قائمة الاختبارات")
        quizzes = db.get_quizzes()
        if not quizzes.empty:
            for _, qrow in quizzes.iterrows():
                q = qrow.to_dict()
                with st.expander(f"{q.get('title','')} (كود: {q.get('quiz_code','')})"):
                    st.write(f"**عدد الأسئلة:** {q.get('num_questions','')} | **نوع الوقت:** {q.get('expiry_type','minutes')}")
                    if q.get('expiry_type') == 'hours':
                        st.write(f"**عدد الساعات:** {q.get('expiry_hours','1')}")
                    elif q.get('expiry_type') == 'minutes':
                        st.write(f"**الدقائق:** {q.get('time_limit_minutes','15')}")
                    st.write(f"**تاريخ الانتهاء:** {q.get('expiry_date','')}")
                    st.write(f"**نشط:** {q.get('is_active','True')}")

                    # زر تعديل الإعدادات
                    if st.button("⚙️ تعديل الإعدادات", key=f"edit_settings_{q['quiz_id']}"):
                        st.session_state[f"edit_quiz_{q['quiz_id']}"] = True
                    if st.session_state.get(f"edit_quiz_{q['quiz_id']}"):
                        with st.form(key=f"edit_form_{q['quiz_id']}"):
                            new_title = st.text_input("العنوان", value=q.get("title",""))
                            new_num = st.number_input("عدد الأسئلة", value=int(q.get("num_questions",20)), min_value=1)
                            new_type = st.radio("نوع الوقت",
                                                ["minutes", "end_of_day", "hours"],
                                                index=["minutes","end_of_day","hours"].index(q.get("expiry_type","minutes")),
                                                key=f"edit_type_{q['quiz_id']}")
                            new_time_limit = 15
                            new_expiry_hours = 1
                            if new_type == "minutes":
                                new_time_limit = st.number_input("الدقائق", value=int(q.get("time_limit_minutes",15)), min_value=1)
                            elif new_type == "hours":
                                new_expiry_hours = st.number_input("عدد الساعات", value=int(q.get("expiry_hours",1)), min_value=1)
                            new_expiry_date = st.date_input("تاريخ الانتهاء", value=pd.to_datetime(q.get("expiry_date", datetime.now().strftime("%Y-%m-%d"))).date())
                            new_active = st.checkbox("نشط", value=(q.get("is_active","True")=="True"))
                            new_pass = st.text_input("كلمة مرور جديدة (اختياري)")
                            if st.form_submit_button("💾 حفظ التعديلات"):
                                updates = {
                                    "title": new_title,
                                    "num_questions": new_num,
                                    "expiry_type": new_type,
                                    "time_limit_minutes": new_time_limit if new_type=="minutes" else 0,
                                    "expiry_hours": new_expiry_hours if new_type=="hours" else 0,
                                    "expiry_date": new_expiry_date.strftime("%Y-%m-%d"),
                                    "is_active": str(new_active)
                                }
                                if new_pass.strip():
                                    updates["password"] = new_pass.strip()
                                db.update_quiz(q["quiz_id"], updates)
                                st.success("تم التحديث!")
                                st.session_state[f"edit_quiz_{q['quiz_id']}"] = False
                                time.sleep(1)
                                st.rerun()
                    # زر حذف الامتحان
                    if st.button("🗑️ حذف الامتحان", key=f"del_quiz_{q['quiz_id']}"):
                        db.delete_quiz(q["quiz_id"])
                        st.success("تم الحذف")
                        time.sleep(1)
                        st.rerun()

            # إضافة أسئلة لاختبار محدد
            st.markdown("---")
            st.subheader("📝 إضافة أسئلة لاختبار")
            active_q = quizzes[quizzes.is_active == "True"] if not quizzes.empty else pd.DataFrame()
            if not active_q.empty:
                selected_quiz = st.selectbox("اختر اختباراً", active_q["quiz_id"],
                                             format_func=lambda x: active_q[active_q.quiz_id==x]["title"].values[0])
                if selected_quiz:
                    questions = db.get_quiz_questions(selected_quiz)
                    st.write(f"**الأسئلة الحالية:** {len(questions)}")
                    with st.form("add_q"):
                        qtext = st.text_area("نص السؤال*")
                        qtype = st.selectbox("النوع", ["اختيار من متعدد","صح وخطأ","أكمل","إجابة قصيرة"])
                        opts = {}
                        if qtype == "اختيار من متعدد":
                            cols = st.columns(4)
                            opts = {f"option{i+1}": cols[i].text_input(f"الخيار {i+1}") for i in range(4)}
                        elif qtype == "صح وخطأ":
                            opts = {"option1":"صح","option2":"خطأ","option3":"","option4":""}
                        else:
                            opts = {"option1":"","option2":"","option3":"","option4":""}
                        correct = st.text_input("الإجابة الصحيحة*")
                        if st.form_submit_button("إضافة سؤال"):
                            if not qtext or not correct:
                                st.error("السؤال والإجابة مطلوبان")
                            else:
                                db.add_question({"question_id":str(uuid.uuid4()), "quiz_id":selected_quiz,
                                                 "question_text":qtext, "question_type":qtype,
                                                 "option1":opts.get("option1",""), "option2":opts.get("option2",""),
                                                 "option3":opts.get("option3",""), "option4":opts.get("option4",""),
                                                 "correct_answer":correct})
                                st.success("تمت الإضافة")
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("لا توجد اختبارات.")

    # نتائج الاختبارات (للمدرسين وأمناء الخدمة)
    st.markdown("---")
    st.subheader("📊 نتائج الاختبارات")
    results = db.get_quiz_results()
    if not results.empty:
        students = db.get_students()
        if role == "Teacher" and section_id and not students.empty:
            sec_ids = students[students.section_id == section_id]["student_id"].tolist()
            results = results[results.student_id.isin(sec_ids)]
        st.dataframe(results[["student_name","score","total_marks","submission_time"]], use_container_width=True)
    else:
        st.info("لا توجد نتائج بعد.")

# =============================================================================
# Reports
# =============================================================================
def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    section_id = user.get("section_id", "")
    attendance = db.get_attendance()
    students = db.get_students()
    if user["role"] == "Teacher" and section_id:
        attendance = attendance[attendance.section_id == section_id] if not attendance.empty else attendance
        if not students.empty: students = students[students.section_id == section_id]
    if attendance.empty:
        st.info("لا بيانات حضور.")
        return
    attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    month = st.selectbox("الشهر", range(1,13), index=datetime.now().month-1)
    year = st.number_input("السنة", value=datetime.now().year)
    monthly = attendance[(attendance.date.dt.month==month)&(attendance.date.dt.year==year)]
    if not monthly.empty:
        pivot = monthly.groupby(["student_id","status"]).size().unstack(fill_value=0).reset_index()
        if not students.empty:
            pivot = pivot.merge(students[["student_id","full_name"]], on="student_id", how="left")
        st.dataframe(pivot, use_container_width=True)
        fig = px.pie(monthly, names="status", title=f"نسب الحضور {month}/{year}")
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("🏆 أكثر 10 غياباً")
    if not attendance.empty:
        top10 = attendance[attendance.status=="غائب"].groupby("student_id").size().reset_index(name="أيام").nlargest(10,"أيام")
        if not students.empty:
            top10 = top10.merge(students[["student_id","full_name"]], on="student_id", how="left")
        st.dataframe(top10[["full_name","أيام"]], use_container_width=True)

# =============================================================================
# Logs & Change Password
# =============================================================================
def show_logs(db: Database):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db.get_logs()
    if not logs.empty:
        st.dataframe(logs.sort_values("timestamp", ascending=False), use_container_width=True)

def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    with st.form("change_pwd"):
        old = st.text_input("الحالية", type="password")
        new = st.text_input("الجديدة", type="password")
        confirm = st.text_input("تأكيد الجديدة", type="password")
        if st.form_submit_button("تغيير"):
            if not old or not new or not confirm:
                st.error("املأ كل الحقول")
            elif old != st.session_state.user.get("password"):
                st.error("كلمة المرور الحالية خطأ")
            elif new != confirm:
                st.error("غير متطابقتين")
            else:
                db.update_user(st.session_state.user["user_id"], {"password": new})
                st.session_state.user["password"] = new
                st.success("تم التغيير")

# =============================================================================
# Main App
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

    st.markdown('<div class="help-float-container">', unsafe_allow_html=True)
    if st.button("🆘 مركز المساعدة", key="fixed_help_btn"):
        st.session_state.open_help_dialog = True
    st.markdown('</div>', unsafe_allow_html=True)

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
            if st.session_state.show_sidebar:
                choice = show_sidebar(db)
            else:
                st.markdown("<style>section[data-testid='stSidebar']{display:none!important}</style>", unsafe_allow_html=True)
                st.markdown('<div class="floating-show-btn">', unsafe_allow_html=True)
                if st.button("☰", key="show_sidebar_btn"):
                    st.session_state.show_sidebar = True
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
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
        except:
            pass

if __name__ == "__main__":
    main()
