import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas
def show_quick_checkin(db: Database):
    """Quick attendance check-in with search autocomplete and QR scanner with overlays."""
    st.markdown("<h2 class='main-header'>⚡ تسجيل حضور سريع</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")

    if role == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور.")
        return

    # Initialize session state for QR scanner
    if 'qr_scan_image' not in st.session_state:
        st.session_state.qr_scan_image = None
    if 'qr_scan_result' not in st.session_state:
        st.session_state.qr_scan_result = None
    if 'qr_confirmed' not in st.session_state:
        st.session_state.qr_confirmed = False

    students_df = db.get_students()
    if students_df.empty:
        st.info("لا توجد طالبات مسجلات.")
        return

    # Filter by section for teachers
    if role == "Teacher" and section_id:
        if "section_id" in students_df.columns:
            students_df = students_df[students_df.section_id == section_id]

    if students_df.empty:
        st.info("لا توجد طالبات في فصلك.")
        return

    sections = db.get_sections()
    if not sections.empty and "section_id" in students_df.columns and "section_id" in sections.columns:
        students_df = students_df.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
    else:
        students_df["section_name"] = ""

    # ===== Tabs: Manual Check-in & QR Scanner =====
    tab1, tab2 = st.tabs(["⌨️ تسجيل يدوي", "📷 مسح QR Code"])

    # ===== Tab 1: Manual Check-in =====
    with tab1:
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        search_term = st.text_input("🔍 بحث بالاسم", placeholder="اكتب اسم الطالبة...", key="quick_checkin_search")
        st.markdown('</div>', unsafe_allow_html=True)

        if search_term:
            filtered = students_df[students_df["full_name"].astype(str).str.contains(search_term, na=False, case=False)]
            if not filtered.empty:
                selected_student = st.selectbox(
                    "اختر الطالبة",
                    filtered["student_id"].tolist(),
                    format_func=lambda x: filtered[filtered.student_id == x]["full_name"].values[0],
                    key="selected_student_checkin_manual"
                )

                if selected_student:
                    student_row = filtered[filtered.student_id == selected_student].iloc[0]
                    name = student_row.get("full_name", "")
                    sid = selected_student

                    avatar_color = get_avatar_color(name)
                    first_letter = name[0] if name else "?"

                    st.markdown(f"""
                    <div style="display:flex; align-items:center; gap:1rem; padding:1rem; background:var(--card-bg); border-radius:12px; margin:1rem 0;">
                        <div class="member-avatar" style="background:{avatar_color};">{first_letter}</div>
                        <div style="flex:1;">
                            <div style="font-weight:700; font-size:1.1rem;">{name}</div>
                            <div style="font-size:0.85rem; color:var(--text-secondary);">{student_row.get('section_name', '') if student_row.get('section_name') else 'بدون خدمة'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ حضور", use_container_width=True, type="primary", key="quick_present_manual"):
                            today_str = get_cairo_now().strftime("%Y-%m-%d")
                            existing = db.get_attendance_by_date_section(today_str, student_row.get("section_id", ""))
                            
                            record_id = str(uuid.uuid4())
                            if not existing.empty and sid in existing["student_id"].values:
                                record_id = existing[existing.student_id == sid]["record_id"].values[0]
                            
                            db.batch_add_attendance([{
                                "record_id": record_id, "date": today_str, "student_id": sid,
                                "status": "حاضر", "notes": "تسجيل سريع", "recorded_by": user.get("user_id", ""),
                                "section_id": student_row.get("section_id", "")
                            }])
                            db.add_log(user.get("user_id", ""), f"تسجيل حضور سريع - {name}")
                            st.success(f"✅ تم تسجيل حضور {name}")
                            st.toast(f"✅ تم تسجيل حضور {name}!", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                    with col2:
                        if st.button("❌ غياب", use_container_width=True, key="quick_absent_manual"):
                            today_str = get_cairo_now().strftime("%Y-%m-%d")
                            existing = db.get_attendance_by_date_section(today_str, student_row.get("section_id", ""))
                            
                            record_id = str(uuid.uuid4())
                            if not existing.empty and sid in existing["student_id"].values:
                                record_id = existing[existing.student_id == sid]["record_id"].values[0]
                            
                            db.batch_add_attendance([{
                                "record_id": record_id, "date": today_str, "student_id": sid,
                                "status": "غائب", "notes": "تسجيل سريع", "recorded_by": user.get("user_id", ""),
                                "section_id": student_row.get("section_id", "")
                            }])
                            db.add_log(user.get("user_id", ""), f"تسجيل غياب سريع - {name}")
                            st.warning(f"❌ تم تسجيل غياب {name}")
                            st.toast(f"❌ تم تسجيل غياب {name}", icon="⚠️")
                            time.sleep(0.5)
                            st.rerun()

    # ===== Tab 2: QR Scanner (NEW RELIABLE IMPLEMENTATION) =====
    with tab2:
        st.markdown("#### 📷 مسح QR Code")
        st.info("📱 وجّه الكاميرا نحو QR Code الطالبة")
        
        # Camera input - this is the most reliable way in Streamlit
        camera_image = st.camera_input("📸 التقط صورة QR Code", key="qr_camera_input")
        
        if camera_image is not None:
            # Process the image
            from PIL import Image
            import numpy as np
            
            try:
                image = Image.open(camera_image)
                
                # Check if OpenCV is available
                if CV2_AVAILABLE:
                    # Convert to OpenCV format
                    opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
                    detector = cv2.QRCodeDetector()
                    qr_data, bbox, _ = detector.detectAndDecode(opencv_image)
                else:
                    # Try to use jsQR via HTML component would require separate implementation
                    # For now, just show the image
                    qr_data = None
                
                if qr_data and qr_data.strip():
                    # Parse QR data
                    parts = qr_data.split('\n')
                    qr_name = ""
                    qr_id = ""
                    
                    for part in parts:
                        trimmed = part.strip()
                        if trimmed.startswith("Member:"):
                            qr_name = trimmed.replace("Member:", "").strip()
                        elif trimmed.startswith("ID:"):
                            qr_id = trimmed.replace("ID:", "").strip()
                    
                    # Validate QR code
                    validation = validate_qr_code(db, qr_data, students_df)
                    
                    if not validation['valid']:
                        st.markdown(f"""
                        <div style="text-align:center; padding:1.5rem; background:rgba(220,53,69,0.1); border:2px solid #dc3545; border-radius:15px; margin:1rem 0;">
                            <div style="font-size:3rem; margin-bottom:0.5rem;">❌</div>
                            <div style="font-size:1.2rem; font-weight:700; color:#dc3545;">{validation['message']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        log_details_operation(
                            db=db, student_id=qr_id, student_name=qr_name,
                            status="Invalid", operation_type="QR_Scan_Failed",
                            qr_data=qr_data, device_info="Camera Input",
                            notes=validation['message']
                        )
                    else:
                        student_id = validation['student_id']
                        student_name = validation['student_name']
                        section_id_val = validation['section_id']
                        today_str = get_cairo_now().strftime("%Y-%m-%d")
                        
                        # Get section name
                        section_name = ""
                        if not sections.empty and section_id_val in sections["section_id"].values:
                            section_name = sections[sections.section_id == section_id_val]["section_name"].values[0]
                        
                        # Check for duplicate
                        is_duplicate = check_duplicate_attendance(db, student_id, today_str)
                        
                        if is_duplicate:
                            avatar_color = get_avatar_color(student_name)
                            first_letter = student_name[0] if student_name else "?"
                            st.markdown(f"""
                            <div style="text-align:center; padding:1.5rem; background:rgba(255,193,7,0.1); border:2px solid #ffc107; border-radius:15px; margin:1rem 0;">
                                <div style="font-size:3rem; margin-bottom:0.5rem;">⚠️</div>
                                <div style="display:flex; align-items:center; gap:1rem; justify-content:center; margin-bottom:0.5rem;">
                                    <div class="member-avatar" style="background:{avatar_color};">{first_letter}</div>
                                    <div style="text-align:right;">
                                        <div style="font-size:1.2rem; font-weight:700;">{student_name}</div>
                                        <div style="font-size:0.9rem; color:#666;">{section_name if section_name else 'بدون خدمة'}</div>
                                    </div>
                                </div>
                                <div style="font-size:1.1rem; font-weight:600; color:#d4a017;">تم تسجيل حضور {student_name} مسبقاً اليوم!</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # Show confirmation and auto-register
                            avatar_color = get_avatar_color(student_name)
                            first_letter = student_name[0] if student_name else "?"
                            now_time = get_cairo_now().strftime("%I:%M %p")
                            
                            st.markdown(f"""
                            <div style="text-align:center; padding:1.5rem; background:rgba(40,167,69,0.08); border:2px solid #28a745; border-radius:15px; margin:1rem 0;">
                                <div style="font-size:2rem; margin-bottom:0.8rem;">✅</div>
                                <div style="display:flex; align-items:center; gap:1rem; justify-content:center; margin-bottom:0.8rem; flex-wrap:wrap;">
                                    <div class="member-avatar" style="background:{avatar_color}; width:64px; height:64px; font-size:1.8rem;">{first_letter}</div>
                                    <div style="text-align:right;">
                                        <div style="font-size:1.4rem; font-weight:700;">{student_name}</div>
                                        <div style="font-size:1rem; color:#667eea; font-weight:600;">🏫 {section_name if section_name else 'بدون خدمة'}</div>
                                    </div>
                                </div>
                                <div style="background:var(--card-bg); border-radius:10px; padding:0.8rem; margin:0.5rem 0;">
                                    <div style="font-size:0.95rem; color:var(--text-secondary);">
                                        📅 التاريخ: {get_cairo_now().strftime("%Y-%m-%d")} | 🕐 الوقت: {now_time}
                                    </div>
                                    <div style="font-size:0.95rem; color:var(--text-secondary); margin-top:0.2rem;">
                                        ✅ الحالة: <span style="color:#28a745; font-weight:700;">حاضر</span>
                                    </div>
                                </div>
                                <div style="font-size:1rem; color:#28a745; margin-top:0.5rem; font-weight:700;">تم تسجيل الحضور تلقائياً!</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Auto-register after confirmation display
                            record_id = str(uuid.uuid4())
                            db.batch_add_attendance([{
                                "record_id": record_id, "date": today_str, "student_id": student_id,
                                "status": "حاضر", "notes": "تسجيل حضور عن طريق QR Code (كاميرا)",
                                "recorded_by": user.get("user_id", ""), "section_id": section_id_val
                            }])
                            db.add_log(user.get("user_id", ""), f"تسجيل حضور QR Code - {student_name}")
                            log_details_operation(
                                db=db, student_id=student_id, student_name=student_name,
                                status="Present", operation_type="QR_Checkin_Camera",
                                qr_data=qr_data, device_info="Camera Input",
                                notes="تم التسجيل تلقائياً من الكاميرا"
                            )
                            
                            st.success(f"✅ تم تسجيل حضور {student_name} بنجاح")
                            st.toast(f"✅ تم تسجيل حضور {student_name}!", icon="🎉")
                            
                            # Clear camera input for next scan
                            time.sleep(1)
                            st.session_state.qr_camera_input = None
                            st.rerun()
                else:
                    st.warning("QR Code غير مقروء. حاول مرة أخرى.")
                    
            except Exception as e:
                st.error(f"خطأ في معالجة الصورة: {str(e)}")

        elif CV2_AVAILABLE:
            st.markdown('<div class="filter-container">', unsafe_allow_html=True)
            st.markdown("##### 📸 التصوير باستخدام الكاميرا")
            st.markdown("انقر على زر التصوير أعلاه للمسح")
            st.markdown('</div>', unsafe_allow_html=True)

    # ===== Today's Attendance Table =====
    st.markdown("---")
    st.subheader("📋 جدول الحاضرين اليوم")
    today_attendance_all = db.get_attendance()
    today_att = pd.DataFrame()
    if not today_attendance_all.empty and "date" in today_attendance_all.columns:
        today_str_display = get_cairo_now().strftime("%Y-%m-%d")
        today_att = today_attendance_all[today_attendance_all.date == today_str_display].copy()
        if not today_att.empty and "student_id" in today_att.columns and not students_df.empty:
            today_att = today_att.merge(students_df[["student_id", "full_name"]], on="student_id", how="left")
    if not today_att.empty:
        display_cols = ["full_name", "status", "notes"]
        if "time" in today_att.columns:
            display_cols.insert(2, "time")
        st.dataframe(today_att[display_cols], use_container_width=True)
    else:
        st.info("لا يوجد حضور مسجل اليوم")

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
from io import BytesIO, StringIO
import base64

try:
    import numpy as np
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    np = None

try:
    from PIL import Image
    PYPLACE_AVAILABLE = True
except ImportError:
    PYPLACE_AVAILABLE = False
    Image = None

# Note: pyzbar removed due to system library dependency (libzbar) not available on Streamlit Cloud
# Using a browser-based QR scanner instead

# Browser-based QR scanner fallback  
def decode_qr_from_image(image):
    """
    Decode QR code from a PIL Image using browser-based approach.
    Falls back to OpenCV if available, otherwise shows a message.
    """
    if CV2_AVAILABLE:
        try:
            import cv2
            import numpy as np
            gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(gray)
            if data:
                return data
        except Exception as e:
            pass
    return None

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
# نظام الصلاحيات والأمان
# =============================================================================
import hashlib
import os

def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    return hash_password(password) == hashed


def get_client_info():
    """Get client browser, OS, device type, and screen size from session state or request."""
    try:
        # Try to get from session state (set via JavaScript on login page)
        browser = st.session_state.get('client_browser', st.session_state.get('user_agent', 'Unknown'))
        os = st.session_state.get('client_os', 'Unknown')
        device_type = st.session_state.get('client_device', 'Desktop')
        screen_width = st.session_state.get('screen_width', 'Unknown')
        screen_height = st.session_state.get('screen_height', 'Unknown')
        
        # Parse browser from user agent if still unknown
        if browser == 'Unknown' or not browser:
            ua_string = st.session_state.get('user_agent', '')
            if ua_string:
                browser = _parse_browser(ua_string)
                os = _parse_os(ua_string)
        
        return {
            'browser': browser,
            'os': os,
            'device_type': device_type,
            'screen_width': screen_width,
            'screen_height': screen_height
        }
    except Exception:
        return {'browser': 'Unknown', 'os': 'Unknown', 'device_type': 'Desktop', 'screen_width': 'Unknown', 'screen_height': 'Unknown'}

def _parse_browser(user_agent):
    """Parse browser name from user agent string."""
    if not user_agent:
        return 'Unknown'
    ua_lower = user_agent.lower()
    if 'chrome' in ua_lower and 'edg' not in ua_lower:
        return 'Chrome'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        return 'Safari'
    elif 'firefox' in ua_lower:
        return 'Firefox'
    elif 'edg' in ua_lower:
        return 'Edge'
    elif 'opera' in ua_lower or 'opr' in ua_lower:
        return 'Opera'
    return 'Other'

def _parse_os(user_agent):
    """Parse OS from user agent string."""
    if not user_agent:
        return 'Unknown'
    ua_lower = user_agent.lower()
    if 'windows' in ua_lower:
        return 'Windows'
    elif 'mac' in ua_lower or 'ios' in ua_lower:
        return 'Mac/iOS'
    elif 'android' in ua_lower:
        return 'Android'
    elif 'linux' in ua_lower:
        return 'Linux'
    return 'Other'

def get_ip_address():
    """Get client IP address from session state or query params."""
    try:
        # Try to get from session state (set by JavaScript)
        stored_ip = st.session_state.get('client_ip', 'Unknown')
        if stored_ip and stored_ip != 'Unknown':
            return stored_ip
        # Try to get from query params (if passed from frontend)
        ip = st.query_params.get('ip', ['Unknown'])[0]
        if ip and ip != 'Unknown':
            return ip
        return 'Unknown'
    except Exception:
        return 'Unknown'

def mask_ip(ip: str) -> str:
    """Mask IP address for privacy (keep first 2 octets for IPv4)."""
    if not ip or ip in ['Unknown', 'Streamlit-Server']:
        return '***.***.***.***'
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.***.***"
    return '***.***.***.***'

def get_location_from_ip(ip: str) -> dict:
    """Get approximate location from IP address using free API."""
    if not ip or ip in ['Unknown', 'Streamlit-Server']:
        return {'country': 'Unknown', 'city': 'Unknown', 'region': 'Unknown'}
    
    try:
        # Using ipapi.co (free tier: 1000 requests/day)
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'country': data.get('country_name', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'region': data.get('region', 'Unknown')
            }
    except Exception:
        pass
    
    # Fallback if API fails
    return {'country': 'Unknown', 'city': 'Unknown', 'region': 'Unknown'}

def log_security_event(db, user_id, user_name, action, details=""):
    client_info = get_client_info()
    ip_address = get_ip_address()
    location = get_location_from_ip(ip_address)

    entry = {
        "log_id": str(uuid.uuid4()),
        "timestamp": get_cairo_now().isoformat(),
        "user_id": user_id,
        "user_name": user_name,
        "action": action,
        "details": details,
        "browser": client_info['browser'],
        "os": client_info['os'],
        "device_type": client_info['device_type'],
        "screen_size": f"{client_info['screen_width']}x{client_info['screen_height']}",
        "ip_masked": mask_ip(ip_address),
        "country": location['country'],
        "city": location['city'],
        "region": location['region']
    }

    df = db.get_logs()
    if df.empty:
        df = pd.DataFrame(columns=["log_id", "timestamp", "user_id", "user_name", "action", "details",
                                   "browser", "os", "device_type", "screen_size", "ip_masked",
                                   "country", "city", "region"])
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    if len(df) > 2000:
        df = df.tail(2000)
    db._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "user_name", "action", "details",
                                   "browser", "os", "device_type", "screen_size", "ip_masked",
                                   "country", "city", "region"])


def log_attendance_event(db, student_id, student_name, status, method="يدوي", recorded_by="", section_id=""):
    entry = {
        "record_id": str(uuid.uuid4()),
        "timestamp": get_cairo_now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": get_cairo_now().strftime("%Y-%m-%d"),
        "student_id": student_id,
        "student_name": student_name,
        "status": status,
        "method": method,
        "recorded_by": recorded_by,
        "section_id": section_id
    }

    df = db.get_attendance()
    if df.empty:
        df = pd.DataFrame(columns=["record_id", "timestamp", "date", "student_id", "student_name",
                                   "status", "method", "recorded_by", "section_id"])
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    if len(df) > 5000:
        df = df.tail(5000)
    db._df_to_sheet("Attendance", df, ["record_id", "timestamp", "date", "student_id", "student_name",
                                         "status", "method", "recorded_by", "section_id"])

def get_current_user_role():
    """Get current user's role from session."""
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        return st.session_state.user.get("role", "")
    return ""

def has_permission(required_role: str):
    """Check if current user has required permission."""
    current_role = get_current_user_role()
    if current_role == "Admin":
        return True
    return current_role == required_role

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
# CSS محسّن مع Dark/Light Mode ودعم Responsive
# =============================================================================
def inject_css():
    # Determine current theme
    theme = st.session_state.get("theme", "light")
    is_dark = (theme == "dark")
    
    # Theme colors
    if is_dark:
        bg_primary = "#0d1b2a"
        bg_secondary = "#1b2838"
        bg_card = "#1e3a5f"
        text_primary = "#f5f5f5"
        text_secondary = "#c0c0c0"
        sidebar_bg = "linear-gradient(180deg, #0d1b2a 0%, #1b2838 100%)"
        sidebar_border = "1px solid rgba(212,175,55,0.15)"
        card_bg = "rgba(30,58,95,0.85)"
        card_border = "1px solid rgba(212,175,55,0.1)"
        header_bg = "rgba(30,58,95,0.9)"
        gradient_start = "#0d1b2a"
        gradient_end = "#1b2838"
        metric_bg = "rgba(30,58,95,0.9)"
        metric_border = "1px solid rgba(212,175,55,0.2)"
        shadow_color = "rgba(0,0,0,0.3)"
        gold = "#d4af37"
        gold_light = "rgba(212,175,55,0.15)"
    else:
        bg_primary = "#f0f2f6"
        bg_secondary = "#f5f7fa"
        bg_card = "#ffffff"
        text_primary = "#1a1a2e"
        text_secondary = "#555555"
        sidebar_bg = "linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%)"
        sidebar_border = "1px solid rgba(0,0,0,0.08)"
        card_bg = "rgba(255,255,255,0.95)"
        card_border = "1px solid rgba(0,0,0,0.05)"
        header_bg = "rgba(255,255,255,0.9)"
        gradient_start = "#f5f7fa"
        gradient_end = "#e4e8ec"
        metric_bg = "rgba(255,255,255,0.95)"
        metric_border = "1px solid rgba(0,0,0,0.05)"
        shadow_color = "rgba(0,0,0,0.08)"
        gold = "#d4af37"
        gold_light = "rgba(212,175,55,0.1)"

    st.markdown(f"""
    <style>
        :root {{
            --bg-primary: {bg_primary};
            --bg-secondary: {bg_secondary};
            --bg-card: {bg_card};
            --text-primary: {text_primary};
            --text-secondary: {text_secondary};
            --sidebar-bg: {sidebar_bg};
            --sidebar-border: {sidebar_border};
            --card-bg: {card_bg};
            --card-border: {card_border};
            --header-bg: {header_bg};
            --gradient-start: {gradient_start};
            --gradient-end: {gradient_end};
            --metric-bg: {metric_bg};
            --metric-border: {metric_border};
            --shadow-color: {shadow_color};
            --gold: {gold};
            --gold-light: {gold_light};
        }}

        html, body, .stApp {{
            color-scheme: {"dark" if is_dark else "light"} !important;
        }}

        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * {{ font-family: 'Cairo', sans-serif; }}
        body {{ direction: rtl; text-align: right; background-color: var(--bg-primary); color: var(--text-primary); }}
        .stApp {{ background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%); }}
        header[data-testid="stHeader"] {{ display: none !important; }}
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}

        [data-testid="stSidebarNavToggle"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[aria-label*="Close sidebar"],
        button[aria-label*="Close"],
        [data-testid="baseButton-header"],
        [data-testid="stSidebarResizer"] {{
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
        }}

        section[data-testid="stSidebar"] {{
            position: fixed !important;
            top: 0 !important;
            right: 0 !important;
            height: 100vh !important;
            width: 300px !important;
            max-width: 100vw !important;
            z-index: 10000 !important;
            transition: transform 0.3s ease !important;
            box-shadow: -5px 0 15px var(--shadow-color);
            overflow-y: auto !important;
            margin: 0 !important;
            padding-top: 1rem !important;
            background: var(--sidebar-bg) !important;
            border-left: var(--sidebar-border) !important;
            transform: translateX(0);
        }}

        @media (max-width: 768px) {{
            section[data-testid="stSidebar"] {{
                width: 100vw !important;
            }}
        }}

        [data-testid="stSidebarOverlay"] {{
            display: none !important;
        }}

        [data-testid="stAppViewContainer"] > [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {{
            max-width: 100% !important;
            width: 100% !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
        }}

        /* ===== Theme Toggle Button ===== */
        .theme-toggle-btn .stButton > button {{
            width: 100% !important;
            text-align: center !important;
            padding: 0.6rem !important;
            font-size: 0.95rem !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            background: var(--gold-light) !important;
            color: var(--gold) !important;
            border: 1px solid var(--gold) !important;
            box-shadow: none !important;
            transition: all 0.3s ease !important;
        }}
        .theme-toggle-btn .stButton > button:hover {{
            background: var(--gold) !important;
            color: #1e3a5f !important;
            transform: scale(1.02) !important;
        }}

        /* ===== Quick Action Buttons ===== */
        .quick-action-btn .stButton > button {{
            width: 100% !important;
            text-align: center !important;
            padding: 0.7rem 0.5rem !important;
            font-size: 0.9rem !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 2px 8px rgba(102,126,234,0.3) !important;
            transition: all 0.2s ease !important;
        }}
        .quick-action-btn .stButton > button:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 15px rgba(102,126,234,0.5) !important;
        }}

        /* ===== Nav Buttons ===== */
        .nav-btn-container .stButton > button {{
            width: 100% !important;
            text-align: right !important;
            justify-content: flex-start !important;
            padding: 0.7rem 1rem !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            background: transparent !important;
            color: var(--text-primary) !important;
            border: 1px solid transparent !important;
            box-shadow: none !important;
            transition: all 0.2s ease !important;
            direction: rtl !important;
        }}
        .nav-btn-container .stButton > button:hover {{
            background: var(--gold-light) !important;
            color: var(--gold) !important;
            border-color: rgba(212,175,55,0.2) !important;
            transform: translateX(-2px) !important;
        }}
        .nav-btn-container .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 2px 8px rgba(102,126,234,0.3) !important;
        }}
        .nav-btn-container .stButton > button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%) !important;
            color: white !important;
            transform: translateX(-2px) !important;
        }}

        .floating-show-btn .stButton > button {{
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
        }}
        .floating-show-btn .stButton > button:hover {{
            transform: scale(1.08) !important;
            box-shadow: 0 6px 20px rgba(102,126,234,0.6) !important;
        }}

        .help-float-container .stButton > button {{
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
        }}
        .help-float-container .stButton > button:hover {{
            transform: scale(1.04) !important;
            box-shadow: 0 6px 20px rgba(243,156,18,0.5) !important;
        }}

        .main-header {{
            font-size: 2.2rem; font-weight: 700; color: var(--text-primary); text-align: center;
            margin-bottom: 1.5rem; padding: 1rem; background: var(--header-bg);
            border-radius: 15px; box-shadow: 0 4px 12px var(--shadow-color);
            backdrop-filter: blur(5px); border: var(--card-border);
            margin-top: 100px;
        }}
        .card {{ background: var(--card-bg); border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px var(--shadow-color); margin-bottom: 1rem; transition: transform 0.2s; color: var(--text-primary); border: var(--card-border); }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px var(--shadow-color); }}
        .stButton > button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 8px; font-weight: 600;
            transition: all 0.2s; box-shadow: 0 2px 8px rgba(102,126,234,0.3);
        }}
        .stButton > button:hover {{ transform: scale(1.02); box-shadow: 0 5px 15px rgba(102,126,234,0.4); }}
        .stRadio > div, .stSelectbox > div, .stMultiSelect > div {{ direction: rtl; }}
        .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput {{ text-align: right; }}
        .content-area {{ padding: 0 1rem; }}

        .stDataFrame {{ background: var(--card-bg); border-radius: 10px; box-shadow: 0 2px 8px var(--shadow-color); color: var(--text-primary); }}
        .streamlit-expanderHeader {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important; border-radius: 8px; font-weight: 600;
        }}
        .stForm {{ background: var(--card-bg); padding: 20px; border-radius: 15px; box-shadow: 0 4px 12px var(--shadow-color); }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
        .stTabs [data-baseweb="tab"] {{
            background: rgba(102,126,234,0.1); border-radius: 8px 8px 0 0;
            padding: 10px 20px; font-weight: 600; color: #667eea;
            border: 1px solid rgba(102,126,234,0.2); border-bottom: none;
        }}
        .stTabs [aria-selected="true"] {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; color: white !important; }}
        .stSuccess {{ background: rgba(40,167,69,0.1); border: 1px solid rgba(40,167,69,0.2); color: #155724; border-radius: 10px; }}
        .stError {{ background: rgba(220,53,69,0.1); border: 1px solid rgba(220,53,69,0.2); color: #721c24; border-radius: 10px; }}

        iframe[title="st_components.html"] {{
            border: none !important;
            background: transparent !important;
        }}

        /* ===== KPI Cards ===== */
        .kpi-card {{
            background: var(--metric-bg);
            border-radius: 16px;
            padding: 1.2rem 1rem;
            text-align: center;
            border: var(--metric-border);
            box-shadow: 0 4px 15px var(--shadow-color);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        .kpi-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 25px var(--shadow-color);
        }}
        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 16px 16px 0 0;
        }}
        .kpi-card .kpi-icon {{
            font-size: 2rem;
            margin-bottom: 0.3rem;
        }}
        .kpi-card .kpi-label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
            margin-bottom: 0.2rem;
        }}
        .kpi-card .kpi-value {{
            font-size: 2rem;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1.2;
        }}
        .kpi-card .kpi-sub {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.2rem;
        }}
        .kpi-card.gold::before {{
            background: linear-gradient(90deg, #d4af37, #f0d060);
        }}
        .kpi-card.green::before {{
            background: linear-gradient(90deg, #28a745, #48c868);
        }}
        .kpi-card.blue::before {{
            background: linear-gradient(90deg, #1e3a5f, #2a5a8f);
        }}
        .kpi-card.purple::before {{
            background: linear-gradient(90deg, #764ba2, #9b6fc0);
        }}

        /* ===== Sidebar Section Header ===== */
        .sidebar-section-header {{
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--gold);
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 0.5rem 0.5rem 0.3rem 0.5rem;
            border-bottom: 1px solid var(--gold-light);
            margin-top: 0.5rem;
            margin-bottom: 0.3rem;
        }}

        /* ===== Sidebar User Card ===== */
        .sidebar-user-card {{
            background: var(--gold-light);
            border-radius: 12px;
            padding: 0.8rem 1rem;
            margin-bottom: 0.5rem;
            border: 1px solid rgba(212,175,55,0.2);
            text-align: center;
        }}
        .sidebar-user-card .user-name {{
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-primary);
        }}
        .sidebar-user-card .user-role {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        /* ===== Responsive Design ===== */
        @media (max-width: 768px) {{
            .floating-show-btn .stButton > button {{
                width: 50px !important;
                height: 50px !important;
                font-size: 24px !important;
                top: 14px !important;
                right: 14px !important;
            }}
            .help-float-container .stButton > button {{
                right: 80px !important;
                top: 14px !important;
                padding: 10px 16px !important;
                font-size: 14px !important;
            }}
            .main-header {{ font-size: 1.6rem; margin-top: 110px; }}
            .kpi-card .kpi-value {{ font-size: 1.5rem; }}
            .kpi-card .kpi-icon {{ font-size: 1.5rem; }}
            .kpi-card {{ padding: 0.8rem 0.5rem; }}
        }}

        @media (max-width: 480px) {{
            .main-header {{ font-size: 1.3rem; margin-top: 100px; padding: 0.7rem; }}
            .kpi-card .kpi-value {{ font-size: 1.2rem; }}
            .kpi-card .kpi-icon {{ font-size: 1.2rem; }}
            .kpi-card {{ padding: 0.6rem 0.3rem; }}
            .kpi-card .kpi-label {{ font-size: 0.7rem; }}
            section[data-testid="stSidebar"] {{ width: 100vw !important; }}
        }}

        /* ===== Metric Customization ===== */
        div[data-testid="metric-container"] {{
            background: var(--metric-bg);
            border-radius: 16px;
            padding: 1rem;
            border: var(--metric-border);
            box-shadow: 0 4px 15px var(--shadow-color);
            transition: all 0.3s ease;
        }}
        div[data-testid="metric-container"]:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 25px var(--shadow-color);
        }}
        div[data-testid="metric-container"] > div:first-child {{
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            color: var(--text-secondary) !important;
        }}
        div[data-testid="metric-container"] > div:nth-child(2) {{
            font-size: 2rem !important;
            font-weight: 800 !important;
            color: var(--text-primary) !important;
        }}
        div[data-testid="metric-container"] > div:nth-child(3) {{
            font-size: 0.8rem !important;
            color: var(--text-secondary) !important;
        }}

        /* ===== Collapsible Sidebar Sections ===== */
        .sidebar-collapsible {{
            margin-bottom: 0.3rem;
        }}
        .sidebar-collapsible summary {{
            cursor: pointer;
            padding: 0.5rem;
            font-weight: 700;
            color: var(--gold);
            font-size: 0.85rem;
            border-radius: 8px;
            transition: all 0.2s;
            list-style: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .sidebar-collapsible summary:hover {{
            background: var(--gold-light);
        }}
        .sidebar-collapsible summary::-webkit-details-marker {{
            display: none;
        }}
        .sidebar-collapsible[open] summary {{
            margin-bottom: 0.3rem;
        }}

        /* ===== Member Cards & Avatar ===== */
        .member-card {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 1.2rem;
            border: var(--card-border);
            box-shadow: 0 4px 15px var(--shadow-color);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            height: 100%;
        }}
        .member-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 25px var(--shadow-color);
        }}
        .member-avatar {{
            width: 56px; height: 56px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.5rem; font-weight: 800; color: white;
            margin: 0 auto 0.5rem auto; flex-shrink: 0;
            box-shadow: 0 3px 10px rgba(0,0,0,0.15);
        }}
        .member-avatar-sm {{
            width: 40px; height: 40px; font-size: 1.1rem;
        }}
        .status-badge {{
            display: inline-block; padding: 0.2rem 0.8rem; border-radius: 20px;
            font-size: 0.75rem; font-weight: 700; text-align: center;
            min-width: 70px;
        }}
        .status-badge.active {{ background: rgba(40,167,69,0.15); color: #28a745; border: 1px solid rgba(40,167,69,0.3); }}
        .status-badge.inactive {{ background: rgba(220,53,69,0.15); color: #dc3545; border: 1px solid rgba(220,53,69,0.3); }}
        .status-badge.newcomer {{ background: rgba(255,193,7,0.15); color: #d4a017; border: 1px solid rgba(255,193,7,0.3); }}
        .status-badge.leader {{ background: rgba(102,126,234,0.15); color: #667eea; border: 1px solid rgba(102,126,234,0.3); }}

        /* ===== Member Grid ===== */
        .member-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        @media (max-width: 768px) {{
            .member-grid {{
                grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
                gap: 0.8rem;
            }}
        }}
        @media (max-width: 480px) {{
            .member-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* ===== Member Detail Row ===== */
        .member-detail-row {{
            display: flex; align-items: center; gap: 0.5rem;
            padding: 0.3rem 0; font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        .member-detail-row .label {{
            font-weight: 600; color: var(--text-primary); min-width: 70px;
        }}

        /* ===== Filter Section ===== */
        .filter-container {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1rem;
            border: var(--card-border);
            margin-bottom: 1rem;
        }}

        /* ===== Bulk Action Bar ===== */
        .bulk-action-bar {{
            background: var(--gold-light);
            border-radius: 12px;
            padding: 0.8rem 1rem;
            border: 1px solid rgba(212,175,55,0.2);
            margin-bottom: 1rem;
            display: flex; align-items: center; gap: 0.8rem;
            flex-wrap: wrap;
        }}

        /* ===== Toast Custom Colors ===== */
        .stAlert {{
            border-radius: 10px !important;
        }}
        div[data-testid="stAlertContainer"] > div:has(> div > svg[color="#28a745"]) {{
            background: rgba(40,167,69,0.12) !important;
            border: 1px solid rgba(40,167,69,0.3) !important;
        }}
        div[data-testid="stAlertContainer"] > div:has(> div > svg[color="#dc3545"]) {{
            background: rgba(220,53,69,0.12) !important;
            border: 1px solid rgba(220,53,69,0.3) !important;
        }}
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
    _details_lock = threading.Lock()

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
    
    def _ensure_details_sheet(self):
        """Ensure 'Details' sheet exists with proper headers."""
        try:
            ws = self.spreadsheet.worksheet("Details")
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title="Details", rows=1000, cols=8)
            ws.append_row([
                "Timestamp", "ID", "Name", "Status", "Operation_Type",
                "QR_Data", "Device_Info", "Notes"
            ])

    def __init__(self, creds, spreadsheet_id):
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        self._ensure_required_sheets()

    def _ensure_required_sheets(self):
        """Ensure all required sheets exist with proper headers."""
        sheets_config = {
            "Logs": ["log_id", "timestamp", "user_id", "user_name", "action", "details",
                     "browser", "os", "device_type", "screen_size", "ip_masked",
                     "country", "city", "region"],
            "Attendance": ["record_id", "timestamp", "date", "student_id", "student_name",
                          "status", "method", "recorded_by", "section_id"],
            "Events": ["event_id", "event_name", "event_date", "location", "event_type",
                       "description", "max_attendees", "created_by", "created_at"],
            "EventRSVPs": ["rsvp_id", "event_id", "student_id", "student_name",
                           "rsvp_status", "rsvp_date", "actual_attendance"]
        }
        for sheet_name, columns in sheets_config.items():
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
                # Verify sheet has headers
                try:
                    existing_headers = ws.get_all_values()[0] if ws.get_all_values() else []
                    if not existing_headers or len(existing_headers) == 0:
                        ws.append_row(columns)
                except (IndexError, gspread.exceptions.APIError):
                    # If we can't read headers, try to append them
                    try:
                        ws.append_row(columns)
                    except:
                        pass
            except gspread.WorksheetNotFound:
                try:
                    ws = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(columns))
                    ws.append_row(columns)
                except Exception as e:
                    print(f"Error creating sheet {sheet_name}: {e}")

    def _get_or_create_worksheet(self, name, columns):
        """Get or create worksheet with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                Database._rate_limit()
                try:
                    ws = self.spreadsheet.worksheet(name)
                except gspread.WorksheetNotFound:
                    try:
                        ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=max(len(columns), 1) if columns else 1)
                        if columns:
                            ws.append_row(columns)
                    except Exception as e:
                        print(f"Error creating worksheet {name}: {e}")
                        raise
                time.sleep(0.2)
                return ws
            except gspread.exceptions.APIError as e:
                if attempt < max_retries - 1:
                    delay = 2 * (2 ** attempt)
                    print(f"API Error accessing worksheet {name}, retrying in {delay}s... (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    print(f"Failed to access worksheet {name} after {max_retries} attempts")
                    raise
        return None

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
        """Read sheet data with retry logic and error handling."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
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
            except gspread.exceptions.APIError as e:
                if attempt < max_retries - 1:
                    delay = 2 * (2 ** attempt)  # Exponential backoff: 2s, 4s
                    print(f"API Error reading {sheet_name}, retrying in {delay}s... (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                else:
                    print(f"Failed to read sheet {sheet_name} after {max_retries} attempts: {e}")
                    return pd.DataFrame()
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"Error reading sheet {sheet_name}: {e}")
                    return pd.DataFrame()
        return pd.DataFrame()

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

    # --- AuditLog (Google Sheets) for persistent security logging ---
    def get_audit_logs_sheet(self):
        return self._sheet_to_df("AuditLog")

    def add_audit_log_sheet(self, entry: dict):
        """Save audit log entry to Google Sheets for persistence on cloud."""
        df = self.get_audit_logs_sheet()
        if df.empty:
            df = pd.DataFrame(columns=["timestamp", "user_id", "user_name", "action", "details",
                                       "browser", "os", "device_type", "screen_size", "ip_masked",
                                       "country", "city", "region", "privacy_consent"])
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        # Keep only last 2000 records
        if len(df) > 2000:
            df = df.tail(2000)
        self._df_to_sheet("AuditLog", df, ["timestamp", "user_id", "user_name", "action", "details",
                                           "browser", "os", "device_type", "screen_size", "ip_masked",
                                           "country", "city", "region", "privacy_consent"])

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
        "theme": "light",
        "user_agent": "",
        "screen_width": "Unknown",
        "screen_height": "Unknown"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout(db=None):
    if db and st.session_state.user:
        try:
            log_security_event(db, 
                           st.session_state.user.get("user_id", ""), 
                           st.session_state.user.get("full_name", ""), 
                           "تسجيل الخروج", 
                           "خروج من النظام")
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
            name = st.text_input( "الاسم *", placeholder="أدخل اسمك الكامل")
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
                "user_id": "admin-001", "username": "admin", "password": hash_password("admin123"),
                "role": "System Admin", "full_name": "مدير النظام",
                "section_id": "", "phone": "0100000000", "email": "admin@church.com"
            }
            db.add_user(admin_data)
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.toast("✅ تم إنشاء مدير النظام بنجاح!", icon="🎉")
            st.info("**اسم المستخدم:** `admin`\n\n**كلمة المرور:** `admin123`")
            time.sleep(2)
            st.rerun()
        st.stop()

def show_login_page(db: Database, jwt_secret: str):
    st.markdown("<h1 class='main-header'>⛪ <br>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
    show_initialization(db)
    
    # Read client info from query params and store in session state
    try:
        query_params = st.query_params
        if 'browser' in query_params:
            st.session_state['client_browser'] = query_params['browser']
        if 'os' in query_params:
            st.session_state['client_os'] = query_params['os']
        if 'device' in query_params:
            st.session_state['client_device'] = query_params['device']
        if 'width' in query_params:
            st.session_state['screen_width'] = query_params['width']
        if 'height' in query_params:
            st.session_state['screen_height'] = query_params['height']
        if 'ip' in query_params:
            st.session_state['client_ip'] = query_params['ip']
    except Exception:
        pass
    
    # Capture browser, device info AND REAL CLIENT IP via JavaScript
    st.markdown("""
    <script>
    (function() {
        try {
            // Get browser info
            const ua = navigator.userAgent;
            let browser = 'Unknown';
            if (ua.indexOf('Chrome') > -1 && ua.indexOf('Edg') === -1) browser = 'Chrome';
            else if (ua.indexOf('Safari') > -1 && ua.indexOf('Chrome') === -1) browser = 'Safari';
            else if (ua.indexOf('Firefox') > -1) browser = 'Firefox';
            else if (ua.indexOf('Edg') > -1) browser = 'Edge';
            else if (ua.indexOf('Opera') > -1 || ua.indexOf('OPR') > -1) browser = 'Opera';
            
            // Get OS
            let os = 'Unknown';
            if (ua.indexOf('Windows') > -1) os = 'Windows';
            else if (ua.indexOf('Mac') > -1 || ua.indexOf('iOS') > -1) os = 'Mac/iOS';
            else if (ua.indexOf('Android') > -1) os = 'Android';
            else if (ua.indexOf('Linux') > -1) os = 'Linux';
            
            // Get device type
            let device = 'Desktop';
            if (ua.indexOf('Mobile') > -1 || ua.indexOf('Android') > -1) device = 'Mobile';
            else if (ua.indexOf('Tablet') > -1 || (ua.indexOf('iPad') > -1)) device = 'Tablet';
            
            // Get screen size
            const width = window.screen.width;
            const height = window.screen.height;
            
            // Store in sessionStorage for retrieval
            sessionStorage.setItem('client_browser', browser);
            sessionStorage.setItem('client_os', os);
            sessionStorage.setItem('client_device', device);
            sessionStorage.setItem('screen_width', width);
            sessionStorage.setItem('screen_height', height);
            
            // Fetch real client IP and then update query params
            fetch('https://api.ipify.org?format=json')
                .then(res => res.json())
                .then(data => {
                    const clientIP = data.ip || 'Unknown';
                    sessionStorage.setItem('client_ip', clientIP);
                    
                    // Update query params with all data including real IP
                    const params = new URLSearchParams(window.location.search);
                    params.set('browser', browser);
                    params.set('os', os);
                    params.set('device', device);
                    params.set('width', width);
                    params.set('height', height);
                    params.set('ip', clientIP);
                    window.history.replaceState({}, '', '?' + params.toString());
                })
                .catch(err => {
                    console.error('Error fetching IP:', err);
                    // Still update params without IP
                    const params = new URLSearchParams(window.location.search);
                    params.set('browser', browser);
                    params.set('os', os);
                    params.set('device', device);
                    params.set('width', width);
                    params.set('height', height);
                    window.history.replaceState({}, '', '?' + params.toString());
                });
        } catch(e) {
            console.error('Error capturing client info:', e);
        }
    })();
    </script>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])
    with tab1:
        st.warning("""
        ⚠️ **تنبيه هام - سياسة الأمان والخصوصية**
        
        عند تسجيل الدخول، يقوم النظام تلقائياً بتسجيل:
        - عنوان IP (مشفر)
        - نوع المتصفح ونظام التشغيل
        - نوع الجهاز
        
        هذه البيانات تستخدم **لأغراض أمنية فقط** لحماية النظام ومراقبة النشاط المشبوه.
        """)
        
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم").strip()
            password = st.text_input("كلمة المرور", type="password").strip()
            st.markdown("---")
            if st.form_submit_button("🔐 تسجيل الدخول", use_container_width=True, type="primary"):
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
                            # Verify password (support both hashed and plain text for migration)
                            stored_password = user.get("password", "")
                            password_valid = False
                            if len(stored_password) == 64:  # Hashed password (SHA256 = 64 chars)
                                password_valid = verify_password(password, stored_password)
                            else:  # Plain text (legacy)
                                password_valid = (password == stored_password)
                            
                            if password_valid:
                                # Migrate password to hash if it's plain text
                                if len(stored_password) != 64:
                                    db.update_user(user.get("user_id", ""), {"password": hash_password(password)})
                                
                                token = generate_token(user, jwt_secret)
                                st.session_state.token = token
                                st.session_state.user = user
                                st.session_state.authenticated = True
                                st.session_state.menu_choice = "🏠 لوحة التحكم"
                                st.session_state.show_sidebar = True
                                # Disabled automatic logging to prevent API errors
                                # db.add_log(user.get("user_id", ""), "تسجيل الدخول")
                                # log_security_event(db, user.get("user_id", ""), user.get("full_name", ""), "تسجيل الدخول", "دخول ناجح")
                                st.success("تم تسجيل الدخول بنجاح!")
                                st.toast("✅ مرحباً بك في النظام!", icon="👋")
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
                        except:
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
            st.toast("✅ تم تسليم الاختبار بنجاح!", icon="🎉")
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
# Sidebar Navigation محسّن
# =============================================================================
def show_sidebar_navigation(db: Database):
    with st.sidebar:
        # ===== Church Header =====
        st.markdown("""
        <div style="text-align:center; padding:0.5rem 0;">
            <span style="font-size:2rem;">⛪</span>
            <h3 style="margin:0.2rem 0; font-weight:700; color:var(--gold);">كنيسة الشهيدة دميانة</h3>
        </div>
        """, unsafe_allow_html=True)
        
        user = st.session_state.user
        
        # ===== User Card =====
        st.markdown(f"""
        <div class="sidebar-user-card">
            <div class="user-name">👤 {user.get('full_name', '')}</div>
            <div class="user-role">🔰 {user.get('role', '')}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # ===== Theme Toggle =====
        st.markdown('<div class="theme-toggle-btn">', unsafe_allow_html=True)
        current_theme = st.session_state.get("theme", "light")
        theme_label = "🌙 الوضع الليلي" if current_theme == "light" else "☀️ الوضع النهاري"
        if st.button(theme_label, key="theme_toggle_btn", use_container_width=True):
            st.session_state.theme = "dark" if current_theme == "light" else "light"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # ===== Quick Actions =====
        st.markdown('<div class="sidebar-section-header">⚡ إجراءات سريعة</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="quick-action-btn">', unsafe_allow_html=True)
        if st.button("➕ إضافة عضو سريع", key="quick_add_member", use_container_width=True):
            st.session_state.menu_choice = "👥 إدارة المستخدمين"
            st.session_state.show_sidebar = False
            st.rerun()
        if st.button("✅ تسجيل حضور اليوم", key="quick_attendance", use_container_width=True):
            st.session_state.menu_choice = "📋 الحضور"
            st.session_state.show_sidebar = False
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # ===== Navigation Sections =====
        role = user.get("role", "")
        menus = {
            "System Admin": [
                ("🏠", "لوحة التحكم"),
                ("👥", "إدارة المستخدمين"),
                ("🌟", "إدارة الأعضاء"),
                ("🏫", "إدارة المراحل"),
                ("⚡", "حضور سريع"),
                ("📋", "الحضور"),
                ("📈", "لوحة تحكم الحضور"),
                ("💬", "الافتقاد"),
                ("📝", "المسابقات والاختبارات"),
                ("📅", "الفعاليات"),
                ("📊", "التقارير والإحصائيات"),
                ("📜", "سجل العمليات"),
                ("🔒", "تغيير كلمة المرور")
            ],
            "Father Account": [
                ("🏠", "لوحة التحكم"),
                ("📅", "الفعاليات"),
                ("📊", "التقارير والإحصائيات"),
                ("🔒", "تغيير كلمة المرور")
            ],
            "Service Manager": [
                ("🏠", "لوحة التحكم"),
                ("👩‍🎓", "طالباتي"),
                ("💬", "الافتقاد"),
                ("📝", "المسابقات والاختبارات"),
                ("📅", "الفعاليات"),
                ("📊", "التقارير والإحصائيات"),
                ("🔒", "تغيير كلمة المرور")
            ],
            "Teacher": [
                ("🏠", "لوحة التحكم"),
                ("👩‍🎓", "طالباتي"),
                ("⚡", "حضور سريع"),
                ("📋", "الحضور"),
                ("📈", "لوحة تحكم الحضور"),
                ("💬", "الافتقاد"),
                ("🏆", "درجات المسابقات"),
                ("📅", "الفعاليات"),
                ("🔒", "تغيير كلمة المرور")
            ]
        }
        menu_items = menus.get(role, [])
        if not menu_items:
            st.warning("صلاحية غير معروفة")
            return None

        current_choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
        # Build full menu text for comparison
        menu_texts = [f"{icon} {label}" for icon, label in menu_items]
        if current_choice not in menu_texts:
            current_choice = menu_texts[0]
            st.session_state.menu_choice = current_choice

        # ===== Collapsible Navigation Sections =====
        # Main Menu
        st.markdown('<div class="sidebar-section-header">📌 القائمة الرئيسية</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="nav-btn-container">', unsafe_allow_html=True)
        for icon, label in menu_items:
            item_text = f"{icon} {label}"
            btn_type = "primary" if item_text == current_choice else "secondary"
            if st.button(item_text, key=f"nav_btn_{label}", use_container_width=True, type=btn_type):
                if item_text != current_choice:
                    st.session_state.menu_choice = item_text
                st.session_state.show_sidebar = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        
        # ===== Hide Sidebar & Logout =====
        if st.button("✕ إخفاء القائمة", key="hide_sidebar_btn", use_container_width=True):
            st.session_state.show_sidebar = False
            st.rerun()
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout_btn"):
            logout(db)

    return current_choice

# =============================================================================
# Dashboard محسّن مع KPI Cards متحركة
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
    
    # Calculate attendance percentage
    total_today = present_today + absent_today
    attendance_pct = round((present_today / total_today) * 100, 1) if total_today > 0 else 0
    
    # New members this month (students added this month)
    new_members = 0
    if not students.empty and "student_id" in students.columns:
        # Estimate new members as those with IDs created recently (simplified)
        new_members = len(students[students["status"] == "active"]) if "status" in students.columns else 0

    # ===== KPI Cards with Custom HTML =====
    st.markdown("""
    <style>
        .kpi-row {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
            direction: rtl;
        }
        .kpi-col {
            flex: 1;
            min-width: 180px;
        }
        @media (max-width: 768px) {
            .kpi-col {
                min-width: 140px;
                flex: 0 0 calc(50% - 0.5rem);
            }
        }
        @media (max-width: 480px) {
            .kpi-col {
                min-width: 100%;
                flex: 0 0 100%;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Animated counter effect using CSS animation
    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-col">
            <div class="kpi-card blue">
                <div class="kpi-icon">👩‍🎓</div>
                <div class="kpi-label">إجمالي الأعضاء</div>
                <div class="kpi-value" style="animation: countUp 1s ease-out;">{total_students}</div>
                <div class="kpi-sub">طالبة مسجلة</div>
            </div>
        </div>
        <div class="kpi-col">
            <div class="kpi-card green">
                <div class="kpi-icon">✅</div>
                <div class="kpi-label">الحضور اليوم</div>
                <div class="kpi-value">{present_today}</div>
                <div class="kpi-sub">من أصل {total_today} طالبة</div>
            </div>
        </div>
        <div class="kpi-col">
            <div class="kpi-card gold">
                <div class="kpi-icon">📈</div>
                <div class="kpi-label">نسبة الحضور</div>
                <div class="kpi-value">{attendance_pct}%</div>
                <div class="kpi-sub">نسبة حضور اليوم</div>
            </div>
        </div>
        <div class="kpi-col">
            <div class="kpi-card purple">
                <div class="kpi-icon">🌟</div>
                <div class="kpi-label">الأعضاء الجدد</div>
                <div class="kpi-value">{new_members}</div>
                <div class="kpi-sub">طالبة نشطة</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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
                        st.dataframe(section_scores.rename(columns={"section_name":"الفصل", "score":"متوسط الدرجات"}).set_index("الفصل"), use_container_width=True)

# =============================================================================
# إدارة المستخدمين (بما في ذلك إدارة المراحل)
# =============================================================================
def show_stages_management(db: Database):
    """صفحة منفصلة لإدارة المراحل"""
    st.markdown("<h2 class='main-header'>🏫 إدارة المراحل الدراسية</h2>", unsafe_allow_html=True)
    stages = db.get_stages()
    users = db.get_users()
    
    if not stages.empty:
        if not users.empty and "user_id" in users.columns and "full_name" in users.columns:
            stages_display = stages.merge(
                users[["user_id", "full_name"]].rename(columns={"user_id":"manager_user_id", "full_name":"المسؤول"}), 
                on="manager_user_id", how="left"
            )
        else:
            stages_display = stages.copy()
            stages_display["المسؤول"] = ""
        st.dataframe(stages_display[["stage_id", "stage_name", "المسؤول"]], use_container_width=True)
    else:
        st.info("لا توجد مراحل مسجلة بعد.")
    
    with st.expander("➕ إضافة مرحلة جديدة", expanded=False):
        with st.form("add_stage_form_standalone"):
            stage_name = st.text_input("اسم المرحلة*", placeholder="مثال: KG1, KG2, الصف الأول...")
            eligible_users = users[users.role.isin(["Service Manager", "Teacher", "Father Account", "System Admin"])] if not users.empty else pd.DataFrame()
            manager_id = ""
            if not eligible_users.empty:
                manager_choice = st.selectbox("مسؤول المرحلة (اختياري)", ["None"] + eligible_users["user_id"].tolist(),
                                              format_func=lambda x: "بدون" if x == "None" else eligible_users[eligible_users.user_id==x]["full_name"].values[0])
                manager_id = manager_choice if manager_choice != "None" else ""
            else:
                st.info("لا يوجد مستخدمون مؤهلون.")
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
                    st.toast("✅ تمت إضافة المرحلة بنجاح!", icon="🎉")
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
                st.toast("✅ تم تحديث المرحلة!", icon="✅")
                time.sleep(1)
                st.rerun()
            if col2.button("حذف المرحلة"):
                db.delete_stage(stage_sel)
                st.success("تم حذف المرحلة")
                st.toast("🗑️ تم حذف المرحلة", icon="⚠️")
                time.sleep(1)
                st.rerun()

def show_user_management(db: Database, active_tab: int = 0):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    sections = db.get_sections()
    stages = db.get_stages()
    students = db.get_students()
    
    # If a specific tab is requested, show only that tab's content
    if active_tab == 5:
        show_stages_management(db)
        return
    
    tab_names = ["الخدام", "المدرسات", "الطالبات", "أمناء الخدمة", "إدارة الفصول", "إدارة المراحل"]
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(tab_names)

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
                        st.toast("✅ تم إضافة المستخدم بنجاح!", icon="🎉")
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
                    st.toast("✅ تم تحديث بيانات المستخدم!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المستخدم", key="delete_user_btn"):
                    if selected_user_id == st.session_state.user.get("user_id"):
                        st.error("لا يمكنك حذف حسابك الحالي!")
                    else:
                        db.delete_user(selected_user_id)
                        st.success("تم الحذف")
                        st.toast("🗑️ تم حذف المستخدم", icon="⚠️")
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
                        st.toast("✅ تمت إضافة المدرسة بنجاح!", icon="🎉")
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
                        st.toast("✅ تمت إضافة الطالبة بنجاح!", icon="🎉")
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
                    st.toast("✅ تم تحديث بيانات الطالبة!", icon="✅")
                    time.sleep(1)
                    st.rerun()
        with st.expander("🗑️ حذف طالبة"):
            if not students.empty:
                delete_id = st.selectbox("اختر طالبة للحذف", students["student_id"], key="delete_student_sel")
                if st.button("تأكيد حذف الطالبة"):
                    db.delete_student(delete_id)
                    st.success("تم الحذف")
                    st.toast("🗑️ تم حذف الطالبة", icon="⚠️")
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
                        st.toast("✅ تمت إضافة الفصل بنجاح!", icon="🎉")
                        time.sleep(1)
                        st.rerun()
        with st.expander("🗑️ حذف فصل"):
            if not sections.empty:
                del_sec = st.selectbox("اختر فصل", sections["section_id"], key="del_section_sel")
                if st.button("تأكيد حذف الفصل"):
                    db.delete_section(del_sec)
                    st.success("تم الحذف")
                    st.toast("🗑️ تم حذف الفصل", icon="⚠️")
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
                        st.toast("✅ تمت إضافة المرحلة بنجاح!", icon="🎉")
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
                    st.toast("✅ تم تحديث المرحلة!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                if col2.button("حذف المرحلة"):
                    db.delete_stage(stage_sel)
                    st.success("تم حذف المرحلة")
                    st.toast("🗑️ تم حذف المرحلة", icon="⚠️")
                    time.sleep(1)
                    st.rerun()

# =============================================================================
# نظام إدارة الأعضاء المتقدم
# =============================================================================
def generate_qr_base64(data: str) -> str:
    """Generate a QR code image and return as base64 string."""
    try:
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

def get_avatar_color(name: str) -> str:
    """Generate a consistent color from a name."""
    colors = ["#667eea", "#28a745", "#d4af37", "#dc3545", "#17a2b8", "#e83e8c", "#fd7e14", "#6f42c1"]
    idx = sum(ord(c) for c in name) % len(colors)
    return colors[idx]

def get_status_badge_class(status: str) -> str:
    """Map status to CSS badge class."""
    mapping = {
        "active": "active", "Active": "active",
        "inactive": "inactive", "Inactive": "inactive",
        "newcomer": "newcomer", "Newcomer": "newcomer",
        "leader": "leader", "Leader": "leader"
    }
    return mapping.get(status, "active")

def get_status_label(status: str) -> str:
    """Get Arabic label for status."""
    mapping = {
        "active": "نشط", "Active": "نشط",
        "inactive": "غير نشط", "Inactive": "غير نشط",
        "newcomer": "جديد", "Newcomer": "جديد",
        "leader": "قائد", "Leader": "قائد"
    }
    return mapping.get(status, status)

def check_consecutive_absences(db, student_id, weeks=3):
    """Check if student was absent for N+ times in last 3 weeks."""
    attendance = db.get_attendance()
    if attendance.empty or "student_id" not in attendance.columns:
        return False
    
    student_att = attendance[attendance.student_id == student_id]
    if student_att.empty:
        return False
    
    if "date" in student_att.columns:
        student_att["date"] = pd.to_datetime(student_att["date"], errors="coerce")
    
    today = get_cairo_now()
    three_weeks_ago = today - timedelta(weeks=weeks)
    recent = student_att[student_att.date >= three_weeks_ago]
    
    if recent.empty:
        return False
    
    absent_count = len(recent[recent.status == "غائب"])
    return absent_count >= weeks

def get_students_needing_followup(db):
    """Get list of students with 3+ absences in last 3 weeks."""
    students = db.get_students()
    attendance = db.get_attendance()
    if students.empty or attendance.empty:
        return []
    
    if "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
    
    today = get_cairo_now()
    three_weeks_ago = today - timedelta(weeks=3)
    # Make datetimes compatible for comparison (both naive)
    three_weeks_ago_naive = three_weeks_ago.replace(tzinfo=None)
    recent_att = attendance[attendance.date >= three_weeks_ago_naive]
    
    needs_followup = []
    for _, student in students.iterrows():
        sid = student.get("student_id", "")
        name = student.get("full_name", "")
        if not sid:
            continue
        student_recent = recent_att[recent_att.student_id == sid]
        if student_recent.empty:
            continue
        absent_count = len(student_recent[student_recent.status == "غائب"])
        if absent_count >= 3:
            needs_followup.append({
                "student_id": sid,
                "full_name": name,
                "reason": f"غيب {absent_count} مرات آخر 3 أسابيع"
            })
    return needs_followup

def calculate_age(birthdate_str: str) -> int:
    """Calculate age from birthdate string."""
    if not birthdate_str or birthdate_str == "":
        return 0
    try:
        bd = pd.to_datetime(birthdate_str, errors="coerce")
        if pd.isna(bd):
            return 0
        now = get_cairo_now()
        return now.year - bd.year - ((now.month, now.day) < (bd.month, bd.day))
    except Exception:
        return 0

def export_to_csv(df: pd.DataFrame, filename: str = "members_export.csv") -> bytes:
    """Export DataFrame to CSV bytes."""
    output = StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return output.getvalue().encode("utf-8-sig")

def export_to_excel(df: pd.DataFrame, filename: str = "members_export.xlsx") -> bytes:
    """Export DataFrame to Excel bytes using openpyxl."""
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "الأعضاء"
        # Write headers
        for col_idx, col_name in enumerate(df.columns, 1):
            ws.cell(row=1, column=col_idx, value=col_name)
        # Write data
        for row_idx, row in df.iterrows():
            for col_idx, col_name in enumerate(df.columns, 1):
                ws.cell(row=row_idx + 2, column=col_idx, value=str(row.get(col_name, "")))
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()
    except Exception:
        # Fallback to CSV if openpyxl fails
        return export_to_csv(df, filename.replace(".xlsx", ".csv"))

def show_member_management(db: Database):
    """Advanced member management with cards, search, filter, bulk actions."""
    st.markdown("<h2 class='main-header'>👥 إدارة الأعضاء المتقدمة</h2>", unsafe_allow_html=True)
    
    # Get data
    students = db.get_students()
    sections = db.get_sections()
    attendance = db.get_attendance()
    
    if students.empty:
        st.info("لا توجد طالبات مسجلات بعد.")
        return
    
    # Merge section names
    if not sections.empty and "section_id" in sections.columns:
        students = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
    else:
        students["section_name"] = ""
    
    # Ensure status column exists with defaults
    if "status" not in students.columns:
        students["status"] = "active"
    students["status"] = students["status"].fillna("active").astype(str)
    
    # Calculate age if birthdate exists
    if "birthdate" in students.columns:
        students["age"] = students["birthdate"].apply(calculate_age)
    else:
        students["age"] = 0
    
    # ===== Search & Filter Section =====
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    
    col_search, col_status, col_section, col_age, col_reset = st.columns([2, 1.2, 1.5, 1.2, 0.8])
    
    with col_search:
        search_term = st.text_input("🔍 بحث بالاسم", placeholder="اكتب اسم الطالبة...", key="member_search")
    
    with col_status:
        status_options = ["الكل", "Active", "Inactive", "Newcomer", "Leader"]
        status_labels = ["الكل", "نشط", "غير نشط", "جديد", "قائد"]
        status_map = dict(zip(status_options, status_labels))
        selected_status = st.selectbox("🏷️ الحالة", status_options, 
                                       format_func=lambda x: status_map.get(x, x), key="member_status_filter")
    
    with col_section:
        section_options = ["الكل"]
        if not sections.empty:
            section_options += sections["section_id"].tolist()
        selected_section = st.selectbox("📚 الخدمة", section_options,
                                        format_func=lambda x: "الكل" if x == "الكل" else (
                                            sections[sections.section_id == x]["section_name"].values[0] if not sections.empty else x
                                        ), key="member_section_filter")
    
    with col_age:
        age_range = st.slider("🎂 العمر", 0, 30, (0, 30), key="member_age_filter")
    
    with col_reset:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 إعادة ضبط", key="reset_filters", use_container_width=True):
            for key in ["member_search", "member_status_filter", "member_section_filter", "member_age_filter"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ===== Apply Filters =====
    filtered = students.copy()
    
    if search_term:
        filtered = filtered[filtered["full_name"].astype(str).str.contains(search_term, na=False, case=False)]
    
    if selected_status and selected_status != "الكل":
        filtered = filtered[filtered["status"].astype(str).str.lower() == selected_status.lower()]
    
    if selected_section and selected_section != "الكل":
        filtered = filtered[filtered["section_id"] == selected_section]
    
    if "age" in filtered.columns:
        filtered = filtered[(filtered["age"] >= age_range[0]) & (filtered["age"] <= age_range[1])]
    
    # ===== Bulk Actions =====
    st.markdown('<div class="bulk-action-bar">', unsafe_allow_html=True)
    st.markdown(f"<span style='font-weight:700;'>📊 {len(filtered)} طالبة</span>", unsafe_allow_html=True)
    
    # Checkbox for select all
    select_all = st.checkbox("تحديد الكل", key="select_all_members")
    
    col_export_csv, col_export_xlsx, col_export_all = st.columns([1, 1, 1.5])
    
    with col_export_csv:
        if st.button("📥 تصدير CSV", key="export_csv_btn", use_container_width=True):
            csv_bytes = export_to_csv(filtered)
            st.download_button(
                label="📥 تحميل CSV",
                data=csv_bytes,
                file_name="members_export.csv",
                mime="text/csv",
                key="download_csv_btn"
            )
            st.toast("✅ تم تصدير الملف!", icon="📥")
    
    with col_export_xlsx:
        if st.button("📥 تصدير Excel", key="export_xlsx_btn", use_container_width=True):
            xlsx_bytes = export_to_excel(filtered)
            st.download_button(
                label="📥 تحميل Excel",
                data=xlsx_bytes,
                file_name="members_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_xlsx_btn"
            )
            st.toast("✅ تم تصدير الملف!", icon="📥")
    
    with col_export_all:
        if st.button("📥 تصدير الكل (بدون فلتر)", key="export_all_btn", use_container_width=True):
            all_csv = export_to_csv(students)
            st.download_button(
                label="📥 تحميل الكل CSV",
                data=all_csv,
                file_name="all_members_export.csv",
                mime="text/csv",
                key="download_all_btn"
            )
            st.toast("✅ تم تصدير جميع الأعضاء!", icon="📥")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ===== Member Cards Grid =====
    if filtered.empty:
        st.warning("⚠️ لا توجد نتائج تطابق البحث.")
        return
    
    # Store selected members in session state
    if "selected_members" not in st.session_state:
        st.session_state.selected_members = set()
    
    # Status update dropdown (appears at top if any member selected)
    selected_ids = [sid for sid in st.session_state.selected_members if sid in filtered["student_id"].values]
    if selected_ids:
        with st.container():
            st.markdown(f"<div class='bulk-action-bar' style='background:rgba(102,126,234,0.1);'>✅ تم اختيار {len(selected_ids)} طالبة</div>", unsafe_allow_html=True)
            new_status = st.selectbox("تغيير حالة المختارين إلى:", 
                                      ["Active", "Inactive", "Newcomer", "Leader"],
                                      format_func=lambda x: {"Active": "نشط", "Inactive": "غير نشط", "Newcomer": "جديد", "Leader": "قائد"}.get(x, x),
                                      key="bulk_status_change")
            if st.button("تطبيق التغيير", key="apply_bulk_status", use_container_width=True):
                for sid in selected_ids:
                    db.update_student(sid, {"status": new_status})
                st.session_state.selected_members = set()
                st.success(f"✅ تم تحديث حالة {len(selected_ids)} طالبة!")
                st.toast(f"✅ تم تحديث الحالة!", icon="🎉")
                time.sleep(1)
                st.rerun()
    
    # Display as grid of cards
    st.markdown('<div class="member-grid">', unsafe_allow_html=True)
    
    for _, row in filtered.iterrows():
        sid = row.get("student_id", "")
        name = row.get("full_name", "")
        section_name = row.get("section_name", "")
        status = row.get("status", "active")
        phone = row.get("phone", "")
        parent_phone = row.get("parent_phone", "")
        school = row.get("school", "")
        age = row.get("age", 0)
        birthdate = row.get("birthdate", "")
        
        # Generate avatar
        avatar_color = get_avatar_color(name)
        first_letter = name[0] if name else "?"
        
        # Generate QR code
        qr_data = f"Member: {name}\nID: {sid}\nSection: {section_name}"
        qr_b64 = generate_qr_base64(qr_data)
        
        # Status badge
        badge_class = get_status_badge_class(status)
        status_label = get_status_label(status)
        
        # Checkbox for selection
        is_selected = sid in st.session_state.selected_members
        
        st.markdown(f"""
        <div class="member-card">
            <div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.8rem;">
                <div class="member-avatar" style="background:{avatar_color};">{first_letter}</div>
                <div style="flex:1; min-width:0;">
                    <div style="font-weight:700; font-size:1rem; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name}</div>
                    <div style="font-size:0.8rem; color:var(--text-secondary);">{section_name if section_name else 'بدون خدمة'}</div>
                </div>
                <div>
                    <span class="status-badge {badge_class}">{status_label}</span>
                </div>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center; margin-bottom:0.5rem;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">🎂 {age} سنة</div>
                <div style="font-size:0.8rem; color:var(--text-secondary);">📞 {phone if phone else '—'}</div>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
                <div style="font-size:0.75rem; color:var(--text-secondary);">🆔 {sid[:8]}...</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Checkbox for selection (using Streamlit widget)
        col_check, col_status_change = st.columns([1, 3])
        with col_check:
            checked = st.checkbox("اختيار", value=is_selected, key=f"sel_{sid}")
            if checked and sid not in st.session_state.selected_members:
                st.session_state.selected_members.add(sid)
                st.rerun()
            elif not checked and sid in st.session_state.selected_members:
                st.session_state.selected_members.discard(sid)
                st.rerun()
        
        with col_status_change:
            # Quick status change dropdown
            current_status = status
            new_s = st.selectbox("تغيير الحالة", 
                                 ["", "Active", "Inactive", "Newcomer", "Leader"],
                                 index=0,
                                 format_func=lambda x: {"": "—", "Active": "نشط", "Inactive": "غير نشط", "Newcomer": "جديد", "Leader": "قائد"}.get(x, x),
                                 key=f"status_{sid}")
            if new_s and new_s != current_status:
                db.update_student(sid, {"status": new_s})
                st.toast(f"✅ تم تحديث حالة {name}", icon="✅")
                time.sleep(0.5)
                st.rerun()
        
        # ===== Member Details Expander =====
        with st.expander(f"📋 تفاصيل {name}", expanded=False):
            # Attendance history
            st.markdown("#### 📅 سجل الحضور")
            if not attendance.empty and "student_id" in attendance.columns:
                student_att = attendance[attendance["student_id"] == sid].copy()
                if not student_att.empty:
                    if "date" in student_att.columns:
                        student_att["date"] = pd.to_datetime(student_att["date"], errors="coerce")
                        student_att = student_att.sort_values("date", ascending=False)
                    present_count = len(student_att[student_att["status"] == "حاضر"]) if "status" in student_att.columns else 0
                    absent_count = len(student_att[student_att["status"] == "غائب"]) if "status" in student_att.columns else 0
                    col_p, col_a = st.columns(2)
                    col_p.metric("✅ أيام الحضور", present_count)
                    col_a.metric("❌ أيام الغياب", absent_count)
                    st.dataframe(student_att[["date", "status", "notes"]].head(10), use_container_width=True)
                else:
                    st.info("لا توجد سجلات حضور.")
            else:
                st.info("لا توجد بيانات حضور.")
            
            st.markdown("#### 📞 بيانات التواصل")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**رقم الهاتف:** {phone if phone else 'غير متاح'}")
                st.markdown(f"**رقم ولي الأمر:** {parent_phone if parent_phone else 'غير متاح'}")
            with col2:
                st.markdown(f"**المدرسة:** {school if school else 'غير متاح'}")
                st.markdown(f"**تاريخ الميلاد:** {birthdate if birthdate else 'غير متاح'}")
            
            # QR Code
            if qr_b64:
                st.markdown("#### 📱 QR Code")
                st.markdown(f'<img src="data:image/png;base64,{qr_b64}" width="120" style="border-radius:8px;">', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# Attendance, Follow-up, My Students, etc.
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
            st.toast("✅ تم تسجيل الحضور بنجاح!", icon="🎉")
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
            st.toast("🗑️ تم حذف سجل الحضور", icon="⚠️")
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
                    st.toast("✅ تم تسجيل الافتقاد بنجاح!", icon="🎉")
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
                        st.toast("✅ تمت المتابعة بنجاح!", icon="🎉")
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
                    st.toast("✅ تم إنشاء الاختبار بنجاح!", icon="🎉")
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
                                st.toast("✅ تمت إضافة السؤال بنجاح!", icon="🎉")
                                time.sleep(1)
                                st.rerun()
                    if not questions.empty:
                        del_q = st.selectbox("اختر سؤالاً لحذفه", questions["question_id"])
                        if st.button("حذف السؤال"):
                            db.delete_question(del_q)
                            st.success("تم الحذف")
                            st.toast("🗑️ تم حذف السؤال", icon="⚠️")
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
                        st.toast(f"🔴 تم إغلاق الاختبار: {title}", icon="🔒")
                        time.sleep(1)
                        st.rerun()
                else:
                    if col_actions[0].button("تفعيل", key=f"act_{qid}"):
                        db.update_quiz(qid, {"is_active": "True"})
                        st.success(f"تم تفعيل الاختبار: {title}")
                        st.toast(f"🟢 تم تفعيل الاختبار: {title}", icon="✅")
                        time.sleep(1)
                        st.rerun()
                if col_actions[1].button("حذف (النتائج تبقى)", key=f"del_keep_{qid}"):
                    db.delete_quiz_keep_results(qid)
                    st.success(f"تم حذف الاختبار '{title}' مع الاحتفاظ بالنتائج.")
                    st.toast(f"🗑️ تم حذف الاختبار مع الاحتفاظ بالنتائج", icon="⚠️")
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
                    except:
                        pass
                if "submission_time" in results.columns:
                    try:
                        results["تسليم الاختبار"] = pd.to_datetime(results["submission_time"]).apply(
                            lambda x: format_cairo_time(x.replace(tzinfo=CAIRO_TZ)) if pd.notna(x) else ""
                        )
                        time_cols.append("تسليم الاختبار")
                    except:
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

def show_reports(db: Database):
    st.markdown("<h2 class='main-header'>📊 التقارير والإحصائيات</h2>", unsafe_allow_html=True)
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    attendance = db.get_attendance()
    students = db.get_students()
    sections = db.get_sections()

    if role == "Teacher" and section_id:
        if not students.empty and "section_id" in students.columns:
            students = students[students.section_id == section_id]
        if not attendance.empty and "section_id" in attendance.columns:
            attendance = attendance[attendance.section_id == section_id]
        if not sections.empty and "section_id" in sections.columns:
            sections = sections[sections.section_id == section_id]

    if attendance.empty:
        st.info("لا توجد بيانات حضور.")
        return
    if "date" in attendance.columns:
        attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")

    # ===== Report Builder =====
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("### 📋 منشئ التقارير")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        report_type = st.selectbox(
            "نوع التقرير",
            ["تقرير الحضور الأسبوعي", "تقرير الحضور الشهري", "تقرير الأعضاء الجدد", "تقرير الأعضاء الغائبين"],
            key="report_type"
        )
    with col2:
        date_from = st.date_input("من تاريخ", get_cairo_now().date() - timedelta(days=30), key="report_from")
    with col3:
        date_to = st.date_input("إلى تاريخ", get_cairo_now().date(), key="report_to")
    
    # Additional filters
    if not sections.empty:
        section_filter = st.multiselect(
            "تصفية حسب الخدمة",
            options=sections["section_id"].tolist(),
            format_func=lambda x: sections[sections.section_id == x]["section_name"].values[0] if x in sections["section_id"].values else x,
            default=sections["section_id"].tolist() if "report_sections" not in st.session_state else st.session_state.report_sections,
            key="report_sections"
        )
    else:
        section_filter = []
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Convert dates
    date_from_str = date_from.strftime("%Y-%m-%d")
    date_to_str = date_to.strftime("%Y-%m-%d")
    
    # Filter data by date range
    if "date" in attendance.columns:
        mask = (attendance.date >= date_from_str) & (attendance.date <= date_to_str)
        period_attendance = attendance[mask].copy()
    else:
        period_attendance = pd.DataFrame()
    
    # Filter by sections if selected
    if section_filter and not period_attendance.empty and "section_id" in period_attendance.columns:
        period_attendance = period_attendance[period_attendance.section_id.isin(section_filter)]
    
    # ===== Summary KPI Cards =====
    st.markdown("### 📊 ملخص الفترة")
    if not period_attendance.empty:
        # Calculate KPIs
        total_records = len(period_attendance)
        present_count = len(period_attendance[period_attendance.status == "حاضر"]) if "status" in period_attendance.columns else 0
        absent_count = len(period_attendance[period_attendance.status == "غائب"]) if "status" in period_attendance.columns else 0
        late_count = len(period_attendance[period_attendance.status == "متأخر"]) if "status" in period_attendance.columns else 0
        
        attendance_rate = round((present_count / total_records) * 100, 1) if total_records > 0 else 0
        
        # Calculate unique students
        unique_students = period_attendance["student_id"].nunique() if "student_id" in period_attendance.columns else 0
        
        # Find students needing followup
        students_needing_followup = get_students_needing_followup(db)
        followup_count = len(students_needing_followup)
        
        # Calculate days in period
        days_count = (date_to - date_from).days + 1
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📅 إجمالي الحضور في الفترة", f"{present_count}", f"من {total_records} سجل")
        col2.metric("📈 متوسط الحضور اليومي", f"{round(present_count/days_count, 1) if days_count > 0 else 0}", f"للمدة {days_count} يوم")
        col3.metric("🏫 أكثر خدمة حضوراً", "غير متاح", help="يتطلب بيانات أكثر تفصيلاً")
        col4.metric("⚠️ بحاجة لمتابعة", f"{followup_count}", "طالبة")
        
        st.markdown("---")
    else:
        st.warning("لا توجد بيانات للفترة المحددة.")
        return
    
    # ===== Interactive Charts =====
    st.markdown("### 📈 الرسوم البيانية")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("📊 الحضور عبر الزمن")
        if not period_attendance.empty and "date" in period_attendance.columns and "status" in period_attendance.columns:
            # Group by date and status
            daily_summary = period_attendance.groupby(["date", "status"]).size().reset_index(name="العدد")
            
            if not daily_summary.empty:
                fig = px.line(
                    daily_summary, 
                    x="date", 
                    y="العدد",
                    color="status",
                    labels={"date": "التاريخ", "العدد": "عدد الطالبات", "status": "الحالة"},
                    color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"},
                    title="الحضور اليومي"
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد بيانات للعرض")
        else:
            st.info("لا توجد بيانات كافية")
    
    with col_chart2:
        st.subheader("📊 مقارنة الحضور بين الخدمات")
        if not period_attendance.empty and "section_id" in period_attendance.columns:
            # Merge with section names
            if not sections.empty:
                section_att = period_attendance.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
            else:
                section_att = period_attendance.copy()
                section_att["section_name"] = section_att["section_id"]
            
            if "section_name" in section_att.columns and "status" in section_att.columns:
                section_summary = section_att.groupby(["section_name", "status"]).size().reset_index(name="العدد")
                
                if not section_summary.empty:
                    # Create grouped bar chart
                    fig = px.bar(
                        section_summary,
                        x="section_name",
                        y="العدد",
                        color="status",
                        labels={"section_name": "الخدمة", "العدد": "عدد الطالبات", "status": "الحالة"},
                        color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"},
                        title="الحضور حسب الخدمة",
                        barmode="group"
                    )
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        xaxis_tickangle=-45
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("لا توجد بيانات للعرض")
            else:
                st.info("لا توجد بيانات كافية")
        else:
            st.info("لا توجد بيانات كافية")
    
    # Pie chart - full width
    st.subheader("🥧 نسبة الحضور مقابل الغياب")
    if not period_attendance.empty and "status" in period_attendance.columns:
        status_summary = period_attendance["status"].value_counts().reset_index()
        status_summary.columns = ["الحالة", "العدد"]
        
        if not status_summary.empty:
            fig = px.pie(
                status_summary,
                names="الحالة",
                values="العدد",
                title="توزيع الحالات",
                hole=0.4,
                color_discrete_map={"حاضر": "#28a745", "غائب": "#dc3545", "متأخر": "#ffc107"}
            )
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات")
    else:
        st.info("لا توجد بيانات كافية")
    
    st.markdown("---")
    
    # ===== Detailed Table =====
    st.markdown("### 📋 جدول التفاصيل")
    
    if report_type == "تقرير الأعضاء الغائبين":
        st.subheader("❌ الأعضاء الغائبين")
        if not period_attendance.empty:
            absent_df = period_attendance[period_attendance.status == "غائب"].copy() if "status" in period_attendance.columns else pd.DataFrame()
            if not absent_df.empty and not students.empty:
                absent_df = absent_df.merge(students[["student_id", "full_name"]], on="student_id", how="left")
                absent_df = absent_df[["full_name", "date", "status", "notes"]].sort_values("date", ascending=False)
                st.dataframe(absent_df, use_container_width=True)
            else:
                st.info("لا يوجد غياب في الفترة المحددة")
        else:
            st.info("لا توجد بيانات")
    
    elif report_type == "تقرير الحضور الأسبوعي":
        st.subheader("📅 ملخص أسبوعي")
        if not period_attendance.empty and "date" in period_attendance.columns:
            # Add week number
            period_attendance["week"] = period_attendance["date"].dt.isocalendar().week
            
            weekly_summary = period_attendance.groupby(["week", "status"]).size().reset_index(name="العدد")
            if not weekly_summary.empty:
                st.dataframe(weekly_summary, use_container_width=True)
            else:
                st.info("لا توجد بيانات")
        else:
            st.info("لا توجد بيانات")
    
    else:
        # Default: show all records
        if not period_attendance.empty:
            display_df = period_attendance.copy()
            if not students.empty:
                display_df = display_df.merge(students[["student_id", "full_name"]], on="student_id", how="left")
                display_df = display_df[["full_name", "date", "status", "notes"]]
            else:
                display_df = display_df[["date", "student_id", "status", "notes"]]
            st.dataframe(display_df.sort_values("date", ascending=False), use_container_width=True)
        else:
            st.info("لا توجد بيانات")
    
    st.markdown("---")
    
    # ===== Export Options =====
    st.markdown("### 📥 تصدير التقرير")
    
    col_export1, col_export2, col_export3 = st.columns(3)
    
    with col_export1:
        if st.button("📥 تصدير CSV", use_container_width=True, key="export_report_csv"):
            if not period_attendance.empty:
                # Prepare export data
                export_df = period_attendance.copy()
                if not students.empty:
                    export_df = export_df.merge(students[["student_id", "full_name"]], on="student_id", how="left")
                    export_df = export_df[["full_name", "date", "status", "notes"]]
                else:
                    export_df = export_df[["date", "student_id", "status", "notes"]]
                
                csv_data = export_to_csv(export_df, f"تقرير_{report_type}_{date_from_str}_{date_to_str}.csv")
                st.download_button(
                    label="📥 تحميل CSV",
                    data=csv_data,
                    file_name=f"تقرير_{report_type}_{date_from_str}_{date_to_str}.csv",
                    mime="text/csv",
                    key="download_report_csv"
                )
                st.toast("✅ تم تجهيز الملف للتحميل", icon="📥")
            else:
                st.warning("لا توجد بيانات للتصدير")
    
    with col_export2:
        if st.button("📥 تصدير Excel", use_container_width=True, key="export_report_excel"):
            if not period_attendance.empty:
                # Prepare export data
                export_df = period_attendance.copy()
                if not students.empty:
                    export_df = export_df.merge(students[["student_id", "full_name"]], on="student_id", how="left")
                    export_df = export_df[["full_name", "date", "status", "notes"]]
                else:
                    export_df = export_df[["date", "student_id", "status", "notes"]]
                
                excel_data = export_to_excel(export_df, f"تقرير_{report_type}_{date_from_str}_{date_to_str}.xlsx")
                st.download_button(
                    label="📥 تحميل Excel",
                    data=excel_data,
                    file_name=f"تقرير_{report_type}_{date_from_str}_{date_to_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_report_excel"
                )
                st.toast("✅ تم تجهيز الملف للتحميل", icon="📥")
            else:
                st.warning("لا توجد بيانات للتصدير")
    
    with col_export3:
        if st.button("📄 تصدير PDF", use_container_width=True, key="export_report_pdf"):
            st.info("📄 ميزة تصدير PDF قيد التطوير. يرجى استخدام CSV أو Excel للتصدير حالياً.")

# =============================================================================
# Events Page UI
# =============================================================================
def show_events_page(db: Database):
    st.markdown("<h2 class='main-header'>📅 الفعاليات والمناسبات</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    events_df = db.get_events()
    rsvps_df = db.get_event_rsvps()
    students = db.get_students()
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 الفعاليات القادمة", "➕ إضافة فعالية", "🎫 تسجيل الحظور المتوقع", "✅ تسجيل حضور الفعالية"])
    
    with tab1:
        st.subheader("📋 الفعاليات القادمة")
        if events_df.empty:
            st.info("لا توجد فعاليات مسجلة بعد.")
        else:
            events_df["event_date"] = pd.to_datetime(events_df["event_date"], errors="coerce")
            events_df = events_df.sort_values("event_date")
            
            col1, col2 = st.columns(2)
            with col1:
                event_type_filter = st.selectbox("تصفية حسب النوع", ["الكل"] + list(events_df["event_type"].unique()), key="event_type_filter")
            with col2:
                show_past = st.checkbox("عرض الفعاليات المنتهية", value=False, key="show_past_events")
            
            filtered_events = events_df.copy()
            if event_type_filter != "الكل":
                filtered_events = filtered_events[filtered_events.event_type == event_type_filter]
            
            today = get_cairo_now().replace(tzinfo=None)
            if not show_past:
                filtered_events = filtered_events[filtered_events.event_date >= today]
            
            if filtered_events.empty:
                st.info("لا توجد فعاليات مطابقة.")
            else:
                for _, event in filtered_events.iterrows():
                    event_id = event.get("event_id", "")
                    event_name = event.get("event_name", "")
                    event_date = event.get("event_date", "")
                    location = event.get("location", "")
                    event_type = event.get("event_type", "")
                    description = event.get("description", "")
                    max_attendees = event.get("max_attendees", "")
                    
                    if pd.notna(event_date):
                        date_str = event_date.strftime("%Y-%m-%d %I:%M %p")
                    else:
                        date_str = "غير محدد"
                    
                    rsvp_count = get_event_attendees_count(db, event_id)
                    type_emoji = {"اجتماع": "💬", "خدمة": "⛪", "رحلة": "🚌", "احتفال": "🎉"}.get(event_type, "📅")
                    
                    st.markdown(f"""
                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;">
                            <h3 style="margin:0; color:var(--text-primary);">{type_emoji} {event_name}</h3>
                            <span style="background:var(--gold-light); color:var(--gold); padding:0.3rem 0.8rem; border-radius:20px; font-size:0.8rem; font-weight:600;">{event_type}</span>
                        </div>
                        <div style="font-size:0.9rem; color:var(--text-secondary); margin-bottom:0.5rem;">📅 {date_str} | 📍 {location if location else 'غير محدد'}</div>
                        {f'<div style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:0.5rem;">👥 السعة: {max_attendees} شخص</div>' if max_attendees else ''}
                        <div style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:0.8rem;">✅ المسجلون: {rsvp_count} {f'/ {max_attendees}' if max_attendees else ''}</div>
                        {f'<div style="padding:0.8rem; background:var(--card-bg); border-radius:8px; margin-top:0.5rem;">{description}</div>' if description else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if not rsvps_df.empty:
                        event_rsvps = rsvps_df[rsvps_df.event_id == event_id]
                        if not event_rsvps.empty:
                            with st.expander(f"📋 قائمة المسجلين ({len(event_rsvps)})"):
                                for _, rsvp in event_rsvps.iterrows():
                                    st.write(f"👤 {rsvp.get('student_name', '')} - {rsvp.get('rsvp_status', '')}")
    
    with tab2:
        st.subheader("➕ إضافة فعالية جديدة")
        with st.form("add_event_form"):
            event_name = st.text_input("اسم الفعالية*", placeholder="مثال: اجتماع شهري")
            event_type = st.selectbox("نوع الفعالية*", ["اجتماع", "خدمة", "رحلة", "احتفال"])
            event_date = st.date_input("تاريخ الفعالية*", value=get_cairo_now().date() + timedelta(days=7))
            event_time = st.time_input("وقت الفعالية", value=None)
            location = st.text_input("المكان", placeholder="مثال: قاعة الاجتماعات")
            max_attendees = st.number_input("السعة القصوى (اختياري)", min_value=0, value=0, help="اتركه 0 لعدم تحديد سعة")
            description = st.text_area("الوصف", placeholder="تفاصيل إضافية عن الفعالية...")
            
            submitted = st.form_submit_button("➕ إضافة الفعالية", use_container_width=True)
            if submitted:
                if not event_name or not event_date:
                    st.error("يرجى ملء اسم الفعالية والتاريخ على الأقل")
                else:
                    if event_time:
                        datetime_str = f"{event_date} {event_time}"
                    else:
                        datetime_str = f"{event_date} 00:00"
                    
                    event_data = {
                        "event_name": event_name,
                        "event_date": datetime_str,
                        "location": location,
                        "event_type": event_type,
                        "description": description,
                        "max_attendees": str(max_attendees) if max_attendees > 0 else "",
                        "created_by": user.get("user_id", "")
                    }
                    
                    event_id = add_event(db, event_data)
                    st.success(f"✅ تم إضافة الفعالية بنجاح!")
                    st.toast("✅ تم إضافة الفعالية!", icon="🎉")
                    time.sleep(1)
                    st.rerun()
    
    with tab3:
        st.subheader("🎫 تسجيل الحضور المتوقع")
        if events_df.empty:
            st.info("لا توجد فعاليات للتسجيل فيها.")
        else:
            events_df["event_date"] = pd.to_datetime(events_df["event_date"], errors="coerce")
            events_df = events_df.sort_values("event_date")
            event_options = events_df[events_df.event_date >= get_cairo_now().replace(tzinfo=None)]
            
            if event_options.empty:
                st.info("لا توجد فعاليات مستقبلية.")
            else:
                selected_event_id = st.selectbox(
                    "اختر الفعالية",
                    event_options["event_id"].tolist(),
                    format_func=lambda x: event_options[event_options.event_id == x]["event_name"].values[0],
                    key="rsvp_event_select"
                )
                
                if selected_event_id:
                    event_row = event_options[event_options.event_id == selected_event_id].iloc[0]
                    event_name = event_row.get("event_name", "")
                    max_att = event_row.get("max_attendees", "")
                    
                    st.markdown(f"**الفعالية:** {event_name}")
                    try:
                        max_att_val = int(float(max_att)) if max_att and str(max_att).strip() else 0
                    except (ValueError, TypeError):
                        max_att_val = 0
                    if max_att_val > 0:
                        current_rsvps = get_event_attendees_count(db, selected_event_id)
                        st.markdown(f"**المسجلون:** {current_rsvps}/{max_att_val}")
                    
                    user_id = user.get("user_id", "")
                    existing_rsvp = rsvps_df[(rsvps_df.event_id == selected_event_id) & (rsvps_df.student_id == user_id)] if not rsvps_df.empty else pd.DataFrame()
                    
                    if not existing_rsvp.empty:
                        st.info("✅ أنت مسجل في هذه الفعالية بالفعل")
                    else:
                        if not students.empty:
                            student_options = students[students["status"] == "active"] if "status" in students.columns else students
                            if not student_options.empty:
                                selected_student = st.selectbox(
                                    "اختر العضو للتسجيل",
                                    student_options["student_id"].tolist(),
                                    format_func=lambda x: student_options[student_options.student_id == x]["full_name"].values[0],
                                    key="rsvp_student_select"
                                )
                                
                                if selected_student:
                                    student_name = student_options[student_options.student_id == selected_student]["full_name"].values[0]
                                    if st.button("✅ تسجيل الحضور المتوقع", use_container_width=True, key="rsvp_submit"):
                                        success = add_event_rsvp(db, selected_event_id, selected_student, student_name)
                                        if success:
                                            st.success(f"✅ تم تسجيل {student_name} في الفعالية")
                                            st.toast("✅ تم التسجيل!", icon="🎫")
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.warning("هذا العضو مسجل بالفعل")
    
    with tab4:
        st.subheader("✅ تسجيل حضور الفعالية")
        if events_df.empty:
            st.info("لا توجد فعاليات.")
        else:
            events_df["event_date"] = pd.to_datetime(events_df["event_date"], errors="coerce")
            past_events = events_df[events_df.event_date < get_cairo_now().replace(tzinfo=None)]
            
            if past_events.empty:
                st.info("لا توجد فعاليات منتهية.")
            else:
                selected_event_id = st.selectbox(
                    "اختر الفعالية",
                    past_events["event_id"].tolist(),
                    format_func=lambda x: past_events[past_events.event_id == x]["event_name"].values[0],
                    key="attendance_event_select"
                )
                
                if selected_event_id:
                    event_row = past_events[past_events.event_id == selected_event_id].iloc[0]
                    event_name = event_row.get("event_name", "")
                    st.markdown(f"**الفعالية:** {event_name}")
                    
                    event_rsvps = rsvps_df[rsvps_df.event_id == selected_event_id] if not rsvps_df.empty else pd.DataFrame()
                    
                    if event_rsvps.empty:
                        st.info("لا يوجد مسجلين في هذه الفعالية.")
                    else:
                        st.markdown(f"**عدد المسجلين:** {len(event_rsvps)}")
                        
                        st.markdown("### تسجيل الحضور الفعلي")
                        attendance_data = {}
                        for _, rsvp in event_rsvps.iterrows():
                            student_id = rsvp.get("student_id", "")
                            student_name = rsvp.get("student_name", "")
                            current_status = rsvp.get("actual_attendance", "")
                            
                            col1, col2 = st.columns([3, 2])
                            col1.write(f"👤 {student_name}")
                            
                            status = col2.selectbox(
                                "الحالة",
                                ["", "حضر", "لم يحضر"],
                                index=0 if not current_status else (1 if current_status == "حضر" else 2),
                                key=f"att_{student_id}"
                            )
                            attendance_data[student_id] = status
                        
                        if st.button("💾 حفظ الحضور", use_container_width=True, key="save_event_attendance"):
                            success_count = 0
                            for student_id, status in attendance_data.items():
                                if status:
                                    if update_event_attendance(db, selected_event_id, student_id, status):
                                        success_count += 1
                            
                            if success_count > 0:
                                st.success(f"✅ تم تحديث حضور {success_count} عضو")
                                st.toast("✅ تم حفظ الحضور!", icon="✅")
                                time.sleep(1)
                                st.rerun()
                        
                        st.markdown("---")
                        st.subheader("📊 ملخص الحضور")
                        if not event_rsvps.empty and "actual_attendance" in event_rsvps.columns:
                            attended = len(event_rsvps[event_rsvps.actual_attendance == "حضر"])
                            absent = len(event_rsvps[event_rsvps.actual_attendance == "لم يحضر"])
                            not_recorded = len(event_rsvps[event_rsvps.actual_attendance == ""])
                            
                            col1, col2, col3 = st.columns(3)
                            col1.metric("✅ حضر", attended)
                            col2.metric("❌ لم يحضر", absent)
                            col3.metric("⏳ لم يسجل", not_recorded)

def get_events_badge_count(db):
    upcoming = get_upcoming_events(db, days=3)
    return len(upcoming)

# =============================================================================
# Details Logging System
# =============================================================================
def log_details_operation(db: Database, student_id: str, student_name: str, status: str, 
                         operation_type: str, qr_data: str = "", device_info: str = "Default Camera", 
                         notes: str = ""):
    """Log operation details to the Details sheet in Google Sheets."""
    try:
        db._ensure_details_sheet()
        timestamp = get_cairo_now().strftime("%Y-%m-%d %H:%M:%S")
        
        details_record = {
            "Timestamp": timestamp,
            "ID": student_id if student_id else "N/A",
            "Name": student_name if student_name else "Unknown",
            "Status": status,
            "Operation_Type": operation_type,
            "QR_Data": qr_data if qr_data else "N/A",
            "Device_Info": device_info,
            "Notes": notes
        }
        
        # Thread-safe writing to Details sheet
        with Database._details_lock:
            df = db._sheet_to_df("Details")
            if df.empty:
                df = pd.DataFrame(columns=["Timestamp", "ID", "Name", "Status", "Operation_Type",
                                           "QR_Data", "Device_Info", "Notes"])
            df = pd.concat([df, pd.DataFrame([details_record])], ignore_index=True)
            # Keep only last 2000 records
            if len(df) > 2000:
                df = df.tail(2000)
            db._df_to_sheet("Details", df, ["Timestamp", "ID", "Name", "Status", "Operation_Type",
                                            "QR_Data", "Device_Info", "Notes"])
    except Exception as e:
        print(f"Error logging details: {e}")

def validate_qr_code(db: Database, qr_data: str, students_df: pd.DataFrame) -> dict:
    """
    Validate QR code against registered students.
    Returns dict with 'valid', 'student_id', 'student_name', 'section_id', 'message'
    """
    if not qr_data or qr_data.strip() == "":
        return {
            "valid": False,
            "student_id": "",
            "student_name": "",
            "section_id": "",
            "message": "QR Code فارغ"
        }
    
    # Parse QR data
    parts = qr_data.split('\n')
    qr_name = ""
    qr_id = ""
    
    for part in parts:
        trimmed = part.strip()
        if trimmed.startswith("Member:"):
            qr_name = trimmed.replace("Member:", "").strip()
        elif trimmed.startswith("ID:"):
            qr_id = trimmed.replace("ID:", "").strip()
    
    if not qr_id or not qr_name:
        return {
            "valid": False,
            "student_id": "",
            "student_name": "",
            "section_id": "",
            "message": "❌ QR Code غير صالح - بيانات ناقصة"
        }
    
    # Search in students dataframe
    if students_df.empty or "student_id" not in students_df.columns:
        return {
            "valid": False,
            "student_id": qr_id,
            "student_name": qr_name,
            "section_id": "",
            "message": "❌ QR Code غير معروف - لا توجد طالبات مسجلات"
        }
    
    # Try to match by ID or Name
    student_match = students_df[
        (students_df["student_id"] == qr_id) | 
        (students_df["full_name"] == qr_name)
    ]
    
    if student_match.empty:
        return {
            "valid": False,
            "student_id": qr_id,
            "student_name": qr_name,
            "section_id": "",
            "message": "❌ QR Code غير مسجل في النظام"
        }
    
    student_row = student_match.iloc[0]
    return {
        "valid": True,
        "student_id": student_row.get("student_id", qr_id),
        "student_name": student_row.get("full_name", qr_name),
        "section_id": student_row.get("section_id", ""),
        "message": "✅ QR Code صالح"
    }

def check_duplicate_attendance(db: Database, student_id: str, date_str: str) -> bool:
    """Check if student already has attendance record for today."""
    attendance = db.get_attendance()
    if attendance.empty or "student_id" not in attendance.columns or "date" not in attendance.columns:
        return False
    # Normalize to string for safe comparison
    attendance["date"] = attendance["date"].astype(str).str.strip()
    date_str = str(date_str).strip()
    today_att = attendance[attendance["date"] == date_str]
    if today_att.empty:
        return False
    student_ids = today_att["student_id"].astype(str).str.strip().tolist()
    return str(student_id).strip() in student_ids

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

def show_audit_log(db: Database):
    """Display login/access audit log with device and location info."""
    st.markdown("<h2 class='main-header'>🔐 سجل الدخول والعمليات</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    role = user.get("role", "")
    
    # Only System Admin can view audit log
    if role != "System Admin":
        st.error("🚫 غير مصرح لك بعرض سجل الدخول")
        return
    
    audit_df = db.get_logs()
    
    if audit_df.empty:
        st.info("لا توجد سجلات دخول بعد.")
        return
    
    # Convert timestamp
    if "timestamp" in audit_df.columns:
        audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"], errors="coerce")
        audit_df = audit_df.sort_values("timestamp", ascending=False)
    
    # Summary stats
    st.markdown("### 📊 ملخص السجلات")
    col1, col2, col3, col4 = st.columns(4)
    
    total_records = len(audit_df)
    unique_users = audit_df["user_name"].nunique() if "user_name" in audit_df.columns else 0
    
    with col1:
        st.metric("📋 إجمالي السجلات", total_records)
    with col2:
        st.metric("👥 مستخدمين فريدين", unique_users)
    with col3:
        if "device_type" in audit_df.columns:
            desktop_count = len(audit_df[audit_df["device_type"] == "Desktop"])
            st.metric("🖥️ عمليات من سطح المكتب", desktop_count)
    with col4:
        if "privacy_consent" in audit_df.columns:
            consent_count = len(audit_df[audit_df["privacy_consent"] == "✅ Agreed"])
            st.metric("✅ موافقات الخصوصية", consent_count)
    
    st.markdown("---")
    
    # Filters
    st.markdown("### 🔍 تصفية السجلات")
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        if "user_name" in audit_df.columns:
            user_options = ["الكل"] + sorted(audit_df["user_name"].dropna().unique().tolist())
            filter_user = st.selectbox("المستخدم", user_options, key="audit_filter_user")
        else:
            filter_user = "الكل"
    
    with col_filter2:
        if "action" in audit_df.columns:
            action_options = ["الكل"] + sorted(audit_df["action"].dropna().unique().tolist())
            filter_action = st.selectbox("الإجراء", action_options, key="audit_filter_action")
        else:
            filter_action = "الكل"
    
    with col_filter3:
        if "device_type" in audit_df.columns:
            device_options = ["الكل"] + sorted(audit_df["device_type"].dropna().unique().tolist())
            filter_device = st.selectbox("نوع الجهاز", device_options, key="audit_filter_device")
        else:
            filter_device = "الكل"
    
    # Apply filters
    filtered_audit = audit_df.copy()
    
    if filter_user != "الكل" and "user_name" in filtered_audit.columns:
        filtered_audit = filtered_audit[filtered_audit["user_name"] == filter_user]
    
    if filter_action != "الكل" and "action" in filtered_audit.columns:
        filtered_audit = filtered_audit[filtered_audit["action"] == filter_action]
    
    if filter_device != "الكل" and "device_type" in filtered_audit.columns:
        filtered_audit = filtered_audit[filtered_audit["device_type"] == filter_device]
    
    st.markdown(f"<div style='margin:1rem 0;'><strong>📊 السجلات المعروضة:</strong> {len(filtered_audit)} من {total_records}</div>", unsafe_allow_html=True)
    
    # Display table
    if not filtered_audit.empty:
        # Select and rename columns for display
        display_columns = {}
        
        if "timestamp" in filtered_audit.columns:
            display_columns["timestamp"] = "التاريخ والوقت"
        if "user_name" in filtered_audit.columns:
            display_columns["user_name"] = "اسم المستخدم"
        if "action" in filtered_audit.columns:
            display_columns["action"] = "الإجراء"
        if "details" in filtered_audit.columns:
            display_columns["details"] = "التفاصيل"
        if "browser" in filtered_audit.columns:
            display_columns["browser"] = "المتصفح"
        if "os" in filtered_audit.columns:
            display_columns["os"] = "نظام التشغيل"
        if "device_type" in filtered_audit.columns:
            display_columns["device_type"] = "نوع الجهاز"
        if "screen_size" in filtered_audit.columns:
            display_columns["screen_size"] = "حجم الشاشة"
        if "ip_masked" in filtered_audit.columns:
            display_columns["ip_masked"] = "IP (مجهز)"
        if "country" in filtered_audit.columns:
            display_columns["country"] = "الدولة"
        if "city" in filtered_audit.columns:
            display_columns["city"] = "المدينة"
        if "privacy_consent" in filtered_audit.columns:
            display_columns["privacy_consent"] = "الخصوصية"
        
        # Filter available columns
        available_cols = [k for k in display_columns.keys() if k in filtered_audit.columns]
        display_df = filtered_audit[available_cols].copy()
        display_df.columns = [display_columns[c] for c in available_cols]
        
        # Format timestamp
        if "التاريخ والوقت" in display_df.columns:
            display_df["التاريخ والوقت"] = display_df["التاريخ والوقت"].apply(
                lambda x: x.strftime("%Y-%m-%d %I:%M:%S %p") if pd.notna(x) else ""
            )
        
        st.dataframe(display_df, use_container_width=True, height=600)
        
        # Export options
        st.markdown("---")
        st.markdown("### 📥 تصدير السجلات")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            if st.button("📥 تصدير CSV", use_container_width=True, key="export_audit_csv"):
                csv_data = export_to_csv(display_df, "audit_log_export.csv")
                st.download_button(
                    label="📥 تحميل CSV",
                    data=csv_data,
                    file_name=f"audit_log_{get_cairo_now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key="download_audit_csv"
                )
                st.toast("✅ تم تجهيز الملف للتحميل", icon="📥")
        
        with col_exp2:
            if st.button("📥 تصدير Excel", use_container_width=True, key="export_audit_excel"):
                excel_data = export_to_excel(display_df, "audit_log_export.xlsx")
                st.download_button(
                    label="📥 تحميل Excel",
                    data=excel_data,
                    file_name=f"audit_log_{get_cairo_now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_audit_excel"
                )
                st.toast("✅ تم تجهيز الملف للتحميل", icon="📥")
    else:
        st.info("لا توجد سجلات مطابقة للتصفية المحددة.")

# =============================================================================
# Events Management System (Google Sheets)
# =============================================================================
def add_event(db, event_data):
    new_event = {
        "event_id": str(uuid.uuid4()),
        "event_name": event_data["event_name"],
        "event_date": event_data["event_date"],
        "location": event_data["location"],
        "event_type": event_data["event_type"],
        "description": event_data["description"],
        "max_attendees": event_data.get("max_attendees", ""),
        "created_by": event_data.get("created_by", st.session_state.user.get("user_id", "")),
        "created_at": get_cairo_now().strftime("%Y-%m-%d %H:%M:%S")
    }
    db.add_event(new_event)
    return new_event["event_id"]

def delete_event(db, event_id):
    db.delete_event(event_id)
    # Also delete all RSVPs for this event
    db.delete_event_rsvps(event_id)

def add_event_rsvp(db, event_id, student_id, student_name):
    new_rsvp = {
        "rsvp_id": str(uuid.uuid4()),
        "event_id": event_id,
        "student_id": student_id,
        "student_name": student_name,
        "rsvp_status": "متوقع الحضور",
        "rsvp_date": get_cairo_now().strftime("%Y-%m-%d %H:%M:%S"),
        "actual_attendance": ""
    }
    return db.add_event_rsvp(new_rsvp)

def update_event_attendance(db, event_id, student_id, attendance_status):
    return db.update_event_attendance(event_id, student_id, attendance_status)

def get_upcoming_events(db, days=3):
    events_df = db.get_events()
    if events_df.empty:
        return pd.DataFrame()
    events_df["event_date"] = pd.to_datetime(events_df["event_date"], errors="coerce")
    today = get_cairo_now().replace(tzinfo=None)
    future_date = today + timedelta(days=days)
    upcoming = events_df[(events_df.event_date >= today) & (events_df.event_date <= future_date)]
    return upcoming.sort_values("event_date")

def get_event_attendees_count(db, event_id):
    return db.get_event_attendees_count(event_id)

def change_password(db: Database):
    st.markdown("<h2 class='main-header'>🔒 تغيير كلمة المرور</h2>", unsafe_allow_html=True)
    with st.form("change_password_form"):
        old = st.text_input("كلمة المرور الحالية", type="password").strip()
        new = st.text_input("كلمة المرور الجديدة", type="password").strip()
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password").strip()
        if st.form_submit_button("تغيير كلمة المرور"):
            if not old or not new or not confirm:
                st.error("الرجاء ملء جميع الحقول")
            else:
                # Verify old password (support both hashed and plain text)
                stored_password = st.session_state.user.get("password", "")
                old_valid = False
                if len(stored_password) == 64:  # Hashed
                    old_valid = verify_password(old, stored_password)
                else:  # Plain text
                    old_valid = (old == stored_password)
                
                if not old_valid:
                    st.error("كلمة المرور الحالية غير صحيحة")
                elif len(new) < 4:
                    st.error("كلمة المرور الجديدة يجب أن تكون 4 أحرف على الأقل")
                elif new != confirm:
                    st.error("كلمتا المرور غير متطابقتين")
                else:
                    # Hash new password before storing
                    hashed_new = hash_password(new)
                    db.update_user(st.session_state.user["user_id"], {"password": hashed_new})
                    st.session_state.user["password"] = hashed_new
                    st.success("✅ تم تغيير كلمة المرور بنجاح!")

# =============================================================================
# QR Code Management
# =============================================================================
def show_print_all_qr_codes(db: Database):
    """Display all members' QR codes for printing."""
    st.markdown("<h2 class='main-header'>🖨️ طباعة QR Codes</h2>", unsafe_allow_html=True)
    
    students = db.get_students()
    sections = db.get_sections()
    
    if students.empty:
        st.info("لا توجد طالبات مسجلات.")
        return
    
    if not sections.empty and "section_id" in sections.columns:
        students = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
    else:
        students["section_name"] = ""
    
    st.markdown("### 📱 جميع الأعضاء")
    cols = st.columns(4)
    col_idx = 0
    
    for _, row in students.iterrows():
        sid = row.get("student_id", "")
        name = row.get("full_name", "")
        section_name = row.get("section_name", "")
        
        qr_data = f"Member: {name}\nID: {sid}\nSection: {section_name}"
        qr_b64 = generate_qr_base64(qr_data)
        
        with cols[col_idx % 4]:
            if qr_b64:
                st.markdown(f"""
                <div style="text-align:center; padding:1rem; background:white; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.1); margin-bottom:1rem;">
                    <div style="font-weight:700; font-size:0.9rem; margin-bottom:0.5rem;">{name}</div>
                    <img src="data:image/png;base64,{qr_b64}" width="100" style="border-radius:8px;">
                    <div style="font-size:0.75rem; color:#666; margin-top:0.3rem;">{section_name if section_name else ''}</div>
                </div>
                """, unsafe_allow_html=True)
        
        col_idx += 1

# =============================================================================
# Quick Check-in
# =============================================================================
def show_quick_checkin(db: Database):
    """Quick attendance check-in with search autocomplete and QR scanner with overlays."""
    st.markdown("<h2 class='main-header'>⚡ تسجيل حضور سريع</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    
    if role == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور.")
        return
    
    students = db.get_students()
    if students.empty:
        st.info("لا توجد طالبات مسجلات.")
        return
    
    # Filter by section for teachers
    if role == "Teacher" and section_id and "section_id" in students.columns:
        students = students[students.section_id == section_id]
    
    if students.empty:
        st.info("لا توجد طالبات في فصلك.")
        return
    
    sections = db.get_sections()
    if not sections.empty and "section_id" in students.columns and "section_id" in sections.columns:
        students = students.merge(sections[["section_id", "section_name"]], on="section_id", how="left")
    else:
        students["section_name"] = ""
    
    # ===== Tabs: Manual Check-in & QR Scanner =====
    tab1, tab2 = st.tabs(["⌨️ تسجيل يدوي", "📷 مسح QR Code"])
    
    with tab1:
        # Search with autocomplete
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        search_term = st.text_input("🔍 بحث بالاسم", placeholder="اكتب اسم الطالبة...", key="quick_checkin_search")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if search_term:
            filtered = students[students["full_name"].astype(str).str.contains(search_term, na=False, case=False)]
            if not filtered.empty:
                selected_student = st.selectbox(
                    "اختر الطالبة",
                    filtered["student_id"].tolist(),
                    format_func=lambda x: filtered[filtered.student_id == x]["full_name"].values[0],
                    key="selected_student_checkin"
                )
                
                if selected_student:
                    student_row = filtered[filtered.student_id == selected_student].iloc[0]
                    name = student_row.get("full_name", "")
                    section_name = student_row.get("section_name", "")
                    sid = selected_student
                    
                    # Display member info
                    avatar_color = get_avatar_color(name)
                    first_letter = name[0] if name else "?"
                    
                    st.markdown(f"""
                    <div style="display:flex; align-items:center; gap:1rem; padding:1rem; background:var(--card-bg); border-radius:12px; margin:1rem 0;">
                        <div class="member-avatar" style="background:{avatar_color};">{first_letter}</div>
                        <div style="flex:1;">
                            <div style="font-weight:700; font-size:1.1rem;">{name}</div>
                            <div style="font-size:0.85rem; color:var(--text-secondary);">{section_name if section_name else 'بدون خدمة'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Quick check-in buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ حضور", use_container_width=True, type="primary", key="quick_present"):
                            today_str = get_cairo_now().strftime("%Y-%m-%d")
                            existing = db.get_attendance_by_date_section(today_str, student_row.get("section_id", ""))
                            
                            record_id = str(uuid.uuid4())
                            if not existing.empty and sid in existing["student_id"].values:
                                record_id = existing[existing.student_id == sid]["record_id"].values[0]
                            
                            db.batch_add_attendance([{
                                "record_id": record_id,
                                "date": today_str,
                                "student_id": sid,
                                "status": "حاضر",
                                "notes": "تسجيل سريع",
                                "recorded_by": user.get("user_id", ""),
                                "section_id": student_row.get("section_id", "")
                            }])
                            db.add_log(user.get("user_id", ""), f"تسجيل حضور سريع - {name}")
                            st.success(f"✅ تم تسجيل حضور {name}")
                            st.toast(f"✅ تم تسجيل حضور {name}!", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ غياب", use_container_width=True, key="quick_absent"):
                            today_str = get_cairo_now().strftime("%Y-%m-%d")
                            existing = db.get_attendance_by_date_section(today_str, student_row.get("section_id", ""))
                            
                            record_id = str(uuid.uuid4())
                            if not existing.empty and sid in existing["student_id"].values:
                                record_id = existing[existing.student_id == sid]["record_id"].values[0]
                            
                            db.batch_add_attendance([{
                                "record_id": record_id,
                                "date": today_str,
                                "student_id": sid,
                                "status": "غائب",
                                "notes": "تسجيل سريع",
                                "recorded_by": user.get("user_id", ""),
                                "section_id": student_row.get("section_id", "")
                            }])
                            db.add_log(user.get("user_id", ""), f"تسجيل غياب سريع - {name}")
                            st.warning(f"❌ تم تسجيل غياب {name}")
                            st.toast(f"❌ تم تسجيل غياب {name}", icon="⚠️")
                            time.sleep(0.5)
                            st.rerun()
            else:
                st.warning("⚠️ لا توجد نتائج")
        
        # Today's attendance list
        st.markdown("---")
        st.subheader("📋 الحاضرين اليوم")
        today_str = get_cairo_now().strftime("%Y-%m-%d")
        today_attendance = db.get_attendance()
        
        if not today_attendance.empty and "date" in today_attendance.columns:
            today_attendance = today_attendance[today_attendance.date == today_str]
            
            if not today_attendance.empty:
                # Merge with student names
                if "student_id" in today_attendance.columns and not students.empty:
                    today_attendance = today_attendance.merge(students[["student_id", "full_name"]], on="student_id", how="left")
                
                if "status" in today_attendance.columns:
                    present = today_attendance[today_attendance.status == "حاضر"]
                    absent = today_attendance[today_attendance.status == "غائب"]
                    
                    col_p, col_a = st.columns(2)
                    col_p.metric("✅ الحاضرون", len(present))
                    col_a.metric("❌ الغائبون", len(absent))
                    
                    st.markdown("#### الحاضرين:")
                    if not present.empty:
                        for _, att in present.iterrows():
                            att_time = get_cairo_now().strftime("%I:%M %p")
                            st.write(f"✅ {att.get('full_name', '')} - {att_time}")
                    else:
                        st.info("لا يوجد حضور حتى الآن")
                    
                    st.markdown("#### الغائبون:")
                    if not absent.empty:
                        for _, att in absent.iterrows():
                            st.write(f"❌ {att.get('full_name', '')}")
                    else:
                        st.info("لا يوجد غياب")
            else:
                st.info("لا توجد سجلات حضور لهذا اليوم")
        else:
            st.info("لا توجد بيانات حضور")
    
    with tab2:
        st.markdown("#### 📷 مسح QR Code")
        st.info("📱 وجه الكاميرا نحو QR Code للطالبة")
        
        # Browser-based QR scanner with visual overlay
        qr_scanner_html = """
        <div id="qr-scanner-container" style="width: 100%; max-width: 640px; margin: 0 auto; padding: 1rem; background: var(--card-bg); border-radius: 12px;">
            <div id="qr-scanner" style="width: 100%; height: 400px; background: #000; border-radius: 8px; position: relative; overflow: hidden;">
                <video id="video" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;" playsinline autoplay muted></video>
                <canvas id="canvas" style="display: none;"></canvas>
                
                <!-- Animated scanning overlay -->
                <div id="qr-overlay" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px; border: 3px solid #d4af37; border-radius: 12px; box-shadow: 0 0 0 9999px rgba(0,0,0,0.5); transition: all 0.3s ease;">
                    <!-- Animated corner brackets -->
                    <div style="position: absolute; top: -3px; left: -3px; width: 40px; height: 40px; border-top: 4px solid #28a745; border-left: 4px solid #28a745; border-radius: 12px 0 0 0;"></div>
                    <div style="position: absolute; top: -3px; right: -3px; width: 40px; height: 40px; border-top: 4px solid #28a745; border-right: 4px solid #28a745; border-radius: 0 12px 0 0;"></div>
                    <div style="position: absolute; bottom: -3px; left: -3px; width: 40px; height: 40px; border-bottom: 4px solid #28a745; border-left: 4px solid #28a745; border-radius: 0 0 0 12px;"></div>
                    <div style="position: absolute; bottom: -3px; right: -3px; width: 40px; height: 40px; border-bottom: 4px solid #28a745; border-right: 4px solid #28a745; border-radius: 0 0 12px 0;"></div>
                    
                    <!-- Scanning line animation -->
                    <div id="scan-line" style="position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, transparent, #28a745, transparent); box-shadow: 0 0 10px #28a745; animation: scanMove 2s linear infinite;"></div>
                </div>
                
                <!-- Success overlay (hidden by default) -->
                <div id="success-overlay" style="display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px; border: 3px solid #28a745; border-radius: 12px; background: rgba(40, 167, 69, 0.2); box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);">
                    <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 4rem;">✅</div>
                </div>
                
                <!-- Error overlay (hidden by default) -->
                <div id="error-overlay" style="display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px; border: 3px solid #dc3545; border-radius: 12px; background: rgba(220, 53, 69, 0.2); box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);">
                    <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 4rem;">❌</div>
                </div>
            </div>
            
            <div id="qr-status" style="margin-top: 1rem; padding: 0.8rem; background: var(--gold-light); border-radius: 8px; text-align: center; font-weight: 600; color: var(--text-primary);">
                ⏳ جاري تشغيل الكاميرا...
            </div>
            
            <button id="start-scan-btn" style="margin-top: 1rem; padding: 0.7rem 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; width: 100%; font-size: 1rem;">
                📷 بدء المسح
            </button>
        </div>

        <style>
            @keyframes scanMove {
                0% { top: 0; opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { top: 100%; opacity: 0; }
            }
        </style>

        <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
        <script>
            let video = document.getElementById('video');
            let canvas = document.getElementById('canvas');
            let ctx = canvas.getContext('2d');
            let scanning = false;
            let stream = null;
            let qrDetected = false;

            function showOverlay(type) {
                document.getElementById('qr-overlay').style.display = 'none';
                document.getElementById('success-overlay').style.display = 'none';
                document.getElementById('error-overlay').style.display = 'none';
                
                if (type === 'success') {
                    document.getElementById('success-overlay').style.display = 'block';
                } else if (type === 'error') {
                    document.getElementById('error-overlay').style.display = 'block';
                }
            }

            function startCamera() {
                const statusDiv = document.getElementById('qr-status');
                const startBtn = document.getElementById('start-scan-btn');
                
                if (scanning) {
                    stopCamera();
                    return;
                }

                // Reset overlays
                qrDetected = false;
                document.getElementById('qr-overlay').style.display = 'block';
                document.getElementById('success-overlay').style.display = 'none';
                document.getElementById('error-overlay').style.display = 'none';

                // Ensure video element is ready
                if (!video) {
                    statusDiv.innerHTML = '❌ خطأ: عنصر الفيديو غير موجود';
                    return;
                }

                navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: 'environment',
                        width: { ideal: 1280 },
                        height: { ideal: 720 }
                    } 
                })
                .then(function(mediaStream) {
                    stream = mediaStream;
                    video.srcObject = mediaStream;
                    video.setAttribute('playsinline', true);
                    video.setAttribute('autoplay', true);
                    video.setAttribute('muted', true);
                    video.play().then(function() {
                        scanning = true;
                        statusDiv.innerHTML = '✅ الكاميرا تعمل - وجّهها نحو QR Code';
                        statusDiv.style.background = 'rgba(40,167,69,0.15)';
                        startBtn.innerHTML = '⏹️ إيقاف المسح';
                        startBtn.style.background = 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)';
                        requestAnimationFrame(tick);
                    }).catch(function(err) {
                        console.error("Video play error:", err);
                        statusDiv.innerHTML = '❌ خطأ في تشغيل الفيديو: ' + err.message;
                        statusDiv.style.background = 'rgba(220,53,69,0.15)';
                    });
                })
                .catch(function(err) {
                    console.error("Camera error:", err);
                    statusDiv.innerHTML = '❌ خطأ في الوصول للكاميرا: ' + err.message;
                    statusDiv.style.background = 'rgba(220,53,69,0.15)';
                });
            }

            function stopCamera() {
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    stream = null;
                }
                scanning = false;
                qrDetected = false;
                const statusDiv = document.getElementById('qr-status');
                const startBtn = document.getElementById('start-scan-btn');
                statusDiv.innerHTML = '⏹️ الكاميرا متوقفة';
                statusDiv.style.background = 'var(--gold-light)';
                startBtn.innerHTML = '📷 بدء المسح';
                startBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                
                // Reset overlays
                document.getElementById('qr-overlay').style.display = 'block';
                document.getElementById('success-overlay').style.display = 'none';
                document.getElementById('error-overlay').style.display = 'none';
            }

            function tick() {
                if (!scanning) return;
                
                if (video.readyState === video.HAVE_ENOUGH_DATA && !qrDetected) {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    let imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    let code = jsQR(imageData.data, imageData.width, imageData.height, {
                        inversionAttempts: 'dontInvert'
                    });
                    
                    if (code) {
                        // QR Code detected!
                        qrDetected = true;
                        scanning = false;
                        
                        // Show success overlay
                        showOverlay('success');
                        statusDiv.innerHTML = '✅ تم اكتشاف QR Code بنجاح!';
                        statusDiv.style.background = 'rgba(40,167,69,0.15)';
                        
                        // Parse QR data
                        const parts = code.data.split('\\n');
                        let name = "";
                        let sid = "";
                        
                        parts.forEach(part => {
                            const trimmed = part.trim();
                            if (trimmed.startsWith("Member:")) {
                                name = trimmed.replace("Member:", "").trim();
                            } else if (trimmed.startsWith("ID:")) {
                                sid = trimmed.replace("ID:", "").trim();
                            }
                        });

                        // Send result to Streamlit via URL params (without page reload)
                        const params = new URLSearchParams(window.location.search);
                        params.set('qr_name', encodeURIComponent(name));
                        params.set('qr_id', encodeURIComponent(sid));
                        params.set('qr_raw', encodeURIComponent(code.data));
                        window.history.replaceState({}, '', window.location.pathname + '?' + params.toString());
                        
                        // Trigger Streamlit to re-read query params
                        window.dispatchEvent(new Event('popstate'));
                        
                        return;
                    }
                }
                requestAnimationFrame(tick);
            }

            // Start button handler
            document.getElementById('start-scan-btn').addEventListener('click', startCamera);

            // Auto-start on load
            window.addEventListener('load', function() {
                setTimeout(startCamera, 500);
            });

            // Cleanup on unload
            window.addEventListener('beforeunload', function() {
                stopCamera();
            });
        </script>
        """
        
        # Read QR scan result from query params (set by JS via URL redirect)
        try:
            qr_raw_param = st.query_params.get('qr_raw', [''])[0]
            if qr_raw_param and not st.session_state.get('qr_scan_result'):
                st.session_state.qr_scan_result = {
                    'name': st.query_params.get('qr_name', [''])[0],
                    'student_id': st.query_params.get('qr_id', [''])[0],
                    'raw': qr_raw_param
                }
                st.query_params.clear()
        except Exception:
            pass
        
        st.components.v1.html(qr_scanner_html, height=550, scrolling=False)
        
        # Initialize session state for QR result and rate limiting
        if 'qr_scan_result' not in st.session_state:
            st.session_state.qr_scan_result = None
        if 'last_qr_scan_time' not in st.session_state:
            st.session_state.last_qr_scan_time = 0
        if 'qr_scan_cooldown' not in st.session_state:
            st.session_state.qr_scan_cooldown = 2  # seconds between scans
        
        # Process QR scan result with validation
        if st.session_state.get('qr_scan_result'):
            result = st.session_state.qr_scan_result
            raw_qr_data = result.get('raw', '')
            qr_name = result.get('name', '')
            qr_id = result.get('student_id', '')
            
            # ===== Step 1: Validate QR code against registered students =====
            validation = validate_qr_code(db, raw_qr_data, students)
            
            if not validation['valid']:
                # Show detailed error with the parsed QR data
                st.markdown(f"""
                <div style="text-align:center; padding:1.5rem; background:rgba(220,53,69,0.1); border:2px solid #dc3545; border-radius:15px; margin:1rem 0;">
                    <div style="font-size:3rem; margin-bottom:0.5rem;">❌</div>
                    <div style="font-size:1.2rem; font-weight:700; color:#dc3545;">{validation['message']}</div>
                    <div style="font-size:0.9rem; color:#666; margin-top:0.5rem;">
                        بيانات QR Code الممسوحة:<br>
                        المعرف: {qr_id if qr_id else 'غير موجود'}<br>
                        الاسم: {qr_name if qr_name else 'غير موجود'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                log_details_operation(
                    db=db,
                    student_id=qr_id,
                    student_name=qr_name,
                    status="Invalid",
                    operation_type="QR_Scan_Failed",
                    qr_data=raw_qr_data,
                    device_info="QR Scanner",
                    notes=validation['message']
                )
                if st.button("🔁 إعادة المسح", use_container_width=True, key="retry_invalid_qr"):
                    st.session_state.qr_scan_result = None
                    st.rerun()
                return
            
            # ===== Step 2: Get validated student info =====
            student_id = validation['student_id']
            student_name = validation['student_name']
            section_id = validation['section_id']
            today_str = get_cairo_now().strftime("%Y-%m-%d")
            
            # Get section name
            section_name = ""
            if not sections.empty and section_id in sections["section_id"].values:
                section_name = sections[sections.section_id == section_id]["section_name"].values[0]
            
            # ===== Step 3: Check for duplicate attendance =====
            is_duplicate = check_duplicate_attendance(db, student_id, today_str)
            
            if is_duplicate:
                avatar_color = get_avatar_color(student_name)
                first_letter = student_name[0] if student_name else "?"
                st.markdown(f"""
                <div style="text-align:center; padding:1.5rem; background:rgba(255,193,7,0.1); border:2px solid #ffc107; border-radius:15px; margin:1rem 0;">
                    <div style="font-size:3rem; margin-bottom:0.5rem;">⚠️</div>
                    <div style="display:flex; align-items:center; gap:1rem; justify-content:center; margin-bottom:0.5rem;">
                        <div class="member-avatar" style="background:{avatar_color};">{first_letter}</div>
                        <div style="text-align:right;">
                            <div style="font-size:1.2rem; font-weight:700;">{student_name}</div>
                            <div style="font-size:0.9rem; color:#666;">{section_name if section_name else 'بدون خدمة'}</div>
                        </div>
                    </div>
                    <div style="font-size:1.1rem; font-weight:600; color:#d4a017;">تم تسجيل حضور {student_name} مسبقاً اليوم!</div>
                    <div style="font-size:0.9rem; color:#666; margin-top:0.3rem;">لا يمكن تسجيل الحضور أكثر من مرة في نفس اليوم.</div>
                </div>
                """, unsafe_allow_html=True)
                
                log_details_operation(
                    db=db,
                    student_id=student_id,
                    student_name=student_name,
                    status="Duplicate",
                    operation_type="QR_Scan_Duplicate",
                    qr_data=raw_qr_data,
                    device_info="QR Scanner",
                    notes="محاولة تسجيل مكرر في نفس اليوم"
                )
                if st.button("🔁 مسح طالبة أخرى", use_container_width=True, key="duplicate_ok"):
                    st.session_state.qr_scan_result = None
                    st.rerun()
                return
            
            # ===== Step 4: Show student info with Confirm/Cancel buttons =====
            if not st.session_state.get('qr_confirmed'):
                avatar_color = get_avatar_color(student_name)
                first_letter = student_name[0] if student_name else "?"
                now_time = get_cairo_now().strftime("%I:%M %p")
                
                st.markdown(f"""
                <div style="text-align:center; padding:1.5rem; background:rgba(40,167,69,0.08); border:2px solid #28a745; border-radius:15px; margin:1rem 0;">
                    <div style="font-size:2rem; margin-bottom:0.8rem;">✅</div>
                    <div style="display:flex; align-items:center; gap:1rem; justify-content:center; margin-bottom:0.8rem; flex-wrap:wrap;">
                        <div class="member-avatar" style="background:{avatar_color}; width:64px; height:64px; font-size:1.8rem;">{first_letter}</div>
                        <div style="text-align:right;">
                            <div style="font-size:1.4rem; font-weight:700;">{student_name}</div>
                            <div style="font-size:1rem; color:#667eea; font-weight:600;">🏫 {section_name if section_name else 'بدون خدمة'}</div>
                            <div style="font-size:0.9rem; color:#666; margin-top:0.3rem;">🆔 {student_id[:12]}...</div>
                        </div>
                    </div>
                    <div style="background:var(--card-bg); border-radius:10px; padding:0.8rem; margin:0.5rem 0;">
                        <div style="font-size:0.95rem; color:var(--text-secondary);">
                            📅 التاريخ: {get_cairo_now().strftime("%Y-%m-%d")} | 🕐 الوقت: {now_time}
                        </div>
                        <div style="font-size:0.95rem; color:var(--text-secondary); margin-top:0.2rem;">
                            ✅ الحالة: <span style="color:#28a745; font-weight:700;">حاضر</span>
                        </div>
                    </div>
                    <div style="font-size:0.9rem; color:#666; margin-top:0.5rem;">
                        هل أنت متأكد من تسجيل حضور هذه الطالبة؟
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ تأكيد الحضور", use_container_width=True, type="primary", key="confirm_attendance"):
                        st.session_state.qr_confirmed = True
                        st.rerun()
                with col2:
                    if st.button("❌ إلغاء", use_container_width=True, key="cancel_attendance"):
                        st.session_state.qr_scan_result = None
                        st.session_state.qr_confirmed = None
                        st.rerun()
                
                # Also add a retry button
                if st.button("🔁 مسح طالبة أخرى", use_container_width=True, key="rescan_btn_conf"):
                    st.session_state.qr_scan_result = None
                    st.session_state.qr_confirmed = None
                    st.rerun()
                
                return
            
            # ===== Step 5: Save attendance after confirmation =====
            record_id = str(uuid.uuid4())
            db.batch_add_attendance([{
                "record_id": record_id, "date": today_str, "student_id": student_id,
                "status": "حاضر", "notes": "تسجيل حضور عن طريق QR Code", "recorded_by": user.get("user_id", ""),
                "section_id": section_id
            }])
            db.add_log(user.get("user_id", ""), f"تسجيل حضور QR Code - {student_name}")
            log_details_operation(
                db=db,
                student_id=student_id,
                student_name=student_name,
                status="Present",
                operation_type="QR_Checkin",
                qr_data=raw_qr_data,
                device_info="QR Scanner",
                notes="تسجيل حضور عن طريق QR Code"
            )
            
            # Show success message with student info
            avatar_color = get_avatar_color(student_name)
            first_letter = student_name[0] if student_name else "?"
            now_time = get_cairo_now().strftime("%I:%M %p")
            
            st.markdown(f"""
            <div style="text-align:center; padding:1.5rem; background:rgba(40,167,69,0.12); border:2px solid #28a745; border-radius:15px; margin:1rem 0; animation:fadeIn 0.5s;">
                <div style="font-size:3rem; margin-bottom:0.5rem;">🎉</div>
                <div style="display:flex; align-items:center; gap:1rem; justify-content:center; margin-bottom:0.8rem; flex-wrap:wrap;">
                    <div class="member-avatar" style="background:{avatar_color}; width:64px; height:64px; font-size:1.8rem;">{first_letter}</div>
                    <div style="text-align:right;">
                        <div style="font-size:1.4rem; font-weight:700; color:#28a745;">✅ تم تسجيل حضور {student_name}</div>
                        <div style="font-size:1rem; color:#667eea; font-weight:600;">🏫 {section_name if section_name else 'بدون خدمة'}</div>
                    </div>
                </div>
                <div style="background:var(--card-bg); border-radius:10px; padding:0.8rem; margin:0.5rem 0;">
                    <div style="font-size:0.95rem; color:var(--text-secondary);">
                        📅 التاريخ: {get_cairo_now().strftime("%Y-%m-%d")} | 🕐 الوقت: {now_time}
                    </div>
                    <div style="font-size:0.95rem; color:var(--text-secondary); margin-top:0.2rem;">
                        ✅ الحالة: <span style="color:#28a745; font-weight:700;">حاضر</span>
                    </div>
                </div>
            </div>
            <style>
            @keyframes fadeIn {{
                from {{ opacity:0; transform:translateY(10px); }}
                to {{ opacity:1; transform:translateY(0); }}
            }}
            </style>
            """, unsafe_allow_html=True)
            
            st.success(f"✅ تم تسجيل حضور {student_name} بنجاح")
            st.toast(f"✅ تم تسجيل حضور {student_name}!", icon="🎉")
            
            # Reset for next scan
            if st.button("🔁 مسح طالبة أخرى", use_container_width=True, key="scan_another"):
                st.session_state.qr_scan_result = None
                st.session_state.qr_confirmed = None
                st.rerun()
    
    
    st.markdown("---")
    st.subheader("📋 جدول الحاضرين اليوم")
    # Get today's attendance for display
    today_attendance_all = db.get_attendance()
    today_att = pd.DataFrame()
    if not today_attendance_all.empty and "date" in today_attendance_all.columns:
        today_str_display = get_cairo_now().strftime("%Y-%m-%d")
        today_att = today_attendance_all[today_attendance_all.date == today_str_display].copy()
        if not today_att.empty and "student_id" in today_att.columns and not students.empty:
            today_att = today_att.merge(students[["student_id", "full_name"]], on="student_id", how="left")
    if not today_att.empty:
        display_df = today_att[["full_name", "status", "notes", "time"]].copy() if "time" in today_att.columns else today_att[["full_name", "status", "notes"]].copy()
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("لا يوجد حضور مسجل اليوم")

# =============================================================================
# Bulk Attendance
# =============================================================================
def show_bulk_attendance(db: Database):
    """Bulk attendance registration for all members."""
    st.markdown("<h2 class='main-header'>📋 تسجيل حضور المجموعة</h2>", unsafe_allow_html=True)
    
    user = st.session_state.user
    role = user.get("role", "")
    section_id = user.get("section_id", "")
    
    if role == "Service Manager":
        st.error("🚫 أمناء الخدمة لا يمكنهم تسجيل الحضور.")
        return
    
    students = db.get_students()
    sections = db.get_sections()
    
    if students.empty:
        st.info("لا توجد طالبات مسجلات.")
        return
    
    if sections.empty:
        st.warning("لا توجد فصول مسجلة.")
        return
    
    # Section selection
    if role == "Teacher" and section_id:
        selected_section = section_id
        section_name = sections[sections.section_id == section_id]["section_name"].values[0] if not sections.empty else section_id
        st.write(f"**الفصل:** {section_name}")
    else:
        selected_section = st.selectbox("اختر الفصل", sections["section_id"],
                                       format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])

    section_students = students[students.section_id == selected_section] if not students.empty and "section_id" in students.columns else pd.DataFrame()
    if section_students.empty:
        st.info("لا توجد طالبات في هذا الفصل.")
        return
    
    date = st.date_input("التاريخ", get_cairo_now().date())
    date_str = date.strftime("%Y-%m-%d")
    
    existing = db.get_attendance_by_date_section(date_str, selected_section)
    already_filled = not existing.empty
    
    if already_filled:
        st.warning("⚠️ يوجد تسجيل حضور سابق لهذا اليوم")
    
    st.markdown('<div class="bulk-action-bar">', unsafe_allow_html=True)
    st.markdown(f"<span style='font-weight:700;'>👥 {len(section_students)} طالبة</span>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Grid layout with checkboxes
    st.markdown('<div class="member-grid">', unsafe_allow_html=True)
    
    attendance_status = {}
    
    for _, student in section_students.iterrows():
        sid = student.get("student_id", "")
        name = student.get("full_name", "")
        
        # Check existing status
        prev_status = "حاضر"
        if already_filled and sid in existing["student_id"].values:
            prev_status = existing[existing.student_id == sid]["status"].values[0]
        
        attendance_status[sid] = prev_status
        
        avatar_color = get_avatar_color(name)
        first_letter = name[0] if name else "?"
        
        # Member card
        st.markdown(f"""
        <div class="member-card">
            <div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.8rem;">
                <div class="member-avatar" style="background:{avatar_color};">{first_letter}</div>
                <div style="flex:1; min-width:0;">
                    <div style="font-weight:700; font-size:1rem; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick select buttons
        col_p, col_a, col_l = st.columns(3)
        with col_p:
            is_present = st.checkbox("✅ حاضر", value=(prev_status == "حاضر"), key=f"bulk_present_{sid}")
            if is_present:
                attendance_status[sid] = "حاضر"
        with col_a:
            is_absent = st.checkbox("❌ غائب", value=(prev_status == "غائب"), key=f"bulk_absent_{sid}")
            if is_absent:
                attendance_status[sid] = "غائب"
        with col_l:
            is_late = st.checkbox("🕐 متأخر", value=(prev_status == "متأخر"), key=f"bulk_late_{sid}")
            if is_late:
                attendance_status[sid] = "متأخر"
        
        st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Save button
    if st.button("💾 حفظ الحضور للكل", use_container_width=True, type="primary", key="save_bulk_attendance"):
        with st.spinner("جاري حفظ الحضور..."):
            records = []
            for sid, status in attendance_status.items():
                student_name = section_students[section_students.student_id == sid]["full_name"].values[0] if sid in section_students["student_id"].values else sid
                
                record_id = str(uuid.uuid4())
                if already_filled and sid in existing["student_id"].values:
                    record_id = existing[existing.student_id == sid]["record_id"].values[0]
                
                records.append({
                    "record_id": record_id,
                    "date": date_str,
                    "student_id": sid,
                    "status": status,
                    "notes": "تسجيل جماعي",
                    "recorded_by": user.get("user_id", ""),
                    "section_id": selected_section
                })
            
            db.batch_add_attendance(records)
            db.add_log(user.get("user_id", ""), f"تسجيل حضور جماعي فصل {selected_section} ليوم {date_str}")
            st.success("✅ تم حفظ الحضور بنجاح!")
            st.toast("✅ تم حفظ الحضور بنجاح!", icon="🎉")
            time.sleep(1)
            st.rerun()

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

            # Determine current page choice
            if st.session_state.show_sidebar:
                # Sidebar is visible - use its returned choice
                choice = show_sidebar_navigation(db)
            else:
                # Sidebar is hidden - use stored choice with validation
                choice = st.session_state.get("menu_choice", "🏠 لوحة التحكم")
                role = st.session_state.user.get("role", "")
                
                # Define valid menu items for current role
                all_menus = {
            "System Admin": [
                "🏠 لوحة التحكم", "👥 إدارة المستخدمين", "🌟 إدارة الأعضاء", "🏫 إدارة المراحل",
                "⚡ حضور سريع", "📋 الحضور", "📈 لوحة تحكم الحضور",
                "💬 الافتقاد", "📝 المسابقات والاختبارات", "📅 الفعاليات",
                "📊 التقارير والإحصائيات", "📜 سجل العمليات", "🔐 سجل الدخول", "🔒 تغيير كلمة المرور"
            ],
                    "Father Account": ["🏠 لوحة التحكم", "📅 الفعاليات", "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                    "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "💬 الافتقاد",
                                        "📝 المسابقات والاختبارات", "📅 الفعاليات",
                                        "📊 التقارير والإحصائيات", "🔒 تغيير كلمة المرور"],
                    "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "⚡ حضور سريع", "📋 الحضور",
                                "📈 لوحة تحكم الحضور", "💬 الافتقاد",
                                "🏆 درجات المسابقات", "📅 الفعاليات", "🔒 تغيير كلمة المرور"]
                }
                valid_items = set()
                for r in ["System Admin", "Father Account", "Service Manager", "Teacher"]:
                    valid_items.update(all_menus.get(r, []))
                
                if choice not in valid_items:
                    st.session_state.menu_choice = "🏠 لوحة التحكم"
                    choice = "🏠 لوحة التحكم"
            
            # Safety: ensure choice is never None
            if not choice:
                choice = "🏠 لوحة التحكم"
                st.session_state.menu_choice = choice
            
            # Always render the floating button when sidebar is hidden
            if not st.session_state.show_sidebar:
                st.markdown('<div class="floating-show-btn">', unsafe_allow_html=True)
                show_btn_key = f"show_sidebar_btn_{hash(str(st.session_state.get('show_sidebar', True)))}"
                if st.button("☰", key=show_btn_key):
                    st.session_state.show_sidebar = True
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("<div class='content-area'>", unsafe_allow_html=True)
            if choice == "🏠 لوحة التحكم":
                show_dashboard(db)
            elif choice == "👥 إدارة المستخدمين":
                if st.session_state.user.get("role") == "System Admin":
                    show_user_management(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "🌟 إدارة الأعضاء":
                if st.session_state.user.get("role") == "System Admin":
                    show_member_management(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "🏫 إدارة المراحل":
                if st.session_state.user.get("role") == "System Admin":
                    show_stages_management(db)
                else:
                    st.error("🚫 غير مصرح")
            elif choice == "⚡ حضور سريع":
                show_quick_checkin(db)
            elif choice == "📋 الحضور":
                show_attendance(db)
            elif choice == "📈 لوحة تحكم الحضور":
                show_attendance(db)
            elif choice == "💬 الافتقاد":
                show_followup(db)
            elif choice == "🏆 درجات المسابقات":
                show_class_competition_scores(db)
            elif choice == "📝 المسابقات والاختبارات":
                show_quizzes(db)
            elif choice == "📅 الفعاليات":
                show_events_page(db)
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
