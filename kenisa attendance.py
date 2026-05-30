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

# ===================== الإعدادات العامة =====================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
APP_VERSION = "2.4.0"

st.set_page_config(
    page_title="نظام الغياب والافتقاد - كنيسة الشهيدة دميانة",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_credentials():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return creds
    except Exception as e:
        err_msg = "❌ خطأ في بيانات اعتماد Google. تأكد من .streamlit/secrets.toml\n" + str(e)
        st.error(err_msg)
        st.stop()

def get_spreadsheet_id():
    try:
        return st.secrets["sheets"]["spreadsheet_id"]
    except Exception as e:
        err_msg = "❌ لم يتم العثور على spreadsheet_id في secrets.toml: " + str(e)
        st.error(err_msg)
        st.stop()

def get_jwt_secret():
    try:
        return st.secrets["sheets"]["jwt_secret"]
    except:
        return DEFAULT_JWT_SECRET

# ===================== التصميم العام =====================
def inject_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

        * {
            font-family: 'Cairo', sans-serif;
        }

        body {
            direction: rtl;
            text-align: right;
            background-color: #f0f2f6;
            color: #1a1a2e;
        }

        .stApp {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
        }

        /* إخفاء رأس الصفحة والتذييل */
        header[data-testid="stHeader"] {
            display: none !important;
        }
        #MainMenu {
            visibility: hidden;
        }
        footer {
            visibility: hidden;
        }

        /* إخفاء جميع أزرار الشريط الجانبي الافتراضية نهائياً */
        button[data-testid="collapsedControl"],
        button[data-testid="stSidebarCollapseButton"],
        button[aria-label="Close sidebar"],
        [data-testid="stSidebar"] > button,
        [data-testid="stSidebar"] > div:first-child > button,
        [data-testid="stSidebarResizer"],
        [data-testid="stSidebarNavToggle"] {
            display: none !important;
        }

        /* العناوين الرئيسية */
        .main-header {
            font-size: 2.2rem;
            font-weight: 700;
            color: #1a1a2e;
            text-align: center;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: rgba(255,255,255,0.9);
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            backdrop-filter: blur(5px);
            border: 1px solid rgba(0,0,0,0.05);
        }

        .card {
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            margin-bottom: 1rem;
            transition: transform 0.2s, box-shadow 0.2s;
            color: #1a1a2e;
            border: 1px solid rgba(0,0,0,0.05);
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }

        .stat-card {
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            padding: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            color: #1a1a2e;
            border: 1px solid rgba(0,0,0,0.05);
        }
        .stat-card .value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #667eea;
            margin: 0.5rem 0;
        }
        .stat-card .label {
            font-size: 1rem;
            color: #555;
            font-weight: 600;
        }

        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s;
            box-shadow: 0 2px 8px rgba(102,126,234,0.3);
        }
        .stButton > button:hover {
            transform: scale(1.02);
            box-shadow: 0 5px 15px rgba(102,126,234,0.4);
        }
        .stButton > button:active {
            transform: scale(0.98);
        }

        .stRadio > div, .stSelectbox > div, .stMultiSelect > div {
            direction: rtl;
        }
        .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput {
            text-align: right;
        }

        /* تنسيق الشريط الجانبي */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
            border-left: 1px solid rgba(0,0,0,0.08);
            padding-top: 1rem;
        }
        section[data-testid="stSidebar"] .stRadio > div {
            direction: rtl;
        }
        section[data-testid="stSidebar"] .stRadio label {
            font-weight: 600;
            color: #1a1a2e;
            font-size: 1rem;
        }

        /* زر الإخفاء داخل الشريط */
        .hide-sidebar-btn button {
            background: #667eea !important;
            color: white !important;
            font-weight: bold;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        /* زر الإظهار العائم */
        .floating-show-btn {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 99999;
        }
        .floating-show-btn button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 14px !important;
            width: 65px !important;
            height: 65px !important;
            font-size: 28px !important;
            font-weight: bold !important;
            box-shadow: 0 4px 20px rgba(102,126,234,0.5) !important;
            transition: all 0.2s !important;
        }
        .floating-show-btn button:hover {
            transform: scale(1.1) !important;
            box-shadow: 0 8px 25px rgba(118,75,162,0.6) !important;
        }

        /* مؤقت الاختبار */
        .timer-container {
            text-align: center;
            margin: 1rem 0;
        }
        .timer-box {
            display: inline-block;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 0.8rem 2rem;
            border-radius: 15px;
            font-size: 1.8rem;
            font-weight: bold;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }

        /* تنسيق الجداول */
        .stDataFrame {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }

        /* تنسيق expander */
        .streamlit-expanderHeader {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            border-radius: 8px;
            font-weight: 600;
        }
        .streamlit-expanderContent {
            background: white;
            border-radius: 0 0 8px 8px;
            border: 1px solid rgba(0,0,0,0.05);
        }

        /* تنسيق النماذج */
        .stForm {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            border: 1px solid rgba(0,0,0,0.05);
        }

        /* تنسيق التبويبات */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(102,126,234,0.1);
            border-radius: 8px 8px 0 0;
            padding: 10px 20px;
            font-weight: 600;
            color: #667eea;
            border: 1px solid rgba(102,126,234,0.2);
            border-bottom: none;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
        }

        /* تنسيق selectbox */
        .stSelectbox > div > div {
            background: white;
            border-radius: 8px;
            border: 1px solid rgba(0,0,0,0.1);
        }

        /* تنسيق toast و success messages */
        .stSuccess, .stInfo, .stWarning, .stError {
            border-radius: 10px;
            font-weight: 600;
        }
        .stSuccess {
            background: rgba(40,167,69,0.1);
            border: 1px solid rgba(40,167,69,0.2);
            color: #155724;
        }
        .stError {
            background: rgba(220,53,69,0.1);
            border: 1px solid rgba(220,53,69,0.2);
            color: #721c24;
        }

        /* تنسيق عمود المحتوى */
        .content-area {
            padding: 0 1rem;
        }

        /* تنسيق البحث */
        .search-box input {
            border-radius: 25px !important;
            border: 2px solid #667eea !important;
            padding: 10px 20px !important;
        }

        /* تأثيرات إضافية */
        .fade-in {
            animation: fadeIn 0.5s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
    """, unsafe_allow_html=True)

# ===================== كلاس إدارة قاعدة البيانات =====================
class Database:
    """يدير كل العمليات مع Google Sheets."""
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

    # ---------- المستخدمون ----------
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
        self._df_to_sheet("Users", df, [
            "user_id", "username", "password", "role",
            "full_name", "section_id", "phone", "email"
        ])

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

    # ---------- الأقسام ----------
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

    # ---------- الطالبات ----------
    def get_students(self):
        return self._sheet_to_df("Students")

    def add_student(self, student_data: dict):
        df = self.get_students()
        if df.empty:
            df = pd.DataFrame(columns=[
                "student_id", "full_name", "section_id", "teacher_id",
                "phone", "parent_phone", "birthdate", "address", "notes", "status"
            ])
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        self._df_to_sheet("Students", df, [
            "student_id", "full_name", "section_id", "teacher_id",
            "phone", "parent_phone", "birthdate", "address", "notes", "status"
        ])

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

    # ---------- الحضور ----------
    def get_attendance(self):
        return self._sheet_to_df("Attendance")

    def add_attendance_record(self, record: dict):
        df = self.get_attendance()
        if df.empty:
            df = pd.DataFrame(columns=[
                "record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"
            ])
        existing_idx = df[df.record_id == record["record_id"]].index
        if len(existing_idx) > 0:
            for k, v in record.items():
                df.at[existing_idx[0], k] = v
        else:
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("Attendance", df, [
            "record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"
        ])

    def get_attendance_by_date_section(self, date_str, section_id):
        df = self.get_attendance()
        if df.empty:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    # ---------- الافتقاد ----------
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record: dict):
        df = self.get_followup()
        if df.empty:
            df = pd.DataFrame(columns=[
                "record_id", "student_id", "teacher_id", "followup_date",
                "followup_type", "notes", "regularity_status"
            ])
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("FollowUp", df, [
            "record_id", "student_id", "teacher_id", "followup_date",
            "followup_type", "notes", "regularity_status"
        ])

    # ---------- الاختبارات ----------
    def get_quizzes(self):
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data: dict):
        df = self.get_quizzes()
        if df.empty:
            df = pd.DataFrame(columns=[
                "quiz_id", "title", "description", "created_by", "section_id",
                "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                "quiz_code", "password", "is_active"
            ])
        df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
        self._df_to_sheet("Quizzes", df, [
            "quiz_id", "title", "description", "created_by", "section_id",
            "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
            "quiz_code", "password", "is_active"
        ])

    def update_quiz(self, quiz_id, updates):
        df = self.get_quizzes()
        idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = v
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def get_quiz_questions(self, quiz_id):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            return pd.DataFrame()
        return df[df.quiz_id == quiz_id]

    def add_question(self, q_data: dict):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            df = pd.DataFrame(columns=[
                "question_id", "quiz_id", "question_text", "question_type",
                "option1", "option2", "option3", "option4", "correct_answer"
            ])
        df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
        self._df_to_sheet("QuizQuestions", df, [
            "question_id", "quiz_id", "question_text", "question_type",
            "option1", "option2", "option3", "option4", "correct_answer"
        ])

    def delete_question(self, question_id):
        df = self._sheet_to_df("QuizQuestions")
        df = df[df.question_id != question_id]
        self._df_to_sheet("QuizQuestions", df, df.columns.tolist())

    # ---------- نتائج الاختبارات ----------
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
            df = pd.DataFrame(columns=[
                "result_id", "quiz_id", "student_id", "student_name",
                "score", "total_marks", "submission_time", "answers"
            ])
        df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, [
            "result_id", "quiz_id", "student_id", "student_name",
            "score", "total_marks", "submission_time", "answers"
        ])

    # ---------- السجلات ----------
    def add_log(self, user_id, action, details=""):
        df = self._sheet_to_df("Logs")
        if df.empty:
            df = pd.DataFrame(columns=["log_id", "timestamp", "user_id", "action", "details"])
        log = {
            "log_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details
        }
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

# ===================== JWT =====================
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

# ===================== الجلسة =====================
def init_session():
    defaults = {
        "authenticated": False,
        "user": None,
        "token": None,
        "student_quiz": None,
        "student_quiz_started": False,
        "quiz_phase": "enter_name",
        "student_name": "",
        "quiz_start_time": None,
        "quiz_end_time": None,
        "quiz_answers": {},
        "quiz_submitted": False,
        "last_score": 0,
        "login_attempted": False,
        "menu_choice": "🏠 لوحة التحكم",
        "show_sidebar": True
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

# ===================== دوال مساعدة =====================
def search_students(df, query):
    if df.empty or not query:
        return df
    query = str(query).lower()
    mask = (
        df["full_name"].astype(str).str.lower().str.contains(query, na=False) |
        df["phone"].astype(str).str.contains(query, na=False) |
        df["parent_phone"].astype(str).str.contains(query, na=False) |
        df["address"].astype(str).str.lower().str.contains(query, na=False)
    )
    return df[mask]

def export_to_csv(df, filename):
    if df.empty:
        return None
    return df.to_csv(index=False).encode("utf-8-sig")

# ===================== تهيئة أول مدير =====================
def show_initialization(db: Database):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", type="primary", use_container_width=True):
            admin_data = {
                "user_id": "admin-001",
                "username": "admin",
                "password": "admin123",
                "role": "System Admin",
                "full_name": "مدير النظام",
                "section_id": "",
                "phone": "0100000000",
                "email": "admin@church.com"
            }
            db.add_user(admin_data)
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.info("**اسم المستخدم:** `admin`\n\n**كلمة المرور:** `admin123`")
            time.sleep(2)
            st.rerun()
        st.stop()

# ===================== صفحة تسجيل الدخول =====================
def show_login_page(db: Database, jwt_secret: str):
    st.markdown("<h1 class='main-header'>⛪ نظام الغياب والافتقاد<br>الكنيسة الشهيدة دميانة بأسيوط</h1>", unsafe_allow_html=True)

    show_initialization(db)

    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم", placeholder="admin")
            password = st.text_input("كلمة المرور", type="password", placeholder="admin123")
            submitted = st.form_submit_button("تسجيل الدخول", use_container_width=True)

            if submitted:
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
            submitted = st.form_submit_button("بدء الاختبار", use_container_width=True)

            if submitted:
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
                                    st.session_state.quiz_start_time = None
                                    st.session_state.quiz_end_time = None
                                    st.session_state.quiz_answers = {}
                                    st.session_state.quiz_submitted = False
                                    st.rerun()
                            except Exception as e:
                                st.error(f"خطأ في التحقق من الاختبار: {str(e)}")

# ===================== واجهة الطالبة لحل الاختبار =====================
def show_student_quiz(db: Database):
    quiz = st.session_state.student_quiz

    # --- المرحلة: إدخال الاسم ---
    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz['title']}")
        st.markdown(f"**عدد الأسئلة:** {quiz['num_questions']} | **الدرجة الكلية:** 20 | **الوقت:** {quiz['time_limit_minutes']} دقيقة")
        st.markdown("---")
        name = st.text_input("الاسم الثلاثي الكامل للطالبة*", placeholder="أدخل اسمك بالكامل")
        if st.button("بدء الاختبار", use_container_width=True, type="primary"):
            if not name.strip():
                st.error("الرجاء إدخال الاسم")
                return
            # التحقق من عدم وجود محاولة سابقة بنفس الاسم
            existing_results = db.get_quiz_results(quiz["quiz_id"])
            if not existing_results.empty:
                if name.strip().lower() in existing_results["student_name"].str.lower().values:
                    st.error("لقد قمت بتسليم هذا الاختبار بالفعل. لا يمكنك تكرار المحاولة.")
                    return
            # تسجيل الاسم وبدء الوقت
            st.session_state.student_name = name.strip()
            st.session_state.quiz_start_time = datetime.now()
            time_limit_seconds = int(quiz["time_limit_minutes"]) * 60
            st.session_state.quiz_end_time = st.session_state.quiz_start_time + timedelta(seconds=time_limit_seconds)
            st.session_state.quiz_phase = "taking_quiz"
            st.rerun()
        return

    # --- المرحلة: إنهاء الاختبار (تم تسليمه أو انتهى الوقت) ---
    if st.session_state.quiz_submitted or st.session_state.quiz_phase == "finished":
        st.success("تم تسليم الاختبار بنجاح!")
        if "last_score" in st.session_state:
            st.info(f"نتيجتك: {st.session_state.last_score}/20")
        if st.button("إنهاء والعودة إلى الرئيسية", use_container_width=True):
            for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                        "quiz_start_time", "quiz_end_time", "quiz_answers", "quiz_submitted", "last_score"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        return

    # --- المرحلة: أثناء حل الاختبار ---
    # عرض المؤقت بواسطة JavaScript (عد تنازلي حي)
    end_time_str = st.session_state.quiz_end_time.isoformat()
    st.markdown(f"""
    <div class="timer-container">
        <div class="timer-box" id="quiz-timer">⏳ الوقت المتبقي: --:--</div>
    </div>
    <input type="hidden" id="end-time-data" value="{end_time_str}">
    <script>
        (function() {{
            const endTime = new Date(document.getElementById('end-time-data').value);
            const timerDiv = document.getElementById('quiz-timer');

            function updateTimer() {{
                const now = new Date();
                const diff = endTime - now;
                if (diff <= 0) {{
                    timerDiv.innerHTML = '⏳ الوقت المتبقي: 00:00';
                    // النقر على زر التسليم المخفي
                    const btn = document.getElementById('timeout-submit-btn');
                    if (btn) {{
                        btn.click();
                    }}
                    return;
                }}
                const mins = Math.floor(diff / 60000);
                const secs = Math.floor((diff % 60000) / 1000);
                timerDiv.innerHTML = `⏳ الوقت المتبقي: ${{mins.toString().padStart(2,'0')}}:${{secs.toString().padStart(2,'0')}}`;
                setTimeout(updateTimer, 1000);
            }}
            updateTimer();
        }})();
    </script>
    """, unsafe_allow_html=True)

    st.title(f"📝 {quiz['title']}")
    st.markdown(f"الطالبة: **{st.session_state.student_name}** | الدرجة الكلية: 20")
    st.markdown("---")

    # عرض الأسئلة
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
            options = []
            if q_type == "اختيار من متعدد":
                options = [q["option1"], q["option2"], q["option3"], q["option4"]]
            else:
                options = ["صح", "خطأ"]
            options = [opt for opt in options if opt and str(opt).strip()]

            if options:
                current_index = options.index(prev_answer) if prev_answer in options else None
                ans = st.radio("اختر الإجابة", options, key=f"q_{q_id}", index=current_index)
                st.session_state.quiz_answers[q_id] = ans if ans else ""
        else:
            ans = st.text_input("الإجابة", key=f"q_{q_id}", value=prev_answer)
            st.session_state.quiz_answers[q_id] = ans
        st.markdown("---")

    # زر التسليم اليدوي
    if st.button("تسليم الاختبار", type="primary", use_container_width=True):
        auto_submit_quiz(db, quiz)
        st.session_state.quiz_phase = "finished"
        st.rerun()

    # زر مخفي للإرسال التلقائي عند انتهاء الوقت
    st.markdown('<div id="timeout-btn-container" style="display:none;">', unsafe_allow_html=True)
    if st.button("إرسال تلقائي", key="timeout_submit_btn"):
        if not st.session_state.quiz_submitted:
            auto_submit_quiz(db, quiz)
            st.session_state.quiz_phase = "finished"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def auto_submit_quiz(db, quiz):
    """حساب النتيجة وتخزينها (الدرجة من 20)"""
    questions = db.get_quiz_questions(quiz["quiz_id"])
    if questions.empty:
        return

    correct_count = 0
    answers_dict = dict(st.session_state.quiz_answers)

    for _, q_row in questions.iterrows():
        q = q_row.to_dict()
        correct = str(q["correct_answer"]).strip().lower()
        user_ans = str(answers_dict.get(q["question_id"], "")).strip().lower()
        if correct == user_ans:
            correct_count += 1

    num_q = len(questions)
    score = round((correct_count / num_q) * 20, 1) if num_q > 0 else 0

    result = {
        "result_id": str(uuid.uuid4()),
        "quiz_id": quiz["quiz_id"],
        "student_id": "external",
        "student_name": st.session_state.student_name,
        "score": score,
        "total_marks": 20,
        "submission_time": datetime.now().isoformat(),
        "answers": json.dumps(answers_dict, ensure_ascii=False)
    }
    db.save_quiz_result(result)
    st.session_state.quiz_submitted = True
    st.session_state.last_score = score

# ===================== القائمة الجانبية =====================
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
                "🏠 لوحة التحكم",
                "👥 إدارة المستخدمين",
                "👩‍🎓 الطالبات",
                "👩‍🏫 المدرسات والأقسام",
                "📋 الحضور",
                "💬 الافتقاد",
                "📝 المسابقات والاختبارات",
                "📊 التقارير والإحصائيات",
                "📜 سجل العمليات",
                "🔒 تغيير كلمة المرور"
            ],
            "Father Account": [
                "🏠 لوحة التحكم",
                "📊 التقارير والإحصائيات",
                "🔒 تغيير كلمة المرور"
            ],
            "Service Manager": [
                "🏠 لوحة التحكم",
                "👩‍🎓 طالباتي",
                "📋 الحضور",
                "💬 الافتقاد",
                "📝 المسابقات والاختبارات",
                "📊 التقارير والإحصائيات",
                "🔒 تغيير كلمة المرور"
            ],
            "Teacher": [
                "🏠 لوحة التحكم",
                "👩‍🎓 طالباتي",
                "📋 الحضور",
                "💬 الافتقاد",
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
            "القائمة الرئيسية",
            menu_items,
            index=menu_items.index(current_choice),
            key="nav_radio",
            label_visibility="collapsed"
        )

        if choice != current_choice:
            st.session_state.menu_choice = choice
            st.rerun()

        st.divider()

        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout()

        return choice

# ===================== صفحات التطبيق (مكتملة) =====================

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
            fig = px.histogram(recent, x="date", color="status", barmode="group",
                              title="الحضور اليومي", color_discrete_sequence=["#667eea", "#764ba2", "#f093fb"])
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Cairo", size=14),
                xaxis_title="التاريخ",
                yaxis_title="عدد الطالبات"
            )
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
        else:
            st.info("لا توجد بنات منقطعات حالياً.")

def show_admin_users(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    if not users.empty:
        st.dataframe(users, use_container_width=True)
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
            section = None
            if role in ["Service Manager", "Teacher"]:
                section_options = ["None"] + (sections["section_id"].tolist() if not sections.empty else [])
                section = st.selectbox("القسم", section_options)

            phone = st.text_input("رقم الهاتف (اختياري)")
            email = st.text_input("البريد الإلكتروني (اختياري)")

            if st.form_submit_button("إضافة", use_container_width=True):
                if not username or not password or not full_name:
                    st.error("اسم المستخدم وكلمة المرور والاسم الكامل مطلوبان")
                else:
                    existing = users[users.username == username]
                    if not existing.empty:
                        st.error("اسم المستخدم موجود مسبقاً!")
                    else:
                        user_data = {
                            "user_id": str(uuid.uuid4()),
                            "username": username,
                            "password": password,
                            "role": role,
                            "full_name": full_name,
                            "section_id": section if section and section != "None" else "",
                            "phone": phone,
                            "email": email
                        }
                        db.add_user(user_data)
                        db.add_log(st.session_state.user["user_id"], f"إضافة مستخدم {username}")
                        st.success("تم إضافة المستخدم بنجاح")
                        time.sleep(1)
                        st.rerun()

    with st.expander("✏️ تعديل / حذف مستخدم"):
        if not users.empty:
            selected_user_id = st.selectbox("اختر المستخدم", users["user_id"],
                                            format_func=lambda x: f"{users[users.user_id==x]['full_name'].values[0]} ({users[users.user_id==x]['username'].values[0]})")
            user_data = users[users.user_id == selected_user_id].iloc[0].to_dict()

            roles_list = ["System Admin", "Father Account", "Service Manager", "Teacher"]
            current_role = user_data.get("role", "Teacher")
            role_index = roles_list.index(current_role) if current_role in roles_list else 3
            new_role = st.selectbox("الصلاحية الجديدة", roles_list, index=role_index)

            col1, col2 = st.columns(2)
            if col1.button("تحديث الصلاحية", use_container_width=True):
                db.update_user(selected_user_id, {"role": new_role})
                db.add_log(st.session_state.user["user_id"], f"تعديل صلاحية المستخدم {selected_user_id}")
                st.success("تم التحديث")
                time.sleep(1)
                st.rerun()
            if col2.button("حذف المستخدم", use_container_width=True, type="secondary"):
                if selected_user_id == st.session_state.user["user_id"]:
                    st.error("لا يمكنك حذف حسابك الحالي!")
                else:
                    db.delete_user(selected_user_id)
                    db.add_log(st.session_state.user["user_id"], f"حذف المستخدم {selected_user_id}")
                    st.success("تم الحذف")
                    time.sleep(1)
                    st.rerun()

def show_students_management(db: Database):
    st.markdown("<h2 class='main-header'>👩‍🎓 إدارة الطالبات</h2>", unsafe_allow_html=True)
    students = db.get_students()
    sections = db.get_sections()
    all_users = db.get_users()
    teachers = all_users[all_users.role.isin(["Teacher", "Service Manager"])] if not all_users.empty else pd.DataFrame()

    st.markdown("<div class='search-box'>", unsafe_allow_html=True)
    search_query = st.text_input("🔍 البحث السريع (اسم، تليفون، عنوان...)", placeholder="اكتب للبحث...")
    st.markdown("</div>", unsafe_allow_html=True)

    if search_query:
        students = search_students(students, search_query)
        if not students.empty:
            st.info(f"تم العثور على {len(students)} نتيجة")
        else:
            st.warning("لا توجد نتائج مطابقة")

    if not students.empty and not sections.empty:
        display_df = students.merge(sections[["section_id","section_name"]], on="section_id", how="left")
        st.dataframe(display_df, use_container_width=True)
    elif not students.empty:
        st.dataframe(students, use_container_width=True)
    else:
        st.info("لا توجد طالبات مسجلة بعد.")

    with st.expander("➕ إضافة طالبة جديدة"):
        with st.form("add_student_form"):
            full_name = st.text_input("الاسم الكامل*")
            section = st.selectbox("القسم", sections["section_id"] if not sections.empty else [],
                                  format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0] if not sections.empty else x)
            teacher = st.selectbox("المدرسة المسؤولة", teachers["user_id"] if not teachers.empty else [],
                                   format_func=lambda x: teachers[teachers.user_id==x]["full_name"].values[0] if not teachers.empty else x)
            phone = st.text_input("رقم الهاتف")
            parent_phone = st.text_input("رقم ولي الأمر")
            birthdate = st.date_input("تاريخ الميلاد", value=None)
            address = st.text_area("العنوان")
            notes = st.text_area("ملاحظات")

            if st.form_submit_button("إضافة", use_container_width=True):
                if not full_name:
                    st.error("الاسم الكامل مطلوب")
                else:
                    db.add_student({
                        "student_id": str(uuid.uuid4()),
                        "full_name": full_name,
                        "section_id": section,
                        "teacher_id": teacher,
                        "phone": phone,
                        "parent_phone": parent_phone,
                        "birthdate": birthdate.strftime("%Y-%m-%d") if birthdate else "",
                        "address": address,
                        "notes": notes,
                        "status": "active"
                    })
                    db.add_log(st.session_state.user["user_id"], f"إضافة طالبة {full_name}")
                    st.success("تمت الإضافة")
                    time.sleep(1)
                    st.rerun()

    with st.expander("✏️ تعديل بيانات طالبة"):
        if not students.empty:
            selected_student = st.selectbox("اختر طالبة", students["student_id"],
                                            format_func=lambda x: students[students.student_id==x]["full_name"].values[0])
            student_row = students[students.student_id == selected_student].iloc[0].to_dict()

            new_full_name = st.text_input("الاسم الكامل", value=student_row.get("full_name", ""))
            teacher_ids = teachers["user_id"].tolist() if not teachers.empty else []
            current_teacher = student_row.get("teacher_id", "")
            teacher_index = teacher_ids.index(current_teacher) if current_teacher in teacher_ids else 0
            new_teacher = st.selectbox("المدرسة المسؤولة", teachers["user_id"] if not teachers.empty else [],
                                       format_func=lambda x: teachers[teachers.user_id==x]["full_name"].values[0] if not teachers.empty else x,
                                       index=teacher_index)
            new_phone = st.text_input("رقم الهاتف", value=student_row.get("phone", ""))
            new_parent = st.text_input("رقم ولي الأمر", value=student_row.get("parent_phone", ""))
            new_notes = st.text_area("ملاحظات", value=student_row.get("notes", ""))
            status_list = ["active", "inactive"]
            current_status = student_row.get("status", "active")
            status_index = 0 if current_status == "active" else 1
            new_status = st.selectbox("الحالة", status_list, index=status_index)

            if st.button("حفظ التعديلات", use_container_width=True):
                db.update_student(selected_student, {
                    "full_name": new_full_name,
                    "teacher_id": new_teacher,
                    "phone": new_phone,
                    "parent_phone": new_parent,
                    "notes": new_notes,
                    "status": new_status
                })
                db.add_log(st.session_state.user["user_id"], f"تعديل بيانات الطالبة {selected_student}")
                st.success("تم التحديث")
                time.sleep(1)
                st.rerun()

def show_teachers_sections(db: Database):
    st.markdown("<h2 class='main-header'>👩‍🏫 المدرسات والأقسام</h2>", unsafe_allow_html=True)

    sections = db.get_sections()
    st.subheader("📚 الأقسام")
    if not sections.empty:
        st.dataframe(sections, use_container_width=True)
    else:
        st.info("لا توجد أقسام مسجلة.")

    with st.expander("➕ إضافة قسم جديد"):
        with st.form("add_section_form"):
            name = st.text_input("اسم القسم*")
            managers = db.get_users()
            managers = managers[managers.role == "Service Manager"] if not managers.empty else pd.DataFrame()
            manager_options = ["None"] + (managers["user_id"].tolist() if not managers.empty else [])
            manager = st.selectbox("مدير القسم", manager_options,
                                   format_func=lambda x: managers[managers.user_id==x]["full_name"].values[0] if x != "None" and not managers.empty else "لا يوجد")
            if st.form_submit_button("إضافة", use_container_width=True):
                if not name:
                    st.error("اسم القسم مطلوب")
                else:
                    db.add_section({
                        "section_id": str(uuid.uuid4()),
                        "section_name": name,
                        "manager_user_id": manager if manager != "None" else ""
                    })
                    db.add_log(st.session_state.user["user_id"], f"إضافة قسم {name}")
                    st.success("تمت الإضافة")
                    time.sleep(1)
                    st.rerun()

    st.markdown("---")
    st.subheader("👩‍🏫 المدرسات وطالباتهن")
    teachers = db.get_users()
    teachers = teachers[teachers.role == "Teacher"] if not teachers.empty else pd.DataFrame()
    students = db.get_students()

    if not teachers.empty:
        for _, t in teachers.iterrows():
            t_data = t.to_dict()
            assigned = students[students.teacher_id == t_data["user_id"]] if not students.empty else pd.DataFrame()
            with st.container():
                st.markdown(f"<div class='card'><h4>👩‍🏫 {t_data.get('full_name', '')}</h4><p>عدد الطالبات: <strong>{len(assigned)}</strong></p></div>", unsafe_allow_html=True)
                if not assigned.empty:
                    st.dataframe(assigned[["full_name", "section_id", "phone"]], use_container_width=True)
    else:
        st.info("لا يوجد مدرسات مسجلات.")

def show_attendance(db: Database):
    st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
    sections = db.get_sections()
    if sections.empty:
        st.warning("لا توجد أقسام. يرجى إضافة أقسام أولاً.")
        return

    section = st.selectbox("اختر القسم", sections["section_id"],
                           format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
    date = st.date_input("التاريخ", datetime.now())
    date_str = date.strftime("%Y-%m-%d")

    students = db.get_students()
    section_students = students[students.section_id == section] if not students.empty else pd.DataFrame()

    if section_students.empty:
        st.info("لا توجد طالبات في هذا القسم.")
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
        status = cols[1].radio("الحالة", status_list,
                              index=status_index,
                              key=f"att_{sid}", horizontal=True)
        notes = cols[2].text_input("ملاحظة", value=prev_notes, key=f"note_{sid}", label_visibility="collapsed")

        statuses[sid] = status
        notes_dict[sid] = notes
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("💾 حفظ الحضور", type="primary", use_container_width=True):
        with st.spinner("جاري حفظ الحضور..."):
            for sid, status in statuses.items():
                prev_record = existing[existing.student_id == sid] if already_filled else pd.DataFrame()
                record_id = prev_record.iloc[0]["record_id"] if not prev_record.empty else str(uuid.uuid4())

                record = {
                    "record_id": record_id,
                    "date": date_str,
                    "student_id": sid,
                    "status": status,
                    "notes": notes_dict.get(sid, ""),
                    "recorded_by": st.session_state.user["user_id"],
                    "section_id": section
                }
                db.add_attendance_record(record)
            db.add_log(st.session_state.user["user_id"], f"تسجيل حضور قسم {section} ليوم {date_str}")
        st.success("✅ تم تسجيل الحضور بنجاح")
        time.sleep(1)
        st.rerun()

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
            db.add_followup_record({
                "record_id": str(uuid.uuid4()),
                "student_id": student_data["student_id"],
                "teacher_id": user_id,
                "followup_date": datetime.now().strftime("%Y-%m-%d"),
                "followup_type": ftype,
                "notes": notes,
                "regularity_status": regularity
            })
            db.add_log(user_id, f"متابعة الطالبة {student_data.get('full_name', '')}")
            st.success("✅ تم تسجيل الافتقاد بنجاح")

    st.markdown("---")
    st.subheader("📋 سجل المتابعات السابقة")
    followups = db.get_followup()
    if not followups.empty:
        student_fups = followups[followups.student_id == student_data["student_id"]]
        if not student_fups.empty:
            st.dataframe(student_fups[["followup_date", "followup_type", "notes", "regularity_status"]].sort_values("followup_date", ascending=False),
                         use_container_width=True)
        else:
            st.info("لا توجد متابعات سابقة لهذه الطالبة.")
    else:
        st.info("لا توجد متابعات مسجلة.")

def show_quizzes(db: Database):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    user_role = st.session_state.user["role"]

    if user_role in ["System Admin", "Service Manager"]:
        st.subheader("➕ إنشاء اختبار جديد (الدرجة الكلية ثابتة 20)")
        with st.form("quiz_form"):
            title = st.text_input("عنوان الاختبار*")
            desc = st.text_area("وصف الاختبار")
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
                    db.add_quiz({
                        "quiz_id": quiz_id,
                        "title": title,
                        "description": desc,
                        "created_by": st.session_state.user["user_id"],
                        "section_id": "",
                        "num_questions": num_questions,
                        "time_limit_minutes": time_limit,
                        "total_marks": 20,
                        "expiry_date": expiry.strftime("%Y-%m-%d"),
                        "quiz_code": quiz_code,
                        "password": quiz_password,
                        "is_active": "True"
                    })
                    st.success(f"✅ تم إنشاء الاختبار!\n\n**الكود:** `{quiz_code}`\n**كلمة المرور:** `{quiz_password}`")
                    db.add_log(st.session_state.user["user_id"], f"إنشاء اختبار {title}")
                    time.sleep(2)
                    st.rerun()

        st.markdown("---")
        st.subheader("📝 إدارة الأسئلة")
        quizzes = db.get_quizzes()
        if not quizzes.empty:
            active_quizzes = quizzes[quizzes.is_active == "True"] if "is_active" in quizzes.columns else quizzes
            if not active_quizzes.empty:
                quiz_choice = st.selectbox("اختر اختباراً", active_quizzes["quiz_id"],
                                           format_func=lambda x: active_quizzes[active_quizzes.quiz_id==x]["title"].values[0])
                if quiz_choice:
                    questions = db.get_quiz_questions(quiz_choice)
                    st.markdown(f"**عدد الأسئلة الحالية:** {len(questions)}")
                    if not questions.empty:
                        st.dataframe(questions[["question_text", "question_type", "correct_answer"]], use_container_width=True)

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
                            opts["option1"] = "صح"
                            opts["option2"] = "خطأ"
                            opts["option3"] = ""
                            opts["option4"] = ""
                        else:
                            opts["option1"] = ""
                            opts["option2"] = ""
                            opts["option3"] = ""
                            opts["option4"] = ""

                        correct = st.text_input("الإجابة الصحيحة*", help="للاختيار من متعدد: أدخل نص الإجابة الصحيحة. لصح/خطأ: أدخل 'صح' أو 'خطأ'")

                        if st.form_submit_button("إضافة سؤال", use_container_width=True):
                            if not qtext or not correct:
                                st.error("نص السؤال والإجابة الصحيحة مطلوبان")
                            else:
                                db.add_question({
                                    "question_id": str(uuid.uuid4()),
                                    "quiz_id": quiz_choice,
                                    "question_text": qtext,
                                    "question_type": qtype,
                                    "option1": opts.get("option1", ""),
                                    "option2": opts.get("option2", ""),
                                    "option3": opts.get("option3", ""),
                                    "option4": opts.get("option4", ""),
                                    "correct_answer": correct
                                })
                                db.add_log(st.session_state.user["user_id"], f"إضافة سؤال لاختبار {quiz_choice}")
                                st.success("✅ تمت إضافة السؤال")
                                time.sleep(1)
                                st.rerun()
            else:
                st.info("لا توجد اختبارات نشطة.")
        else:
            st.info("لا توجد اختبارات مسجلة.")

    st.markdown("---")
    st.subheader("📊 نتائج الاختبارات")
    results = db.get_quiz_results()
    if not results.empty:
        quizzes_df = db.get_quizzes()
        if not quizzes_df.empty:
            merged = results.merge(quizzes_df[["quiz_id","title"]], on="quiz_id", how="left")
            st.dataframe(merged[["title", "student_name", "score", "total_marks", "submission_time"]].sort_values("submission_time", ascending=False),
                        use_container_width=True)
        else:
            st.dataframe(results[["quiz_id", "student_name", "score", "total_marks", "submission_time"]], use_container_width=True)

        if st.button("🏆 ترتيب الطالبات", use_container_width=True):
            top = results.groupby("student_name")["score"].sum().reset_index().sort_values("score", ascending=False)
            top.columns = ["اسم الطالبة", "المجموع"]
            st.dataframe(top, use_container_width=True)

        csv = export_to_csv(results, "quiz_results.csv")
        if csv:
            st.download_button("📥 تصدير النتائج إلى CSV", csv, "quiz_results.csv", "text/csv", use_container_width=True)
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
    month = col1.selectbox("الشهر", range(1,13), index=datetime.now().month-1)
    year = col2.number_input("السنة", value=datetime.now().year, min_value=2020, max_value=2030)

    monthly = attendance[(attendance.date.dt.month == month) & (attendance.date.dt.year == year)]
    if not monthly.empty:
        summary = monthly.groupby(["student_id", "status"]).size().reset_index(name="count")
        pivot = summary.pivot(index="student_id", columns="status", values="count").fillna(0).reset_index()

        students_df = db.get_students()
        if not students_df.empty and not pivot.empty:
            pivot = pivot.merge(students_df[["student_id","full_name"]], on="student_id", how="left")
            display_cols = ["full_name"] + [col for col in pivot.columns if col not in ["student_id", "full_name"]]
            st.dataframe(pivot[display_cols], use_container_width=True)
        elif not pivot.empty:
            st.dataframe(pivot, use_container_width=True)

        fig = px.pie(monthly, names="status", title=f"نسب الحضور لشهر {month}/{year}",
                    color_discrete_sequence=["#667eea", "#764ba2", "#f093fb"])
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Cairo", size=14)
        )
        st.plotly_chart(fig, use_container_width=True)

        csv = export_to_csv(monthly, "attendance_report.csv")
        if csv:
            st.download_button("📥 تصدير التقرير إلى CSV", csv, "attendance_report.csv", "text/csv", use_container_width=True)
    else:
        st.info("لا توجد بيانات لهذا الشهر.")

    st.subheader("👩‍🏫 نشاط المدرسات في الافتقاد")
    followups = db.get_followup()
    if not followups.empty:
        teacher_activity = followups.groupby("teacher_id").size().reset_index(name="عدد المتابعات")
        teachers_df = db.get_users()
        if not teachers_df.empty:
            teacher_activity = teacher_activity.merge(teachers_df[["user_id","full_name"]], left_on="teacher_id", right_on="user_id", how="left")
            st.dataframe(teacher_activity[["full_name", "عدد المتابعات"]], use_container_width=True)
        else:
            st.dataframe(teacher_activity, use_container_width=True)
    else:
        st.info("لا توجد متابعات مسجلة.")

def show_logs(db: Database):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db._sheet_to_df("Logs")
    if not logs.empty:
        logs["timestamp"] = pd.to_datetime(logs["timestamp"], errors="coerce")
        st.dataframe(logs.sort_values("timestamp", ascending=False), use_container_width=True)

        csv = export_to_csv(logs, "logs.csv")
        if csv:
            st.download_button("📥 تصدير السجلات", csv, "logs.csv", "text/csv", use_container_width=True)
    else:
        st.info("لا توجد سجلات.")

def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    current_user = st.session_state.user

    with st.form("change_password_form"):
        old_pwd = st.text_input("كلمة المرور الحالية", type="password")
        new_pwd = st.text_input("كلمة المرور الجديدة", type="password")
        confirm_pwd = st.text_input("تأكيد كلمة المرور الجديدة", type="password")

        if st.form_submit_button("تغيير كلمة المرور", use_container_width=True):
            if not old_pwd or not new_pwd or not confirm_pwd:
                st.error("الرجاء ملء جميع الحقول")
            elif old_pwd != current_user.get("password", ""):
                st.error("كلمة المرور الحالية غير صحيحة")
            elif len(new_pwd) < 4:
                st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
            elif new_pwd != confirm_pwd:
                st.error("كلمتا المرور الجديدتان غير متطابقتين")
            else:
                db.update_user(current_user["user_id"], {"password": new_pwd})
                st.session_state.user["password"] = new_pwd
                db.add_log(current_user["user_id"], "تغيير كلمة المرور")
                st.success("✅ تم تغيير كلمة المرور بنجاح!")
                time.sleep(1)
                st.rerun()

# ===================== التطبيق الرئيسي =====================
def main():
    inject_css()
    init_session()

    try:
        creds = get_credentials()
    except:
        return

    db = Database(creds, get_spreadsheet_id())
    jwt_secret = get_jwt_secret()

    if st.session_state.student_quiz_started and st.session_state.student_quiz:
        show_student_quiz(db)
        return

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
            st.markdown("""
                <style>
                    section[data-testid="stSidebar"] {
                        display: none !important;
                    }
                </style>
            """, unsafe_allow_html=True)
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
                show_admin_users(db)
            else:
                st.error("🚫 غير مصرح لك بالوصول لهذه الصفحة")
        elif choice in ["👩‍🎓 الطالبات", "👩‍🎓 طالباتي"]:
            show_students_management(db)
        elif choice == "👩‍🏫 المدرسات والأقسام":
            if st.session_state.user["role"] == "System Admin":
                show_teachers_sections(db)
            else:
                st.error("🚫 غير مصرح لك بالوصول لهذه الصفحة")
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

        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
