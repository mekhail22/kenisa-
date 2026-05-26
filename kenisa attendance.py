import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import hashlib
import uuid
import json
import random
import string
import jwt
import secrets
import time

# ===================== الإعدادات العامة (قيم افتراضية قابلة للتجاوز) =====================
DEFAULT_PASSWORD_SALT = "K9f2Lm8QxP4rV7sA"          # يمكن تغييرها في secrets.toml
DEFAULT_JWT_SECRET = "t7Yp!2kL$9xR@vN8#wQ3^eH*5Jm+6Uc0"

def get_credentials():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return creds
    except Exception as e:
        st.error(f"❌ خطأ في بيانات اعتماد Google. تأكد من .streamlit/secrets.toml: {e}")
        st.stop()

def get_spreadsheet_id():
    return st.secrets["sheets"]["spreadsheet_id"]

def get_salt():
    # استخدام القيمة من secrets إذا وجدت، وإلا الافتراضية
    try:
        return st.secrets["sheets"]["password_salt"]
    except:
        return DEFAULT_PASSWORD_SALT

def get_jwt_secret():
    try:
        return st.secrets["sheets"]["jwt_secret"]
    except:
        return DEFAULT_JWT_SECRET

# ===================== CSS =====================
def inject_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { font-family: 'Cairo', sans-serif; }
        body { direction: rtl; text-align: right; }
        .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 100%); }
        .main-header {
            font-size: 2.2rem; font-weight: 700; color: #2c3e50; text-align: center;
            margin-bottom: 1.5rem; padding: 1rem; background: white; border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        .card {
            background: white; border-radius: 15px; padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 1rem;
            transition: transform 0.2s;
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
        .stat-card {
            background: white; border-radius: 15px; padding: 1.2rem; text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .stat-card .value { font-size: 2.2rem; font-weight: 700; color: #2c3e50; margin: 0.5rem 0; }
        .stat-card .label { font-size: 1rem; color: #7f8c8d; }
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;
            border: none; border-radius: 8px; font-weight: 600; transition: 0.2s;
        }
        .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(102,126,234,0.4); }
        .stRadio > div, .stSelectbox > div, .stMultiSelect > div { direction: rtl; }
        .stMarkdown, .stTextInput, .stTextArea, .stNumberInput, .stDateInput { text-align: right; }
    </style>
    """, unsafe_allow_html=True)

# ===================== قاعدة البيانات =====================
class Database:
    def __init__(self, creds, spreadsheet_id):
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(self, name, columns):
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=2000, cols=len(columns))
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
            ws.update([columns] + df.values.tolist())
        else:
            ws.update([columns])

    # --- المستخدمون ---
    def get_users(self):
        return self._sheet_to_df("Users")

    def add_user(self, user_data: dict):
        df = self.get_users()
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        self._df_to_sheet("Users", df, [
            "user_id", "username", "password_hash", "role",
            "full_name", "section_id", "phone", "email"
        ])

    # --- الأقسام ---
    def get_sections(self):
        return self._sheet_to_df("Sections")

    def add_section(self, sec_data: dict):
        df = self.get_sections()
        df = pd.concat([df, pd.DataFrame([sec_data])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    # --- الطالبات ---
    def get_students(self):
        return self._sheet_to_df("Students")

    def add_student(self, student_data: dict):
        df = self.get_students()
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        self._df_to_sheet("Students", df, [
            "student_id", "full_name", "section_id", "teacher_id",
            "phone", "parent_phone", "birthdate", "address", "notes", "status"
        ])

    # --- الحضور ---
    def get_attendance(self):
        return self._sheet_to_df("Attendance")

    def add_attendance_record(self, record: dict):
        df = self.get_attendance()
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("Attendance", df, [
            "record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"
        ])

    # --- الافتقاد ---
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record: dict):
        df = self.get_followup()
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("FollowUp", df, [
            "record_id", "student_id", "teacher_id", "followup_date",
            "followup_type", "notes", "regularity_status"
        ])

    # --- الاختبارات ---
    def get_quizzes(self):
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data: dict):
        df = self.get_quizzes()
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
        return df[df.quiz_id == quiz_id] if not df.empty else pd.DataFrame()

    def add_question(self, q_data: dict):
        df = self._sheet_to_df("QuizQuestions")
        df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
        self._df_to_sheet("QuizQuestions", df, [
            "question_id", "quiz_id", "question_text", "question_type",
            "option1", "option2", "option3", "option4", "correct_answer"
        ])

    def save_quiz_result(self, result: dict):
        df = self._sheet_to_df("QuizResults")
        df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, [
            "result_id", "quiz_id", "student_id", "student_name",
            "score", "total_marks", "submission_time", "answers"
        ])

    def add_log(self, user_id, action, details=""):
        df = self._sheet_to_df("Logs")
        log = {
            "log_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "details": details
        }
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

# ===================== التشفير والتوثيق =====================
def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()

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
        "student_quiz_started": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def logout():
    if st.session_state.user:
        db = Database(get_credentials(), get_spreadsheet_id())
        db.add_log(st.session_state.user["user_id"], "تسجيل الخروج")
    st.session_state.clear()
    st.rerun()

# ===================== صفحة التهيئة الإجبارية =====================
def show_initialization(db: Database, salt: str):
    users = db.get_users()
    if users.empty:
        st.markdown("<div class='card'><h2 style='text-align:center;'>🔧 لا يوجد مستخدمون بعد</h2>", unsafe_allow_html=True)
        st.markdown("#### يرجى الضغط على الزر التالي لإنشاء مدير النظام الافتراضي:")
        if st.button("🛠️ تهيئة النظام وإنشاء المسؤول الأول", type="primary"):
            admin_data = {
                "user_id": "admin-001",
                "username": "admin",
                "password_hash": hash_password("admin123", salt),
                "role": "System Admin",
                "full_name": "مدير النظام",
                "section_id": "",
                "phone": "0100000000",
                "email": "admin@church.com"
            }
            db.add_user(admin_data)
            st.success("✅ تم إنشاء مدير النظام بنجاح!")
            st.info("**اسم المستخدم:** `admin`  \n**كلمة المرور:** `admin123`")
            st.markdown("---")
            st.markdown("**التالي:** أعد تحميل الصفحة أو انتظر التحديث التلقائي...")
            time.sleep(2)
            st.rerun()
        st.stop()  # منع عرض باقي الصفحة حتى التهيئة

# ===================== واجهة تسجيل الدخول =====================
def show_login_page(db: Database, salt: str, jwt_secret: str):
    st.markdown("<h1 class='main-header'>⛪ نظام الغياب والافتقاد<br>الكنيسة الشهيدة دميانة بأسيوط</h1>", unsafe_allow_html=True)

    show_initialization(db, salt)

    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم", placeholder="admin")
            password = st.text_input("كلمة المرور", type="password", placeholder="admin123")
            submitted = st.form_submit_button("تسجيل الدخول", use_container_width=True)

            if submitted:
                users = db.get_users()
                user_row = users[users.username == username]
                if user_row.empty:
                    st.error("اسم المستخدم غير موجود")
                else:
                    user = user_row.iloc[0].to_dict()
                    expected_hash = hash_password(password, salt)
                    if expected_hash == user["password_hash"]:
                        token = generate_token(user, jwt_secret)
                        st.session_state.token = token
                        st.session_state.user = user
                        st.session_state.authenticated = True
                        db.add_log(user["user_id"], "تسجيل الدخول")
                        st.success("تم تسجيل الدخول بنجاح!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("كلمة المرور غير صحيحة")
                        # تشخيص مبسط (قابل للإخفاء)
                        with st.expander("لماذا تظهر خاطئة؟ (تشخيص)"):
                            st.write("**الهاش المحسوب من كلمة المرور المدخلة:**")
                            st.code(expected_hash)
                            st.write("**الهاش المخزن في قاعدة البيانات:**")
                            st.code(user["password_hash"])
                            st.write("**الـ Salt المستخدم حاليًا:**", salt)

    with tab2:
        st.subheader("دخول الاختبار الإلكتروني")
        code = st.text_input("كود الاختبار", placeholder="مثال: GEN123")
        passwd = st.text_input("كلمة مرور الاختبار", type="password", placeholder="مثال: QUIZ99")
        if st.button("بدء الاختبار", key="student_quiz_btn"):
            quizzes = db.get_quizzes()
            quiz = quizzes[(quizzes.quiz_code == code) & (quizzes.password == passwd)]
            if quiz.empty:
                st.error("كود أو كلمة مرور خاطئة")
            else:
                quiz = quiz.iloc[0].to_dict()
                if pd.to_datetime(quiz["expiry_date"]) < datetime.now():
                    st.error("انتهت صلاحية الاختبار")
                    db.update_quiz(quiz["quiz_id"], {"is_active": "False"})
                else:
                    st.session_state.student_quiz = quiz
                    st.session_state.student_quiz_started = True
                    st.rerun()

# ===================== اختبار الطالبات =====================
def show_student_quiz(db: Database):
    quiz = st.session_state.student_quiz
    st.title(f"📝 {quiz['title']}")
    st.markdown(f"الوقت: {quiz['time_limit_minutes']} دقيقة | الدرجة: {quiz['total_marks']}")

    questions = db.get_quiz_questions(quiz["quiz_id"])
    if questions.empty:
        st.warning("لا توجد أسئلة بعد.")
        if st.button("العودة"):
            st.session_state.student_quiz = None
            st.session_state.student_quiz_started = False
            st.rerun()
        return

    student_name = st.text_input("الاسم الثلاثي", placeholder="أدخل اسمك")
    answers = {}
    for idx, row in questions.iterrows():
        q = row.to_dict()
        st.markdown(f"**س {idx+1}: {q['question_text']}**")
        q_type = q["question_type"]
        if q_type in ["اختيار من متعدد", "صح وخطأ"]:
            options = []
            if q_type == "اختيار من متعدد":
                options = [q["option1"], q["option2"], q["option3"], q["option4"]]
            else:
                options = ["صح", "خطأ"]
            options = [o for o in options if o]
            if options:
                ans = st.radio("الإجابة", options, key=f"q_{idx}", index=None)
                answers[q["question_id"]] = ans if ans else ""
        else:
            ans = st.text_input("الإجابة", key=f"q_{idx}")
            answers[q["question_id"]] = ans
        st.markdown("---")

    if st.button("تسليم الاختبار", type="primary", disabled=not student_name.strip()):
        score = sum(1 for _, q in questions.iterrows() if str(q["correct_answer"]).strip().lower() == str(answers.get(q["question_id"], "")).strip().lower())
        db.save_quiz_result({
            "result_id": str(uuid.uuid4()),
            "quiz_id": quiz["quiz_id"],
            "student_id": "external",
            "student_name": student_name,
            "score": score,
            "total_marks": len(questions),
            "submission_time": datetime.now().isoformat(),
            "answers": json.dumps(answers, ensure_ascii=False)
        })
        st.balloons()
        st.success(f"نتيجتك: {score}/{len(questions)}")
        if st.button("إنهاء"):
            st.session_state.student_quiz = None
            st.session_state.student_quiz_started = False
            st.rerun()

# ===================== القائمة الجانبية =====================
def sidebar_menu():
    role = st.session_state.user["role"]
    menus = {
        "System Admin": ["🏠 لوحة التحكم", "👥 إدارة المستخدمين", "👩‍🎓 الطالبات", "👩‍🏫 المدرسات والأقسام",
                         "📋 الحضور", "💬 الافتقاد", "📝 المسابقات والاختبارات", "📊 التقارير", "📜 السجلات"],
        "Father Account": ["🏠 لوحة التحكم", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات", "📊 التقارير"],
        "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات", "📊 التقارير"],
        "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد"]
    }
    menu = menus.get(role, [])
    st.sidebar.markdown(f"### 👤 {st.session_state.user['full_name']}  \n*{role}*")
    st.sidebar.markdown("---")
    choice = st.sidebar.radio("القائمة", menu)
    if st.sidebar.button("تسجيل الخروج"):
        logout()
    return choice

# ===================== صفحات التطبيق =====================
def show_dashboard(db):
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()
    col1, col2, col3, col4 = st.columns(4)
    today = datetime.now().strftime("%Y-%m-%d")
    present = len(attendance[(attendance.date == today) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent = len(attendance[(attendance.date == today) & (attendance.status == "غائب")]) if not attendance.empty else 0
    col1.markdown(f"<div class='stat-card'><div class='label'>الطالبات</div><div class='value'>{len(students)}</div></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='stat-card'><div class='label'>حضور اليوم</div><div class='value'>{present}</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='stat-card'><div class='label'>غياب اليوم</div><div class='value'>{absent}</div></div>", unsafe_allow_html=True)
    need_fup = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0
    col4.markdown(f"<div class='stat-card'><div class='label'>منقطعات</div><div class='value'>{need_fup}</div></div>", unsafe_allow_html=True)

    if not attendance.empty:
        attendance["date"] = pd.to_datetime(attendance["date"])
        last_week = datetime.now() - timedelta(days=7)
        recent = attendance[attendance.date >= last_week]
        if not recent.empty:
            fig = px.histogram(recent, x="date", color="status", barmode="group", title="الحضور الأسبوعي")
            st.plotly_chart(fig, use_container_width=True)

def show_admin_users(db, salt):
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    users = db.get_users()
    if not users.empty:
        st.dataframe(users, use_container_width=True)
    with st.expander("➕ إضافة مستخدم"):
        with st.form("add_user"):
            col1, col2 = st.columns(2)
            uname = col1.text_input("اسم المستخدم")
            full = col2.text_input("الاسم الكامل")
            pwd = col1.text_input("كلمة المرور", type="password")
            role = col2.selectbox("الصلاحية", ["System Admin", "Father Account", "Service Manager", "Teacher"])
            sec = None
            sections = db.get_sections()
            if role in ["Service Manager", "Teacher"]:
                sec = st.selectbox("القسم", ["None"] + sections["section_id"].tolist() if not sections.empty else ["None"])
            if st.form_submit_button("إضافة"):
                if not uname or not pwd:
                    st.error("مطلوب اسم المستخدم وكلمة المرور")
                else:
                    db.add_user({
                        "user_id": str(uuid.uuid4()),
                        "username": uname,
                        "password_hash": hash_password(pwd, salt),
                        "role": role,
                        "full_name": full,
                        "section_id": sec if sec and sec != "None" else "",
                        "phone": "",
                        "email": ""
                    })
                    st.success("تمت الإضافة")
                    st.rerun()

def show_students(db):
    st.markdown("<h2 class='main-header'>👩‍🎓 الطالبات</h2>", unsafe_allow_html=True)
    students = db.get_students()
    sections = db.get_sections()
    teachers = db.get_users()[db.get_users().role.isin(["Teacher", "Service Manager"])]
    if not students.empty:
        disp = students.merge(sections[["section_id","section_name"]], on="section_id", how="left")
        st.dataframe(disp, use_container_width=True)
    with st.expander("➕ إضافة طالبة"):
        with st.form("add_student"):
            name = st.text_input("الاسم الكامل")
            sec = st.selectbox("القسم", sections["section_id"] if not sections.empty else [])
            teacher = st.selectbox("المسؤولة", teachers["user_id"] if not teachers.empty else [])
            phone = st.text_input("هاتف")
            parent = st.text_input("هاتف ولي الأمر")
            if st.form_submit_button("إضافة") and name:
                db.add_student({
                    "student_id": str(uuid.uuid4()),
                    "full_name": name,
                    "section_id": sec,
                    "teacher_id": teacher,
                    "phone": phone,
                    "parent_phone": parent,
                    "birthdate": "",
                    "address": "",
                    "notes": "",
                    "status": "active"
                })
                st.success("تمت الإضافة")
                st.rerun()

def show_teachers_sections(db):
    st.markdown("<h2 class='main-header'>👩‍🏫 المدرسات والأقسام</h2>", unsafe_allow_html=True)
    sections = db.get_sections()
    st.subheader("الأقسام")
    if not sections.empty:
        st.dataframe(sections, use_container_width=True)
    with st.expander("➕ إضافة قسم"):
        with st.form("add_section"):
            name = st.text_input("اسم القسم")
            if st.form_submit_button("إضافة") and name:
                db.add_section({"section_id": str(uuid.uuid4()), "section_name": name, "manager_user_id": ""})
                st.success("تمت الإضافة")
                st.rerun()
    st.markdown("---")
    st.subheader("المدرسات وطالباتهن")
    teachers = db.get_users()[db.get_users().role == "Teacher"]
    students = db.get_students()
    for _, t in teachers.iterrows():
        tdata = t.to_dict()
        assigned = students[students.teacher_id == tdata["user_id"]]
        st.write(f"**{tdata['full_name']}**: {len(assigned)} طالبة")
        if not assigned.empty:
            st.dataframe(assigned[["full_name"]], use_container_width=True)

def show_attendance(db):
    st.markdown("<h2 class='main-header'>📋 الحضور</h2>", unsafe_allow_html=True)
    sections = db.get_sections()
    if sections.empty:
        st.warning("لا توجد أقسام")
        return
    sec = st.selectbox("القسم", sections["section_id"], format_func=lambda x: sections[sections.section_id==x]["section_name"].values[0])
    date = st.date_input("التاريخ", datetime.now())
    students = db.get_students()
    sec_students = students[students.section_id == sec]
    if sec_students.empty:
        st.info("لا توجد طالبات")
        return
    statuses = {}
    for _, s in sec_students.iterrows():
        status = st.radio(s["full_name"], ["حاضر", "غائب", "متأخر"], key=s["student_id"])
        statuses[s["student_id"]] = status
    if st.button("حفظ الحضور", type="primary"):
        for sid, status in statuses.items():
            db.add_attendance_record({
                "record_id": str(uuid.uuid4()),
                "date": date.strftime("%Y-%m-%d"),
                "student_id": sid,
                "status": status,
                "notes": "",
                "recorded_by": st.session_state.user["user_id"],
                "section_id": sec
            })
        st.success("تم التسجيل")

def show_followup(db):
    st.markdown("<h2 class='main-header'>💬 الافتقاد</h2>", unsafe_allow_html=True)
    user_role = st.session_state.user["role"]
    user_id = st.session_state.user["user_id"]
    students = db.get_students()
    if user_role == "Teacher":
        responsible = students[students.teacher_id == user_id]
    elif user_role == "Service Manager":
        sec_id = st.session_state.user.get("section_id", "")
        responsible = students[students.section_id == sec_id] if sec_id else students
    else:
        responsible = students
    if responsible.empty:
        st.info("لا توجد طالبات")
        return
    student = st.selectbox("الطالبة", responsible["full_name"])
    sdata = responsible[responsible.full_name == student].iloc[0].to_dict()
    with st.form("fup"):
        ftype = st.selectbox("النوع", ["زيارة", "اتصال", "رسالة"])
        notes = st.text_area("ملاحظات")
        reg = st.selectbox("الحالة", ["منتظم", "متقطع", "منقطع"])
        if st.form_submit_button("حفظ"):
            db.add_followup_record({
                "record_id": str(uuid.uuid4()),
                "student_id": sdata["student_id"],
                "teacher_id": user_id,
                "followup_date": datetime.now().strftime("%Y-%m-%d"),
                "followup_type": ftype,
                "notes": notes,
                "regularity_status": reg
            })
            st.success("تم التسجيل")

def show_quizzes(db):
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    if st.session_state.user["role"] in ["System Admin", "Service Manager"]:
        with st.form("new_quiz"):
            title = st.text_input("العنوان")
            desc = st.text_area("الوصف")
            c1, c2 = st.columns(2)
            num_q = c1.number_input("عدد الأسئلة", 1, 50, 5)
            time_l = c2.number_input("الوقت (دقائق)", 1, 180, 15)
            expiry = st.date_input("تاريخ الانتهاء", datetime.now() + timedelta(days=7))
            if st.form_submit_button("إنشاء") and title:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                pwd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                qid = str(uuid.uuid4())
                db.add_quiz({
                    "quiz_id": qid,
                    "title": title,
                    "description": desc,
                    "created_by": st.session_state.user["user_id"],
                    "section_id": "",
                    "num_questions": num_q,
                    "time_limit_minutes": time_l,
                    "total_marks": num_q,
                    "expiry_date": expiry.strftime("%Y-%m-%d"),
                    "quiz_code": code,
                    "password": pwd,
                    "is_active": "True"
                })
                st.success(f"تم! الكود: {code} - كلمة المرور: {pwd}")
        st.markdown("---")
        st.subheader("إضافة أسئلة")
        quizzes = db.get_quizzes()
        active_quizzes = quizzes[quizzes.is_active == "True"]
        if not active_quizzes.empty:
            q_choice = st.selectbox("اختبار", active_quizzes["quiz_id"], format_func=lambda x: active_quizzes[active_quizzes.quiz_id==x]["title"].values[0])
            with st.form("add_q"):
                qtext = st.text_area("السؤال")
                qtype = st.selectbox("النوع", ["اختيار من متعدد", "صح وخطأ", "أكمل", "إجابة قصيرة"])
                opts = {}
                if qtype == "اختيار من متعدد":
                    cols = st.columns(4)
                    for i, col in enumerate(cols, 1):
                        opts[f"option{i}"] = col.text_input(f"الخيار {i}")
                correct = st.text_input("الإجابة الصحيحة")
                if st.form_submit_button("إضافة سؤال") and qtext and correct:
                    db.add_question({
                        "question_id": str(uuid.uuid4()),
                        "quiz_id": q_choice,
                        "question_text": qtext,
                        "question_type": qtype,
                        "option1": opts.get("option1", ""),
                        "option2": opts.get("option2", ""),
                        "option3": opts.get("option3", ""),
                        "option4": opts.get("option4", ""),
                        "correct_answer": correct
                    })
                    st.success("تمت الإضافة")
                    st.rerun()
    st.markdown("---")
    st.subheader("النتائج")
    results = db._sheet_to_df("QuizResults")
    if not results.empty:
        st.dataframe(results[["quiz_id", "student_name", "score", "total_marks", "submission_time"]], use_container_width=True)

def show_reports(db):
    st.markdown("<h2 class='main-header'>📊 التقارير</h2>", unsafe_allow_html=True)
    attendance = db.get_attendance()
    if attendance.empty:
        st.info("لا توجد بيانات حضور")
        return
    attendance["date"] = pd.to_datetime(attendance["date"])
    month = st.selectbox("الشهر", range(1,13), index=datetime.now().month-1)
    monthly = attendance[attendance.date.dt.month == month]
    if not monthly.empty:
        summary = monthly.groupby(["student_id","status"]).size().unstack(fill_value=0)
        students_df = db.get_students()
        summary = summary.merge(students_df[["student_id","full_name"]], on="student_id")
        st.dataframe(summary)
        fig = px.pie(monthly, names="status", title=f"نسب الحضور لشهر {month}")
        st.plotly_chart(fig)

def show_logs(db):
    st.markdown("<h2 class='main-header'>📜 السجلات</h2>", unsafe_allow_html=True)
    logs = db._sheet_to_df("Logs")
    if not logs.empty:
        st.dataframe(logs.sort_values("timestamp", ascending=False), use_container_width=True)

# ===================== التطبيق الرئيسي =====================
def main():
    st.set_page_config(page_title="نظام الكنيسة - الغياب والافتقاد", page_icon="⛪", layout="wide", initial_sidebar_state="expanded")
    inject_css()
    init_session()

    try:
        creds = get_credentials()
    except:
        return
    db = Database(creds, get_spreadsheet_id())
    salt = get_salt()
    jwt_secret = get_jwt_secret()

    if st.session_state.student_quiz_started and st.session_state.student_quiz:
        show_student_quiz(db)
        return

    if not st.session_state.authenticated:
        show_login_page(db, salt, jwt_secret)
    else:
        if not verify_token(st.session_state.token, jwt_secret):
            st.error("انتهت الجلسة، سجل الدخول مجددًا")
            st.session_state.clear()
            st.rerun()
            return
        choice = sidebar_menu()
        if choice is None:
            return
        if choice == "🏠 لوحة التحكم":
            show_dashboard(db)
        elif choice == "👥 إدارة المستخدمين":
            if st.session_state.user["role"] == "System Admin": show_admin_users(db, salt)
            else: st.error("غير مصرح")
        elif choice in ["👩‍🎓 الطالبات", "👩‍🎓 طالباتي"]:
            show_students(db)
        elif choice == "👩‍🏫 المدرسات والأقسام":
            if st.session_state.user["role"] == "System Admin": show_teachers_sections(db)
            else: st.error("غير مصرح")
        elif choice == "📋 الحضور":
            show_attendance(db)
        elif choice == "💬 الافتقاد":
            show_followup(db)
        elif choice in ["📝 المسابقات والاختبارات", "📝 المسابقات"]:
            show_quizzes(db)
        elif choice == "📊 التقارير":
            show_reports(db)
        elif choice == "📜 السجلات":
            if st.session_state.user["role"] == "System Admin": show_logs(db)
            else: st.error("غير مصرح")

if __name__ == "__main__":
    main()
