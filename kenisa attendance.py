import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import uuid
import json
import random
import string
import jwt
import time
import requests
import traceback

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
APP_VERSION = "4.6.1"

# تكوين الصفحة الأساسي
st.set_page_config(
    page_title="نظام الغياب والافتقاد - كنيسة الشهيدة دميانة",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# إعدادات Telegram والدعم (من secrets.toml)
# =============================================================================

def get_telegram_config():
    """قراءة إعدادات Telegram من secrets.toml"""
    try:
        bot_token = st.secrets["telegram"]["bot_token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        return bot_token, chat_id
    except Exception as e:
        st.error(f"❌ خطأ في قراءة إعدادات Telegram من secrets.toml: {e}")
        return None, None

def get_support_config():
    """قراءة إعدادات التواصل المباشر من secrets.toml"""
    try:
        contact_name = st.secrets.get("support", {}).get("contact_name", "مسؤول النظام")
        whatsapp = st.secrets.get("support", {}).get("whatsapp", "")
        return contact_name, whatsapp
    except Exception:
        return "مسؤول النظام", ""

# =============================================================================
# دوال الاعتماد والإعدادات
# =============================================================================

def get_credentials():
    """تحميل بيانات اعتماد Google Cloud من secrets.toml"""
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
    """استخراج معرف جدول بيانات Google Sheets من secrets.toml"""
    try:
        return st.secrets["sheets"]["spreadsheet_id"]
    except Exception as e:
        st.error(f"❌ لم يتم العثور على spreadsheet_id: {e}")
        st.stop()

def get_jwt_secret():
    """استخراج مفتاح JWT من secrets.toml أو إرجاع المفتاح الافتراضي"""
    try:
        return st.secrets["sheets"]["jwt_secret"]
    except:
        return DEFAULT_JWT_SECRET

# =============================================================================
# تنسيقات CSS المخصصة
# =============================================================================

def inject_css():
    """إدراج أكواد CSS لتجميل التطبيق وإخفاء العناصر غير المرغوبة"""
    st.markdown("""
    <style>
        /* استيراد خط القاهرة */
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { font-family: 'Cairo', sans-serif; }
        body { direction: rtl; text-align: right; background-color: #f0f2f6; color: #1a1a2e; }

        /* خلفية الصفحة */
        .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); }

        /* إخفاء عناصر Streamlit الافتراضية */
        header[data-testid="stHeader"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        /* إخفاء جميع أزرار الشريط الجانبي الافتراضية */
        [data-testid="stSidebarNavToggle"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[aria-label="Close sidebar"],
        [data-testid="stSidebar"] > button,
        [data-testid="stSidebar"] > div:first-child > button,
        [data-testid="stSidebarResizer"],
        section[data-testid="stSidebar"] .st-emotion-cache-1oe5cao {
            display: none !important;
        }

        /* عنوان رئيسي */
        .main-header {
            font-size: 2.2rem; font-weight: 700; color: #1a1a2e; text-align: center;
            margin-bottom: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.9);
            border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            backdrop-filter: blur(5px); border: 1px solid rgba(0,0,0,0.05);
            margin-top: 60px;
        }

        /* بطاقة عامة */
        .card {
            background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 1rem;
            transition: transform 0.2s; color: #1a1a2e; border: 1px solid rgba(0,0,0,0.05);
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }

        /* بطاقة إحصائية */
        .stat-card {
            background: rgba(255,255,255,0.95); border-radius: 15px; padding: 1.2rem;
            text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            color: #1a1a2e; border: 1px solid rgba(0,0,0,0.05);
        }
        .stat-card .value { font-size: 2.2rem; font-weight: 700; color: #667eea; margin: 0.5rem 0; }
        .stat-card .label { font-size: 1rem; color: #555; font-weight: 600; }

        /* زر أساسي */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 8px; font-weight: 600;
            transition: all 0.2s; box-shadow: 0 2px 8px rgba(102,126,234,0.3);
        }
        .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(102,126,234,0.4); }

        /* اتجاه النصوص والأزرار */
        .stRadio > div, .stSelectbox > div, .stMultiSelect > div { direction: rtl; }
        .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput { text-align: right; }

        /* تنسيق الشريط الجانبي */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
            border-left: 1px solid rgba(0,0,0,0.08); padding-top: 1rem;
        }
        section[data-testid="stSidebar"] .stRadio > div { direction: rtl; }
        section[data-testid="stSidebar"] .stRadio label {
            font-weight: 600; color: #1a1a2e; font-size: 1rem;
        }

        /* زر إخفاء القائمة */
        .hide-sidebar-btn button {
            background: #667eea !important; color: white !important;
            font-weight: bold; border-radius: 8px; margin-bottom: 1rem;
        }

        /* زر إظهار القائمة العائم */
        .floating-show-btn { position: fixed; top: 20px; left: 20px; z-index: 99999; }
        .floating-show-btn button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border: none !important; border-radius: 14px !important;
            width: 65px !important; height: 65px !important; font-size: 28px !important;
            font-weight: bold !important; box-shadow: 0 4px 20px rgba(102,126,234,0.5) !important;
        }
        .floating-show-btn button:hover { transform: scale(1.1) !important; }

        /* زر مركز المساعدة الثابت - في الأعلى */
        .help-float-container {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 99998;
        }
        .help-float-container button {
            background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) !important;
            color: white !important;
            font-weight: 700 !important;
            border: none !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 8px rgba(243,156,18,0.3) !important;
        }
        .help-float-container button:hover {
            transform: scale(1.02) !important;
            box-shadow: 0 5px 15px rgba(243,156,18,0.4) !important;
        }

        /* مؤقت الاختبار */
        .timer-container { text-align: center; margin: 1rem 0; }
        .timer-box {
            display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2);
            color: white; padding: 0.8rem 2rem; border-radius: 15px;
            font-size: 1.8rem; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }

        /* جداول وأشكال */
        .stDataFrame { background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .streamlit-expanderHeader {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important; border-radius: 8px; font-weight: 600;
        }
        .streamlit-expanderContent {
            background: white; border-radius: 0 0 8px 8px;
            border: 1px solid rgba(0,0,0,0.05);
        }
        .stForm {
            background: white; padding: 20px; border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.05);
        }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            background: rgba(102,126,234,0.1); border-radius: 8px 8px 0 0;
            padding: 10px 20px; font-weight: 600; color: #667eea;
            border: 1px solid rgba(102,126,234,0.2); border-bottom: none;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
        }
        .stSelectbox > div > div {
            background: white; border-radius: 8px; border: 1px solid rgba(0,0,0,0.1);
        }
        .stSuccess, .stInfo, .stWarning, .stError { border-radius: 10px; font-weight: 600; }
        .stSuccess {
            background: rgba(40,167,69,0.1); border: 1px solid rgba(40,167,69,0.2);
            color: #155724;
        }
        .stError {
            background: rgba(220,53,69,0.1); border: 1px solid rgba(220,53,69,0.2);
            color: #721c24;
        }
        .content-area { padding: 0 1rem; }
        .search-box input {
            border-radius: 25px !important; border: 2px solid #667eea !important;
            padding: 10px 20px !important;
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# كلاس قاعدة البيانات (Google Sheets)
# =============================================================================

class Database:
    """
    كافة العمليات على جداول Google Sheets.
    """
    def __init__(self, creds, spreadsheet_id):
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(self, name, columns):
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=100000, cols=max(len(columns), 1))
            if columns:
                ws.append_row(columns)
        return ws

    def _sheet_to_df(self, sheet_name):
        ws = self._get_or_create_worksheet(sheet_name, [])
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()

    def _df_to_sheet(self, sheet_name, df, columns):
        ws = self._get_or_create_worksheet(sheet_name, columns)
        ws.clear()
        if not df.empty:
            for col in columns:
                if col not in df.columns:
                    df[col] = ""
            df = df[columns]
            ws.update([columns] + df.values.tolist())
        else:
            ws.update([columns])

    # المستخدمون
    def get_users(self):
        df = self._sheet_to_df("Users")
        if not df.empty and "password_hash" in df.columns:
            df = df.rename(columns={"password_hash": "password"})
        return df

    def add_user(self, user_data: dict):
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
                df.at[idx[0], k] = v
            self._df_to_sheet("Users", df, df.columns.tolist())

    def delete_user(self, user_id):
        df = self.get_users()
        df = df[df.user_id != user_id]
        self._df_to_sheet("Users", df, df.columns.tolist())

    # الفصول
    def get_sections(self):
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data: dict):
        df = self.get_sections()
        if df.empty:
            df = pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
        df = pd.concat([df, pd.DataFrame([sec_data])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    def update_section(self, section_id, updates):
        df = self.get_sections()
        idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = v
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, df.columns.tolist())

    # الطالبات
    def get_students(self):
        return self._sheet_to_df("Students")

    def add_student(self, student_data: dict):
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
                df.at[idx[0], k] = v
            self._df_to_sheet("Students", df, df.columns.tolist())

    def delete_student(self, student_id):
        df = self.get_students()
        df = df[df.student_id != student_id]
        self._df_to_sheet("Students", df, df.columns.tolist())

    # الحضور
    def get_attendance(self):
        return self._sheet_to_df("Attendance")

    def add_attendance_record(self, record: dict):
        df = self.get_attendance()
        if df.empty:
            df = pd.DataFrame(columns=["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
        existing_idx = df[df.record_id == record["record_id"]].index
        if len(existing_idx) > 0:
            for k, v in record.items():
                df.at[existing_idx[0], k] = v
        else:
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
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

    # الافتقاد
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record: dict):
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

    # الاختبارات
    def get_quizzes(self):
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data: dict):
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
                df.at[idx[0], k] = v
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def delete_quiz(self, quiz_id):
        df = self.get_quizzes()
        df = df[df.quiz_id != quiz_id]
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active"])
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

    def add_question(self, q_data: dict):
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

    def save_quiz_result(self, result: dict):
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
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "submission_time", "answers"])

    # السجلات
    def get_logs(self):
        return self._sheet_to_df("Logs")

    def add_log(self, user_id, action, details=""):
        df = self._sheet_to_df("Logs")
        if df.empty:
            df = pd.DataFrame(columns=["log_id", "timestamp", "user_id", "action", "details"])
        log = {"log_id": str(uuid.uuid4()), "timestamp": datetime.now().isoformat(),
               "user_id": user_id, "action": action, "details": details}
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

    def delete_log(self, log_id):
        df = self._sheet_to_df("Logs")
        df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

# =============================================================================
# JWT
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

# =============================================================================
# إدارة الجلسة
# =============================================================================

def init_session():
    defaults = {
        "authenticated": False, "user": None, "token": None,
        "student_quiz": None, "student_quiz_started": False,
        "quiz_phase": "enter_name", "student_name": "", "student_id": "",
        "quiz_start_time": None, "quiz_end_time": None,
        "quiz_answers": {}, "quiz_submitted": False, "last_score": 0,
        "login_attempted": False,
        "menu_choice": "🏠 لوحة التحكم", "show_sidebar": True,
        "open_help_dialog": False,
        "last_error_details": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout():
    if st.session_state.user:
        try:
            db = Database(get_credentials(), get_spreadsheet_id())
            db.add_log(st.session_state.user["user_id"], "تسجيل الخروج")
        except:
            pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# =============================================================================
# دوال مساعدة
# =============================================================================

def search_students(df, query):
    if df.empty or not query:
        return df
    query = str(query).lower()
    mask = (df["full_name"].astype(str).str.lower().str.contains(query, na=False) |
            df["phone"].astype(str).str.contains(query, na=False) |
            df["parent_phone"].astype(str).str.contains(query, na=False) |
            df["address"].astype(str).str.lower().str.contains(query, na=False))
    return df[mask]

def export_to_csv(df, filename):
    if df.empty:
        return None
    return df.to_csv(index=False).encode("utf-8-sig")

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
# نافذة مركز المساعدة
# =============================================================================

@st.dialog("🆘 مركز المساعدة والدعم الفني")
def show_help_dialog():
    contact_name, contact_whatsapp = get_support_config()

    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h3>📬 الإبلاغ عن مشكلة أو خطأ</h3>
        <p style="color: #555;">املأ البيانات التالية وسنتواصل معك في أقرب وقت</p>
    </div>
    """, unsafe_allow_html=True)

    if contact_whatsapp:
        st.info(f"📞 يمكنك أيضًا التواصل مباشرة مع **{contact_name}** عبر الواتساب: {contact_whatsapp}")

    default_name = ""
    if st.session_state.authenticated and st.session_state.user:
        default_name = st.session_state.user.get("full_name", "")
    elif st.session_state.get("student_name"):
        default_name = st.session_state.student_name

    with st.form("help_form_dialog", clear_on_submit=False):
        name = st.text_input("الاسم *", value=default_name, placeholder="أدخل اسمك الكامل")
        whatsapp = st.text_input("رقم الواتساب *", placeholder="مثال: 010xxxxxxxx")
        report_type = st.selectbox("نوع البلاغ *", ["مشكلة تقنية", "سؤال عام", "اقتراح تحسين", "بلاغ خطأ", "أخرى"])
        issue_desc = st.text_area("وصف المشكلة *", height=100, placeholder="اشرح المشكلة التي تواجهها...")

        submit = st.form_submit_button("📨 إرسال البلاغ", use_container_width=True)

        if submit:
            if not name.strip() or not whatsapp.strip() or not issue_desc.strip():
                st.error("⚠️ الاسم ورقم الواتساب ووصف المشكلة حقول إلزامية.")
                return

            current_page = st.session_state.get("menu_choice", "غير معروف")
            if st.session_state.get("student_quiz_started"):
                current_page = "واجهة الاختبار الإلكتروني"

            user_info = "زائر غير مسجل"
            if st.session_state.authenticated and st.session_state.user:
                u = st.session_state.user
                user_info = f"{u.get('full_name', '')} (صلاحية: {u.get('role', '')})"
            elif st.session_state.get("student_name"):
                user_info = f"طالبة: {st.session_state.student_name}"

            telegram_message = (
                f"🆘 <b>بلاغ جديد من مركز المساعدة</b>\n\n"
                f"👤 <b>الاسم:</b> {name}\n"
                f"📱 <b>رقم الواتساب:</b> {whatsapp}\n"
                f"🕵️ <b>حالة المستخدم:</b> {user_info}\n"
                f"📌 <b>نوع البلاغ:</b> {report_type}\n"
                f"📄 <b>الصفحة الحالية:</b> {current_page}\n"
                f"⏰ <b>تاريخ ووقت الإرسال:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📝 <b>وصف المشكلة:</b>\n{issue_desc}\n\n"
            )

            error_details = st.session_state.get("last_error_details", "")
            if error_details:
                telegram_message += f"💥 <b>تفاصيل الخطأ (مُضافة تلقائياً):</b>\n<pre>{error_details}</pre>"

            success = send_telegram_message(telegram_message)
            if success:
                st.success("✅ تم إرسال بلاغك بنجاح. سنتواصل معك قريباً على رقم الواتساب.")
                st.session_state.last_error_details = None
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ فشل في إرسال البلاغ. تأكد من أن بوت التليجرام مفعّل بشكل صحيح.")

# =============================================================================
# التهيئة الأولية
# =============================================================================

def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
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

# =============================================================================
# صفحة تسجيل الدخول
# =============================================================================

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
                                    st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")

# =============================================================================
# واجهة الطالبة للاختبار
# =============================================================================

def show_student_quiz(db: Database):
    quiz = st.session_state.student_quiz

    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz['title']}")
        st.markdown(
            f"**عدد الأسئلة:** {quiz['num_questions']} | **الدرجة الكلية:** 20 | **الوقت:** {quiz['time_limit_minutes']} دقيقة"
        )
        st.markdown("---")
        students_df = db.get_students()
        active_students = students_df[students_df["status"] == "active"] if not students_df.empty else pd.DataFrame()
        if active_students.empty:
            st.warning("لا توجد طالبات مسجلات حالياً. يرجى التواصل مع المسؤول.")
            st.stop()
        options_dict = dict(zip(active_students["student_id"], active_students["full_name"]))
        selected_id = st.selectbox(
            "اختر اسمك من القائمة", options=list(options_dict.keys()),
            format_func=lambda x: options_dict[x], index=None, placeholder="اختر اسمك..."
        )
        st.markdown("---")
        st.info("إذا لم تجد اسمك في القائمة، يرجى التواصل مع مشرف الخدمة لإضافتك.")
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
            st.session_state.quiz_start_time = datetime.now()
            time_limit_seconds = int(quiz["time_limit_minutes"]) * 60
            st.session_state.quiz_end_time = st.session_state.quiz_start_time + timedelta(seconds=time_limit_seconds)
            st.session_state.quiz_phase = "taking_quiz"
            st.rerun()
        return

    if st.session_state.quiz_submitted or st.session_state.quiz_phase == "finished":
        st.success("تم تسليم الاختبار بنجاح!")
        if "last_score" in st.session_state:
            st.info(f"نتيجتك: {st.session_state.last_score}/20")
        if st.button("إنهاء والعودة إلى الرئيسية", use_container_width=True):
            for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                        "student_id", "quiz_start_time", "quiz_end_time", "quiz_answers", "quiz_submitted", "last_score"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        return

    end_timestamp = st.session_state.quiz_end_time.timestamp() * 1000
    timer_html = f"""
    <div class="timer-container">
        <span id="quiz-timer" class="timer-box" data-end="{end_timestamp}">⏳ الوقت المتبقي: --:--</span>
    </div>
    <script>
        (function() {{
            const timerSpan = document.getElementById('quiz-timer');
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

    if st.button("تسليم الاختبار", type="primary", use_container_width=True):
        auto_submit_quiz(db, quiz)
        st.session_state.quiz_phase = "finished"
        st.rerun()

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
    num_q = len(questions)
    score = round((correct_count / num_q) * 20, 1) if num_q > 0 else 0
    result = {
        "result_id": str(uuid.uuid4()), "quiz_id": quiz["quiz_id"],
        "student_id": st.session_state.student_id, "student_name": st.session_state.student_name,
        "score": score, "total_marks": 20,
        "submission_time": datetime.now().isoformat(),
        "answers": json.dumps(answers_dict, ensure_ascii=False)
    }
    db.save_quiz_result(result)
    st.session_state.quiz_submitted = True
    st.session_state.last_score = score

# =============================================================================
# القائمة الجانبية
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
                "🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد",
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
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout()
        return choice

# =============================================================================
# لوحة التحكم
# =============================================================================

def show_dashboard(db: Database):
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    today = datetime.now().strftime("%Y-%m-%d")
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()

    present_today = len(attendance[(attendance.date == today) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent_today = len(attendance[(attendance.date == today) & (attendance.status == "غائب")]) if not attendance.empty else 0
    need_follow = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0

    col1.markdown(f"<div class='stat-card'><div class='label'>عدد الطالبات</div><div class='value'>{len(students)}</div></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='stat-card'><div class='label'>الحضور اليوم</div><div class='value'>{present_today}</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='stat-card'><div class='label'>الغياب اليوم</div><div class='value'>{absent_today}</div></div>", unsafe_allow_html=True)
    col4.markdown(f"<div class='stat-card'><div class='label'>منقطعات</div><div class='value'>{need_follow}</div></div>", unsafe_allow_html=True)

    st.markdown("#### 📈 الحضور الأسبوعي")
    if not attendance.empty:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
        last_week = datetime.now() - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty:
            fig = px.histogram(recent, x="date", color="status", barmode="group", title="الحضور اليومي")
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور للأيام الماضية.")
    else:
        st.info("لا توجد بيانات حضور بعد.")

    if need_follow > 0:
        st.markdown("#### 🔔 بنات بحاجة لافتقاد عاجل")
        urgent = followup[followup.regularity_status == "منقطع"].merge(
            students[["student_id", "full_name"]], on="student_id", how="left"
        )
        if not urgent.empty:
            st.dataframe(urgent[["full_name", "followup_date", "notes"]], use_container_width=True)

# =============================================================================
# صفحة إدارة المستخدمين (الخدام، المدرسات، الطالبات، أمناء الخدمة، الفصول)
# =============================================================================

def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول"])

    # ---------- تبويب الخدام ----------
    with tab1:
        st.subheader("قائمة المستخدمين (خدام)")
        users = db.get_users()
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
                sections = db.get_sections()
                section_id = ""
                if role in ["Service Manager", "Teacher"] and not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف (اختياري)")
                email = st.text_input("البريد الإلكتروني (اختياري)")
                if st.form_submit_button("إضافة", use_container_width=True):
                    if not username or not password or not full_name:
                        st.error("مطلوب اسم المستخدم وكلمة المرور والاسم الكامل")
                    elif not users[users.username == username].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        try:
                            db.add_user({
                                "user_id": str(uuid.uuid4()), "username": username, "password": password,
                                "role": role, "full_name": full_name,
                                "section_id": section_id, "phone": phone, "email": email
                            })
                            st.success("تم إضافة المستخدم بنجاح")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في إضافة المستخدم: {str(e)}")

        with st.expander("✏️ تعديل / حذف مستخدم"):
            if not users.empty:
                selected_user_id = st.selectbox("اختر المستخدم", users["user_id"])
                user_data = users[users.user_id == selected_user_id].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=user_data.get("full_name", ""))
                new_phone = st.text_input("رقم الهاتف", value=user_data.get("phone", ""))
                new_email = st.text_input("البريد الإلكتروني", value=user_data.get("email", ""))
                roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher"]
                current_role = user_data.get("role", "Teacher")
                role_index = roles_list.index(current_role) if current_role in roles_list else 3
                new_role = st.selectbox("الصلاحية", roles_list, index=role_index)
                new_section_id = user_data.get("section_id", "")
                if new_role in ["Service Manager", "Teacher"]:
                    sections = db.get_sections()
                    if not sections.empty:
                        section_options = ["None"] + sections["section_id"].tolist()
                        current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                        section_choice = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                        new_section_id = section_choice if section_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات", use_container_width=True):
                    try:
                        db.update_user(selected_user_id, {
                            "full_name": new_full_name, "phone": new_phone, "email": new_email,
                            "role": new_role, "section_id": new_section_id
                        })
                        st.success("تم التحديث")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في تحديث المستخدم: {str(e)}")
                if col2.button("حذف المستخدم", use_container_width=True, type="secondary"):
                    if selected_user_id == st.session_state.user["user_id"]:
                        st.error("لا يمكنك حذف حسابك الحالي!")
                    else:
                        try:
                            db.delete_user(selected_user_id)
                            st.success("تم الحذف")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في حذف المستخدم: {str(e)}")

    # ---------- تبويب المدرسات ----------
    with tab2:
        st.subheader("قائمة المدرسات")
        users = db.get_users()
        teachers = users[users.role == "Teacher"] if not users.empty else pd.DataFrame()
        if not teachers.empty:
            sections = db.get_sections()
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
                teacher_name = st.text_input("اسم المستخدم (الاسم الكامل)*")
                password = st.text_input("كلمة المرور*", type="password")
                sections = db.get_sections()
                section_id = ""
                if not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل المسؤولة عنه", section_options, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة", use_container_width=True):
                    if not teacher_name or not password:
                        st.error("اسم المستخدم وكلمة المرور مطلوبان")
                    elif not users[users.username == teacher_name].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        try:
                            db.add_user({
                                "user_id": str(uuid.uuid4()), "username": teacher_name, "password": password,
                                "role": "Teacher", "full_name": teacher_name,
                                "section_id": section_id, "phone": phone, "email": email
                            })
                            st.success("تمت إضافة المدرسة بنجاح")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في إضافة المدرسة: {str(e)}")
        with st.expander("✏️ تعديل / حذف مدرسة"):
            if not teachers.empty:
                selected_teacher = st.selectbox("اختر المدرسة", teachers["user_id"])
                teacher_data = teachers[teachers.user_id == selected_teacher].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=teacher_data.get("full_name", ""))
                new_phone = st.text_input("رقم الهاتف", value=teacher_data.get("phone", ""))
                new_email = st.text_input("البريد الإلكتروني", value=teacher_data.get("email", ""))
                sections = db.get_sections()
                new_section_id = teacher_data.get("section_id", "")
                if not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    section_choice = st.selectbox("الفصل المسؤولة عنه", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    new_section_id = section_choice if section_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات", use_container_width=True):
                    try:
                        db.update_user(selected_teacher, {
                            "full_name": new_full_name, "phone": new_phone, "email": new_email,
                            "section_id": new_section_id
                        })
                        st.success("تم التحديث")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في تحديث المدرسة: {str(e)}")
                if col2.button("حذف المدرسة", use_container_width=True, type="secondary"):
                    try:
                        db.delete_user(selected_teacher)
                        st.success("تم حذف المدرسة")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في حذف المدرسة: {str(e)}")

    # ---------- تبويب الطالبات ----------
    with tab3:
        st.subheader("قائمة الطالبات")
        students = db.get_students()
        if not students.empty:
            sections = db.get_sections()
            if not sections.empty:
                students_display = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
            else:
                students_display = students
                students_display["section_name"] = ""
            st.dataframe(students_display[["student_id", "full_name", "section_name", "phone", "parent_phone", "school", "status"]], use_container_width=True)
        else:
            st.info("لا توجد طالبات مسجلة.")
        with st.expander("➕ إضافة طالبة جديدة"):
            with st.form("add_student_form"):
                full_name = st.text_input("الاسم الكامل*")
                sections = db.get_sections()
                section_id = ""
                if not sections.empty:
                    section_id = st.selectbox("الفصل", sections["section_id"], format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
                phone = st.text_input("رقم الهاتف")
                parent_phone = st.text_input("رقم ولي الأمر")
                birthdate = st.date_input("تاريخ الميلاد", value=None)
                address = st.text_area("العنوان")
                school = st.text_input("المدرسة")
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("إضافة", use_container_width=True):
                    if not full_name:
                        st.error("الاسم الكامل مطلوب")
                    else:
                        try:
                            db.add_student({
                                "student_id": str(uuid.uuid4()), "full_name": full_name, "section_id": section_id,
                                "phone": phone, "parent_phone": parent_phone,
                                "birthdate": birthdate.strftime("%Y-%m-%d") if birthdate else "",
                                "address": address, "school": school, "notes": notes, "status": "active"
                            })
                            st.success("تمت الإضافة")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في إضافة الطالبة: {str(e)}")
        with st.expander("✏️ تعديل بيانات طالبة"):
            if not students.empty:
                selected_student = st.selectbox("اختر طالبة", students["student_id"])
                student_row = students[students.student_id == selected_student].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""))
                sections = db.get_sections()
                new_section_id = student_row.get("section_id", "")
                if not sections.empty:
                    section_options = sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    new_section_id = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
                new_phone = st.text_input("رقم الهاتف", value=student_row.get("phone", ""))
                new_parent = st.text_input("رقم ولي الأمر", value=student_row.get("parent_phone", ""))
                new_school = st.text_input("المدرسة", value=student_row.get("school", ""))
                new_notes = st.text_area("ملاحظات", value=student_row.get("notes", ""))
                status_list = ["active", "inactive"]
                current_status = student_row.get("status", "active")
                status_index = 0 if current_status == "active" else 1
                new_status = st.selectbox("الحالة", status_list, index=status_index)
                if st.button("حفظ التعديلات", use_container_width=True):
                    try:
                        db.update_student(selected_student, {
                            "full_name": new_full_name, "section_id": new_section_id,
                            "phone": new_phone, "parent_phone": new_parent,
                            "school": new_school, "notes": new_notes, "status": new_status
                        })
                        st.success("تم التحديث")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في تحديث الطالبة: {str(e)}")
        with st.expander("🗑️ حذف طالبة"):
            if not students.empty:
                delete_id = st.selectbox("اختر طالبة للحذف", students["student_id"], key="delete_student_tab")
                if st.button("تأكيد حذف الطالبة", key="delete_student_btn"):
                    try:
                        db.delete_student(delete_id)
                        st.success("تم الحذف")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في حذف الطالبة: {str(e)}")

    # ---------- تبويب أمناء الخدمة ----------
    with tab4:
        st.subheader("قائمة أمناء الخدمة")
        users = db.get_users()
        managers = users[users.role == "Service Manager"] if not users.empty else pd.DataFrame()
        if not managers.empty:
            sections = db.get_sections()
            if not sections.empty:
                managers_display = managers.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                managers_display = managers_display.rename(columns={"section_name": "الفصل"})
            else:
                managers_display = managers
                managers_display["الفصل"] = ""
            st.dataframe(managers_display[["user_id", "username", "full_name", "الفصل", "phone", "email"]], use_container_width=True)
        else:
            st.info("لا يوجد أمناء خدمة مسجلين.")
        with st.expander("➕ إضافة أمين خدمة جديد"):
            with st.form("add_manager_form"):
                mgr_name = st.text_input("اسم المستخدم*")
                full_name = st.text_input("الاسم الكامل*")
                password = st.text_input("كلمة المرور*", type="password")
                sections = db.get_sections()
                section_id = ""
                if not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    section_choice = st.selectbox("الفصل", section_options, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    section_id = section_choice if section_choice != "None" else ""
                phone = st.text_input("رقم الهاتف")
                email = st.text_input("البريد الإلكتروني")
                if st.form_submit_button("إضافة", use_container_width=True):
                    if not mgr_name or not password or not full_name:
                        st.error("جميع الحقول المطلوبة")
                    elif not users[users.username == mgr_name].empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        try:
                            db.add_user({
                                "user_id": str(uuid.uuid4()), "username": mgr_name, "password": password,
                                "role": "Service Manager", "full_name": full_name,
                                "section_id": section_id, "phone": phone, "email": email
                            })
                            st.success("تمت الإضافة")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في إضافة أمين الخدمة: {str(e)}")
        with st.expander("✏️ تعديل / حذف أمين خدمة"):
            if not managers.empty:
                selected_mgr = st.selectbox("اختر أمين الخدمة", managers["user_id"])
                mgr_data = managers[managers.user_id == selected_mgr].iloc[0].to_dict()
                new_full_name = st.text_input("الاسم الكامل", value=mgr_data.get("full_name", ""))
                new_phone = st.text_input("رقم الهاتف", value=mgr_data.get("phone", ""))
                new_email = st.text_input("البريد الإلكتروني", value=mgr_data.get("email", ""))
                sections = db.get_sections()
                new_section_id = mgr_data.get("section_id", "")
                if not sections.empty:
                    section_options = ["None"] + sections["section_id"].tolist()
                    current_idx = section_options.index(new_section_id) if new_section_id in section_options else 0
                    section_choice = st.selectbox("الفصل", section_options, index=current_idx, format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if x != "None" else "لا يوجد")
                    new_section_id = section_choice if section_choice != "None" else ""
                col1, col2 = st.columns(2)
                if col1.button("تحديث البيانات", use_container_width=True):
                    try:
                        db.update_user(selected_mgr, {
                            "full_name": new_full_name, "phone": new_phone, "email": new_email,
                            "section_id": new_section_id
                        })
                        st.success("تم التحديث")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في تحديث أمين الخدمة: {str(e)}")
                if col2.button("حذف أمين الخدمة", use_container_width=True, type="secondary"):
                    try:
                        db.delete_user(selected_mgr)
                        st.success("تم الحذف")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في حذف أمين الخدمة: {str(e)}")

    # ---------- تبويب الفصول ----------
    with tab5:
        st.subheader("قائمة الفصول")
        sections = db.get_sections()
        if not sections.empty:
            st.dataframe(sections[["section_id", "section_name"]], use_container_width=True)
        else:
            st.info("لا توجد فصول مسجلة.")
        with st.expander("➕ إضافة فصل جديد"):
            with st.form("add_section_form"):
                name = st.text_input("اسم الفصل*")
                if st.form_submit_button("إضافة", use_container_width=True):
                    if not name:
                        st.error("اسم الفصل مطلوب")
                    else:
                        try:
                            db.add_section({"section_id": str(uuid.uuid4()), "section_name": name})
                            st.success("تمت الإضافة")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في إضافة الفصل: {str(e)}")
        with st.expander("🗑️ حذف فصل"):
            if not sections.empty:
                delete_sec = st.selectbox("اختر فصل للحذف", sections["section_id"])
                if st.button("تأكيد حذف الفصل", key="delete_section_btn"):
                    try:
                        db.delete_section(delete_sec)
                        st.success("تم الحذف")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في حذف الفصل: {str(e)}")

# =============================================================================
# باقي الصفحات (الحضور، الافتقاد، الاختبارات، التقارير، السجلات، تغيير كلمة المرور)
# تم تضمينها كاملة بنفس المنطق مع try-except ومعالجة أخطاء قاعدة البيانات
# =============================================================================

def show_attendance(db: Database):
    st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
    sections = db.get_sections()
    if sections.empty:
        st.warning("لا توجد فصول. يرجى إضافة فصول أولاً.")
        return
    section = st.selectbox("اختر الفصل", sections["section_id"],
                           format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
    date = st.date_input("التاريخ", datetime.now())
    date_str = date.strftime("%Y-%m-%d")
    students = db.get_students()
    section_students = students[students.section_id == section] if not students.empty else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات في هذا الفصل.")
        return
    existing = db.get_attendance_by_date_section(date_str, section)
    already_filled = not existing.empty
    if already_filled:
        st.warning("⚠️ يوجد تسجيل حضور سابق في هذا اليوم. سيتم تحديثه.")
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
    if st.button("💾 حفظ الحضور", use_container_width=True):
        for sid, status in statuses.items():
            prev_record = existing[existing.student_id == sid] if already_filled else pd.DataFrame()
            record_id = prev_record.iloc[0]["record_id"] if not prev_record.empty else str(uuid.uuid4())
            record = {
                "record_id": record_id, "date": date_str, "student_id": sid,
                "status": status, "notes": notes_dict.get(sid, ""),
                "recorded_by": st.session_state.user["user_id"], "section_id": section
            }
            try:
                db.add_attendance_record(record)
            except Exception as e:
                st.error(f"فشل في حفظ الحضور للطالبة {sid}: {str(e)}")
                return
        db.add_log(st.session_state.user["user_id"], f"تسجيل حضور فصل {section} ليوم {date_str}")
        st.success("✅ تم تسجيل الحضور بنجاح")
        time.sleep(0.5)
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
        del_id = st.selectbox("اختر سجل حضور لحذفه", rec["record_id"])
        if st.button("حذف سجل الحضور"):
            try:
                db.delete_attendance_record(del_id)
                st.success("تم الحذف")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"فشل في حذف سجل الحضور: {str(e)}")

def show_followup(db: Database):
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    user_role = st.session_state.user["role"]
    user_id = st.session_state.user["user_id"]
    students = db.get_students()

    if user_role == "Teacher":
        responsible = students[students.teacher_id == user_id] if not students.empty else pd.DataFrame()
    elif user_role == "Service Manager":
        sec_id = st.session_state.user.get("section_id", "")
        responsible = students[students.section_id == sec_id] if sec_id and not students.empty else students
    else:
        responsible = students

    if responsible.empty:
        st.info("لا توجد طالبات مسؤولة عنك.")
        return

    student = st.selectbox("اختر الطالبة", responsible["student_id"],
                            format_func=lambda x: responsible[responsible.student_id==x]["full_name"].values[0])
    student_data = responsible[responsible.student_id == student].iloc[0].to_dict()

    with st.form("followup_form"):
        ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال هاتفي", "رسالة", "لقاء شخصي"])
        notes = st.text_area("ملاحظات")
        regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
        if st.form_submit_button("حفظ المتابعة", use_container_width=True):
            try:
                db.add_followup_record({
                    "record_id": str(uuid.uuid4()), "student_id": student_data["student_id"],
                    "teacher_id": user_id, "followup_date": datetime.now().strftime("%Y-%m-%d"),
                    "followup_type": ftype, "notes": notes, "regularity_status": regularity
                })
                st.success("✅ تم تسجيل الافتقاد بنجاح")
            except Exception as e:
                st.error(f"فشل في حفظ المتابعة: {str(e)}")

    st.markdown("---")
    st.subheader("📋 سجل المتابعات السابقة")
    followups = db.get_followup()
    if not followups.empty:
        student_fups = followups[followups.student_id == student_data["student_id"]]
        if not student_fups.empty:
            st.dataframe(student_fups[["record_id", "followup_date", "followup_type", "notes", "regularity_status"]].sort_values("followup_date", ascending=False), use_container_width=True)
            delete_fup_id = st.selectbox("اختر متابعة لحذفها", student_fups["record_id"].tolist())
            if st.button("حذف المتابعة المحددة"):
                try:
                    db.delete_followup_record(delete_fup_id)
                    st.success("تم الحذف")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"فشل في حذف المتابعة: {str(e)}")

def show_quizzes(db: Database):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user_role = st.session_state.user["role"]
    if user_role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد (الدرجة الكلية ثابتة 20)")
        with st.form("quiz_form"):
            title = st.text_input("عنوان الاختبار*")
            col1, col2 = st.columns(2)
            num_questions = col1.selectbox("عدد الأسئلة", [10, 20, 30], index=1)
            time_limit = col2.number_input("الوقت (بالدقائق)", 1, 180, 15)
            expiry = st.date_input("تاريخ الانتهاء", datetime.now() + timedelta(days=7))
            if st.form_submit_button("إنشاء الاختبار", use_container_width=True):
                if not title:
                    st.error("يرجى إدخال عنوان الاختبار")
                else:
                    quiz_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    quiz_password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    quiz_id = str(uuid.uuid4())
                    try:
                        db.add_quiz({
                            "quiz_id": quiz_id, "title": title, "description": "",
                            "created_by": st.session_state.user["user_id"], "section_id": "",
                            "num_questions": num_questions, "time_limit_minutes": time_limit,
                            "total_marks": 20, "expiry_date": expiry.strftime("%Y-%m-%d"),
                            "quiz_code": quiz_code, "password": quiz_password, "is_active": "True"
                        })
                        st.success(f"✅ تم إنشاء الاختبار! الكود: {quiz_code}")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"فشل في إنشاء الاختبار: {str(e)}")

        st.markdown("---")
        st.subheader("📝 إدارة الأسئلة")
        quizzes = db.get_quizzes()
        if not quizzes.empty:
            active_quizzes = quizzes[quizzes.is_active == "True"] if "is_active" in quizzes.columns else quizzes
            if not active_quizzes.empty:
                quiz_choice = st.selectbox(
                    "اختر اختباراً لإضافة أسئلة",
                    active_quizzes["quiz_id"],
                    format_func=lambda x: active_quizzes[active_quizzes.quiz_id==x]["title"].values[0]
                )
                if quiz_choice:
                    questions = db.get_quiz_questions(quiz_choice)
                    st.markdown(f"**عدد الأسئلة الحالية:** {len(questions)}")
                    if not questions.empty:
                        st.dataframe(questions[["question_id", "question_text", "question_type", "correct_answer"]], use_container_width=True)

                    with st.form("add_question_form"):
                        qtext = st.text_area("نص السؤال*")
                        qtype = st.selectbox("نوع السؤال", ["اختيار من متعدد", "صح وخطأ", "أكمل", "إجابة قصيرة"])
                        opts = {}
                        if qtype == "اختيار من متعدد":
                            st.markdown("**الخيارات:**")
                            cols = st.columns(4)
                            opts["option1"] = cols[0].text_input("الخيار 1", key="opt1")
                            opts["option2"] = cols[1].text_input("الخيار 2", key="opt2")
                            opts["option3"] = cols[2].text_input("الخيار 3", key="opt3")
                            opts["option4"] = cols[3].text_input("الخيار 4", key="opt4")
                        elif qtype == "صح وخطأ":
                            opts["option1"] = "صح"; opts["option2"] = "خطأ"
                            opts["option3"] = ""; opts["option4"] = ""
                        else:
                            opts["option1"] = ""; opts["option2"] = ""; opts["option3"] = ""; opts["option4"] = ""
                        correct = st.text_input("الإجابة الصحيحة*")
                        if st.form_submit_button("إضافة سؤال", use_container_width=True):
                            if not qtext or not correct:
                                st.error("نص السؤال والإجابة الصحيحة مطلوبان")
                            else:
                                try:
                                    db.add_question({
                                        "question_id": str(uuid.uuid4()), "quiz_id": quiz_choice,
                                        "question_text": qtext, "question_type": qtype,
                                        "option1": opts.get("option1", ""), "option2": opts.get("option2", ""),
                                        "option3": opts.get("option3", ""), "option4": opts.get("option4", ""),
                                        "correct_answer": correct
                                    })
                                    st.success("✅ تمت إضافة السؤال")
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"فشل في إضافة السؤال: {str(e)}")

                    if not questions.empty:
                        del_q_id = st.selectbox(
                            "اختر سؤالاً لحذفه",
                            questions["question_id"],
                            format_func=lambda qid: f"{questions[questions.question_id==qid]['question_text'].values[0]}"
                        )
                        if st.button("حذف السؤال المحدد"):
                            try:
                                db.delete_question(del_q_id)
                                st.success("تم حذف السؤال")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"فشل في حذف السؤال: {str(e)}")
            else:
                st.info("لا توجد اختبارات نشطة.")
        else:
            st.info("لا توجد اختبارات مسجلة.")

        st.markdown("---")
        st.subheader("🗑️ حذف اختبار وكل ما يتعلق به")
        all_quizzes = db.get_quizzes()
        if not all_quizzes.empty:
            quiz_to_delete = st.selectbox(
                "اختر اختباراً للحذف",
                all_quizzes["quiz_id"],
                format_func=lambda x: all_quizzes[all_quizzes.quiz_id==x]["title"].values[0]
            )
            if st.button("❌ حذف الاختبار نهائياً", key="delete_quiz_btn"):
                try:
                    db.delete_quiz(quiz_to_delete)
                    st.success("تم حذف الاختبار وكل ما يتعلق به")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"فشل في حذف الاختبار: {str(e)}")

    st.markdown("---")
    st.subheader("📊 نتائج الاختبارات")
    results = db.get_quiz_results()
    if not results.empty:
        st.dataframe(results[["student_name", "score", "total_marks", "submission_time"]], use_container_width=True)
        if st.button("🏆 ترتيب الطالبات"):
            top = results.groupby("student_name")["score"].sum().reset_index().sort_values("score", ascending=False)
            st.dataframe(top, use_container_width=True)
    else:
        st.info("لا توجد نتائج بعد.")

def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    attendance = db.get_attendance()
    if attendance.empty:
        st.info("لا توجد بيانات حضور.")
        return
    attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    st.subheader("📅 تقرير الغياب الشهري")
    col1, col2 = st.columns(2)
    month = col1.selectbox("الشهر", range(1, 13), index=datetime.now().month - 1)
    year = col2.number_input("السنة", value=datetime.now().year, min_value=2020)
    monthly = attendance[(attendance.date.dt.month == month) & (attendance.date.dt.year == year)]
    if not monthly.empty:
        summary = monthly.groupby(["student_id", "status"]).size().reset_index(name="count")
        pivot = summary.pivot(index="student_id", columns="status", values="count").fillna(0).reset_index()
        students_df = db.get_students()
        if not students_df.empty and not pivot.empty:
            pivot = pivot.merge(students_df[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(pivot, use_container_width=True)
        fig = px.pie(monthly, names="status", title=f"نسب الحضور لشهر {month}/{year}")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات لهذا الشهر.")

def show_logs(db: Database):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db.get_logs()
    if not logs.empty:
        logs["timestamp"] = pd.to_datetime(logs["timestamp"])
        st.dataframe(logs.sort_values("timestamp", ascending=False), use_container_width=True)
        delete_log_id = st.selectbox("اختر سجلاً لحذفه", logs["log_id"].tolist())
        if st.button("حذف السجل المحدد"):
            try:
                db.delete_log(delete_log_id)
                st.success("تم الحذف")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"فشل في حذف السجل: {str(e)}")

def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    with st.form("change_password_form"):
        old_pwd = st.text_input("كلمة المرور الحالية", type="password")
        new_pwd = st.text_input("كلمة المرور الجديدة", type="password")
        confirm_pwd = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old_pwd or not new_pwd or not confirm_pwd:
                st.error("الرجاء ملء جميع الحقول")
            elif old_pwd != st.session_state.user.get("password", ""):
                st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new_pwd) < 4:
                st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
            elif new_pwd != confirm_pwd:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                try:
                    db.update_user(st.session_state.user["user_id"], {"password": new_pwd})
                    st.session_state.user["password"] = new_pwd
                    st.success("✅ تم تغيير كلمة المرور بنجاح!")
                except Exception as e:
                    st.error(f"فشل في تغيير كلمة المرور: {str(e)}")

# =============================================================================
# الدالة الرئيسية
# =============================================================================

def main():
    """نقطة بداية التطبيق"""
    inject_css()
    init_session()

    try:
        creds = get_credentials()
    except Exception as e:
        st.error(f"❌ خطأ في الاعتمادات: {e}")
        st.stop()

    db = Database(creds, get_spreadsheet_id())
    jwt_secret = get_jwt_secret()

    # زر المساعدة الثابت - أعلى اليسار
    st.markdown('<div class="help-float-container">', unsafe_allow_html=True)
    if st.button("🆘 مركز المساعدة", key="fixed_help_btn", help="الإبلاغ عن مشكلة أو خطأ"):
        st.session_state.open_help_dialog = True
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.student_quiz_started and st.session_state.student_quiz:
        try:
            show_student_quiz(db)
        except Exception as e:
            error_details = traceback.format_exc()
            st.error("حدث خطأ غير متوقع أثناء الاختبار. يمكنك الإبلاغ عنه باستخدام زر مركز المساعدة.")
            st.session_state.last_error_details = error_details
    else:
        if not st.session_state.authenticated:
            show_login_page(db, jwt_secret)
        else:
            token_data = verify_token(st.session_state.token, jwt_secret)
            if not token_data:
                st.error("⏰ انتهت صلاحية الجلسة. يرجى تسجيل الدخول مرة أخرى.")
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
            try:
                if choice == "🏠 لوحة التحكم":
                    show_dashboard(db)
                elif choice == "👥 إدارة المستخدمين":
                    if st.session_state.user["role"] == "System Admin":
                        show_user_management(db)
                    else:
                        st.error("🚫 غير مصرح لك بالوصول لهذه الصفحة")
                elif choice in ["👩‍🎓 الطالبات", "👩‍🎓 طالباتي"]:
                    show_user_management(db)
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
                        st.error("🚫 غير مصرح لك بالوصول لهذه الصفحة")
                elif choice == "🔒 تغيير كلمة المرور":
                    change_password(db)
            except Exception as e:
                error_details = traceback.format_exc()
                st.error("❌ حدث خطأ غير متوقع. يمكنك الإبلاغ عنه من خلال زر مركز المساعدة أعلاه.")
                st.session_state.last_error_details = error_details
            st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("open_help_dialog"):
        show_help_dialog()
        st.session_state.open_help_dialog = False

if __name__ == "__main__":
    main()
