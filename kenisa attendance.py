# =============================================================================
# كنيسة الشهيدة دميانة - نظام الحضور والفعاليات
# Church of St. Demiana - Attendance and Events System
# الإصدار 2.0 - نسخة شاملة مع جميع الوظائف
# Version 2.0 - Complete System with All Features
# =============================================================================
# هذا النظام مُنشأ لإدارة حضور الخدام والطالبات وتنظيم الفعاليات
# Developed for managing attendance and events for church servants and students
# =============================================================================

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure, Bar, Pie, Scatter, Layout
import plotly.graph_objects as go
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
import hashlib
import html
import qrcode
from io import BytesIO
import base64
from typing import Optional, Dict, List, Any, Tuple, Union

# =============================================================================
# SECTION 1: Application Constants & Configuration
# الإعدادات العامة والثوابت
# =============================================================================

CACHE_TTL_SECONDS = 600  # مدة الكاش بالثواني (10 دقائق)
CAIRO_TZ = timezone(timedelta(hours=3), name='Africa/Cairo')

# Rate limiting constants
MAX_GOOGLE_SHEETS_REQUESTS_PER_MINUTE = 40
MAX_LOGIN_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes

# JWT token expiry settings
JWT_EXPIRY_DEFAULT_DAYS = 1  # Regular session - 24 hours
JWT_EXPIRY_REMEMBER_ME_DAYS = 7  # Remember me - 7 days
QUIZ_TOKEN_EXPIRY_HOURS = 48

# User roles constants
ROLE_SYSTEM_ADMIN = "System Admin"
ROLE_FATHER_ACCOUNT = "Father Account"
ROLE_SERVICE_MANAGER = "Service Manager"
ROLE_TEACHER = "Teacher"

# Attendance status constants
STATUS_PRESENT = "حاضر"
STATUS_ABSENT = "غائب"
STATUS_LATE = "متأخر"

# Follow-up types
FOLLOWUP_TYPES = ["اتصال اولي", "اتصال تاني", "اجتماع", "زيارة منزلية"]

# Quiz question types
QUESTION_TYPES = ["اختيار من متعدد", "إجابة قصيرة", "نعم/لا"]

# Event types
EVENT_TYPES = ["اجتماع", "خدمة", "رحلة", "احتفال", "أخرى"]

# RSVP status options
RSVP_STATUSES = ["سأحضر", "لن أحضر", "ربما"]

# =============================================================================
# SECTION 2: Utility Functions
# دوال مساعدة
# =============================================================================

def get_cairo_now() -> datetime:
    """
    Get current Cairo time with timezone awareness.
    Returns current time in Africa/Cairo timezone.
    """
    return datetime.now(CAIRO_TZ)

def format_cairo_time(dt: datetime) -> str:
    """
    Format datetime to Cairo timezone string.
    Returns formatted time string or 'غير متاح' if None.
    """
    if dt is None:
        return "غير متاح"
    return dt.astimezone(CAIRO_TZ).strftime("%Y-%m-%d %I:%M:%S %p")

def format_date_only(dt: datetime) -> str:
    """Format date only to YYYY-MM-DD format."""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")

def generate_student_id() -> str:
    """Generate unique student ID."""
    return f"STD-{uuid.uuid4().hex[:8].upper()}"

def generate_user_id() -> str:
    """Generate unique user ID."""
    return f"USR-{uuid.uuid4().hex[:8].upper()}"

def generate_quiz_id() -> str:
    """Generate unique quiz ID."""
    return f"QUIZ-{uuid.uuid4().hex[:8].upper()}"

def generate_event_id() -> str:
    """Generate unique event ID."""
    return f"EVT-{uuid.uuid4().hex[:8].upper()}"

def generate_record_id() -> str:
    """Generate unique record ID."""
    return f"REC-{uuid.uuid4().hex[:8].upper()}"

# =============================================================================
# SECTION 3: Page Configuration
# إعدادات الصفحة
# =============================================================================

st.set_page_config(
    page_title="نظام- كنيسة الشهيدة دميانة",
    page_icon="⛪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# SECTION 4: Telegram & Support Configuration
# إعدادات التلغرام والدعم
# =============================================================================

def get_telegram_config() -> Tuple[Optional[str], Optional[str]]:
    """
    Get Telegram bot configuration from secrets.
    Returns (bot_token, chat_id) or (None, None) if not configured.
    """
    try:
        return st.secrets["telegram"]["bot_token"], st.secrets["telegram"]["chat_id"]
    except Exception:
        return None, None

def get_support_config() -> Tuple[str, str]:
    """
    Get support contact configuration from secrets.
    Returns (contact_name, whatsapp_number).
    """
    try:
        return (
            st.secrets.get("support", {}).get("contact_name", "مسؤول النظام"),
            st.secrets.get("support", {}).get("whatsapp", "")
        )
    except Exception:
        return "مسؤول النظام", ""

# =============================================================================
# SECTION 5: Authentication & Secrets Configuration
# إعدادات المصادقة والأسرار
# =============================================================================

def get_credentials():
    """
    Get Google Cloud Platform service account credentials.
    Stops application if credentials are invalid.
    """
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return creds
    except Exception as e:
        st.error(f"❌ خطأ في بيانات اعتماد Google: {e}")
        st.stop()

def get_spreadsheet_id() -> str:
    """
    Get Google Sheets spreadsheet ID from secrets.
    Stops application if ID is missing or invalid.
    """
    try:
        sid = st.secrets["sheets"]["spreadsheet_id"]
        if not sid or not isinstance(sid, str) or sid.strip() == "":
            st.error("❌ معرف جدول البيانات غير صالح.")
            st.stop()
        return sid.strip()
    except Exception as e:
        st.error(f"❌ لم يتم العثور على spreadsheet_id: {e}")
        st.stop()

def get_jwt_secret() -> str:
    """
    Get JWT secret from Streamlit secrets.
    CRITICAL SECURITY: Application stops if secret is missing.
    No fallback secrets are allowed.
    """
    try:
        secret = st.secrets["jwt_secret"]
        if not secret or not isinstance(secret, str):
            raise ValueError("JWT secret is empty or invalid")
        if len(secret) < 32:
            st.error("❌ jwt_secret غير آمن - يجب أن يكون على الأقل 32 حرفاً.")
            st.stop()
        return secret
    except Exception:
        st.error("❌ لم يتم العثور على jwt_secret في Secrets.")
        st.stop()
        return ""  # Never reached, but for type safety

# =============================================================================
# SECTION 6: CSS Styling (ONLY place with unsafe_allow_html=True)
# تصميم CSS
# =============================================================================

def inject_css():
    """
    Inject all CSS styles for the application.
    This is the ONLY function allowed to use unsafe_allow_html=True.
    All other HTML rendering must use safe methods.
    """
    st.markdown("""
    <style>
    /* ========================================================================
       Base Styles - Force Light Theme
       النمط الأساسي - إجبار المظهر الفاتح
       ======================================================================== */
    html, body, .stApp {
        color-scheme: light !important;
    }
    
    @media (prefers-color-scheme: dark) {
        html, body, .stApp {
            background-color: #f0f2f6 !important;
            color: #1a1a2e !important;
        }
    }

    /* Arabic Font Import */
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * { 
        font-family: 'Cairo', sans-serif; 
    }
    
    body { 
        direction: rtl; 
        text-align: right; 
        background-color: #f0f2f6; 
        color: #1a1a2e; 
        margin: 0;
        padding: 0;
    }
    
    .stApp { 
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); 
    }

    /* Hide Streamlit UI elements */
    header[data-testid="stHeader"] { 
        display: none !important; 
    }
    
    #MainMenu { 
        visibility: hidden; 
    }
    
    footer { 
        visibility: hidden; 
    }

    /* ========================================================================
       Sidebar - Fixed Position for Mobile
       الشريط الجانبي - تثبيت الموقع للهاتف
       ======================================================================== */
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

    /* ========================================================================
       Main Content Area
       منطقة المحتوى الرئيسية
       ======================================================================== */
    [data-testid="stAppViewContainer"] > [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        max-width: 100% !important;
        width: 100% !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }

    /* ========================================================================
       Navigation Buttons
       أزرار التنقل
       ======================================================================== */
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

    /* ========================================================================
       Floating Action Buttons
       الأزرار العائمة
       ======================================================================== */
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

    /* ========================================================================
       Cards & Headers
       البطاقات والعناوين
       ======================================================================== */
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
        margin-top: 100px;
    }

    .card {
        background: rgba(255,255,255,0.95);
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: transform 0.2s;
        color: #1a1a2e;
        border: 1px solid rgba(0,0,0,0.05);
    }

    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
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

    .stRadio > div, .stSelectbox > div, .stMultiSelect > div {
        direction: rtl;
    }

    .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput {
        text-align: right;
    }

    .content-area {
        padding: 0 1rem;
    }

    /* ========================================================================
       Data Frames & Forms
       الجداول ونماذج الإدخال
       ======================================================================== */
    .stDataFrame {
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border-radius: 8px;
        font-weight: 600;
    }

    .stForm {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }

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

    .stSuccess {
        background: rgba(40,167,69,0.1);
        border: 1px solid rgba(40,167,69,0.2);
        color: #155724;
        border-radius: 10px;
    }

    .stError {
        background: rgba(220,53,69,0.1);
        border: 1px solid rgba(220,53,69,0.2);
        color: #721c24;
        border-radius: 10px;
    }

    iframe[title="st_components.html"] {
        border: none !important;
        background: transparent !important;
    }

    /* ========================================================================
       Responsive Design
       التصميم المتجاوب
       ======================================================================== */
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

        .main-header {
            font-size: 1.6rem;
            margin-top: 110px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# SECTION 7: Cache Initialization
# تهيئة الكاش
# =============================================================================

def init_data_cache():
    """Initialize session state cache structures."""
    if 'data_cache' not in st.session_state:
        st.session_state.data_cache = {}
    if 'data_dirty' not in st.session_state:
        st.session_state.data_dirty = {}

# =============================================================================
# SECTION 8: Retry Decorator
# الديكوراتور المحاولة
# =============================================================================

def retry_operation(max_retries: int = 5, base_delay: float = 2):
    """
    Decorator for retrying failed operations with exponential backoff.
    Handles Google Sheets API rate limiting gracefully.
    """
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
# SECTION 9: Security Functions
# الدوال الأمنية
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hash password using SHA-256 encryption.
    SHA-256 produces a 64-character hexadecimal string.
    تشفير كلمة المرور باستخدام SHA-256
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify password against stored hash.
    No fallback to plain text comparison.
    التحقق من كلمة المرور
    """
    if not password or not stored_hash:
        return False
    return hash_password(password) == stored_hash

def verify_legacy_password(password: str, stored_value: str) -> Tuple[bool, bool]:
    """
    Check if password matches - supports both hashed and plain text for migration.
    Returns (is_match, needs_migration).
    
    Migration process: Legacy users with plain-text passwords (not 64 chars)
    will be automatically migrated to hashed passwords on successful login.
    
    التحقق من كلمة المرور مع دعم ترحيل البيانات القديمة
    """
    if not stored_value:
        return False, False
    # First try as hash (new system) - SHA-256 produces 64 char hex string
    if len(str(stored_value)) == 64:
        hashed = hash_password(password)
        return (hashed == stored_value), False
    # Try plain text comparison (legacy system) - needs migration
    is_match = password == stored_value
    return is_match, is_match

def migrate_user_password(db, user_id: str, plain_password: str):
    """
    Migrate legacy user with plain text password to hashed password.
    Called automatically when a legacy user logs in successfully.
    
    ترحيل كلمة مرور المستخدم القديم
    """
    hashed = hash_password(plain_password)
    db.update_user(user_id, {"password": hashed})

def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent XSS attacks.
    Escapes HTML special characters: < > & " '
    
    تنظيف إدخال المستخدم لمنع هجمات XSS
    """
    if text is None:
        return ""
    text = str(text)
    text = html.escape(text)
    return text

# =============================================================================
# SECTION 10: Rate Limiting Variables
# متغيرات حدود الطلبات
# =============================================================================
_login_attempts = []
_login_lock = threading.Lock()

# =============================================================================
# SECTION 11: Geolocation & VPN Detection
# الكشف عن الموقع والـ VPN
# =============================================================================

VPN_ISPS = [
    "NordVPN", "ExpressVPN", "Mullvad", "Mysterium", "ProtonVPN",
    "Surfshark", "CyberGhost", "IPVanish", "PrivateVPN", "Windscribe",
    "Tunnelbear", "VyprVPN", "Hotspot Shield", "Buffered", "Private Internet Access"
]

def get_visitor_geo_data() -> dict:
    """
    Get visitor IP and location data from external APIs.
    Uses ip-api.com as primary, ipapi.co as fallback.
    
    الحصول على بيانات الموقع الجغرافي للزائر
    """
    geo_data = {
        "ip_address": "",
        "country": "",
        "city": "",
        "region": "",
        "lat": "",
        "lon": "",
        "isp": "",
        "connection_type": "",
        "device_type": "desktop",
        "browser": "",
        "os": "",
        "screen_size": "1920x1080",
        "is_vpn": False,
        "error": None
    }
    
    try:
        # Primary API: ip-api.com
        try:
            response = requests.get("http://ip-api.com/json/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                geo_data["ip_address"] = data.get("query", "")
                geo_data["country"] = data.get("country", "")
                geo_data["city"] = data.get("city", "")
                geo_data["region"] = data.get("regionName", "")
                geo_data["lat"] = str(data.get("lat", ""))
                geo_data["lon"] = str(data.get("lon", ""))
                geo_data["isp"] = data.get("isp", "")
                geo_data["connection_type"] = data.get("type", "")
        except Exception:
            # Fallback API: ipapi.co
            try:
                response = requests.get("https://ipapi.co/json/", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    geo_data["ip_address"] = data.get("ip", "")
                    geo_data["country"] = data.get("country_name", "")
                    geo_data["city"] = data.get("city", "")
                    geo_data["region"] = data.get("region", "")
                    geo_data["lat"] = str(data.get("latitude", ""))
                    geo_data["lon"] = str(data.get("longitude", ""))
                    geo_data["isp"] = data.get("org", "")
            except Exception as fallback_error:
                geo_data["error"] = f"Primary and fallback API failed: {str(fallback_error)}"
    except Exception as e:
        geo_data["error"] = str(e)
    
    return geo_data

def detect_vpn(geo_data: dict) -> bool:
    """
    Detect if visitor is using VPN based on:
    1. Country not being Egypt (blocks foreign access)
    2. ISP containing known VPN provider names
    
    الكشف عن استخدام VPN
    """
    if geo_data.get("country", "") and geo_data["country"] != "Egypt":
        return True
    
    isp = geo_data.get("isp", "").lower()
    for vpn_name in VPN_ISPS:
        if vpn_name.lower() in isp:
            return True
    
    return False

def check_geo_access():
    """
    Check if visitor is allowed based on location.
    Blocks access from outside Egypt and VPN users.
    
    فحص صلاحية الوصول حسب الموقع الجغرافي
    """
    if "visitor_geo" not in st.session_state:
        st.session_state.visitor_geo = get_visitor_geo_data()
    
    geo = st.session_state.visitor_geo
    
    if geo.get("country", "") and geo["country"] != "Egypt":
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h1>🚫 هذا الموقع متاح فقط داخل جمهورية مصر العربية</h1>
            <p>يُرجى التواصل مع الإدارة إذا كنت تعتقد أن هذا خطأ</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()
    
    if detect_vpn(geo):
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h1>❌ تم اكتشاف استخدام VPN</h1>
            <p>الدخول من خارج مصر غير مسموح به.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("تواصل مع الدعم"):
            bot_token, chat_id = get_telegram_config()
            if bot_token and chat_id:
                msg = f"بلاغ VPN: دخول من {geo.get('country', 'غير معروف')} - IP: {geo.get('ip_address', 'غير معروف')}"
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                        json={"chat_id": chat_id, "text": msg},
                        timeout=5
                    )
                except Exception:
                    pass
        st.stop()
    
    return True

def check_login_rate_limit() -> bool:
    """
    Check if login rate limit exceeded.
    Allows maximum 5 login attempts per 15 minutes (900 seconds).
    Returns True if limit is exceeded.
    
    فحص حدود المحاولات في تسجيل الدخول
    """
    global _login_attempts
    now = time.time()
    with _login_lock:
        _login_attempts = [t for t in _login_attempts if now - t < LOGIN_RATE_LIMIT_WINDOW_SECONDS]
        if len(_login_attempts) >= MAX_LOGIN_ATTEMPTS:
            return True
        _login_attempts.append(now)
    return False

# =============================================================================
# SECTION 12: Database Class
# فئة قاعدة البيانات
# =============================================================================

class Database:
    """
    Database class for Google Sheets operations.
    Implements caching, rate limiting, and data sanitization.
    
    فئة قاعدة البيانات لعمليات Google Sheets
    """
    _request_times = []
    _lock = threading.Lock()

    @staticmethod
    def _rate_limit():
        """Rate limit Google Sheets API requests to 40 per minute."""
        now = time.time()
        with Database._lock:
            Database._request_times = [t for t in Database._request_times if now - t < 60]
            if len(Database._request_times) >= MAX_GOOGLE_SHEETS_REQUESTS_PER_MINUTE:
                sleep_time = 60 - (now - Database._request_times[0]) + 1
                if sleep_time > 0:
                    time.sleep(sleep_time)
                Database._request_times = []
            Database._request_times.append(time.time())

    def __init__(self, creds, spreadsheet_id):
        """Initialize database connection with credentials and spreadsheet ID."""
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(self, name: str, columns: List[str]):
        """Get worksheet or create if not exists."""
        Database._rate_limit()
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            cols = max(len(columns), 1) if columns else 1
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=cols)
            if columns:
                ws.append_row(columns)
        time.sleep(0.2)
        return ws

    def _get_cached_df(self, sheet_name: str, fetch_func):
        """Get cached DataFrame or fetch fresh data."""
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

    def _invalidate_cache(self, sheet_name: str):
        """Mark cache as dirty for refresh."""
        init_data_cache()
        st.session_state.data_dirty[sheet_name] = True

    def _read_sheet_raw(self, sheet_name: str) -> pd.DataFrame:
        """Read raw data from sheet with header deduplication."""
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

    def _sheet_to_df(self, sheet_name: str) -> pd.DataFrame:
        """Convert sheet to DataFrame with caching."""
        return self._get_cached_df(sheet_name, lambda: self._read_sheet_raw(sheet_name))

    def _df_to_sheet(self, sheet_name: str, df: pd.DataFrame, columns: List[str]):
        """Write DataFrame to sheet."""
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
    def _safe_str(value) -> str:
        """Safely convert value to string."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    # ========================================================================
    # Users Management - إدارة المستخدمين
    # ========================================================================
    
    def get_users(self) -> pd.DataFrame:
        """Get all users from Users sheet."""
        return self._sheet_to_df("Users")

    def add_user(self, user_data: dict):
        """Add new user with hashed password and sanitized input."""
        df = self.get_users()
        if df.empty:
            df = pd.DataFrame(columns=["user_id", "username", "password", "role",
                                       "full_name", "section_id", "phone", "email"])
        user_data["password"] = hash_password(user_data.get("password", ""))
        for key in ["username", "full_name", "phone", "email"]:
            if key in user_data:
                user_data[key] = sanitize_input(str(user_data.get(key, "")))
        
        for col in ["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"]:
            if col not in df.columns:
                df[col] = ""
        
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        user_cols = ["user_id", "username", "password", "role", "full_name", "section_id", "phone", "email"]
        self._df_to_sheet("Users", df, user_cols)

    def update_user(self, user_id: str, updates: dict):
        """Update user data with password hashing and input sanitization."""
        df = self.get_users()
        idx = df[df.user_id == user_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                if k == "password":
                    v = hash_password(str(v))
                elif k in ["username", "full_name", "phone", "email"]:
                    v = sanitize_input(str(v))
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Users", df, df.columns.tolist())

    def delete_user(self, user_id: str):
        """Delete user by ID."""
        df = self.get_users()
        df = df[df.user_id != user_id]
        self._df_to_sheet("Users", df, df.columns.tolist())

    # ========================================================================
    # Sections Management - إدارة الفصول
    # ========================================================================
    
    def get_sections(self) -> pd.DataFrame:
        """Get all sections from Sections sheet."""
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data: dict):
        """Add new section."""
        self._get_or_create_worksheet("Sections", ["section_id", "section_name", "manager_user_id"])
        df = self.get_sections()
        if df.empty:
            df = pd.DataFrame(columns=["section_id", "section_name", "manager_user_id"])
        
        new_row = {
            "section_id": str(sec_data["section_id"]),
            "section_name": sanitize_input(str(sec_data.get("section_name", ""))),
            "manager_user_id": str(sec_data.get("manager_user_id", ""))
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    def update_section(self, section_id: str, updates: dict):
        """Update section data."""
        df = self.get_sections()
        idx = df[df.section_id == section_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Sections", df, df.columns.tolist())

    def delete_section(self, section_id: str):
        """Delete section by ID."""
        df = self.get_sections()
        df = df[df.section_id != section_id]
        self._df_to_sheet("Sections", df, df.columns.tolist())

    # ========================================================================
    # Students Management - إدارة الطالبات
    # ========================================================================
    
    def get_students(self) -> pd.DataFrame:
        """Get all students from Students sheet."""
        return self._sheet_to_df("Students")

    def add_student(self, student_data: dict):
        """Add new student."""
        df = self.get_students()
        if df.empty:
            df = pd.DataFrame(columns=["student_id", "full_name", "section_id", "teacher_id",
                                       "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])
        
        student_data["teacher_id"] = ""
        for key in ["full_name", "phone", "parent_phone", "address", "notes", "school"]:
            if key in student_data:
                student_data[key] = sanitize_input(str(student_data.get(key, "")))
        
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        self._df_to_sheet("Students", df, ["student_id", "full_name", "section_id", "teacher_id",
                                           "phone", "parent_phone", "birthdate", "address", "notes", "school", "status"])

    def update_student(self, student_id: str, updates: dict):
        """Update student data."""
        df = self.get_students()
        idx = df[df.student_id == student_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Students", df, df.columns.tolist())

    def delete_student(self, student_id: str):
        """Delete student by ID."""
        df = self.get_students()
        df = df[df.student_id != student_id]
        self._df_to_sheet("Students", df, df.columns.tolist())

    # ========================================================================
    # Attendance Management - إدارة الحضور
    # ========================================================================
    
    def get_attendance(self) -> pd.DataFrame:
        """Get all attendance records."""
        return self._sheet_to_df("Attendance")

    def batch_add_attendance(self, records_list: List[dict]):
        """Add multiple attendance records, handling duplicates."""
        if not records_list:
            return
        
        df = self.get_attendance()
        if df.empty:
            df = pd.DataFrame(columns=["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])
        
        existing_ids = set(df["record_id"].tolist()) if not df.empty else set()
        new_records = []
        
        for rec in records_list:
            rec["notes"] = sanitize_input(str(rec.get("notes", "")))
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

    def get_attendance_by_date_section(self, date_str: str, section_id: str) -> pd.DataFrame:
        """Get attendance records filtered by date and section."""
        df = self.get_attendance()
        if df.empty:
            return pd.DataFrame()
        return df[(df.date == date_str) & (df.section_id == section_id)]

    def delete_attendance_record(self, record_id: str):
        """Delete attendance record by ID."""
        df = self.get_attendance()
        df = df[df.record_id != record_id]
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    # ========================================================================
    # Follow-up Management - إدارة الافتقاد
    # ========================================================================
    
    def get_followup(self) -> pd.DataFrame:
        """Get all follow-up records."""
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record: dict):
        """Add follow-up record with duplicate check."""
        df = self.get_followup()
        
        # Check for duplicate
        if not df.empty:
            duplicate = df[(df.student_id == record["student_id"]) &
                           (df.followup_date == record["followup_date"]) &
                           (df.followup_type == record["followup_type"])]
            if not duplicate.empty:
                raise ValueError("⛔ تم تسجيل نفس الافتقاد مسبقاً لنفس الطالبة في نفس التاريخ ونفس النوع.")
        
        if df.empty:
            df = pd.DataFrame(columns=["record_id", "student_id", "teacher_id", "followup_date",
                                       "followup_type", "notes", "regularity_status"])
        
        record["notes"] = sanitize_input(str(record.get("notes", "")))
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date",
                                           "followup_type", "notes", "regularity_status"])

    def delete_followup_record(self, record_id: str):
        """Delete follow-up record."""
        df = self.get_followup()
        df = df[df.record_id != record_id]
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date",
                                           "followup_type", "notes", "regularity_status"])

    # ========================================================================
    # Quizzes Management - إدارة الاختبارات
    # ========================================================================
    
    def get_quizzes(self) -> pd.DataFrame:
        """Get all quizzes."""
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data: dict):
        """Add new quiz."""
        df = self.get_quizzes()
        if df.empty:
            df = pd.DataFrame(columns=["quiz_id", "title", "description", "created_by", "section_id",
                                       "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                       "quiz_code", "password", "is_active"])
        
        quiz_data["password"] = hash_password(str(quiz_data.get("password", "")))
        quiz_data["title"] = sanitize_input(str(quiz_data.get("title", "")))
        quiz_data["description"] = sanitize_input(str(quiz_data.get("description", "")))
        
        df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active"])

    def update_quiz(self, quiz_id: str, updates: dict):
        """Update quiz data."""
        df = self.get_quizzes()
        idx = df[df.quiz_id == quiz_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                if k == "password":
                    v = hash_password(str(v))
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Quizzes", df, df.columns.tolist())

    def delete_quiz_keep_results(self, quiz_id: str):
        """Delete quiz but keep results."""
        df = self.get_quizzes()
        df = df[df.quiz_id != quiz_id]
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id",
                                          "num_questions", "time_limit_minutes", "total_marks", "expiry_date",
                                          "quiz_code", "password", "is_active"])
        
        qdf = self._sheet_to_df("QuizQuestions")
        qdf = qdf[qdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizQuestions", qdf, ["question_id", "quiz_id", "question_text", "question_type",
                                                 "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_quiz(self, quiz_id: str):
        """Delete quiz and all related data."""
        self.delete_quiz_keep_results(quiz_id)
        rdf = self._sheet_to_df("QuizResults")
        rdf = rdf[rdf.quiz_id != quiz_id]
        self._df_to_sheet("QuizResults", rdf, ["result_id", "quiz_id", "student_id", "student_name",
                                               "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def get_quiz_questions(self, quiz_id: str) -> pd.DataFrame:
        """Get questions for a specific quiz."""
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            return pd.DataFrame()
        return df[df.quiz_id == quiz_id]

    def add_question(self, q_data: dict):
        """Add quiz question."""
        df = self._sheet_to_df("QuizQuestions")
        if df.empty:
            df = pd.DataFrame(columns=["question_id", "quiz_id", "question_text", "question_type",
                                       "option1", "option2", "option3", "option4", "correct_answer"])
        
        q_data["question_text"] = sanitize_input(str(q_data.get("question_text", "")))
        df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type",
                                                "option1", "option2", "option3", "option4", "correct_answer"])

    def delete_question(self, question_id: str):
        """Delete quiz question."""
        df = self._sheet_to_df("QuizQuestions")
        df = df[df.question_id != question_id]
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type",
                                                "option1", "option2", "option3", "option4", "correct_answer"])

    # ========================================================================
    # Quiz Results Management - إدارة نتائج الاختبارات
    # ========================================================================
    
    def get_quiz_results(self, quiz_id: Optional[str] = None) -> pd.DataFrame:
        """Get quiz results, optionally filtered by quiz_id."""
        df = self._sheet_to_df("QuizResults")
        if df.empty:
            return pd.DataFrame()
        if quiz_id:
            return df[df.quiz_id == quiz_id]
        return df

    def start_quiz_attempt(self, quiz_id: str, student_id: str, student_name: str) -> str:
        """Start a new quiz attempt and return result_id."""
        result_id = str(uuid.uuid4())
        now_iso = get_cairo_now().isoformat()
        
        new_row = {
            "result_id": result_id,
            "quiz_id": quiz_id,
            "student_id": student_id,
            "student_name": sanitize_input(student_name),
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

    def save_answers(self, result_id: str, answers_dict: dict):
        """Save quiz answers during attempt."""
        df = self._sheet_to_df("QuizResults")
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "answers"] = json.dumps(answers_dict, ensure_ascii=False)
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def submit_quiz_attempt(self, result_id: str, score: int, answers_json: str):
        """Submit completed quiz attempt."""
        df = self._sheet_to_df("QuizResults")
        idx = df[df.result_id == result_id].index
        if len(idx) > 0:
            df.at[idx[0], "score"] = str(score)
            df.at[idx[0], "answers"] = answers_json
            df.at[idx[0], "submission_time"] = get_cairo_now().isoformat()
            df.at[idx[0], "status"] = "submitted"
            self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                                  "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    def delete_quiz_result(self, result_id: str):
        """Delete quiz result."""
        df = self._sheet_to_df("QuizResults")
        df = df[df.result_id != result_id]
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name",
                                              "score", "total_marks", "start_time", "submission_time", "answers", "status"])

    # ========================================================================
    # Logs Management - إدارة السجلات
    # ========================================================================
    
    def get_logs(self) -> pd.DataFrame:
        """Get all log entries."""
        return self._sheet_to_df("Logs")

    def add_log(self, user_id: str, action: str, details: str = ""):
        """Add log entry with visitor geolocation data."""
        log = {
            "log_id": str(uuid.uuid4()),
            "timestamp": get_cairo_now().isoformat(),
            "user_id": user_id,
            "action": sanitize_input(action),
            "details": sanitize_input(details),
            "ip_address": st.session_state.get("visitor_geo", {}).get("ip_address", ""),
            "country": st.session_state.get("visitor_geo", {}).get("country", ""),
            "city": st.session_state.get("visitor_geo", {}).get("city", ""),
            "region": st.session_state.get("visitor_geo", {}).get("region", ""),
            "isp": st.session_state.get("visitor_geo", {}).get("isp", ""),
            "device_type": st.session_state.get("visitor_geo", {}).get("device_type", "desktop"),
            "browser": st.session_state.get("visitor_geo", {}).get("browser", ""),
            "os": st.session_state.get("visitor_geo", {}).get("os", ""),
            "screen_size": st.session_state.get("visitor_geo", {}).get("screen_size", "1920x1080"),
            "is_vpn": st.session_state.get("visitor_geo", {}).get("is_vpn", False)
        }
        
        df = self.get_logs()
        log_cols = ["log_id", "timestamp", "user_id", "action", "details"]
        log_cols.extend([c for c in ["ip_address", "country", "city", "region", "isp", "device_type", "browser", "os", "screen_size", "is_vpn"] if c in df.columns])
        
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, log_cols)

    def delete_log(self, log_id: str):
        """Delete log entry."""
        df = self.get_logs()
        df = df[df.log_id != log_id]
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

    # ========================================================================
    # Events Management - إدارة الفعاليات (Part 6)
    # ========================================================================
    
    def get_events(self) -> pd.DataFrame:
        """Get all events."""
        return self._sheet_to_df("Events")

    def add_event(self, event_data: dict):
        """Add new event."""
        df = self.get_events()
        if df.empty:
            df = pd.DataFrame(columns=["event_id", "event_name", "event_type", "event_date", "event_time",
                                       "location", "max_capacity", "description", "created_by", "is_active", "created_at"])
        
        for key in ["event_name", "location", "description"]:
            if key in event_data:
                event_data[key] = sanitize_input(str(event_data.get(key, "")))
        
        df = pd.concat([df, pd.DataFrame([event_data])], ignore_index=True)
        self._df_to_sheet("Events", df, ["event_id", "event_name", "event_type", "event_date", "event_time",
                                         "location", "max_capacity", "description", "created_by", "is_active", "created_at"])

    def update_event(self, event_id: str, updates: dict):
        """Update event data."""
        df = self.get_events()
        idx = df[df.event_id == event_id].index
        if len(idx) > 0:
            for k, v in updates.items():
                if k in ["event_name", "location", "description"]:
                    v = sanitize_input(str(v))
                df.at[idx[0], k] = self._safe_str(v)
            self._df_to_sheet("Events", df, df.columns.tolist())

    def delete_event(self, event_id: str):
        """Delete event."""
        df = self.get_events()
        df = df[df.event_id != event_id]
        self._df_to_sheet("Events", df, ["event_id", "event_name", "event_type", "event_date", "event_time",
                                         "location", "max_capacity", "description", "created_by", "is_active", "created_at"])

    def get_event_rsvp(self) -> pd.DataFrame:
        """Get all event RSVPs."""
        return self._sheet_to_df("EventRSVP")

    def add_rsvp(self, rsvp_data: dict):
        """Add or update RSVP."""
        df = self.get_event_rsvp()
        if df.empty:
            df = pd.DataFrame(columns=["rsvp_id", "event_id", "student_id", "status", "registered_at", "notes"])
        
        existing = df[(df.event_id == rsvp_data.get("event_id")) & 
                     (df.student_id == rsvp_data.get("student_id"))]
        
        if not existing.empty:
            idx = existing.index[0]
            for k, v in rsvp_data.items():
                df.at[idx, k] = self._safe_str(v)
        else:
            df = pd.concat([df, pd.DataFrame([rsvp_data])], ignore_index=True)
        
        self._df_to_sheet("EventRSVP", df, ["rsvp_id", "event_id", "student_id", "status", "registered_at", "notes"])

    def get_rsvp_for_event(self, event_id: str) -> pd.DataFrame:
        """Get RSVPs for a specific event."""
        df = self.get_event_rsvp()
        if df.empty:
            return pd.DataFrame()
        return df[df.event_id == event_id]

# =============================================================================
# SECTION 13: JWT Token Functions
# دوال رموز JWT
# =============================================================================

def generate_token(user: dict, secret: str, remember_me: bool = False) -> str:
    """
    Generate JWT token for authenticated session.
    
    Args:
        user: User dictionary with user_id, role, full_name, section_id
        secret: JWT secret key from st.secrets
        remember_me: If True, token expires in 7 days; otherwise 24 hours
    
    Returns:
        Encoded JWT token string
    """
    expiry_days = JWT_EXPIRY_REMEMBER_ME_DAYS if remember_me else JWT_EXPIRY_DEFAULT_DAYS
    payload = {
        "user_id": user.get("user_id", ""),
        "role": user.get("role", ""),
        "full_name": user.get("full_name", ""),
        "section_id": user.get("section_id", ""),
        "exp": datetime.utcnow() + timedelta(days=expiry_days)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def generate_quiz_token(quiz_id: str, student_id: str, secret: str = None) -> str:
    """Generate quiz token with 48-hour expiry."""
    if secret is None:
        secret = get_jwt_secret()
    payload = {
        "quiz_id": quiz_id,
        "student_id": student_id,
        "exp": datetime.utcnow() + timedelta(hours=QUIZ_TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def verify_quiz_token(token: str, secret: str = None):
    """Verify quiz token and return payload."""
    if secret is None:
        secret = get_jwt_secret()
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        return None

def verify_token(token: str, secret: str):
    """Verify JWT token and return payload or None if invalid/expired."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None

# =============================================================================
# SECTION 14: Session Initialization
# تهيئة الجلسة
# =============================================================================

def init_session():
    """Initialize session state with default values."""
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

# =============================================================================
# SECTION 15: Utility Functions
# دوال مساعدة
# =============================================================================

def logout(db=None):
    """Clear session and redirect to login page."""
    if db and st.session_state.user:
        try:
            pass  # Log logout action if needed
        except Exception:
            pass
    
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def send_telegram_message(message: str) -> bool:
    """Send message via Telegram bot."""
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

def send_telegram_photo(caption: str, file_bytes: bytes, filename: str) -> bool:
    """Send photo via Telegram bot."""
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
# SECTION 16: Help Dialog
# مركز المساعدة
# =============================================================================

@st.dialog("🆘 مركز المساعدة والدعم الفني", width="large")
def show_help_dialog():
    """Display help and support dialog with form."""
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
                    f"👤 الاسم: {sanitize_input(name)}\n"
                    f"📱 الواتساب: {sanitize_input(whatsapp)}\n"
                    f"📂 النوع: {sanitize_input(issue_type)}\n"
                    f"⚡ الأولوى: {sanitize_input(urgency)}\n"
                    f"📝 التفاصيل: {sanitize_input(issue_desc)}"
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
# SECTION 17: Validation Functions
# دوال التحقق
# =============================================================================

def validate_data_integrity(db) -> List[str]:
    """Validate data integrity and return list of errors."""
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

def auto_fix_missing_sections(db) -> bool:
    """Auto-create missing sections for students."""
    students = db.get_students()
    sections = db.get_sections()
    
    if students.empty:
        return False
    
    existing_ids = set(sections["section_id"].tolist()) if not sections.empty else set()
    students_ids = students["section_id"].dropna().unique().tolist()
    missing = [sid for sid in students_ids if sid and str(sid).strip() not in existing_ids]
    
    if missing:
        for sid in missing:
            db.add_section({"section_id": str(sid), "section_name": f"فصل (معرف {str(sid)[:8]})"})
        return True
    
    return False

# =============================================================================
# SECTION 18: Login & Initialization Functions
# دوال تسجيل الدخول والتهيئة
# =============================================================================

def show_initialization(db):
    """Show initialization screen for first-time setup."""
    users = db.get_users()
    
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2></div>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", use_container_width=True, key="init_admin_btn"):
            admin_data = {
                "user_id": f"admin-{uuid.uuid4().hex[:8]}",
                "username": "admin",
                "password": "admin123",
                "role": ROLE_SYSTEM_ADMIN,
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

def show_login_page(db, jwt_secret):
    """Display login page with tabs for staff and student quiz access."""
    st.markdown("<h1 class='main-header'>⛪ <br>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
    show_initialization(db)
    
    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخاف الطالبات للاختبار"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم").strip()
            password = st.text_input("كلمة المرور", type="password").strip()
            remember_me = st.checkbox("البقاء مسجلاً لمدة أسبوع", key="remember_me_checkbox")
            
            if st.form_submit_button("تسجيل الدخول", use_container_width=True):
                if check_login_rate_limit():
                    st.error("❌ تم تجاوز عدد محاولات تسجيل الدخول. يرجى المحاولة بعد 15 دقيقة.")
                    return
                
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
                            stored_pass = user.get("password", "")
                            
                            # Check password with migration support
                            is_match, needs_migration = verify_legacy_password(password, stored_pass)
                            
                            if is_match:
                                # Migrate legacy password if needed
                                if needs_migration:
                                    migrate_user_password(db, user["user_id"], password)
                                
                                # Generate token with appropriate expiry
                                token = generate_token(user, jwt_secret, remember_me=remember_me)
                                
                                # Set session state
                                st.session_state.token = token
                                st.session_state.user = user
                                st.session_state.authenticated = True
                                st.session_state.menu_choice = "🏠 لوحة التحكم"
                                st.session_state.show_sidebar = True
                                
                                # Log login action
                                db.add_log(user["user_id"], "تسجيل الدخول")
                                
                                st.success("تم تسجيل الدخول بنجاح!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("كلمة المرور غير صحيحة")
    
    with tab2:
        st.info("وضع اختبار الطالبات - قيد التطوير")

# =============================================================================
# SECTION 19: Events Functions (Part 6)
# دوال الفعاليات
# =============================================================================

def show_events(db):
    """Display events management page with add/view functionality."""
    st.markdown("<h2 class='main-header'>📅 الفعاليات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")

    # Check permissions
    if role not in [ROLE_SYSTEM_ADMIN, ROLE_SERVICE_MANAGER]:
        st.error("🚫 هذه الصفحة متاحة للمسؤولين فقط.")
        return

    events = db.get_events()
    today = get_cairo_now().strftime("%Y-%m-%d")

    tab1, tab2 = st.tabs(["📅 الفعاليات القادمة", "📜 الفعاليات الماضية"])

    with tab1:
        future_events = events[events.event_date >= today] if not events.empty and "event_date" in events.columns else pd.DataFrame()
        
        if not future_events.empty:
            for _, e in future_events.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.markdown(f"**{e.get('event_name', '')}**")
                col1.write(f"📍 {e.get('location', '')} | 📅 {e.get('event_date', '')} | 🕐 {e.get('event_time', '')}")
                
                active = e.get("is_active", "True") == "True"
                col2.write("🟢 نشط" if active else "🔴 مغلق")
                
                eid = e.get("event_id", "")
                rsvps = db.get_rsvp_for_event(eid)
                going = len(rsvps[rsvps.status == "سأحضر"]) if not rsvps.empty and "status" in rsvps.columns else 0
                capacity = e.get("max_capacity", "")
                col3.write(f"👥 {going}/{capacity}")
                
                with st.expander("تفاصيل"):
                    st.write(f"**النوع:** {e.get('event_type', '')}")
                    st.write(f"**الوصف:** {e.get('description', '')}")
                
                st.markdown("---")
        else:
            st.info("لا توجد فعاليات قادمة.")

    with tab2:
        past_events = events[events.event_date < today] if not events.empty and "event_date" in events.columns else pd.DataFrame()
        
        if not past_events.empty:
            for _, e in past_events.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.markdown(f"**{e.get('event_name', '')}**")
                col1.write(f"📅 {e.get('event_date', '')}")
                
                rsvps = db.get_rsvp_for_event(e.get("event_id", ""))
                going = len(rsvps[rsvps.status == "سأحضر"]) if not rsvps.empty and "status" in rsvps.columns else 0
                col2.write(f"✅ {going} حضر")
                
                with st.expander("تفاصيل"):
                    st.write(f"**النوع:** {e.get('event_type', '')}")
                    st.write(f"**الموقع:** {e.get('location', '')}")
                
                st.markdown("---")
        else:
            st.info("لا توجد فعاليات ماضية.")

    # Add Event Form
    st.markdown("---")
    st.subheader("➕ إضافة فعالية جديدة")
    
    with st.form("add_event_form"):
        event_name = st.text_input("اسم الفعالية*")
        event_type = st.selectbox("نوع الفعالية", EVENT_TYPES)
        event_date = st.date_input("تاريخ الفعالية", get_cairo_now().date() + timedelta(days=7))
        event_time = st.text_input("وقت الفعالية", "7:00 م")
        location = st.text_input("الموقع")
        max_capacity = st.number_input("السعة القصوى", 1, 1000, 100)
        description = st.text_area("الوصف")
        
        if st.form_submit_button("إضافة الفعالية"):
            if not event_name:
                st.error("اسم الفعالية مطلوب")
            else:
                db.add_event({
                    "event_id": str(uuid.uuid4()),
                    "event_name": sanitize_input(event_name),
                    "event_type": event_type,
                    "event_date": event_date.strftime("%Y-%m-%d"),
                    "event_time": event_time,
                    "location": sanitize_input(location),
                    "max_capacity": str(max_capacity),
                    "description": sanitize_input(description),
                    "created_by": user.get("user_id", ""),
                    "is_active": "True",
                    "created_at": get_cairo_now().isoformat()
                })
                st.success(f"✅ تم إضافة الفعالية: {event_name}")
                time.sleep(1)
                st.rerun()

def show_events_reports(db):
    """Display events reports page."""
    st.markdown("<h2 class='main-header'>📊 تقارير الفعاليات</h2>", unsafe_allow_html=True)

    events = db.get_events()
    rsvps = db.get_event_rsvp()
    attendance = db.get_attendance()

    if events.empty:
        st.info("لا توجد فعاليات.")
        return

    month = st.selectbox("اختر الشهر", range(1, 13), index=get_cairo_now().month-1, key="events_report_month")
    year = st.number_input("السنة", value=get_cairo_now().year, min_value=2020, key="events_report_year")

    if not events.empty and "event_date" in events.columns:
        events_copy = events.copy()
        events_copy["event_month"] = pd.to_datetime(events_copy["event_date"], errors="coerce").dt.month
        events_copy["event_year"] = pd.to_datetime(events_copy["event_date"], errors="coerce").dt.year
        month_events = events_copy[(events_copy.event_month == month) & (events_copy.event_year == year)]

        if not month_events.empty:
            st.subheader(f"📅 الفعاليات لشهر {month}/{year}")
            for _, e in month_events.iterrows():
                eid = e.get("event_id", "")
                event_rsvps = rsvps[rsvps.event_id == eid] if not rsvps.empty else pd.DataFrame()
                going = len(event_rsvps[event_rsvps.status == "سأحضر"]) if not event_rsvps.empty else 0
                arrived = len(attendance[attendance.notes.str.contains(e.get("event_name", ""), na=False)]) if not attendance.empty and "notes" in attendance.columns else 0
                st.write(f"**{e.get('event_name', '')}**: {arrived} / {going} احضرفوا")
            st.markdown("---")

    if not events.empty and not rsvps.empty:
        st.subheader("🏆 أكثر الفعاليات حضوراً")
        attendance_counts = {}
        for _, e in events.iterrows():
            eid = e.get("event_id", "")
            event_rsvps = rsvps[(rsvps.event_id == eid) & (rsvps.status == "سأحضر")]
            going = len(event_rsvps)
            arrived = len(attendance[attendance.notes.str.contains(e.get("event_name", ""), na=False)]) if not attendance.empty and "notes" in attendance.columns else 0
            if going > 0:
                attendance_counts[e.get("event_name", "")] = arrived
        if attendance_counts:
            sorted_events = sorted(attendance_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            for name, count in sorted_events:
                st.write(f"{name}: {count}")
        st.markdown("---")

    if not events.empty:
        st.subheader("📊 مقارنة أنواع الفعاليات")
        type_counts = events.groupby("event_type").size().reset_index(name="count")
        st.dataframe(type_counts)

# =============================================================================
# SECTION 20: Main Application Entry Point
# نقطة الدخول الرئيسية
# =============================================================================

def main():
    """
    Main application entry point.
    Orchestrates authentication, routing, and page rendering.
    """
    inject_css()
    init_session()
    init_data_cache()

    # Initialize database connection
    if 'db_instance' not in st.session_state:
        try:
            creds = get_credentials()
            st.session_state.db_instance = Database(creds, get_spreadsheet_id())
        except Exception as e:
            st.error(f"❌ خطأ في الاتصال: {e}")
            st.stop()

    db = st.session_state.db_instance
    jwt_secret = get_jwt_secret()

    # Help button (floating)
    st.markdown('<div class="help-float-container"></div>', unsafe_allow_html=True)
    if st.button("🆘 مركز المساعدة", key="fixed_help_btn"):
        st.session_state.open_help_dialog = True
        st.rerun()

    # Quiz state check
    if st.session_state.student_quiz_started:
        st.info("وضع الاختبار للطالبات - قيد التطوير")
    else:
        # Authentication check
        if not st.session_state.authenticated:
            show_login_page(db, jwt_secret)
        else:
            # Token validation
            token_data = verify_token(st.session_state.token, jwt_secret)
            if not token_data:
                st.error("⏰ انتهت صلاحية الجلسة.")
                st.session_state.clear()
                time.sleep(2)
                st.rerun()
                return

            # Data validation
            if not st.session_state.get("data_validated"):
                errors = validate_data_integrity(db)
                st.session_state.data_errors = errors
                st.session_state.data_validated = True

            # Page routing
            role = st.session_state.user.get("role", "")
            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
            
            # Route to appropriate page
            if choice == "🏠 لوحة التحكم":
                st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
                st.info("مرحباً بك في لوحة التحكم")
            elif choice == "📅 الفعاليات":
                show_events(db)
            elif choice == "📊 التقارير والإحصائيات":
                show_events_reports(db)
            else:
                st.info(f"الصفحة قيد التطوير: {choice}")
            
            st.markdown("</div>", unsafe_allow_html=True)

    # Help dialog
    if st.session_state.get("open_help_dialog"):
        show_help_dialog()
        st.session_state.open_help_dialog = False

if __name__ == "__main__":
    main()
