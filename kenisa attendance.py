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

# ===================== الإعدادات العامة =====================
SALT = st.secrets["sheets"]["password_salt"]
JWT_SECRET = st.secrets["sheets"]["jwt_secret"]
SPREADSHEET_ID = st.secrets["sheets"]["spreadsheet_id"]
CREDENTIALS = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

# ===================== النمط العام للـ CSS =====================
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
        }

        .stApp {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 100%);
        }

        .css-18e3th9 {
            padding-top: 2rem;
        }

        .stSidebar {
            background-color: #f8f9fa;
            border-left: 1px solid #dee2e6;
        }

        .main-header {
            font-size: 2.2rem;
            font-weight: 700;
            color: #2c3e50;
            text-align: center;
            margin-bottom: 2rem;
            padding: 1rem;
            background: white;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }

        .card {
            background: white;
            border-radius: 15px;
            padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            margin-bottom: 1rem;
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }

        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .stat-card .value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #2c3e50;
            margin: 0.5rem 0;
        }
        .stat-card .label {
            font-size: 1rem;
            color: #7f8c8d;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.5rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-primary:hover {
            transform: scale(1.02);
            box-shadow: 0 5px 15px rgba(102,126,234,0.4);
        }

        /* RTL fix for Streamlit elements */
        .stRadio > div, .stSelectbox > div, .stMultiSelect > div {
            direction: rtl;
        }
        .stMarkdown {
            text-align: right;
        }
    </style>
    """, unsafe_allow_html=True)

# ===================== قاعدة البيانات عبر Google Sheets =====================
class Database:
    def __init__(self):
        self.client = gspread.authorize(CREDENTIALS)
        self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)

    def get_or_create_worksheet(self, name, columns):
        """إرجاع ورقة العمل وإنشائها مع الأعمدة إن لم تكن موجودة."""
        try:
            ws = self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=len(columns))
            ws.append_row(columns)
        return ws

    def _sheet_to_df(self, sheet_name):
        ws = self.get_or_create_worksheet(sheet_name, [])
        data = ws.get_all_records()
        return pd.DataFrame(data)

    def _df_to_sheet(self, sheet_name, df, columns):
        ws = self.get_or_create_worksheet(sheet_name, columns)
        ws.clear()
        ws.update([columns] + df.values.tolist())

    # ---------- جداول المستخدمين ----------
    def get_users(self):
        return self._sheet_to_df("Users")

    def add_user(self, user_data: dict):
        df = self.get_users()
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        self._df_to_sheet("Users", df, ["user_id", "username", "password_hash", "role", "full_name", "section_id"])

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
        df = pd.concat([df, pd.DataFrame([sec_data])], ignore_index=True)
        self._df_to_sheet("Sections", df, ["section_id", "section_name", "manager_user_id"])

    # ---------- الطالبات ----------
    def get_students(self):
        return self._sheet_to_df("Students")

    def add_student(self, student_data: dict):
        df = self.get_students()
        df = pd.concat([df, pd.DataFrame([student_data])], ignore_index=True)
        self._df_to_sheet("Students", df, ["student_id", "full_name", "section_id", "teacher_id", "phone", "parent_phone", "birthdate", "address", "notes", "status"])

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
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("Attendance", df, ["record_id", "date", "student_id", "status", "notes", "recorded_by", "section_id"])

    # ---------- الافتقاد ----------
    def get_followup(self):
        return self._sheet_to_df("FollowUp")

    def add_followup_record(self, record: dict):
        df = self.get_followup()
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._df_to_sheet("FollowUp", df, ["record_id", "student_id", "teacher_id", "followup_date", "followup_type", "notes", "regularity_status"])

    # ---------- الاختبارات ----------
    def get_quizzes(self):
        return self._sheet_to_df("Quizzes")

    def add_quiz(self, quiz_data: dict):
        df = self.get_quizzes()
        df = pd.concat([df, pd.DataFrame([quiz_data])], ignore_index=True)
        self._df_to_sheet("Quizzes", df, ["quiz_id", "title", "description", "created_by", "section_id", "num_questions", "time_limit_minutes", "total_marks", "expiry_date", "quiz_code", "password", "is_active"])

    def get_quiz_questions(self, quiz_id):
        df = self._sheet_to_df("QuizQuestions")
        return df[df.quiz_id == quiz_id] if not df.empty else pd.DataFrame()

    def add_question(self, q_data: dict):
        df = self._sheet_to_df("QuizQuestions")
        df = pd.concat([df, pd.DataFrame([q_data])], ignore_index=True)
        self._df_to_sheet("QuizQuestions", df, ["question_id", "quiz_id", "question_text", "question_type", "option1", "option2", "option3", "option4", "correct_answer"])

    def save_quiz_result(self, result: dict):
        df = self._sheet_to_df("QuizResults")
        df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
        self._df_to_sheet("QuizResults", df, ["result_id", "quiz_id", "student_id", "student_name", "score", "total_marks", "submission_time", "answers"])

    def get_quiz_results(self, quiz_id=None):
        df = self._sheet_to_df("QuizResults")
        if quiz_id:
            df = df[df.quiz_id == quiz_id]
        return df

    # ---------- السجلات ----------
    def add_log(self, user_id, action, details=""):
        df = self._sheet_to_df("Logs")
        log = {"log_id": str(uuid.uuid4()), "timestamp": datetime.now().isoformat(), "user_id": user_id, "action": action, "details": details}
        df = pd.concat([df, pd.DataFrame([log])], ignore_index=True)
        self._df_to_sheet("Logs", df, ["log_id", "timestamp", "user_id", "action", "details"])

# ===================== إدارة الجلسة والصلاحيات =====================
def hash_password(password):
    return hashlib.sha256((password + SALT).encode()).hexdigest()

def generate_token(user):
    payload = {
        "user_id": user["user_id"],
        "role": user["role"],
        "full_name": user["full_name"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def check_authentication():
    if "token" not in st.session_state:
        return False
    payload = verify_token(st.session_state.token)
    if payload:
        st.session_state.user = payload
        return True
    else:
        st.session_state.clear()
        return False

# ===================== واجهة تسجيل الدخول والطالبات =====================
def show_login_page():
    st.markdown("<h1 class='main-header'>⛪ نظام الغياب والافتقاد<br>الكنيسة الشهيدة دميانة بأسيوط</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔐 دخول الخدام", "📝 دخول الطالبات للاختبار"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم")
            password = st.text_input("كلمة المرور", type="password")
            submitted = st.form_submit_button("تسجيل الدخول", use_container_width=True)
            if submitted:
                db = Database()
                users = db.get_users()
                user_row = users[users.username == username]
                if not user_row.empty:
                    user = user_row.iloc[0].to_dict()
                    if user["password_hash"] == hash_password(password):
                        token = generate_token(user)
                        st.session_state.token = token
                        st.session_state.user = user
                        st.session_state.authenticated = True
                        db.add_log(user["user_id"], "login")
                        st.rerun()
                    else:
                        st.error("كلمة المرور غير صحيحة")
                else:
                    st.error("المستخدم غير موجود")

    with tab2:
        st.subheader("دخول الاختبار الإلكتروني")
        code = st.text_input("كود الاختبار")
        passwd = st.text_input("كلمة مرور الاختبار", type="password")
        if st.button("بدء الاختبار", key="student_quiz_btn"):
            db = Database()
            quizzes = db.get_quizzes()
            quiz = quizzes[(quizzes.quiz_code == code) & (quizzes.password == passwd)]
            if quiz.empty:
                st.error("كود أو كلمة مرور خاطئة")
            else:
                quiz = quiz.iloc[0].to_dict()
                if pd.to_datetime(quiz["expiry_date"]) < datetime.now():
                    st.error("انتهت صلاحية الاختبار")
                else:
                    st.session_state.student_quiz = quiz
                    st.session_state.student_quiz_started = True
                    st.rerun()

# ===================== صفحة حل الاختبار للطالبة =====================
def show_student_quiz():
    quiz = st.session_state.student_quiz
    db = Database()
    questions = db.get_quiz_questions(quiz["quiz_id"])
    if questions.empty:
        st.warning("لا توجد أسئلة في هذا الاختبار")
        return

    st.title(quiz["title"])
    st.markdown(f"**الوقت المتبقي:** {quiz['time_limit_minutes']} دقيقة")
    student_name = st.text_input("الاسم الثلاثي للطالبة")
    answers = {}

    for i, q in questions.iterrows():
        q = q.to_dict()
        st.markdown(f"**سؤال {i+1}:** {q['question_text']}")
        q_type = q["question_type"]
        if q_type in ["اختيار من متعدد", "صح وخطأ"]:
            options = []
            if q_type == "اختيار من متعدد":
                options = [q["option1"], q["option2"], q["option3"], q["option4"]]
            else:
                options = ["صح", "خطأ"]
            ans = st.radio("اختر الإجابة", options, key=f"q_{i}")
            answers[q["question_id"]] = ans
        else:
            ans = st.text_input("الإجابة", key=f"q_{i}")
            answers[q["question_id"]] = ans

    if st.button("تسليم الاختبار"):
        if not student_name.strip():
            st.error("الرجاء إدخال الاسم")
            return
        # تصحيح تلقائي
        score = 0
        total = len(questions)
        for _, q in questions.iterrows():
            q = q.to_dict()
            correct = str(q["correct_answer"]).strip()
            user_ans = str(answers.get(q["question_id"], "")).strip()
            if correct.lower() == user_ans.lower():
                score += 1
        result = {
            "result_id": str(uuid.uuid4()),
            "quiz_id": quiz["quiz_id"],
            "student_id": "student_external",  # لا يوجد حساب، لذلك نضع معرف ثابت
            "student_name": student_name,
            "score": score,
            "total_marks": total,
            "submission_time": datetime.now().isoformat(),
            "answers": json.dumps(answers, ensure_ascii=False)
        }
        db.save_quiz_result(result)
        st.success(f"تم تسليم الاختبار! نتيجتك: {score}/{total}")
        st.session_state.pop("student_quiz", None)
        st.session_state.pop("student_quiz_started", None)

# ===================== الصفحات الرئيسية بعد تسجيل الدخول =====================
def sidebar_menu():
    role = st.session_state.user["role"]
    menus = {
        "System Admin": ["🏠 لوحة التحكم", "👥 إدارة المستخدمين", "👩‍🎓 الطالبات", "👩‍🏫 المدرسات والأقسام", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات والاختبارات", "📊 السجلات"],
        "Father Account": ["🏠 لوحة التحكم", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات والاختبارات"],
        "Service Manager": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد", "📝 المسابقات والاختبارات"],
        "Teacher": ["🏠 لوحة التحكم", "👩‍🎓 طالباتي", "📋 الحضور", "💬 الافتقاد"]
    }
    menu = menus.get(role, [])
    if not menu:
        st.sidebar.error("صلاحية غير معروفة")
        return
    choice = st.sidebar.radio("القائمة", menu)
    return choice

def show_dashboard():
    st.markdown("<h2 class='main-header'>📊 لوحة التحكم</h2>", unsafe_allow_html=True)
    db = Database()
    students = db.get_students()
    attendance = db.get_attendance()
    followup = db.get_followup()

    # بطاقات إحصائية
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"<div class='stat-card'><div class='label'>إجمالي البنات</div><div class='value'>{len(students)}</div></div>", unsafe_allow_html=True)
    present_today = len(attendance[(attendance.date == datetime.now().strftime("%Y-%m-%d")) & (attendance.status == "حاضر")]) if not attendance.empty else 0
    absent_today = len(attendance[(attendance.date == datetime.now().strftime("%Y-%m-%d")) & (attendance.status == "غائب")]) if not attendance.empty else 0
    col2.markdown(f"<div class='stat-card'><div class='label'>الحضور اليوم</div><div class='value'>{present_today}</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='stat-card'><div class='label'>الغياب اليوم</div><div class='value'>{absent_today}</div></div>", unsafe_allow_html=True)
    need_followup = len(followup[followup.regularity_status == "منقطع"]) if not followup.empty else 0
    col4.markdown(f"<div class='stat-card'><div class='label'>منقطعات عن المتابعة</div><div class='value'>{need_followup}</div></div>", unsafe_allow_html=True)

    # رسم بياني للحضور
    st.markdown("#### 📈 تحليل الحضور الشهري")
    if not attendance.empty:
        attendance["date"] = pd.to_datetime(attendance["date"])
        monthly = attendance.groupby([attendance.date.dt.to_period("M"), "status"]).size().unstack(fill_value=0)
        fig = px.bar(monthly, x=monthly.index.astype(str), y=monthly.columns, title="الحضور الشهري", labels={"value":"العدد", "index":"الشهر"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات حضور بعد")

    # قائمة البنات المحتاجات متابعة
    st.markdown("#### 🔔 بنات بحاجة لافتقاد عاجل")
    if not followup.empty:
        urgent = followup[followup.regularity_status == "منقطع"].merge(students[["student_id", "full_name"]], on="student_id", how="left")
        st.dataframe(urgent[["full_name", "followup_date", "notes"]], use_container_width=True)
    else:
        st.info("لا توجد متابعات حالياً")

def show_admin_users():
    st.markdown("<h2 class='main-header'>👥 إدارة المستخدمين</h2>", unsafe_allow_html=True)
    db = Database()
    users = db.get_users()
    st.dataframe(users, use_container_width=True)
    with st.expander("➕ إضافة مستخدم"):
        with st.form("add_user"):
            username = st.text_input("اسم المستخدم")
            full_name = st.text_input("الاسم الكامل")
            password = st.text_input("كلمة المرور", type="password")
            role = st.selectbox("الصلاحية", ["System Admin", "Father Account", "Service Manager", "Teacher"])
            section = st.selectbox("القسم (للمدير الخدمة/مدرسة)", ["None"] + db.get_sections()["section_id"].tolist())
            if st.form_submit_button("إضافة"):
                user_data = {
                    "user_id": str(uuid.uuid4()),
                    "username": username,
                    "password_hash": hash_password(password),
                    "role": role,
                    "full_name": full_name,
                    "section_id": section if section != "None" else ""
                }
                db.add_user(user_data)
                st.success("تم إضافة المستخدم")
                st.rerun()

def show_students_management():
    st.markdown("<h2 class='main-header'>👩‍🎓 إدارة الطالبات</h2>", unsafe_allow_html=True)
    db = Database()
    students = db.get_students()
    sections = db.get_sections()
    teachers = db.get_users()[db.get_users().role == "Teacher"]

    st.dataframe(students.merge(sections[["section_id", "section_name"]], on="section_id"), use_container_width=True)
    with st.expander("➕ إضافة طالبة"):
        with st.form("add_student"):
            name = st.text_input("الاسم الكامل")
            sec = st.selectbox("القسم", sections["section_id"])
            teacher = st.selectbox("المدرسة المسؤولة عن الافتقاد", teachers["user_id"])
            phone = st.text_input("رقم الهاتف")
            parent_phone = st.text_input("رقم ولي الأمر")
            st.form_submit_button("إضافة", on_click=lambda: db.add_student({
                "student_id": str(uuid.uuid4()),
                "full_name": name,
                "section_id": sec,
                "teacher_id": teacher,
                "phone": phone,
                "parent_phone": parent_phone,
                "birthdate": "",
                "address": "",
                "notes": "",
                "status": "active"
            }))

def show_attendance():
    st.markdown("<h2 class='main-header'>📋 تسجيل الحضور</h2>", unsafe_allow_html=True)
    db = Database()
    students = db.get_students()
    section = st.selectbox("القسم", db.get_sections()["section_id"])
    date = st.date_input("التاريخ", datetime.now())
    st.markdown("#### سجل الحضور للطالبات في هذا القسم")
    section_students = students[students.section_id == section]
    if section_students.empty:
        st.warning("لا توجد طالبات في هذا القسم")
        return
    statuses = {}
    for _, s in section_students.iterrows():
        status = st.radio(f"{s['full_name']}", ["حاضر", "غائب", "متأخر"], key=s["student_id"])
        statuses[s["student_id"]] = status
    if st.button("حفظ الحضور"):
        for sid, status in statuses.items():
            record = {
                "record_id": str(uuid.uuid4()),
                "date": date.strftime("%Y-%m-%d"),
                "student_id": sid,
                "status": status,
                "notes": "",
                "recorded_by": st.session_state.user["user_id"],
                "section_id": section
            }
            db.add_attendance_record(record)
        st.success("تم تسجيل الحضور بنجاح")

def show_followup():
    st.markdown("<h2 class='main-header'>💬 متابعة الافتقاد</h2>", unsafe_allow_html=True)
    db = Database()
    students = db.get_students()
    followup = db.get_followup()

    teacher_id = st.session_state.user["user_id"]
    my_students = students[students.teacher_id == teacher_id]
    if my_students.empty:
        st.info("ليس لديك طالبات للمتابعة")
        return

    student = st.selectbox("اختر الطالبة", my_students["full_name"])
    student_data = my_students[my_students.full_name == student].iloc[0].to_dict()
    with st.form("add_followup"):
        ftype = st.selectbox("نوع الافتقاد", ["زيارة", "اتصال", "رسالة", "لقاء شخصي"])
        notes = st.text_area("ملاحظات")
        regularity = st.selectbox("حالة الانتظام", ["منتظم", "متقطع", "منقطع"])
        if st.form_submit_button("حفظ"):
            db.add_followup_record({
                "record_id": str(uuid.uuid4()),
                "student_id": student_data["student_id"],
                "teacher_id": teacher_id,
                "followup_date": datetime.now().strftime("%Y-%m-%d"),
                "followup_type": ftype,
                "notes": notes,
                "regularity_status": regularity
            })
            st.success("تم تسجيل الافتقاد")

def show_quizzes():
    st.markdown("<h2 class='main-header'>📝 المسابقات والاختبارات</h2>", unsafe_allow_html=True)
    db = Database()
    if st.session_state.user["role"] in ["Service Manager", "System Admin"]:
        with st.expander("➕ إنشاء اختبار جديد"):
            with st.form("new_quiz"):
                title = st.text_input("عنوان الاختبار")
                desc = st.text_area("وصف")
                num_q = st.number_input("عدد الأسئلة", 1, 20, 5)
                time_limit = st.number_input("الوقت بالدقائق", 1, 120, 15)
                expiry = st.date_input("تاريخ الانتهاء", datetime.now() + timedelta(days=7))
                if st.form_submit_button("إنشاء"):
                    quiz_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    quiz_id = str(uuid.uuid4())
                    db.add_quiz({
                        "quiz_id": quiz_id,
                        "title": title,
                        "description": desc,
                        "created_by": st.session_state.user["user_id"],
                        "section_id": "",
                        "num_questions": num_q,
                        "time_limit_minutes": time_limit,
                        "total_marks": num_q,
                        "expiry_date": expiry.strftime("%Y-%m-%d"),
                        "quiz_code": quiz_code,
                        "password": password,
                        "is_active": "True"
                    })
                    st.success(f"تم إنشاء الاختبار. الكود: {quiz_code} - كلمة المرور: {password}")
                    st.rerun()

        # إدارة الأسئلة لاختبار موجود
        quizzes = db.get_quizzes()
        if not quizzes.empty:
            quiz_choice = st.selectbox("اختبار لإضافة أسئلة", quizzes["quiz_id"])
            q_df = db.get_quiz_questions(quiz_choice)
            st.dataframe(q_df)
            with st.form("add_question"):
                qtext = st.text_input("نص السؤال")
                qtype = st.selectbox("نوع السؤال", ["اختيار من متعدد", "صح وخطأ", "أكمل", "إجابة قصيرة"])
                opts = {}
                if qtype == "اختيار من متعدد":
                    for i in range(1,5):
                        opts[f"option{i}"] = st.text_input(f"الخيار {i}")
                correct = st.text_input("الإجابة الصحيحة")
                if st.form_submit_button("إضافة سؤال"):
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
                    st.success("تمت الإضافة")

    # عرض النتائج
    st.markdown("### نتائج الاختبارات")
    results = db.get_quiz_results()
    if not results.empty:
        st.dataframe(results[["quiz_id", "student_name", "score", "total_marks", "submission_time"]])
    else:
        st.info("لا توجد نتائج بعد")

# ===================== التطبيق الرئيسي =====================
def main():
    inject_css()
    st.set_page_config(page_title="نظام الغياب والافتقاد", layout="wide", initial_sidebar_state="expanded")
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # إذا كانت الطالبة تقدم اختباراً
    if "student_quiz_started" in st.session_state and st.session_state.student_quiz_started:
        show_student_quiz()
        return

    if not st.session_state.authenticated:
        show_login_page()
    else:
        if not check_authentication():
            st.error("انتهت الجلسة، الرجاء تسجيل الدخول مجدداً")
            st.session_state.clear()
            st.rerun()
        choice = sidebar_menu()
        if choice == "🏠 لوحة التحكم":
            show_dashboard()
        elif choice == "👥 إدارة المستخدمين":
            show_admin_users()
        elif choice in ["👩‍🎓 الطالبات", "👩‍🎓 طالباتي"]:
            show_students_management()
        elif choice == "📋 الحضور":
            show_attendance()
        elif choice == "💬 الافتقاد":
            show_followup()
        elif choice == "📝 المسابقات والاختبارات":
            show_quizzes()
        elif choice == "📊 السجلات":
            st.write("قيد التطوير")

if __name__ == "__main__":
    main()
