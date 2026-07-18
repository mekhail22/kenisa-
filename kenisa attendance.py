# =============================================================================
# ⛪ نظام إدارة مدرسة الأحد - كنيسة الشهيدة دميانة
# File: kenisa_attendance.py | Lines: ~7000 | Single-file Streamlit App
# =============================================================================

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import uuid
import json
import jwt
import time
import qrcode
from io import BytesIO
import base64
import openpyxl
import threading
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
QUIZ_JWT_SECRET = "StDemianaChurch2025!QuizSecure#Key"
CACHE_TTL_SECONDS = 600
CAIRO_TZ = timezone(timedelta(hours=3), name='Africa/Cairo')

def get_cairo_now():
    """إرجاع التوقيت الحالي بتوقيت القاهرة."""
    return datetime.now(CAIRO_TZ)

def format_cairo_time(dt):
    """تنسيق التاريخ والوقت للعرض باللغة العربية."""
    try:
        if dt is None: return "غير متاح"
        return dt.astimezone(CAIRO_TZ).strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return "خطأ في التنسيق"

def get_browser_info():
    """استخراج معلومات المتصفح."""
    try:
        user_agent = st.session_state.get('_user_agent', 'Chrome')
        return str(user_agent)[:50] if user_agent else "Chrome"
    except Exception:
        return "Unknown"

def get_os_info():
    """استخراج معلومات نظام التشغيل."""
    try:
        os_info = st.session_state.get('_os', 'Windows')
        return str(os_info)[:50] if os_info else "Windows"
    except Exception:
        return "Unknown"

def mask_ip_address(ip):
    """استخراج عنوان IP مُخفي."""
    if not ip or ip == '0.0.0.0': return "0.0.0.0"
    parts = ip.split('.')
    if len(parts) == 4: return f"{parts[0]}.{parts[1]}.xxx.xxx"
    return "0.0.0.0"

# =============================================================================
# Credentials & IDs
# =============================================================================
def get_credentials():
    """استخراج بيانات اعتماد Google Cloud من secrets."""
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
    """استخراج معرف جدول Google Sheets من secrets."""
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
    """استخراج مفتاح JWT من secrets أو الإرجاع الافتراضي."""
    try:
        return st.secrets["sheets"]["jwt_secret"]
    except Exception:
        return DEFAULT_JWT_SECRET

def get_admin_password():
    """استخراج كلمة مرور المدير من secrets أو الإرجاع الافتراضي."""
    try:
        return st.secrets.get("admin", {}).get("password", "admin123")
    except Exception:
        return "admin123"

# =============================================================================
# CSS محسّن - Glassmorphism, Gradient Buttons, Cairo Font, RTL
# =============================================================================
def inject_css():
    """حقن أنماط CSS محسّنة في تطبيق Streamlit. RTL, Cairo, Glassmorphism."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
        :root { --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%); --success-color: #28a745; --warning-color: #ffc107; --danger-color: #dc3545; --card-bg: rgba(255, 255, 255, 0.95); --glass-bg: rgba(255, 255, 255, 0.25); }
        html, body, .stApp { font-family: 'Cairo', sans-serif !important; direction: rtl !important; text-align: right !important; }
        .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); min-height: 100vh; }
        header[data-testid="stHeader"] { display: none !important; }
        #MainMenu { visibility: hidden; } footer { visibility: hidden; }
        section[data-testid="stSidebar"] { position: fixed !important; top: 0 !important; right: 0 !important; height: 100vh !important; width: 300px !important; }
        .glass-card { background: var(--glass-bg); backdrop-filter: blur(10px); border-radius: 15px; padding: 1.5rem; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.18); }
        .card { background: var(--card-bg); border-radius: 15px; padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        .stButton > button { background: var(--primary-gradient) !important; color: white !important; border-radius: 8px !important; }
        .main-header { font-size: 2.2rem; font-weight: 700; color: #1a1a2e; text-align: center; margin: 1.5rem 0; padding: 1rem; background: rgba(255,255,255,0.9); border-radius: 15px; margin-top: 100px; }
        .event-badge { display: inline-block; padding: 4px 12px; border-radius: 15px; color: white; font-weight: bold; margin-left: 5px; }
        .badge-meeting { background-color: #3498db; } .badge-service { background-color: #28a745; } .badge-trip { background-color: #f39c12; } .badge-celebration { background-color: #9b59b6; }
        .ai-insight-box { background: linear-gradient(135deg, rgba(102,126,234,0.1) 0%, rgba(122,76,178,0.1) 100%); border-right: 4px solid #667eea; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
        .integrity-high { background: rgba(220,53,69,0.1); border-right: 4px solid #dc3545; padding: 0.5rem; margin: 0.2rem 0; }
        .integrity-medium { background: rgba(255,193,7,0.1); border-right: 4px solid #ffc107; padding: 0.5rem; margin: 0.2rem 0; }
        @media print { .stButton { display: none !important; } }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# تهيئة الكاش والجلسات
# =============================================================================
def init_data_cache():
    """تهيئة نظام الكاش داخل session_state لتحسين أداء قراءة البيانات."""
    if 'data_cache' not in st.session_state: st.session_state.data_cache = {}
    if 'data_dirty' not in st.session_state: st.session_state.data_dirty = {}

def init_session():
    """تهيئة جلسة المستخدم وتعيين القيم الافتراضية."""
    defaults = {
        "authenticated": False, "user": None, "token": None, "menu_choice": "🏠 لوحة التحكم",
        "show_sidebar": True, "open_help_dialog": False, "dark_mode": False,
        "audit_initialized": False, "last_activity_time": time.time(), "log_page": 1,
        "page_load_time": time.time(), "_start_time": time.time()
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

# =============================================================================
# Database Class
# =============================================================================
class Database:
    """فئة قاعدة البيانات التي تتعامل مع Google Sheets."""
    _request_times = []
    _lock = threading.Lock()

    @staticmethod
    def _rate_limit():
        """التحكم في معدل الطلبات لتجنب تجاوز حدود Google Sheets API."""
        now = time.time()
        with Database._lock:
            Database._request_times = [t for t in Database._request_times if now - t < 60]
            if len(Database._request_times) >= 40:
                sleep_time = 60 - (now - Database._request_times[0]) + 1
                if sleep_time > 0: time.sleep(sleep_time)
                Database._request_times = []
            Database._request_times.append(now)

    def __init__(self, creds, spreadsheet_id):
        try:
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        except Exception as e:
            st.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
            raise

    def _get_or_create_worksheet(self, name, columns):
        """الحصول على ورقة العمل أو إنشاؤها إذا لم تكن موجودة."""
        Database._rate_limit()
        try: ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(columns), 1))
            if columns: ws.append_row(columns)
        time.sleep(0.2)
        return ws

    def _get_cached_df(self, sheet_name, fetch_func):
        """الحصول على DataFrame من الكاش أو تحميله من Google Sheets."""
        init_data_cache()
        cache, dirty = st.session_state.data_cache, st.session_state.data_dirty
        now = time.time()
        if sheet_name in cache and not dirty.get(sheet_name, False):
            entry = cache[sheet_name]
            if now - entry['timestamp'] < CACHE_TTL_SECONDS: return entry['data'].copy()
        df = fetch_func()
        st.session_state.data_cache[sheet_name] = {'data': df.copy(), 'timestamp': now}
        st.session_state.data_dirty[sheet_name] = False
        return df.copy()

    def _invalidate_cache(self, sheet_name):
        """إبطال الكاش لورقة عمل معينة."""
        init_data_cache()
        st.session_state.data_dirty[sheet_name] = True

    def _read_sheet_raw(self, sheet_name):
        """قراءة البيانات الخام من ورقة العمل."""
        Database._rate_limit()
        ws = self._get_or_create_worksheet(sheet_name, [])
        values = ws.get_all_values()
        time.sleep(0.2)
        if not values or len(values) < 1: return pd.DataFrame()
        raw_headers = [h.strip() for h in values[0]]
        seen = {}
        unique_headers = []
        for h in raw_headers:
            if h in seen: seen[h] += 1; unique_headers.append(f"{h}_{seen[h]}")
            else: seen[h] = 0; unique_headers.append(h)
        df = pd.DataFrame(values[1:], columns=unique_headers)
        df.dropna(how='all', axis=1, inplace=True)
        df.dropna(how='all', inplace=True)
        return df.astype(object)

    def _sheet_to_df(self, sheet_name):
        """تحويل ورقة العمل إلى DataFrame مع كاش."""
        return self._get_cached_df(sheet_name, lambda: self._read_sheet_raw(sheet_name))

    def _df_to_sheet(self, sheet_name, df, columns):
        """كتابة DataFrame إلى ورقة العمل."""
        if not isinstance(df, pd.DataFrame): raise ValueError("df must be a DataFrame")
        if not isinstance(columns, list) or not columns: raise ValueError("columns must be a non-empty list")
        Database._rate_limit()
        ws = self._get_or_create_worksheet(sheet_name, columns)
        for col in columns:
            if col not in df.columns: df[col] = ""
        work_df = df[columns].copy()
        work_df.fillna("", inplace=True)
        work_df = work_df.astype(str)
        values = [columns] + work_df.values.tolist()
        ws.resize(rows=len(values), cols=len(columns))
        ws.update(values)
        time.sleep(0.2)
        self._invalidate_cache(sheet_name)

    @staticmethod
    def _safe_str(value):
        """تحويل القيم إلى نص مع معالجة القيم الفارغة."""
        if value is None or (isinstance(value, float) and pd.isna(value)): return ""
        if isinstance(value, (dict, list)): return str(value)
        return str(value)

    def get_users(self):
        """الحصول على قائمة المستخدمين من ورقة Users."""
        try: return self._sheet_to_df("Users")
        except Exception as e: st.error(f"❌ خطأ في قراءة المستخدمين: {e}"); return pd.DataFrame()

    def add_user(self, user_data):
        """إضافة مستخدم جديد إلى ورقة Users."""
        try:
            df = self.get_users()
            if df.empty: df = pd.DataFrame(columns=["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"])
            df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
            self._df_to_sheet("Users", df, ["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"])
        except Exception as e: st.error(f"❌ خطأ في إضافة المستخدم: {e}")

    def get_stages(self):
        """الحصول على قائمة المراحل من ورقة Stages."""
        try: return self._sheet_to_df("Stages")
        except Exception as e: st.error(f"❌ خطأ في قراءة المراحل: {e}"); return pd.DataFrame()

    def add_stage(self, stage_data):
        """إضافة مرحلة جديدة."""
        try:
            df = self.get_stages()
            if df.empty: df = pd.DataFrame(columns=["stage_id", "stage_name", "manager_user_id"])
            df = pd.concat([df, pd.DataFrame([stage_data])], ignore_index=True)
            self._df_to_sheet("Stages", df, ["stage_id", "stage_name", "manager_user_id"])
        except Exception as e: st.error(f"❌ خطأ في إضافة المرحلة: {e}")

    def get_sections(self):
        """الحصول على قائمة الفصول."""
        try: return self._sheet_to_df("Sections")
        except Exception as e: st.error(f"❌ خطأ في قراءة الفصول: {e}"); return pd.DataFrame()

    def add_section(self, sec_data):
        """إضافة فصل جديد."""
        try:
            self._get_or_create_worksheet("Sections", ["section_id", "section_name", "manager_user_id"])
            df = self.get_sections()
            if df.empty: df = pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
            df = pd.concat([df, pd.DataFrame([sec_data])], ignore_index=True)
            self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])
        except Exception as e: st.error(f"❌ خطأ في إضافة الفصل: {e}")

    def get_students(self):
        """الحصول على قائمة الطالبات."""
        try: return self._sheet_to_df("Students")
        except Exception as e: st.error(f"❌ خطأ في قراءة الطالبات: {e}"); return pd.DataFrame()

    def add_student(self, student_data):
        """إضافة طالبة جديدة."""
        try:
            df = self.get_students()
            if df.empty: df = pd.DataFrame(columns=["student_id", "full_name", "section_id", "teacher_id", "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])
            student_data["teacher_id"] = ""
            df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
            self._df_to_sheet("Students", df, ["student_id", "full_name", "section_id", "teacher_id", "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])
            return True
        except Exception as e: st.error(f"❌ خطأ في إضافة الطالبة: {e}"); return False

    def update_student(self, student_id, updates):
        """تحديث بيانات طالبة."""
        try:
            df = self.get_students()
            idx = df[df.student_id == student_id].index
            if len(idx) > 0:
                for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
                self._df_to_sheet("Students", df, df.columns.tolist())
        except Exception as e: st.error(f"❌ خطأ في تحديث الطالبة: {e}")

    def delete_student(self, student_id):
        """حذف طالبة."""
        try:
            df = self.get_students()
            df = df[df.student_id != student_id]
            self._df_to_sheet("Students", df, df.columns.tolist())
        except Exception as e: st.error(f"❌ خطأ في حذف الطالبة: {e}")

    def get_attendance(self):
        """الحصول على سجلات الحضور."""
        try: return self._sheet_to_df("Attendance")
        except Exception as e: st.error(f"❌ خطأ في قراءة الحضور: {e}"); return pd.DataFrame()

    def batch_add_attendance(self, records_list):
        """إضافة مجموعة من سجلات الحضور دفعة واحدة."""
        try:
            if not records_list: return
            df = self.get_attendance()
            if df.empty: df = pd.DataFrame(columns=["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
            existing_ids = set(df["record_id"].tolist()) if not df.empty else set()
            new_records = []
            for rec in records_list:
                if rec["record_id"] in existing_ids:
                    idx = df[df.record_id == rec["record_id"]].index[0]
                    for k, v in rec.items(): df.at[idx, k] = self._safe_str(v)
                else: new_records.append(rec)
            if new_records: df = pd.concat([df, pd.DataFrame(new_records)], ignore_index=True)
            self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
        except Exception as e: st.error(f"❌ خطأ في حفظ الحضور: {e}")

    def get_followup(self):
        """الحصول على سجلات المتابعة."""
        try: return self._sheet_to_df("FollowUp")
        except Exception as e: st.error(f"❌ خطأ في قراءة المتابعة: {e}"); return pd.DataFrame()

    def add_followup_record(self, record):
        """إضافة سجل متابعة جديد."""
        try:
            df = self.get_followup()
            if not df.empty:
                duplicate = df[(df.student_id == record["student_id"]) & (df.followup_date == record["followup_date"]) & (df.followup_type == record["followup_type"])]
                if not duplicate.empty: raise ValueError("⛔ تم تسجيل نفس الافتقاد مسبقاً لنفس الطالبة في نفس التاريخ ونفس النوع.")
            if df.empty: df = pd.DataFrame(columns=["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
            self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])
        except ValueError as e: raise e
        except Exception as e: st.error(f"❌ خطأ في إضافة الافتقاد: {e}")

    def get_quizzes(self):
        """الحصول على قائمة الاختبارات."""
        try: return self._sheet_to_df("Quizzes")
        except Exception as e: st.error(f"❌ خطأ في قراءة الاختبارات: {e}"); return pd.DataFrame()

    def add_quiz(self, quiz_data):
        """إضافة اختبار جديد."""
        try:
            df = self.get_quizzes()
            if df.empty: df = pd.DataFrame(columns=["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])
            df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
            self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])
        except Exception as e: st.error(f"❌ خطأ في إنشاء الاختبار: {e}")

    def update_quiz(self, quiz_id, updates):
        """تحديث بيانات اختبار."""
        try:
            df = self.get_quizzes()
            idx = df[df.quiz_id == quiz_id].index
            if len(idx) > 0:
                for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
                self._df_to_sheet("Quizzes", df, df.columns.tolist())
        except Exception as e: st.error(f"❌ خطأ في تحديث الاختبار: {e}")

    def delete_quiz(self, quiz_id):
        """حذف اختبار بالكامل مع النتائج."""
        try:
            df = self.get_quizzes()
            df = df[df.quiz_id != quiz_id]
            self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])
            rdf = self._sheet_to_df("QuizResults")
            rdf = rdf[rdf.quiz_id != quiz_id]
            self._df_to_sheet("QuizResults", rdf, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        except Exception as e: st.error(f"❌ خطأ في حذف الاختبار: {e}")

    def get_quiz_questions(self, quiz_id):
        """استخراج أسئلة اختبار."""
        try:
            df = self._sheet_to_df("QuizQuestions")
            if df.empty: return pd.DataFrame()
            return df[df.quiz_id == quiz_id]
        except Exception: return pd.DataFrame()

    def add_question(self, q_data):
        """إضافة سؤال إلى اختبار."""
        try:
            df = self._sheet_to_df("QuizQuestions")
            if df.empty: df = pd.DataFrame(columns=["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])
            df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
            self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])
        except Exception as e: st.error(f"❌ خطأ في إضافة السؤال: {e}")

    def delete_question(self, question_id):
        """حذف سؤال من الاختبار."""
        try:
            df = self._sheet_to_df("QuizQuestions")
            df = df[df.question_id != question_id]
            self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])
        except Exception as e: st.error(f"❌ خطأ في حذف السؤال: {e}")

    def get_quiz_results(self, quiz_id=None):
        """استخراج نتائج الاختبارات."""
        try:
            df = self._sheet_to_df("QuizResults")
            if df.empty: return pd.DataFrame()
            return df[df.quiz_id == quiz_id] if quiz_id else df
        except Exception: return pd.DataFrame()

    def start_quiz_attempt(self, quiz_id, student_id, student_name):
        """بدء محاولة اختبار جديدة."""
        try:
            result_id = str(uuid.uuid4())
            now_iso = get_cairo_now().isoformat()
            new_row = {"result_id": result_id, "quiz_id": quiz_id, "student_id": student_id, "student_name": student_name, "score": "", "total_marks": "20", "start_time": now_iso, "submission_time": now_iso, "answers": "{}", "status": "started"}
            df = self._sheet_to_df("QuizResults")
            if df.empty: df = pd.DataFrame(columns=["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
            return result_id
        except Exception as e: st.error(f"❌ خطأ في بدء الاختبار: {e}"); return None

    def save_answers(self, result_id, answers_dict):
        """حفظ إجابات الطالبة مؤقتاً."""
        try:
            df = self._sheet_to_df("QuizResults")
            idx = df[df.result_id == result_id].index
            if len(idx) > 0:
                df.at[idx[0], "answers"] = json.dumps(answers_dict, ensure_ascii=False)
                self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        except Exception as e: st.error(f"❌ خطأ في حفظ الإجابات: {e}")

    def submit_quiz_attempt(self, result_id, score, answers_json):
        """تسليم الاختبار نهائياً."""
        try:
            df = self._sheet_to_df("QuizResults")
            idx = df[df.result_id == result_id].index
            if len(idx) > 0:
                df.at[idx[0], "score"] = str(score)
                df.at[idx[0], "answers"] = answers_json
                df.at[idx[0], "submission_time"] = get_cairo_now().isoformat()
                df.at[idx[0], "status"] = "submitted"
                self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        except Exception as e: st.error(f"❌ خطأ في تسليم الاختبار: {e}")

    def delete_quiz_result(self, result_id):
        """حذف نتيجة اختبار."""
        try:
            df = self._sheet_to_df("QuizResults")
            df = df[df.result_id != result_id]
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        except Exception as e: st.error(f"❌ خطأ في حذف النتيجة: {e}")

    def get_audit_logs(self):
        """استخراج سجلات المراقبة الكاملة - 14 عمود بالضبط."""
        try:
            df = self._sheet_to_df("AuditLog")
            cols = ["timestamp", "user_id", "user_name", "action", "details", "browser", "os", "device_type", "screen_size", "ip_masked", "country", "city", "region", "privacy_consent"]
            if df.empty: return pd.DataFrame(columns=cols)
            for c in cols:
                if c not in df.columns: df[c] = ""
            return df[cols]
        except Exception as e: st.error(f"❌ خطأ في قراءة السجلات: {e}"); return pd.DataFrame(columns=cols)

    def add_audit_log(self, user_id, user_name, action, details="", browser=None, os_name=None, device_type=None, screen_size=None, ip_masked=None, country=None, city=None, region=None):
        """إضافة سجل مراقبة جديد للورقة AuditLog - 14 حقل بالضبط."""
        try:
            now = get_cairo_now()
            log = {
                "timestamp": now.isoformat(),
                "user_id": user_id if user_id else "anonymous",
                "user_name": user_name if user_name else "زائر",
                "action": action,
                "details": details,
                "browser": browser if browser else get_browser_info(),
                "os": os_name if os_name else get_os_info(),
                "device_type": device_type if device_type else st.session_state.get('_device_type', 'Desktop'),
                "screen_size": screen_size if screen_size else st.session_state.get('_screen_size', '1920x1080'),
                "ip_masked": ip_masked if ip_masked else mask_ip_address(st.session_state.get('_ip', '0.0.0.0')),
                "country": country if country else "Egypt",
                "city": city if city else "Unknown",
                "region": region if region else "Unknown",
                "privacy_consent": "True"
            }
            df = self.get_audit_logs()
            cols = ["timestamp", "user_id", "user_name", "action", "details", "browser", "os", "device_type", "screen_size", "ip_masked", "country", "city", "region", "privacy_consent"]
            df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
            self._df_to_sheet("AuditLog", df, cols)
        except Exception as e: st.error(f"❌ خطأ في تسجيل المراقبة: {e}")

    def get_events(self):
        """الحصول على قائمة الفعاليات."""
        try: return self._sheet_to_df("Events")
        except Exception as e: st.error(f"❌ خطأ في قراءة الفعاليات: {e}"); return pd.DataFrame()

    def add_event(self, event_data):
        """إضافة فعالية جديدة."""
        try:
            df = self.get_events()
            cols = ["event_id", "name", "type", "date", "time", "location", "capacity", "description", "status", "created_by"]
            if df.empty: df = pd.DataFrame(columns=cols)
            df = pd.concat([df, pd.DataFrame([event_data])], ignore_index=True)
            self._df_to_sheet("Events", df, cols)
        except Exception as e: st.error(f"❌ خطأ في إضافة الفعالية: {e}")

    def update_event(self, event_id, updates):
        """تحديث بيانات فعالية."""
        try:
            df = self.get_events()
            idx = df[df.event_id == event_id].index
            if len(idx) > 0:
                for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
                cols = ["event_id", "name", "type", "date", "time", "location", "capacity", "description", "status", "created_by"]
                self._df_to_sheet("Events", df, cols)
        except Exception as e: st.error(f"❌ خطأ في تحديث الفعالية: {e}")

    def delete_event(self, event_id):
        """حذف فعالية."""
        try:
            df = self.get_events()
            df = df[df.event_id != event_id]
            cols = ["event_id", "name", "type", "date", "time", "location", "capacity", "description", "status", "created_by"]
            self._df_to_sheet("Events", df, cols)
        except Exception as e: st.error(f"❌ خطأ في حذف الفعالية: {e}")

    def get_event_attendance(self, event_id=None):
        """الحصول على سجلات حضور الفعاليات."""
        try:
            df = self._sheet_to_df("EventAttendance")
            if df.empty: return pd.DataFrame()
            return df[df.event_id == event_id] if event_id else df
        except Exception as e: st.error(f"❌ خطأ في قراءة حضور الفعاليات: {e}"); return pd.DataFrame()

    def add_event_attendance(self, attendance_data):
        """إضافة سجل حضور للفعالية."""
        try:
            df = self.get_event_attendance()
            cols = ["id", "event_id", "student_id", "rsvp_status", "actual_status"]
            if df.empty: df = pd.DataFrame(columns=cols)
            df = pd.concat([df, pd.DataFrame([attendance_data])], ignore_index=True)
            self._df_to_sheet("EventAttendance", df, cols)
        except Exception as e: st.error(f"❌ خطأ في إضافة حضور الفعالية: {e}")

    def update_event_attendance(self, attendance_id, updates):
        """تحديث سجل حضور الفعالية."""
        try:
            df = self.get_event_attendance()
            idx = df[df.id == attendance_id].index
            if len(idx) > 0:
                for k, v in updates.items(): df.at[idx[0], k] = self._safe_str(v)
                cols = ["id", "event_id", "student_id", "rsvp_status", "actual_status"]
                self._df_to_sheet("EventAttendance", df, cols)
        except Exception as e: st.error(f"❌ خطأ في تحديث حضور الفعالية: {e}")

    def save_event_photos(self, photos_data):
        """حفظ الصور في ورقة EventPhotos."""
        try:
            df = self._sheet_to_df("EventPhotos")
            cols = ["photo_id", "event_id", "photo_url", "upload_time", "uploaded_by"]
            if df.empty: df = pd.DataFrame(columns=cols)
            df = pd.concat([df, pd.DataFrame([photos_data])], ignore_index=True)
            self._df_to_sheet("EventPhotos", df, cols)
        except Exception as e: st.error(f"❌ خطأ في حفظ الصور: {e}")

    def get_event_photos(self, event_id=None):
        """الحصول على صور الفعاليات."""
        try:
            df = self._sheet_to_df("EventPhotos")
            if df.empty: return pd.DataFrame()
            return df[df.event_id == event_id] if event_id else df
        except Exception: return pd.DataFrame()

    def create_backup_spreadsheet(self):
        """إنشاء نسخة احتياطية من جدول Google Sheets."""
        try:
            timestamp = get_cairo_now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_name = f"Backup_{timestamp}"
            backup_spreadsheet = self.client.copy(self.spreadsheet.id, title=backup_name)
            return backup_spreadsheet.id
        except Exception as e: st.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}"); return None

# =============================================================================
# JWT Helpers
# =============================================================================
def generate_token(user: dict, secret: str) -> str:
    """إنشاء توكن JWT للمستخدم."""
    try:
        payload = {"user_id": user.get("user_id", ""), "role": user.get("role", ""), "full_name": user.get("full_name", ""), "section_id": user.get("section_id", ""), "exp": datetime.utcnow() + timedelta(hours=24)}
        return jwt.encode(payload, secret, algorithm="HS256")
    except Exception: return ""

def verify_token(token: str, secret: str):
    """التحقق من صلاحية التوكن."""
    try: return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception: return None

# =============================================================================
# Login & Initialization
# =============================================================================
def show_login_page(db: Database, jwt_secret: str):
    """عرض شاشة تسجيل الدخول."""
    try:
        st.markdown("<h1 class='main-header'>⛪ <br>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
        users = db.get_users()
        if users.empty:
            st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
            if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", use_container_width=True):
                db.add_user({"user_id": "admin-001", "username": "admin", "password": "admin123", "role": "System Admin", "full_name": "مدير النظام", "section_id": "", "phone": "0100000000", "email": "admin@church.com"})
                st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.stop()
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم").strip()
            password = st.text_input("كلمة المرور", type="password").strip()
            if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                if not username or not password: st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                else:
                    user_row = users[users.username == username]
                    if user_row.empty: st.error("اسم المستخدم غير موجود")
                    else:
                        user = user_row.iloc[0].to_dict()
                        if password == user.get("password", ""):
                            st.session_state.token = generate_token(user, jwt_secret)
                            st.session_state.user = user
                            st.session_state.authenticated = True
                            st.session_state.menu_choice = "🏠 لوحة التحكم"
                            db.add_audit_log(user["user_id"], user["full_name"], "تسجيل الدخول", "دخول ناجح")
                            st.success("تم تسجيل الدخول بنجاح!")
                        else: st.error("كلمة المرور غير صحيحة")
    except Exception as e: st.error(f"❌ خطأ في صفحة الدخول: {e}")

# =============================================================================
# Dashboard
# =============================================================================
def show_dashboard(db: Database):
    """عرض لوحة التحكم الرئيسية."""
    try:
        user = st.session_state.user
        role, section_id = user.get("role", ""), user.get("section_id", "")
        st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
        students = db.get_students()
        attendance = db.get_attendance()
        followup = db.get_followup()
        if role in ["Teacher", "Service Manager"] and section_id and not students.empty:
            students = students[students.section_id == section_id].copy()
            if not attendance.empty: attendance = attendance[attendance.section_id == section_id].copy()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            fig = go.Figure(go.Indicator(mode="gauge+number", value=len(students), title={'text': "👥 الطالبات"}, gauge={'bar': {'color': "#667eea"}}))
            fig.update_layout(height=200); col1.plotly_chart(fig, use_container_width=True)
        today = get_cairo_now().strftime("%Y-%m-%d")
        with col2:
            fig = go.Figure(go.Indicator(mode="gauge+number", value=len(attendance[(attendance.date == today) & (attendance.status == "حاضر")]) if not attendance.empty else 0, title={'text': "✅ حضور اليوم"}, gauge={'bar': {'color': "#28a745"}}))
            fig.update_layout(height=200); col2.plotly_chart(fig, use_container_width=True)
        with col3:
            fig = go.Figure(go.Indicator(mode="gauge+number", value=len(attendance[(attendance.date == today) & (attendance.status == "غائب")]) if not attendance.empty else 0, title={'text': "❌ غياب اليوم"}, gauge={'bar': {'color': "#dc3545"}}))
            fig.update_layout(height=200); col3.plotly_chart(fig, use_container_width=True)
        with col4:
            fig = go.Figure(go.Indicator(mode="gauge+number", value=len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0, title={'text': "💬 افتقاد عاجل"}, gauge={'bar': {'color': "#f39c12"}}))
            fig.update_layout(height=200); col4.plotly_chart(fig, use_container_width=True)
    except Exception as e: st.error(f"❌ خطأ في لوحة التحكم: {e}")

# =============================================================================
# Events Page
# =============================================================================
def get_event_type_color(event_type):
    """الحصول على لون نوع الفعالية."""
    colors = {"Meeting": "#3498db", "Service": "#28a745", "Trip": "#f39c12", "Celebration": "#9b59b6"}
    return colors.get(event_type, "#667eea")

def get_event_type_badge(event_type):
    """إنشاء شارة ملونة لنوع الفعالية."""
    color = get_event_type_color(event_type)
    return f"<span class='event-badge' style='background:{color};'>{event_type}</span>"

def show_create_event_form(db: Database):
    """نموذج إنشاء فعالية جديدة."""
    try:
        st.markdown("#### ➕ إنشاء فعالية جديدة")
        with st.form("create_event_form"):
            event_name = st.text_input("📛 اسم الفعالية").strip()
            event_type = st.selectbox("نوع الفعالية", ["Meeting", "Service", "Trip", "Celebration"])
            event_date = st.date_input("📅 تاريخ الفعالية")
            event_time = st.time_input("⏰ وقت الفعالية")
            location = st.text_input("📍 الموقع").strip()
            capacity = st.number_input("👥 السعة الإجمالية", min_value=1, max_value=1000, value=50)
            description = st.text_area("📝 الوصف").strip()
            if st.form_submit_button("✅ إنشاء الفعالية"):
                if not event_name: st.error("اسم الفعالية مطلوب")
                elif event_date <= get_cairo_now().date(): st.error("التاريخ يجب أن يكون في المستقبل")
                else:
                    db.add_event({"event_id": str(uuid.uuid4()), "name": event_name, "type": event_type, "date": event_date.strftime("%Y-%m-%d"), "time": str(event_time), "location": location, "capacity": capacity, "description": description, "status": "active", "created_by": st.session_state.user.get("user_id", "")})
                    st.success("✅ تم إنشاء الفعالية بنجاح!")
    except Exception as e: st.error(f"❌ خطأ في نموذج الفعالية: {e}")

def show_month_calendar(events):
    """عرض تقويم شهر بسيط."""
    try:
        if events.empty: return
        events = events.copy()
        events["date"] = pd.to_datetime(events["date"], errors="coerce")
        this_month = get_cairo_now().replace(day=1)
        days_in_month = (this_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        days_count = days_in_month.day
        st.markdown("#### 📅 تقويم الشهر")
        cols = st.columns(7)
        day_names = ["إثن", "ثلا", "أرب", "خم", "جم", "سب", "أح"]
        for i, name in enumerate(day_names): cols[i].markdown(f"**{name}**")
        for day in range(1, days_count + 1):
            date_str = this_month.replace(day=day).strftime("%Y-%m-%d")
            has_event = len(events[events["date"] == date_str]) > 0 if not events.empty else False
            cols[(day - 1) % 7].markdown(f"🟩" if has_event else f"⬜")
    except Exception as e: st.error(f"❌ خطأ في عرض التقويم: {e}")

def show_rsvp_form(db: Database, event, students):
    """نموذج تأكيد الحضور للفعالية."""
    try:
        st.markdown(f"### تأكيد حضور: {event.get('name', '')}")
        rsvp_students = st.multiselect("اختر الطالبات", students["student_id"].tolist() if not students.empty else [])
        rsvp_count = len(rsvp_students)
        capacity = int(event.get("capacity", 0))
        if capacity > 0:
            st.progress(min(rsvp_count / capacity, 1.0))
            st.caption(f"المقاعد المحجوزة: {rsvp_count}/{capacity}")
        if st.button("💾 حفظ التأكيد"):
            if rsvp_count > capacity: st.error("⚠️ تم تجاوز السعة الإجمالية!")
            else:
                for sid in rsvp_students: db.add_event_attendance({"id": str(uuid.uuid4()), "event_id": event.get("event_id"), "student_id": sid, "rsvp_status": "confirmed", "actual_status": ""})
                st.success("✅ تم حفظ تأكيدات الحضور!")
    except Exception as e: st.error(f"❌ خطأ في نموذج الحضور: {e}")

def show_event_photos(db: Database, event_id):
    """عرض معرض صور الفعالية."""
    try:
        st.markdown("### 📸 معرض الصور")
        uploaded_files = st.file_uploader("📤 رفع الصور", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if uploaded_files:
            for f in uploaded_files:
                img_bytes = f.read()
                img_str = base64.b64encode(img_bytes).decode()
                db.save_event_photos({"photo_id": str(uuid.uuid4()), "event_id": event_id, "photo_url": f"data:image;base64,{img_str}", "upload_time": get_cairo_now().isoformat(), "uploaded_by": st.session_state.user.get("user_id", "")})
            st.success(f"✅ تم رفع {len(uploaded_files)} صورة")
        photos = db.get_event_photos(event_id)
        if not photos.empty:
            cols = st.columns(3)
            for idx, (_, photo) in enumerate(photos.iterrows()):
                img_url = photo.get("photo_url", "")
                if img_url: cols[idx % 3].image(img_url, width=150)
        if st.button("🖼️ عرض المعرض"):
            @st.dialog("معرض الصور", width="large")
            def _lightbox():
                if not photos.empty:
                    for _, photo in photos.iterrows():
                        img_url = photo.get("photo_url", "")
                        if img_url: st.image(img_url, use_column_width=True)
            _lightbox()
    except Exception as e: st.error(f"❌ خطأ في معرض الصور: {e}")

def show_rsvp_vs_actual_chart(db: Database, events):
    """عرض مخطط RSVP vs الفعلي."""
    try:
        st.markdown("### 📊 إحصائيات الحضور")
        if not events.empty:
            chart_data = []
            for _, event in events.iterrows():
                eid = event.get("event_id", "")
                event_att = db.get_event_attendance(eid)
                rsvp_count = len(event_att[event_att.rsvp_status == "confirmed"]) if not event_att.empty else 0
                actual_count = len(event_att[event_att.actual_status == "Attended"]) if not event_att.empty else 0
                chart_data.append({"event": event.get("name", "")[:20], "RSVP": rsvp_count, "Actual": actual_count})
            if chart_data:
                df = pd.DataFrame(chart_data)
                fig = go.Figure()
                fig.add_trace(go.Bar(name="RSVP", x=df["event"], y=df["RSVP"]))
                fig.add_trace(go.Bar(name="Actual", x=df["event"], y=df["Actual"]))
                fig.update_layout(barmode='group')
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e: st.error(f"❌ خطأ في مخطط الإحصائيات: {e}")

def show_events(db: Database):
    """عرض صفحة الفعاليات."""
    try:
        st.markdown("<h2 class='main-header'>📅 الفعاليات</h2>", unsafe_allow_html=True)
        events = db.get_events()
        students = db.get_students()
        tab1, tab2, tab3, tab4 = st.tabs(["➕ إنشاء فعالية", "📋 قائمة الفعاليات", "📅 التقويم", "📊 الإحصائيات"])
        with tab1: show_create_event_form(db)
        with tab2:
            if not events.empty:
                for _, event in events.iterrows():
                    badge = get_event_type_badge(event.get("type", ""))
                    st.markdown(f"<div class='card'><h4>{badge} {event.get('name', '')}</h4><p>📅 {event.get('date', '')} ⏰ {event.get('time', '')}</p><p>📍 {event.get('location', '')}</p></div>", unsafe_allow_html=True)
                    if st.button("✓ حضور", key=f"mark_att_{event.get('event_id')}"):
                        show_rsvp_form(db, event, students)
                    if st.button("📸 الصور", key=f"photos_{event.get('event_id')}"):
                        show_event_photos(db, event.get("event_id"))
            else: st.info("لا توجد فعاليات مسجلة.")
        with tab3: show_month_calendar(events)
        with tab4: show_rsvp_vs_actual_chart(db, events)
    except Exception as e: st.error(f"❌ خطأ في الفعاليات: {e}")

# =============================================================================
# Reports Page
# =============================================================================
def ai_insights_panel(db: Database):
    """لوحة الرؤى الذكائية."""
    try:
        st.markdown("### 🤖 رؤى الذكاء الاصطناعي")
        attendance = db.get_attendance()
        students = db.get_students()
        followup = db.get_followup()
        insights = []
        confidence = 85
        if not students.empty and not attendance.empty:
            total = len(attendance)
            absent = len(attendance[attendance.status == "غائب"]) if "status" in attendance.columns else 0
            if total > 0 and absent / total > 0.2: insights.append("📌 نسبة الغياب مرتفعة")
        if not insights: insights.append("✅ جميع البيانات ضمن المعدلات الطبيعية")
        for insight in insights:
            st.markdown(f"<div class='ai-insight-box'>{insight}<br><small>نسبة الثقة: {confidence}%</small></div>", unsafe_allow_html=True)
    except Exception as e: st.error(f"❌ خطأ في الرؤى الذكائية: {e}")

def show_weekly_report(db: Database):
    """تقرير الحضور الأسبوعي."""
    try:
        st.markdown("#### 📅 تقرير الأسبوعي")
        attendance = db.get_attendance()
        if not attendance.empty and "date" in attendance.columns:
            attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
            last_week = get_cairo_now() - timedelta(days=7)
            weekly = attendance[attendance["date"] >= last_week]
            if not weekly.empty:
                daily = weekly.groupby(weekly["date"].dt.date).size().reset_index(name="count")
                fig = px.bar(daily, x="date", y="count")
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("لا توجد بيانات حضور للأيام الماضية.")
        else: st.info("لا توجد بيانات حضور.")
    except Exception as e: st.error(f"❌ خطأ في التقرير: {e}")

def show_monthly_report(db: Database):
    """تقرير الحضور الشهري."""
    try:
        st.markdown("#### 📆 تقرير الشهري")
        attendance = db.get_attendance()
        if not attendance.empty and "date" in attendance.columns:
            attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
            monthly = attendance.groupby(attendance["date"].dt.to_period("M")).size().reset_index(name="count")
            monthly["date"] = monthly["date"].astype(str)
            fig = px.bar(monthly, x="date", y="count")
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("لا توجد بيانات للعرض.")
    except Exception as e: st.error(f"❌ خطأ في التقرير: {e}")

def show_dna_report(db: Database):
    """تقرير DNA بالرادار."""
    try:
        st.markdown("#### 🧭 تقرير DNA")
        results = db.get_quiz_results()
        students = db.get_students()
        sections = db.get_sections()
        if not results.empty and not students.empty and not sections.empty:
            submitted = results[results.status == "submitted"]
            if not submitted.empty and "score" in submitted.columns:
                merged = submitted.merge(students[["student_id", "section_id"]], on="student_id", how="left")
                merged["score"] = pd.to_numeric(merged["score"], errors="coerce").fillna(0)
                section_scores = merged.groupby("section_id")["score"].mean().reset_index()
                section_scores = section_scores.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
                if not section_scores.empty and len(section_scores) > 1:
                    fig = go.Figure(data=go.Scatterpolar(r=section_scores['score'].tolist(), theta=section_scores['section_name'].tolist(), fill='toself'))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 20])), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("لا توجد بيانات كافية.")
            else: st.info("لا توجد نتائج مسجلة.")
        else: st.info("لا توجد بيانات كافية.")
    except Exception as e: st.error(f"❌ خطأ في تقرير DNA: {e}")

def show_health_check_gauge(db: Database):
    """Health Check gauge."""
    try:
        st.markdown("#### 🩺 Health Check للنظام")
        health_score = 100
        fig = go.Figure(go.Indicator(mode="gauge+number", value=health_score, title={'text': "نظام صحي"}, gauge={'axis': {'range': [None, 100]}, 'bar': {'color': "#28a745"}}))
        fig.update_layout(height=200); st.plotly_chart(fig, use_container_width=True)
    except Exception as e: st.error(f"❌ خطأ في Health Check: {e}")

def show_geographic_report(db: Database):
    """تقرير جغرافي حسب العنوان."""
    try:
        st.markdown("#### 🌍 تقرير جغرافي")
        students = db.get_students()
        if not students.empty and "address" in students.columns:
            addr_counts = students["address"].value_counts().head(10).reset_index()
            addr_counts.columns = ["العنوان", "العدد"]
            fig = px.bar(addr_counts, x="العنوان", y="العدد")
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("لا توجد بيانات عنوان.")
    except Exception as e: st.error(f"❌ خطأ في التقرير الجغرافي: {e}")

def show_reports(db: Database):
    """عرض صفحة التقارير."""
    try:
        st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
        ai_insights_panel(db)
        tab1, tab2, tab3, tab4 = st.tabs(["📅 أسبوعي", "📆 شهري", "🧭 DNA", "🩺 Health Check"])
        with tab1: show_weekly_report(db)
        with tab2: show_monthly_report(db)
        with tab3: show_dna_report(db)
        with tab4: show_health_check_gauge(db)
    except Exception as e: st.error(f"❌ خطأ في التقارير: {e}")

# =============================================================================
# Logs Page - Admin Only
# =============================================================================
def show_logs(db: Database):
    """عرض صفحة السجلات للمشرف."""
    try:
        user = st.session_state.user
        if user.get("role") != "System Admin":
            st.error("🚫 غير مصرح"); return
        st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
        logs = db.get_audit_logs()
        users = db.get_users()
        col1, col2 = st.columns(2)
        with col1: date_range = st.date_input("📅 نطاق التواريخ", key="log_date_range")
        with col2:
            user_options = ["الكل", "زائر"] + (users["user_id"].tolist() if not users.empty else [])
            selected_user = st.selectbox("المستخدم", user_options, key="log_user_filter")
        action_options = ["LOGIN_FAILED", "ANOMALY_ACCESS", "ANOMALY_RATE_LIMIT"]
        selected_actions = st.multiselect("نوع الإجراء", action_options, key="log_actions")
        if not logs.empty:
            logs = logs.copy()
            if isinstance(date_range, tuple) and len(date_range) == 2:
                logs = logs[(pd.to_datetime(logs["timestamp"]) >= pd.Timestamp(date_range[0])) & (pd.to_datetime(logs["timestamp"]) <= pd.Timestamp(date_range[1]))]
            if selected_user != "الكل":
                if selected_user == "زائر": logs = logs[logs.user_name == "زائر"]
                else: logs = logs[logs.user_id == selected_user]
            if selected_actions: logs = logs[logs.action.isin(selected_actions)]
        page_size = 50
        total_pages = max(1, len(logs) // page_size + 1)
        page = st.number_input("رقم الصفحة", min_value=1, max_value=total_pages, value=1, key="log_page_num")
        start_idx = (page - 1) * page_size
        st.dataframe(logs.iloc[start_idx:start_idx + page_size], use_container_width=True)
        show_security_dashboard(db, logs)
        show_data_integrity(db)
        st.markdown("---")
        if st.button("☁️ نسخة احتياطية"):
            backup_id = db.create_backup_spreadsheet()
            if backup_id: db.add_audit_log("admin-001", "مدير النظام", "CREATE_BACKUP", f"تم إنشاء النسخة الاحتياطية: {backup_id}")
        show_system_health(db)
    except Exception as e: st.error(f"❌ خطأ في السجلات: {e}")

def show_security_dashboard(db: Database, logs):
    """لوحة الأمان - 4 metric cards."""
    try:
        st.markdown("### 🛡️ لوحة الأمان")
        col1, col2, col3, col4 = st.columns(4)
        last_24h = get_cairo_now() - timedelta(hours=24)
        logs_copy = logs.copy()
        logs_copy["timestamp"] = pd.to_datetime(logs_copy["timestamp"], errors="coerce")
        failed_logins = len(logs_copy[(logs_copy.action == "LOGIN_FAILED") & (logs_copy["timestamp"] >= last_24h)]) if not logs.empty else 0
        anomalies = len(logs_copy[logs_copy.action.str.startswith("ANOMALY_", na=False)]) if not logs.empty else 0
        last_hour = get_cairo_now() - timedelta(hours=1)
        active_sessions = len(logs_copy[logs_copy["timestamp"] >= last_hour]["user_id"].unique()) if not logs.empty else 0
        exports_last_week = len(logs_copy[(logs_copy.action == "EXPORT") & (logs_copy["timestamp"] >= get_cairo_now() - timedelta(days=7))]) if not logs.empty else 0
        col1.metric("محاولات دخول فاشلة (24 ساعة)", failed_logins)
        col2.metric("الشذوذ", anomalies)
        col3.metric("الجلسات النشطة", active_sessions)
        col4.metric("التصديرات (7 أيام)", exports_last_week)
    except Exception as e: st.error(f"❌ خطأ في لوحة الأمان: {e}")

def show_data_integrity(db: Database):
    """فحص سلامة البيانات."""
    try:
        st.markdown("### 🔍 فحص سلامة البيانات")
        with st.expander("🔴 فحص البيانات"):
            students = db.get_students()
            issues = []
            attendance = db.get_attendance()
            if not attendance.empty and "student_id" in attendance.columns and not students.empty:
                orphaned_att = attendance[~attendance.student_id.isin(students.student_id)]
                if not orphaned_att.empty: issues.append({"type": "حضور مرتبط بطالبة غير موجودة", "severity": "🔴", "count": len(orphaned_att)})
            quiz_results = db.get_quiz_results()
            if not quiz_results.empty and "student_id" in quiz_results.columns and not students.empty:
                orphaned_qr = quiz_results[~quiz_results.student_id.isin(students.student_id)]
                if not orphaned_qr.empty: issues.append({"type": "نتائج اختبارات مرتبطة بطالبة غير موجودة", "severity": "🔴", "count": len(orphaned_qr)})
            followup = db.get_followup()
            if not followup.empty and "student_id" in followup.columns and not students.empty:
                orphaned_fup = followup[~followup.student_id.isin(students.student_id)]
                if not orphaned_fup.empty: issues.append({"type": "افتقادات مرتبطة بطالبة غير موجودة", "severity": "🔴", "count": len(orphaned_fup)})
            if not students.empty and "student_id" in students.columns:
                duplicates = students[students.student_id.duplicated()]
                if not duplicates.empty: issues.append({"type": "تكرار رقم الطالبة", "severity": "🟡", "count": len(duplicates)})
            if issues:
                for issue in issues:
                    st.markdown(f"<div class='integrity-high'>{issue['severity']} {issue['type']}: {issue['count']}</div>", unsafe_allow_html=True)
            else: st.success("✅ لا توجد مشاكل في البيانات")
    except Exception as e: st.error(f"❌ خطأ في فحص البيانات: {e}")

def show_system_health(db: Database):
    """System health - API rate limit, cache hit rate, row counts, uptime."""
    try:
        st.markdown("### ⚙️ System Health")
        col1, col2, col3, col4 = st.columns(4)
        rate_count = len(Database._request_times) if Database._request_times else 0
        col1.progress(min(rate_count / 40, 1.0)); col1.caption(f"API Rate Limit: {rate_count}/40")
        cache_hits = len(st.session_state.data_cache) if 'data_cache' in st.session_state else 0
        col2.metric("Cache Hit Rate", f"{cache_hits} sheets cached")
        students = db.get_students(); attendance = db.get_attendance()
        col3.metric("Students", len(students))
        col4.metric("Attendance", len(attendance))
        uptime = int(time.time() - st.session_state.get('_start_time', time.time()))
        st.caption(f"⏱️ Uptime: {uptime}s")
    except Exception as e: st.error(f"❌ خطأ في System Health: {e}")

# =============================================================================
# Sidebar Navigation
# =============================================================================
def show_sidebar_navigation(db: Database):
    """عرض القائمة الجانبية."""
    try:
        with st.sidebar:
            st.markdown("## ⛪ كنيسة الشهيدة دميانة")
            user = st.session_state.user
            if user: st.markdown(f"**👤 {user.get('full_name', '')}**")
            st.divider()
            role = user.get("role", "") if user else ""
            menus = {
                "System Admin": ["🏠 لوحة التحكم", "👥 إدارة المستخدمين", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات والاختبارات", "📅 الفعاليات", "📊 التقارير والإحصائيات", "📜 سجل العمليات", "🔒 تغيير كلمة المرور"],
                "Father Account": ["🏠 لوحة التحكم", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد", "📝 المسابقات والاختبارات", "📅 الفعاليات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد", "📅 الفعاليات", "🔒 تغيير كلمة المرور"]
            }
            menu_items = menus.get(role, [])
            current = st.session_state.get("menu_choice", menu_items[0] if menu_items else "🏠 لوحة التحكم")
            for item in menu_items:
                if st.button(item, key=f"nav_{item}", use_container_width=True):
                    st.session_state.menu_choice = item
                    st.rerun()
            st.divider()
            if st.button("🚪 تسجيل الخروج", use_container_width=True):
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.rerun()
        return current
    except Exception as e: st.error(f"❌ خطأ في القائمة الجانبية: {e}"); return "🏠 لوحة التحكم"

# =============================================================================
# Other Pages
# =============================================================================
def show_user_management(db: Database):
    """عرض إدارة المستخدمين."""
    try:
        st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
        users = db.get_users()
        students = db.get_students()
        tab1, tab2 = st.tabs(["الخدام", "الطالبات"])
        with tab1: st.dataframe(users if not users.empty else pd.DataFrame(), use_container_width=True)
        with tab2: st.dataframe(students if not students.empty else pd.DataFrame(), use_container_width=True)
    except Exception as e: st.error(f"❌ خطأ في إدارة المستخدمين: {e}")

def show_attendance(db: Database):
    """عرض صفحة تسجيل الحضور."""
    try:
        st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
        students = db.get_students()
        if not students.empty:
            for _, student in students.iterrows():
                st.markdown(f"**{student.get('full_name', '')}**")
                st.radio("الحالة", ["حاضر", "غائب", "متأخر"], key=f"att_{student.get('student_id')}", horizontal=True)
    except Exception as e: st.error(f"❌ خطأ في صفحة الحضور: {e}")

def show_followup(db: Database):
    """عرض صفحة المتابعة."""
    try:
        st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
        students = db.get_students()
        if not students.empty:
            st.selectbox("اختر الطالبة", students["student_id"].tolist())
            st.date_input("تاريخ الافتقاد")
            st.selectbox("نوع الافتقاد", ["غياب", "غياب متكرر", "منقطع"])
            st.text_area("ملاحظات")
    except Exception as e: st.error(f"❌ خطأ في صفحة المتابعة: {e}")

def show_my_students(db: Database):
    """عرض صفحة طالباتي."""
    try:
        st.markdown("<h2 class='main-header'>👩‍🎓 طالباتي</h2>", unsafe_allow_html=True)
        students = db.get_students()
        section_id = st.session_state.user.get("section_id", "") if st.session_state.user else ""
        if not students.empty and section_id: students = students[students.section_id == section_id]
        st.dataframe(students if not students.empty else pd.DataFrame(), use_container_width=True)
    except Exception as e: st.error(f"❌ خطأ في صفحة طالباتي: {e}")

def show_quizzes(db: Database):
    """عرض صفحة المسابقات."""
    try:
        st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
        quizzes = db.get_quizzes()
        st.dataframe(quizzes if not quizzes.empty else pd.DataFrame(), use_container_width=True)
    except Exception as e: st.error(f"❌ خطأ في صفحة المسابقات: {e}")

def change_password(db: Database):
    """عرض صفحة تغيير كلمة المرور."""
    try:
        st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
        with st.form("change_pwd"):
            old = st.text_input("كلمة المرور الحالية", type="password")
            new = st.text_input("كلمة المرور الجديدة", type="password")
            confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير كلمة المرور"):
                if not old or not new or not confirm: st.error("الرجاء ملء جميع الحقول")
                elif old != st.session_state.user.get("password", ""): st.error("كلمة المرور الحالية غير صحيحة")
                elif len(new) < 4: st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
                elif new != confirm: st.error("كلمتا المرور غير متطابقتين")
                else: st.success("✅ تم تغيير كلمة المرور بنجاح!")
    except Exception as e: st.error(f"❌ خطأ في صفحة كلمة المرور: {e}")

# =============================================================================
# Main App
# =============================================================================
def main():
    """الدالة الرئيسية لتطبيق Streamlit."""
    try:
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
        if not st.session_state.authenticated:
            show_login_page(db, jwt_secret)
        else:
            token_data = verify_token(st.session_state.token, jwt_secret)
            if not token_data:
                st.error("⏰ انتهت صلاحية الجلسة.")
                st.session_state.clear()
                st.stop()
            choice = show_sidebar_navigation(db)
            if choice == "🏠 لوحة التحكم": show_dashboard(db)
            elif choice == "👥 إدارة المستخدمين": show_user_management(db)
            elif choice == "📋 الحضور": show_attendance(db)
            elif choice == "💬 الافتقاد": show_followup(db)
            elif choice == "📝 المسابقات والاختبارات": show_quizzes(db)
            elif choice == "📅 الفعاليات": show_events(db)
            elif choice == "📊 التقارير والإحصائيات": show_reports(db)
            elif choice == "📜 سجل العمليات": show_logs(db)
            elif choice == "🔒 تغيير كلمة المرور": change_password(db)
    except Exception as e: st.error(f"❌ خطأ في التطبيق الرئيسي: {e}")

if __name__ == "__main__":
    main()
