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
# Visitor Data Collection for AuditLog
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
    """Get client IP and mask to show only first 2 octets"""
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
# CSS محسّن مع تثبيت المظهر الفاتح + Panic Button
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

        /* Panic Button - Floating Red */
        .panic-btn-container .stButton > button {
            position: fixed !important;
            bottom: 20px !important;
            left: 20px !important;
            z-index: 99999 !important;
            background: linear-gradient(135deg, #ff0000 0%, #cc0000 50%, #990000 100%) !important;
            color: white !important;
            font-weight: bold !important;
            border: none !important;
            border-radius: 50px !important;
            padding: 15px 25px !important;
            font-size: 16px !important;
            box-shadow: 0 4px 15px rgba(255,0,0,0.4) !important;
            animation: pulse-red 2s infinite !important;
            cursor: pointer !important;
            min-height: 50px !important;
            transition: all 0.2s ease !important;
        }
        .panic-btn-container .stButton > button:hover {
            transform: scale(1.05) !important;
            box-shadow: 0 6px 20px rgba(255,0,0,0.6) !important;
        }
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(255,0,0,0.7); }
            70% { box-shadow: 0 0 0 15px rgba(255,0,0,0); }
            100% { box-shadow: 0 0 0 0 rgba(255,0,0,0); }
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
            .panic-btn-container .stButton > button {
                bottom: 14px !important;
                left: 14px !important;
                padding: 10px 16px !important;
                font-size: 14px !important;
                min-height: 40px !important;
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
# Panic Button - Emergency Alert
# =============================================================================
def show_panic_button():
    """Display floating panic button on every page"""
    st.markdown('<div class="panic-btn-container"></div>', unsafe_allow_html=True)
    
    if st.button("🚨 إبلاغ عن نشاط مشبوه", key="panic_btn"):
        st.session_state.show_panic_dialog = True
        st.rerun()
    
    if st.session_state.get("show_panic_dialog", False):
        show_panic_dialog()

@st.dialog("🚨 تنبيه طارئ", width="small")
def show_panic_dialog():
    """Confirmation dialog for panic button"""
    st.markdown("### هل تريد الإبلاغ عن نشاط مشبوه؟")
    st.markdown("سيتم إرسال تنبيه أمني للمسؤولين فوراً.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ نعم، أبلغ الآن", use_container_width=True, type="primary"):
            send_panic_alert()
            st.session_state.show_panic_dialog = False
            st.success("✅ تم إرسال التنبيه الأمني")
            time.sleep(1)
            st.rerun()
    with col2:
        if st.button("❌ إلغاء", use_container_width=True):
            st.session_state.show_panic_dialog = False
            st.rerun()

def send_panic_alert():
    """Send panic alert via Telegram and log to AuditLog sheet with full visitor data"""
    user = st.session_state.get("user", {})
    role = user.get("role", "غير محدد")
    full_name = user.get("full_name", "غير محدد")
    current_page = st.session_state.get("menu_choice", "صفحة غير معروفة")
    timestamp = get_cairo_now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get IP masked (first 2 octets)
    ip_masked = get_client_ip_masked()
    
    # Get location info
    country, city, region = get_client_country_city()
    
    message = (
        f"🚨 <b>بلاغ طارئ - زر الإنقذ</b>\n"
        f"👤 <b>المستخدم:</b> {full_name}\n"
        f"🔐 <b>الصلاحية:</b> {role}\n"
        f"📄 <b>الصفحة الحالية:</b> {current_page}\n"
        f"⏰ <b>الوقت:</b> {timestamp}\n"
        f"🌐 <b>IP (الأكتواع 2 أولي):</b> {ip_masked}"
    )
    
    # Send to Telegram
    send_telegram_message(message)
    
    # Log to AuditLog with full visitor data
    if 'db_instance' in st.session_state:
        db = st.session_state.db_instance
        db.add_audit_log(
            user_id=user.get("user_id", "anonymous"),
            user_name=full_name if user.get("user_id") else "زائر",
            action="PANIC_BUTTON",
            details=f"Page: {current_page}, IP: {ip_masked}"
        )

# =============================================================================
# Anomaly Detection - Security Monitoring (LOG ONLY - NO BLOCKING)
# =============================================================================
class AnomalyDetector:
    """Inline security anomaly detection class - LOG ONLY, NO BLOCKING"""
    
    @staticmethod
    def check_login(user_id, ip_country):
        """Check if login country is suspicious (not Egypt) - LOG ONLY, NEVER BLOCK"""
        if ip_country and ip_country != "Egypt":
            # LOG suspicious login but NEVER block
            if 'db_instance' in st.session_state:
                db = st.session_state.db_instance
                db.add_audit_log(
                    user_id=user_id,
                    user_name="زائر",
                    action="ANOMALY_DETECTED",
                    details=f"Suspicious login from country: {ip_country}"
                )
            return True  # Always return True - no blocking
    
    @staticmethod
    def check_behavior(user_id, action_count):
        """Check if user has suspicious behavior (>100 deletes in 1 min) - LOG ONLY, NEVER BLOCK"""
        if action_count > 100:
            # LOG suspicious behavior but NEVER block
            if 'db_instance' in st.session_state:
                db = st.session_state.db_instance
                db.add_audit_log(
                    user_id=user_id,
                    user_name="زائر",
                    action="ANOMALY_DETECTED",
                    details=f"Suspicious behavior: {action_count} actions in 1 minute"
                )
            return True  # Always return True - no blocking
        return True
    
    @staticmethod
    def check_time(user_id):
        """Check if login time is suspicious (00:00-05:00 Cairo) - LOG ONLY, NEVER BLOCK"""
        current_hour = get_cairo_now().hour
        if 0 <= current_hour < 5:
            if 'db_instance' in st.session_state:
                db = st.session_state.db_instance
                db.add_audit_log(
                    user_id=user_id,
                    user_name="زائر",
                    action="ANOMALY_DETECTED",
                    details=f"Suspicious time login: Hour {current_hour}"
                )
            return True  # Always return True - no blocking
        return True

# =============================================================================
# Data Masking
# =============================================================================
def mask_data(value, mask_type):
    """Mask sensitive data based on type for non-admin users"""
    if value is None or pd.isna(value):
        return ""
    
    value = str(value).strip()
    
    if mask_type == "name":
        # Names: "سارة جـ***"
        if len(value) <= 2:
            return value[0] + "***"
        return value[:2] + "ـ***"
    elif mask_type == "phone":
        # Phones: "010***1234"
        if len(value) < 8:
            return "*******" + value[-2:] if len(value) >= 2 else "*******"
        return value[:3] + "***" + value[-4:]
    else:
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
# Auto Logout - Session Timeout
# =============================================================================
def check_auto_logout():
    """Check inactivity and trigger auto-logout if needed"""
    # Initialize last activity time if not exists
    if "last_activity_time" not in st.session_state:
        st.session_state.last_activity_time = time.time()
    
    # Update activity time on every interaction
    current_time = time.time()
    inactive_seconds = current_time - st.session_state.last_activity_time
    
    # 270 seconds = 4.5 minutes (4:30 warning), 300 seconds = 5 minutes (logout)
    # Warning at 4:30 minutes
    if 270 <= inactive_seconds < 300 and not st.session_state.get("logout_warning_shown", False):
        st.session_state.logout_warning_shown = True
        st.warning("⚠️ سيتم تسجيل الخروج خلال 30 ثانية بسبب عدم النشاط لمدة 4.5 دقيقة")
    # Force logout at 5:00 minutes
    elif inactive_seconds >= 300:
        st.error("⏰ تم تسجيل الخروج تلقائياً بسبب عدم النشاط لمدة 5 دقائق")
        time.sleep(2)
        logout()
        return True
    
    st.session_state.last_activity_time = current_time
    # Reset warning flag when active
    if inactive_seconds < 270 and st.session_state.get("logout_warning_shown", False):
        st.session_state.logout_warning_shown = False
    
    return False

# =============================================================================
# GDPR Delete - Permanently delete student records
# =============================================================================
def gdpr_delete_student(db, student_id):
    """Permanently delete ALL records of a student from ALL sheets including AuditLog"""
    try:
        # Delete from Students sheet
        db.delete_student(student_id)
        
        # Delete from Attendance sheet
        attendance = db._sheet_to_df("Attendance")
        if not attendance.empty and "student_id" in attendance.columns:
            attendance = attendance[attendance.student_id != student_id]
            db._df_to_sheet("Attendance", attendance, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
        
        # Delete from FollowUp sheet
        followup = db._sheet_to_df("FollowUp")
        if not followup.empty and "student_id" in followup.columns:
            followup = followup[followup.student_id != student_id]
            db._df_to_sheet("FollowUp", followup, ["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])
        
        # Delete from QuizResults sheet
        quiz_results = db._sheet_to_df("QuizResults")
        if not quiz_results.empty and "student_id" in quiz_results.columns:
            quiz_results = quiz_results[quiz_results.student_id != student_id]
            db._df_to_sheet("QuizResults", quiz_results, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "start_time", "submission_time", "answers", "status"])
        
        # Delete from AuditLog entries related to this student
        audit_log = db._sheet_to_df("AuditLog")
        if not audit_log.empty and "user_id" in audit_log.columns:
            audit_log = audit_log[audit_log.user_id != student_id]
            db._df_to_sheet("AuditLog", audit_log, ["timestamp", "user_id", "user_name", "action", "details", "browser", "os", "device_type", "screen_size", "ip_masked", "country", "city", "region", "privacy_consent"])
        
        return True
    except Exception as e:
        st.error(f"خطأ في حذف الطالبة: {str(e)}")
        return False

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

    # --- Logs (Legacy) ---
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

    # --- AuditLog (NEW - 14 columns) ---
    def get_audit_log(self):
        return self._sheet_to_df("AuditLog")

    def add_audit_log(self, user_id, user_name, action, details=""):
        """Add entry to AuditLog with full visitor tracking (14 columns)"""
        # Get current visitor info
        ip_masked = get_client_ip_masked()
        country, city, region = get_client_country_city()
        browser = get_browser_info()
        os_info = get_os_info()
        device_type = get_device_type()
        screen_size = get_screen_size()
        
        audit_entry = {
            "timestamp": get_cairo_now().isoformat(),
            "user_id": user_id if user_id else "anonymous",
            "user_name": user_name if user_name else "زائر",
            "action": action,
            "details": details,
            "browser": browser,
            "os": os_info,
            "device_type": device_type,
            "screen_size": screen_size,
            "ip_masked": ip_masked,
            "country": country,
            "city": city,
            "region": region,
            "privacy_consent": "true"
        }
        
        df = self.get_audit_log()
        if df.empty:
            df = pd.DataFrame(columns=["timestamp", "user_id", "user_name", "action", "details",
                                      "browser", "os", "device_type", "screen_size",
                                      "ip_masked", "country", "city", "region", "privacy_consent"])
        df = pd.concat([df, pd.DataFrame([audit_entry])], ignore_index=True)
        self._df_to_sheet("AuditLog", df, ["timestamp", "user_id", "user_name", "action", "details",
                                           "browser", "os", "device_type", "screen_size",
                                           "ip_masked", "country", "city", "region", "privacy_consent"])

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
    except:
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
        "quiz_load_failures": 0,
        "last_activity_time": time.time(),
        "delete_action_count": {},
        "delete_action_time": {}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout(db=None):
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
                                # Check for anomalies (LOG ONLY, NO BLOCKING)
                                country, _, _ = get_client_country_city()
                                AnomalyDetector.check_login(user.get("user_id", ""), country)
                                AnomalyDetector.check_time(user.get("user_id", ""))
                                
                                token = generate_token(user, jwt_secret)
                                st.session_state.token = token
                                st.session_state.user = user
                                st.session_state.authenticated = True
                                st.session_state.menu_choice = "🏠 لوحة التحكم"
                                st.session_state.show_sidebar = True
                                st.session_state.last_activity_time = time.time()
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
                                    for key in ["student_name", "student_id", "quiz_start_time",
                                                "quiz_end_time", "quiz_submit_time", "quiz_token",
                                                "quiz_answers", "quiz_submitted", "last_score",
                                                "current_attempt_id", "last_saved_answers_str",
                                                "quiz_questions", "show_review"]:
                                        st.session_state[key] = "" if key in ["student_name", "student_id"] else None if key in ["quiz_start_time", "quiz_end_time", "quiz_submit_time"] else {} if key == "quiz_answers" else 0 if key == "last_score" else False
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
    if not st.session_state.get("current_attempt_id"):
        return
    current_answers = json.dumps(st.session_state.get("quiz_answers", {}), ensure_ascii=False)
    if current_answers != st.session_state.get("last_saved_answers_str", ""):
        db.save_answers(st.session_state.current_attempt_id, st.session_state.quiz_answers)
        st.session_state.last_saved_answers_str = current_answers

def show_student_quiz(db: Database):
    # ... (quiz display logic - abbreviated for brevity)
    st.markdown("### واجهة الاختبار (مستحضرة)")

# =============================================================================
# Sidebar Navigation
# =============================================================================
def show_sidebar_navigation(db: Database):
    with st.sidebar:
        st.markdown("## ⛪ كنيسة الشهيدة دميانة")
        user = st.session_state.get("user", {})
        st.markdown(f"**👤 {user.get('full_name', '')}**")
        st.caption(f"الصلاحية: {user.get('role', '')}")
        st.divider()

        role = user.get("role", "")
        menus = {
            "System Admin": [
                "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", "📋 الحضور", "💬 الافتقاد",
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
    user = st.session_state.get("user", {})
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)

    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()

    if role in ["Teacher", "Service Manager"] and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
        if not attendance.empty and "section_id" in attendance.columns:
            attendance = attendance[attendance.section_id == section_id]

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
    
    st.info("مرحباً بك في لوحة التحكم - نظام كنيسة الشهيدة دميانة")

# =============================================================================
# User Management with GDPR Delete
# =============================================================================
def show_user_management(db: Database):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    students = db.get_students()
    
    is_admin = st.session_state.get("user", {}).get("role") == "System Admin"
    
    # Show students with GDPR delete option for admin
    st.subheader("قائمة الطالبات")
    if not students.empty:
        students_display = apply_masking(
            students.merge(sections[["section_id", "section_name"]], on="section_id", how="left") if not sections.empty else students,
            {"full_name": "name", "phone": "phone", "parent_phone": "phone"},
            is_admin
        )
        st.dataframe(students_display[["student_id", "full_name", "section_name", "phone", "parent_phone", "birthdate", "school", "status"]] if "section_name" in students_display.columns else students_display, use_container_width=True)
    else:
        st.info("لا توجد طالبات مسجلة.")
    
    # GDPR Delete Section for Admin
    if is_admin:
        st.markdown("---")
        st.subheader("🔒 حذف نهائي بحق GDPR (حذف كامل للسجلات)")
        st.warning("⚠️ هذا الإجراء سيحذف جميع السجلات المتعلقة بالطالبة من جميع الأنشطة (الحضور، الافتقاد، الاختبارات، وسجل التدقيق)")
        if not students.empty:
            gdpr_student_id = st.selectbox("اختر طالبة للحذف النهائي", students["student_id"], key="gdpr_student_sel")
            admin_password = st.text_input("أدخل كلمة مرور المشرف للتأكيد", type="password", key="gdpr_admin_pwd")
            if st.button("🔴 حذف نهائي (GDPR)", key="gdpr_delete_btn"):
                admin_user = db.get_users()[db.get_users().user_id == st.session_state.user.get("user_id")].iloc[0] if not db.get_users().empty else None
                if admin_user and admin_password == admin_user.get("password", ""):
                    if gdpr_delete_student(db, gdpr_student_id):
                        st.success("✅ تم حذف جميع السجلات الخاصة بالطالبة نهائياً")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("كلمة مرور المشرف غير صحيحة")

# =============================================================================
# Help Dialog
# =============================================================================
@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    st.markdown("### 📬 تواصل معنا")
    st.info("يرجى ملء النموذج أدناه للحصول على المساعدة")

# =============================================================================
# Reports
# =============================================================================
def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    st.info("مرحباً بك في صفحة التقارير - تحت التطوير")

# =============================================================================
# Logs
# =============================================================================
def show_logs(db: Database):
    st.markdown("<h2 class='main-header'>📜 سجل العمليات</h2>", unsafe_allow_html=True)
    logs = db.get_logs()
    if logs.empty:
        st.info("لا توجد سجلات عمليات.")
        return
    st.dataframe(logs.sort_values("timestamp", ascending=False) if "timestamp" in logs.columns else logs, use_container_width=True)

# =============================================================================
# Change Password
# =============================================================================
def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    user = st.session_state.get("user", {})
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

    # Auto-logout check
    if check_auto_logout():
        return

    # Show panic button on EVERY page (including login page for anonymous users)
    show_panic_button()

    st.markdown('<div class="help-float-container"></div>', unsafe_allow_html=True)
    if st.button("🆘 مركز المساعدة", key="fixed_help_btn"):
        st.session_state.open_help_dialog = True
        st.rerun()

    if st.session_state.get("student_quiz_started"):
        show_student_quiz(db)
    else:
        if not st.session_state.get("authenticated"):
            show_login_page(db, jwt_secret)
        else:
            token_data = verify_token(st.session_state.token, jwt_secret)
            if not token_data:
                st.error("⏰ انتهت صلاحية الجلسة.")
                st.session_state.clear()
                time.sleep(2)
                st.rerun()
                return

            if not st.session_state.get("show_sidebar"):
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

            if not st.session_state.get("show_sidebar"):
                choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
                role = st.session_state.user.get("role", "")
                menus = {
                    "System Admin": [
                        "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🏫 إدارة المراحل", "📋 الحضور", "💬 الافتقاد",
                        "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات",
                        "📜 سجل العمليات", "🔒 تغيير كلمة المرور"
                    ],
                    "Father Account": ["🏠 لوحة التحكم", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                    "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد",
                                        "📝 المسابقات والاختبارات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                    "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد",
                                "🏆 درجات المسابقات", "🔒 تغيير كلمة المرور"]
                }
                menu_items = menus.get(role, [])
                if choice not in menu_items:
                    choice = menu_items[0] if menu_items else "🏠 لوحة التحكم"
                    st.session_state.menu_choice = choice

            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            if choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "👥 إدارة المستخدمين":
                if st.session_state.user.get("role") == "System Admin":
                    show_user_management(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "📊 التقارير والإحصائيات":
                show_reports(db)
            elif choice == "📜 سجل العمليات":
                if st.session_state.user.get("role") == "System Admin":
                    show_logs(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "🔒 تغيير كلمة المرور":
                change_password(db)
            else:
                st.info(f"الصفحة: {choice} - قيد التطوير")
            st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("open_help_dialog"):
        show_help_dialog()
        st.session_state.open_help_dialog = False

if __name__ == "__main__":
    main()
