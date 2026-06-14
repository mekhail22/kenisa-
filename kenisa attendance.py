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

# =============================================================================
# الإعدادات العامة والثوابت
# =============================================================================
DEFAULT_JWT_SECRET = "StDemianaChurch2025!Secure#Key"
CACHE_TTL_SECONDS = 120
CAIRO_TZ = timezone(timedelta(hours=3), name='Africa/Cairo')

def get_cairo_now():
    return datetime.now(CAIRO_TZ)

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
# CSS محسّن مع تثبيت المظهر الفاتح لمتصفح Safari والمتصفحات الداكنة
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
        """قراءة البيانات من ورقة العمل ومعالجة تكرار رؤوس الأعمدة تلقائياً"""
        cached = self.cache.get(sheet_name)
        if cached is not None:
            return cached.copy()
        try:
            ws = self._get_or_create_worksheet(sheet_name, [])
            values = ws.get_all_values()
            if not values or len(values) < 1:
                df = pd.DataFrame()
            else:
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
                if any(count > 0 for count in seen.values()):
                    st.warning(f"⚠️ تحتوي ورقة '{sheet_name}' على أعمدة مكررة وتم معالجتها تلقائياً. يُنصح بتصحيح الورقة.")

                data_rows = values[1:]
                df = pd.DataFrame(data_rows, columns=unique_headers)
                df.dropna(how='all', axis=1, inplace=True)
                df.dropna(how='all', inplace=True)
                df = df.astype(object)

            self.cache.set(sheet_name, df.copy())
            return df
        except Exception as e:
            st.error(f"❌ فشل قراءة {sheet_name}: {str(e)}")
            return pd.DataFrame()

    def _df_to_sheet(self, sheet_name, df, columns):
        """
        كتابة DataFrame إلى Google Sheet بشكل آمن يمنع فقدان البيانات.
        يتم الاحتفاظ بنسخة احتياطية قبل الكتابة، وفي حال فشل التحديث يتم استرجاع النسخة السابقة.
        """
        if not isinstance(df, pd.DataFrame):
            raise ValueError("df must be a DataFrame")
        if not isinstance(columns, list) or not columns:
            raise ValueError("columns must be a non-empty list")

        ws = self._get_or_create_worksheet(sheet_name, columns)

        # تجهيز البيانات المراد كتابتها
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        work_df = df[columns].copy()
        work_df.fillna("", inplace=True)
        work_df = work_df.astype(str)
        values = [columns] + work_df.values.tolist()
        num_rows = len(values)

        # --- نسخ احتياطي للبيانات الحالية ---
        backup_df = None
        try:
            backup_df = self.cache.get(sheet_name)
            if backup_df is None:
                backup_df = self._sheet_to_df(sheet_name)
        except Exception:
            pass

        # --- الكتابابة الفعلية مع استرجاع في حالة الفشل ---
        try:
            ws.resize(rows=num_rows, cols=len(columns))
            ws.update(values)
            self.cache.invalidate(sheet_name)
        except Exception as e:
            if backup_df is not None and not backup_df.empty:
                try:
                    st.warning("فشل حفظ البيانات، جاري استعادة النسخة السابقة...")
                    self._df_to_sheet(sheet_name, backup_df, columns)
                    self.cache.invalidate(sheet_name)
                    raise Exception(f"تم استرجاع البيانات السابقة بسبب خطأ: {str(e)}")
                except Exception as restore_error:
                    raise Exception(f"فشل حفظ البيانات وفشل استرجاع النسخة الاحتياطية: {str(e)}")
            else:
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
        if "user_id" not in df.columns:
            return
        idx = df[df.user_id == user_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Users", df, df.columns.tolist())

    def delete_user(self, user_id):
        df = self.get_users()
        if "user_id" not in df.columns:
            return
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
        if "section_id" not in df.columns:
            return
        idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id):
        df = self.get_sections()
        if "section_id" not in df.columns:
            return
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
        if "student_id" not in df.columns:
            return
        idx = df[df.student_id == student_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Students", df, df.columns.tolist())

    def delete_student(self, student_id):
        df = self.get_students()
        if "student_id" not in df.columns:
            return
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
        if df.empty or "date" not in df.columns or "section_id" not in df.columns:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    def delete_attendance_record(self, record_id):
        df = self.get_attendance()
        if "record_id" not in df.columns:
            return
        df = df[df.record_id != record_id]
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    # --- FollowUp ---
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record):
        """إضافة سجل افتقاد مع التحقق من عدم وجود تكرار (نفس الطالبة، التاريخ، النوع)"""
        df = self.get_followup()
        # تحقق من عدم وجود سجل مطابق مسبقاً
        if not df.empty and "student_id" in df.columns and "followup_date" in df.columns and "followup_type" in df.columns:
            duplicate = df[
                (df.student_id == record["student_id"]) &
                (df.followup_date == record["followup_date"]) &
                (df.followup_type == record["followup_type"])
            ]
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
        if "record_id" not in df.columns:
            return
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
        if "quiz_id" not in df.columns:
            return
        idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def delete_quiz_keep_results(self, quiz_id):
        df = self.get_quizzes()
        if "quiz_id" not in df.columns:
            return
        df = df[df.quiz_id != quiz_id]
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active"])
        qdf = self._sheet_to_df("QuizQuestions")
        if "quiz_id" not in qdf.columns:
            return
        qdf = qdf[qdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizQuestions", qdf, ["question_id", "quiz_id", "question_text", "question_type",
                                                 "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_quiz(self, quiz_id):
        self.delete_quiz_keep_results(quiz_id)
        rdf = self._sheet_to_df("QuizResults")
        if "quiz_id" not in rdf.columns:
            return
        rdf = rdf[rdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizResults", rdf, ["result_id", "quiz_id", "student_id", "student_name",
                                               "score", "total_marks", "submission_time", "answers", "status"])

    def get_quiz_questions(self, quiz_id):
        df = self._sheet_to_df("QuizQuestions")
        if df.empty or "quiz_id" not in df.columns:
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
        if "question_id" not in df.columns:
            return
        df = df[df.question_id != question_id]
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type",
                                                "option1", "option2", "option3", "option4", "correct_answer"])

    # --- Quiz Results ---
    def get_quiz_results(self, quiz_id=None):
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return pd.DataFrame()
        if quiz_id and "quiz_id" in df.columns:
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
            "submission_time": get_cairo_now().isoformat(),
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
        df = self._sheet_to_df("QuizResults")
        if df.empty or "result_id" not in df.columns or "answers" not in df.columns:
            return
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "answers"] = json.dumps(answers_dict, ensure_ascii=False)
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "submission_time", "answers", "status"])

    def submit_quiz_attempt(self, result_id, score, answers_json):
        df = self._sheet_to_df("QuizResults")
        if df.empty or "result_id" not in df.columns:
            return
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "score"] = str(score)
            df.at[idx[0], "answers"] = answers_json
            df.at[idx[0], "submission_time"] = get_cairo_now().isoformat()
            df.at[idx[0], "status"] = "submitted"
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "submission_time", "answers", "status"])

    def delete_quiz_result(self, result_id):
        df = self._sheet_to_df("QuizResults")
        if "result_id" not in df.columns:
            return
        df = df[df.result_id != result_id]
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "submission_time", "answers", "status"])

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
        self.cache.buffer_log(log)

    def delete_log(self, log_id):
        df = self.get_logs()
        if "log_id" not in df.columns:
            return
        df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

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
        "quiz_questions": None,
        "show_review": False,
        "data_errors": [],
        "data_validated": False
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

# =============================================================================
# Validation Function – فحص سلامة البيانات
# =============================================================================
def validate_data_integrity(db: Database):
    errors = []
    students = db.get_students()
    sections = db.get_sections()
    users = db.get_users()

    if not students.empty and not sections.empty:
        if "section_id" in students.columns and "section_id" in sections.columns:
            valid_sections = set(sections["section_id"].tolist())
            for _, row in students.iterrows():
                sid = row.get("section_id", "")
                if pd.isna(sid) or str(sid).strip() == "":
                    errors.append(f"الطالبة {row.get('full_name', '')} ليس لديها فصل (section_id فارغ).")
                elif str(sid).strip() not in valid_sections:
                    errors.append(f"الطالبة {row.get('full_name', '')} تنتمي لفصل غير موجود ({sid}).")
    elif not students.empty and sections.empty:
        errors.append("لا توجد فصول مسجلة، كل الطالبات بدون فصول.")

    if not users.empty and not sections.empty:
        if "section_id" in sections.columns and "role" in users.columns:
            valid_sections = set(sections["section_id"].tolist())
            for _, row in users.iterrows():
                if row.get("role") in ["Teacher", "Service Manager"]:
                    sid = row.get("section_id", "")
                    if sid and str(sid).strip() not in valid_sections:
                        errors.append(f"المستخدم {row.get('full_name', '')} (دور: {row.get('role', '')}) مرتبط بفصل غير موجود ({sid}).")
    return errors

def auto_fix_missing_sections(db: Database):
    students = db.get_students()
    sections = db.get_sections()
    if students.empty:
        return False
    if "section_id" not in students.columns or (not sections.empty and "section_id" not in sections.columns):
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
            username = st.text_input("اسم المستخدم").strip()
            password = st.text_input("كلمة المرور", type="password").strip()
            if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                if not username or not password:
                    st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                else:
                    with st.spinner("جاري التحقق..."):
                        users = db.get_users()
                        if "username" not in users.columns:
                            st.error("بيانات المستخدمين غير مكتملة")
                            return
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
                        if "quiz_code" not in quizzes.columns or "password" not in quizzes.columns:
                            st.error("بيانات الاختبارات غير متاحة حالياً")
                            return
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
                                    if "quiz_id" in quiz:
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

def show_student_quiz(db: Database):
    quiz = st.session_state.student_quiz
    if st.session_state.quiz_phase == "enter_name":
        st.title(f"📝 {quiz.get('title', '')}")
        st.markdown(f"**عدد الأسئلة:** {quiz.get('num_questions', '')} | **الدرجة الكلية:** 20 | **الوقت:** {quiz.get('time_limit_minutes', '')} دقيقة")
        st.markdown("---")
        students_df = db.get_students()
        if "status" not in students_df.columns:
            st.error("بيانات الطالبات غير متاحة")
            st.stop()
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
            if not sections_df.empty and "section_id" in sections_df.columns and "section_name" in sections_df.columns:
                sec_name = sections_df[sections_df.section_id == section_id]["section_name"].values
                section_name = sec_name[0] if len(sec_name) > 0 else "لم يتم تعيين فصل"
            else:
                section_name = "لم يتم تعيين فصل"
            st.info(f"أنتِ في فصل: **{section_name}**")
        st.markdown("---")
        st.info("إذا لم تجد اسمك في القائمة، يرجى التواصل مع مشرف الخدمة لإضافتك.")
        if selected_id is not None:
            existing = db.get_quiz_results(quiz.get("quiz_id"))
            if not existing.empty and "student_id" in existing.columns:
                student_attempts = existing[existing["student_id"] == selected_id]
                if not student_attempts.empty:
                    attempt = student_attempts.iloc[0]
                    if attempt.get("status") == "started":
                        answers_str = attempt.get("answers", "{}")
                        try:
                            saved_answers = json.loads(answers_str) if answers_str else {}
                        except:
                            saved_answers = {}
                        score = grade_attempt(db, quiz["quiz_id"], saved_answers)
                        db.submit_quiz_attempt(attempt["result_id"], score, json.dumps(saved_answers, ensure_ascii=False))
                        st.warning("تم تسليم محاولتك السابقة تلقائياً بناءً على ما قمت بحفظه.")
                        st.session_state.last_score = score
                        st.session_state.quiz_phase = "finished"
                        st.session_state.quiz_submitted = True
                        st.rerun()
                    else:
                        st.error("لقد قمت بتسليم هذا الاختبار بالفعل. لا يمكنك الدخول مرة أخرى.")
                        st.stop()
        if st.button("بدء الاختبار", use_container_width=True, type="primary", disabled=(selected_id is None), key="start_quiz_btn"):
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
            st.session_state.quiz_phase = "taking_quiz"
            st.rerun()
        return

    if st.session_state.quiz_phase == "taking_quiz":
        now = get_cairo_now()
        if now > st.session_state.quiz_end_time:
            st.warning("انتهى الوقت المخصص للامتحان. جاري تسليم إجاباتك تلقائياً...")
            score = grade_attempt(db, quiz["quiz_id"], st.session_state.quiz_answers)
            answers_json = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
            db.submit_quiz_attempt(st.session_state.current_attempt_id, score, answers_json)
            st.session_state.quiz_submitted = True
            st.session_state.last_score = score
            st.session_state.quiz_phase = "finished"
            st.rerun()

        if not st.session_state.get("quiz_questions"):
            questions_df = db.get_quiz_questions(quiz["quiz_id"])
            if questions_df.empty:
                st.warning("لا توجد أسئلة في هذا الاختبار بعد.")
                return
            st.session_state.quiz_questions = questions_df.to_dict('records')
        else:
            questions_df = pd.DataFrame(st.session_state.quiz_questions)

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

        if st.button("تسليم الاختبار", type="primary", use_container_width=True, key="submit_quiz_btn"):
            score = grade_attempt(db, quiz["quiz_id"], st.session_state.quiz_answers)
            answers_json = json.dumps(st.session_state.quiz_answers, ensure_ascii=False)
            db.submit_quiz_attempt(st.session_state.current_attempt_id, score, answers_json)
            st.session_state.quiz_submitted = True
            st.session_state.last_score = score
            st.session_state.quiz_phase = "finished"
            st.rerun()
        return

    if st.session_state.quiz_phase == "finished":
        if not st.session_state.get("show_review", False):
            st.success("تم تسليم الاختبار بنجاح!")
            score = st.session_state.last_score
            if score.is_integer():
                score_display = int(score)
            else:
                score_display = score
            st.info(f"نتيجتك: {score_display}/20")
            col_btn, _ = st.columns([2, 3])
            if col_btn.button("عرض الإجابات والأخطاء", use_container_width=True, key="show_review_btn"):
                st.session_state.show_review = True
                st.rerun()
            if st.button("إنهاء والعودة إلى الرئيسية", use_container_width=True, key="finish_no_review_btn"):
                for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                            "student_id", "quiz_start_time", "quiz_end_time", "quiz_answers",
                            "quiz_submitted", "last_score", "current_attempt_id", "last_saved_answers_str",
                            "quiz_questions", "show_review"]:
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
                    col1.write(f"إجابتك: {student_ans}")
                    col2.write(f"الإجابة الصحيحة: {correct}")
                    if is_correct:
                        st.success("✅ صحيح")
                    else:
                        st.error("❌ خطأ")
                    st.markdown("---")
                if st.button("إنهاء المراجعة والعودة إلى الرئيسية", use_container_width=True, key="finish_review_btn"):
                    for key in ["student_quiz", "student_quiz_started", "quiz_phase", "student_name",
                                "student_id", "quiz_start_time", "quiz_end_time", "quiz_answers",
                                "quiz_submitted", "last_score", "current_attempt_id", "last_saved_answers_str",
                                "quiz_questions", "show_review"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
        return

# =============================================================================
# Sidebar Navigation
# =============================================================================
def show_sidebar_navigation(db: Database):
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.user
        st.markdown(f"**👤 {user.get('full_name', '')}**")
        st.caption(f"الصلاحية: {user.get('role', '')}")
        st.divider()

        role = user.get("role", "")
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

# =============================================================================
# Dashboard
# =============================================================================
def show_dashboard(db: Database):
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
            if not submitted.empty and "student_id" in submitted.columns and "student_id" in students_all.columns and "section_id" in students_all.columns:
                merged = submitted.merge(students_all[["student_id", "section_id"]], on="student_id", how="left")
                merged["score"] = pd.to_numeric(merged["score"], errors="coerce").fillna(0)
                if "section_id" in merged.columns and "section_id" in sections_all.columns and "section_name" in sections_all.columns:
                    section_scores = merged.groupby("section_id")["score"].mean().reset_index()
                    section_scores = section_scores.merge(sections_all[["section_id", "section_name"]], on="section_id", how="left")
                    if not section_scores.empty:
                        top_section = section_scores.sort_values("score", ascending=False).iloc[0]
                        st.metric(f"أفضل فصل: {top_section.get('section_name', '')}", f"{top_section.get('score', 0):.1f} / 20 متوسط")
                        st.dataframe(section_scores.rename(columns={"section_name":"الفصل", "score":"متوسط الدرجات"}).set_index("الفصل"), use_container_width=True)

# =============================================================================
# إدارة المستخدمين
# =============================================================================
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    students = db.get_students()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول"])

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
            if not users.empty and "user_id" in users.columns:
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
            if not students.empty and "student_id" in students.columns:
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
                    except: birth_date_val = None
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

# =============================================================================
# Attendance
# =============================================================================
def show_attendance(db: Database):
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

# =============================================================================
# Follow-up (مع منع تكرار الافتقاد)
# =============================================================================
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

# =============================================================================
# My Students (مع منع تكرار الافتقاد)
# =============================================================================
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

# =============================================================================
# Class Competition Scores (Teacher Only)
# =============================================================================
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

    if not quizzes.empty and not class_results.empty and "quiz_id" in class_results.columns and "quiz_id" in quizzes.columns:
        class_results = class_results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
        class_results = class_results.rename(columns={"title": "اسم المسابقة"})
    else:
        class_results["اسم المسابقة"] = ""

    if not section_students.empty and not class_results.empty and "student_id" in class_results.columns:
        class_results = class_results.merge(section_students[["student_id", "full_name"]], on="student_id", how="left")
        class_results = class_results.rename(columns={"full_name": "اسم الطالبة"})
    else:
        class_results["اسم الطالبة"] = ""

    if not section_students.empty:
        sec_name = db.get_sections()
        if not sec_name.empty and "section_id" in sec_name.columns:
            my_sec = sec_name[sec_name.section_id == section_id]["section_name"]
            st.info(f"فصلك: **{my_sec.values[0] if len(my_sec)>0 else section_id}**")

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
                # هنا score أصبح رقمي بالفعل
                ranking = filtered_df.groupby("اسم الطالبة")["score"].sum().reset_index().sort_values("score", ascending=False)
                ranking.index = range(1, len(ranking) + 1)
                st.dataframe(ranking, use_container_width=True)
    else:
        st.info("لا توجد نتائج مطابقة للبحث.")

# =============================================================================
# Quizzes (مع تصحيح تجميع الدرجات)
# =============================================================================
def show_quizzes(db: Database):
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
                    if not questions.empty and "question_id" in questions.columns:
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

        if not students.empty and "student_id" in students.columns and "full_name" in students.columns:
            if "student_id" in results.columns:
                results = results.merge(students[["student_id", "full_name", "section_id"]], on="student_id", how="left")
                results.rename(columns={"full_name": "اسم الطالبة"}, inplace=True)
        if not sections_all.empty and "section_id" in sections_all.columns and "section_name" in sections_all.columns:
            if "section_id" in results.columns:
                results = results.merge(sections_all[["section_id", "section_name"]], on="section_id", how="left")
                results.rename(columns={"section_name": "الفصل"}, inplace=True)
        else:
            results["الفصل"] = ""

        if not quizzes.empty and "quiz_id" in quizzes.columns and "title" in quizzes.columns:
            if "quiz_id" in results.columns:
                results = results.merge(quizzes[["quiz_id", "title"]], on="quiz_id", how="left")
                results.rename(columns={"title": "المسابقة"}, inplace=True)

        # تحويل score إلى رقمي لتجنب دمج النصوص
        if "score" in results.columns:
            results["score"] = pd.to_numeric(results["score"], errors="coerce").fillna(0)

        if "quiz_id" in results.columns:
            quiz_ids = results["quiz_id"].unique().tolist()
            if quiz_ids and not quizzes.empty:
                quiz_titles = quizzes[quizzes["quiz_id"].isin(quiz_ids)][["quiz_id", "title"]].drop_duplicates()
                quiz_options = ["الكل"] + quiz_titles["quiz_id"].tolist()
                selected_quiz_filter = st.selectbox(
                    "اختر الاختبار لعرض نتائجه فقط",
                    quiz_options,
                    format_func=lambda x: "الكل" if x == "الكل" else quiz_titles[quiz_titles.quiz_id == x]["title"].values[0]
                )
                if selected_quiz_filter != "الكل":
                    results = results[results.quiz_id == selected_quiz_filter]

        if results.empty:
            st.info("لا توجد نتائج مطابقة للاختبار المحدد.")
        else:
            display_cols = ["اسم الطالبة", "الفصل", "المسابقة", "score", "total_marks", "submission_time"]
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
        if not monthly.empty and "student_id" in monthly.columns and "status" in monthly.columns:
            summary = monthly.groupby(["student_id", "status"]).size().reset_index(name="count")
            pivot = summary.pivot(index="student_id", columns="status", values="count").fillna(0).reset_index()
            if not students.empty and "student_id" in students.columns and "full_name" in students.columns:
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
        if not students.empty and "student_id" in students.columns and "full_name" in students.columns:
            absent_counts = absent_counts.merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(absent_counts[["full_name", "أيام الغياب"]], use_container_width=True)

# =============================================================================
# Logs & Change Password
# =============================================================================
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

def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
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
                st.success("✅ تم تغيير كلمة المرور بنجاح!")

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
                if st.session_state.user.get("role") == "System Admin":
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

    if st.session_state.authenticated:
        try:
            db.cache.flush_logs(db)
        except Exception:
            pass

if __name__ == "__main__":
    main()
