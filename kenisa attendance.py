# app.py - نظام إدارة الغياب والافتقاد لكنيسة الشهيدة دميانه
# نسخة آمنة - تقرأ بيانات الاعتماديات من ملف خارجي

import os
import json
import gspread
from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ============================================
# تحميل بيانات الاعتماديات من ملف خارجي
# ============================================
def load_credentials():
    """تحميل بيانات الاعتماديات من ملف JSON"""
    try:
        with open('credentials.json', 'r', encoding='utf-8') as f:
            print("✅ تم تحميل بيانات الاعتماديات من credentials.json")
            return json.load(f)
    except FileNotFoundError:
        print("❌ ملف credentials.json غير موجود!")
        print("""
        ⚠️ يرجى:
        1. إنشاء ملف credentials.json في نفس مجلد البرنامج
        2. وضع بيانات Google Service Account فيه
        
        مثال لشكل الملف:
        {
            "type": "service_account",
            "project_id": "your-project",
            "private_key_id": "your-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
            "client_email": "your-email@project.iam.gserviceaccount.com",
            "client_id": "your-client-id"
        }
        """)
        return None
    except Exception as e:
        print(f"❌ خطأ في تحميل الملف: {e}")
        return None

# تحميل بيانات الاعتماديات
SERVICE_ACCOUNT_INFO = load_credentials()

if not SERVICE_ACCOUNT_INFO:
    print("❌ لا يمكن تشغيل البرنامج بدون بيانات الاعتماديات!")
    exit(1)

# رابط الشيت
SHEET_NAME = "كنيسة الشهيدة دميانه - نظام المتابعة"

# ============================================
# دوال التعامل مع Google Sheets
# ============================================
def get_sheets_client():
    """تهيئة العميل للاتصال مع Google Sheets"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", 
                 "https://www.googleapis.com/auth/drive",
                 "https://www.googleapis.com/auth/spreadsheets"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
        client = gspread.authorize(creds)
        print("✅ تم الاتصال بـ Google Sheets بنجاح")
        return client
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")
        return None

def init_sheets():
    """تهيئة الشيتات إذا لم تكن موجودة"""
    client = get_sheets_client()
    if not client:
        return False
    
    try:
        try:
            sh = client.open(SHEET_NAME)
            print(f"✅ تم فتح الشيت الموجود: {SHEET_NAME}")
        except:
            sh = client.create(SHEET_NAME)
            print(f"✅ تم إنشاء شيت جديد: {SHEET_NAME}")
        
        # تعريف الأوراق المطلوبة
        worksheets_needed = {
            'الفصول': ['الفصل', 'مسؤول الفصل', 'المساعد', 'عدد الأعضاء', 'الشعب'],
            'الأعضاء': ['الاسم', 'الفصل', 'الشعبة', 'دور الخدمة', 'التليفون', 'العنوان', 'ملاحظات'],
            'الغياب': ['التاريخ', 'الاسم', 'الفصل', 'سبب الغياب', 'تم التواصل', 'ملاحظات'],
            'الافتقاد': ['التاريخ', 'الاسم', 'الفصل', 'نوع الزيارة', 'الحالة', 'تقرير الزيارة']
        }
        
        for sheet_name, headers in worksheets_needed.items():
            try:
                worksheet = sh.worksheet(sheet_name)
                print(f"✅ الورقة موجودة: {sheet_name}")
            except:
                worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
                worksheet.append_row(headers)
                print(f"✅ تم إنشاء ورقة جديدة: {sheet_name}")
                
                if sheet_name == 'الفصول':
                    default_classes = [
                        ['الفصل الأول', 'أمينة الخدمة - ماري', 'مساعدة', 10, 'A,B,C'],
                        ['الفصل الثاني', 'أمينة الخدمة - سارة', 'مساعدة', 10, 'A,B,C'],
                        ['الفصل الثالث', 'أمينة الخدمة - ريتا', 'مساعدة', 10, 'A,B,C'],
                        ['الفصل الرابع', 'أمينة الخدمة - فيفيان', 'مساعدة', 10, 'A,B,C']
                    ]
                    for class_data in default_classes:
                        worksheet.append_row(class_data)
                
                if sheet_name == 'الأعضاء':
                    for class_num in range(1, 5):
                        for member_num in range(1, 11):
                            worksheet.append_row([
                                f"عضو {member_num} فصل {class_num}",
                                f"الفصل {class_num}",
                                chr(64 + (member_num % 3 + 1)),
                                ['خادم', 'مرتل', 'شماس'][member_num % 3],
                                f"0123456789{member_num}",
                                "عنوان العضو",
                                ""
                            ])
        return True
    except Exception as e:
        print(f"❌ خطأ في تهيئة الشيتات: {e}")
        return False

def get_worksheet(sheet_name):
    """الحصول على ورقة عمل معينة"""
    try:
        client = get_sheets_client()
        if not client:
            return None
        sh = client.open(SHEET_NAME)
        return sh.worksheet(sheet_name)
    except Exception as e:
        print(f"خطأ في جلب الورقة {sheet_name}: {e}")
        return None

def get_all_records(sheet_name):
    """جلب كل السجلات من ورقة معينة"""
    try:
        worksheet = get_worksheet(sheet_name)
        if worksheet:
            return worksheet.get_all_records()
        return []
    except Exception as e:
        print(f"خطأ في جلب السجلات من {sheet_name}: {e}")
        return []

def add_record(sheet_name, data):
    """إضافة سجل جديد إلى ورقة معينة"""
    try:
        worksheet = get_worksheet(sheet_name)
        if worksheet:
            worksheet.append_row(data)
            return True
        return False
    except Exception as e:
        print(f"خطأ في إضافة السجل إلى {sheet_name}: {e}")
        return False

# ============================================
# صفحات API
# ============================================
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/classes')
def get_classes():
    records = get_all_records('الفصول')
    return jsonify(records)

@app.route('/api/members')
def get_members():
    records = get_all_records('الأعضاء')
    class_name = request.args.get('class', '')
    if class_name:
        records = [r for r in records if r.get('الفصل') == class_name]
    return jsonify(records)

@app.route('/api/absence')
def get_absence():
    records = get_all_records('الغياب')
    date = request.args.get('date', '')
    if date:
        records = [r for r in records if r.get('التاريخ') == date]
    return jsonify(records)

@app.route('/api/followup')
def get_followup():
    records = get_all_records('الافتقاد')
    status = request.args.get('status', '')
    if status:
        records = [r for r in records if r.get('الحالة') == status]
    return jsonify(records)

@app.route('/api/add_absence', methods=['POST'])
def add_absence():
    try:
        data = request.json
        success = add_record('الغياب', [
            data.get('date', ''),
            data.get('name', ''),
            data.get('class', ''),
            data.get('reason', ''),
            data.get('contacted', 'لا'),
            data.get('notes', '')
        ])
        return jsonify({'success': success, 'message': 'تم التسجيل بنجاح' if success else 'فشل التسجيل'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/add_followup', methods=['POST'])
def add_followup():
    try:
        data = request.json
        success = add_record('الافتقاد', [
            data.get('date', ''),
            data.get('name', ''),
            data.get('class', ''),
            data.get('visit_type', 'منزلية'),
            data.get('status', 'معلق'),
            data.get('report', '')
        ])
        return jsonify({'success': success, 'message': 'تم التسجيل بنجاح' if success else 'فشل التسجيل'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stats')
def get_stats():
    members = get_all_records('الأعضاء')
    absences = get_all_records('الغياب')
    followups = get_all_records('الافتقاد')
    
    classes_stats = {}
    for member in members:
        class_name = member.get('الفصل', '')
        if class_name:
            if class_name not in classes_stats:
                classes_stats[class_name] = {'total': 0, 'absence_today': 0, 'followup_pending': 0}
            classes_stats[class_name]['total'] += 1
    
    today = datetime.now().strftime('%Y-%m-%d')
    for absence in absences:
        if absence.get('التاريخ') == today:
            class_name = absence.get('الفصل', '')
            if class_name in classes_stats:
                classes_stats[class_name]['absence_today'] += 1
    
    for followup in followups:
        if followup.get('الحالة') == 'معلق':
            class_name = followup.get('الفصل', '')
            if class_name in classes_stats:
                classes_stats[class_name]['followup_pending'] += 1
    
    return jsonify({
        'total_members': len(members),
        'total_absence': len(absences),
        'total_followup': len(followups),
        'classes_stats': classes_stats
    })

# ============================================
# قالب HTML
# ============================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>كنيسة الشهيدة دميانه - نظام المتابعة</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 30px;
            border-radius: 20px;
            margin-bottom: 30px;
            text-align: center;
            border: 3px solid gold;
        }
        .header h1 { color: #8B0000; font-size: 2.5em; }
        .header h2 { color: #4a148c; font-size: 1.8em; }
        .classes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .class-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border-right: 8px solid gold;
            cursor: pointer;
            transition: transform 0.3s;
        }
        .class-card:hover { transform: translateY(-5px); }
        .class-card h3 { color: #8B0000; font-size: 1.8em; margin-bottom: 10px; }
        .tabs {
            display: flex;
            gap: 10px;
            margin: 30px 0;
            flex-wrap: wrap;
            justify-content: center;
        }
        .tab-btn {
            padding: 15px 30px;
            border: none;
            border-radius: 30px;
            background: white;
            color: #8B0000;
            border: 2px solid gold;
            cursor: pointer;
            font-weight: bold;
            font-size: 1.1em;
        }
        .tab-btn.active { background: #8B0000; color: gold; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .form-container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin: 20px 0;
        }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #8B0000;
            font-weight: bold;
        }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
        }
        .btn {
            background: #8B0000;
            color: gold;
            padding: 15px 30px;
            border: none;
            border-radius: 30px;
            cursor: pointer;
            font-weight: bold;
            font-size: 1.1em;
        }
        .btn:hover { background: gold; color: #8B0000; }
        .table-container {
            background: white;
            border-radius: 15px;
            padding: 20px;
            overflow-x: auto;
        }
        table { width: 100%; border-collapse: collapse; }
        th { background: #8B0000; color: gold; padding: 15px; }
        td { padding: 12px; border-bottom: 1px solid #eee; text-align: center; }
        .footer { text-align: center; margin-top: 50px; color: white; padding: 20px; }
        .quick-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .quick-stat-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            border: 2px solid gold;
        }
        .quick-stat-card .big-number { font-size: 2.5em; font-weight: bold; color: #4a148c; }
        .success-message {
            background: #4CAF50;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            text-align: center;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✝ كنيسة الشهيدة دميانه ✝</h1>
            <h2>نظام إدارة الغياب والافتقاد</h2>
            <p>4 فصول - كل فصل 10 أفراد - مع مسؤول لكل فصل</p>
        </div>
        
        <div id="classesContainer" class="classes-grid"></div>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('absence')">تسجيل غياب</button>
            <button class="tab-btn" onclick="showTab('followup')">تسجيل افتقاد</button>
            <button class="tab-btn" onclick="showTab('reports')">تقارير</button>
            <button class="tab-btn" onclick="showTab('members')">الأعضاء</button>
        </div>
        
        <div id="successMessage" class="success-message"></div>
        
        <div id="absence" class="tab-content active">
            <div class="quick-stats">
                <div class="quick-stat-card"><h4>غياب اليوم</h4><div class="big-number" id="todayAbsence">0</div></div>
                <div class="quick-stat-card"><h4>إجمالي الغياب</h4><div class="big-number" id="totalAbsence">0</div></div>
            </div>
            <div class="form-container">
                <h3>✝ تسجيل حالة غياب جديدة</h3>
                <form id="absenceForm">
                    <div class="form-group"><label>الفصل</label><select id="absenceClass" required></select></div>
                    <div class="form-group"><label>الاسم</label><select id="absenceName" required></select></div>
                    <div class="form-group"><label>تاريخ الغياب</label><input type="date" id="absenceDate" required></div>
                    <div class="form-group"><label>سبب الغياب</label><input type="text" id="absenceReason" required></div>
                    <button type="submit" class="btn">تسجيل الغياب</button>
                </form>
            </div>
            <div class="table-container">
                <h3>سجل الغياب</h3>
                <table id="absenceTable"><thead><tr><th>التاريخ</th><th>الاسم</th><th>الفصل</th><th>السبب</th></tr></thead><tbody></tbody></table>
            </div>
        </div>
        
        <div id="followup" class="tab-content">
            <div class="quick-stats">
                <div class="quick-stat-card"><h4>افتقاد معلق</h4><div class="big-number" id="pendingFollowup">0</div></div>
                <div class="quick-stat-card"><h4>إجمالي الافتقاد</h4><div class="big-number" id="totalFollowup">0</div></div>
            </div>
            <div class="form-container">
                <h3>✝ تسجيل افتقاد جديد</h3>
                <form id="followupForm">
                    <div class="form-group"><label>الفصل</label><select id="followupClass" required></select></div>
                    <div class="form-group"><label>الاسم</label><select id="followupName" required></select></div>
                    <div class="form-group"><label>تاريخ الزيارة</label><input type="date" id="followupDate" required></div>
                    <div class="form-group"><label>نوع الزيارة</label><select id="visitType"><option value="منزلية">منزلية</option><option value="هاتفية">هاتفية</option></select></div>
                    <button type="submit" class="btn">تسجيل الافتقاد</button>
                </form>
            </div>
            <div class="table-container">
                <h3>سجل الافتقاد</h3>
                <table id="followupTable"><thead><tr><th>التاريخ</th><th>الاسم</th><th>الفصل</th><th>النوع</th></tr></thead><tbody></tbody></table>
            </div>
        </div>
        
        <div id="reports" class="tab-content">
            <div class="table-container">
                <h3>إحصائيات الفصول</h3>
                <table id="statsTable"><thead><tr><th>الفصل</th><th>المسؤول</th><th>عدد الأعضاء</th><th>غياب اليوم</th></tr></thead><tbody></tbody></table>
            </div>
        </div>
        
        <div id="members" class="tab-content">
            <div class="table-container">
                <h3>أعضاء الخدمة</h3>
                <table id="membersTable"><thead><tr><th>الاسم</th><th>الفصل</th><th>دور الخدمة</th><th>التليفون</th></tr></thead><tbody></tbody></table>
            </div>
        </div>
        
        <div class="footer">
            <p>✝ كنيسة الشهيدة دميانه - جميع الحقوق محفوظة © 2024 ✝</p>
        </div>
    </div>
    
    <script>
        let classes = [], members = [];
        function showMessage(msg, isSuccess = true) {
            const msgDiv = document.getElementById('successMessage');
            msgDiv.style.display = 'block';
            msgDiv.textContent = msg;
            msgDiv.style.background = isSuccess ? '#4CAF50' : '#f44336';
            setTimeout(() => { msgDiv.style.display = 'none'; }, 3000);
        }
        async function fetchData() {
            try {
                const classesRes = await fetch('/api/classes');
                classes = await classesRes.json();
                const membersRes = await fetch('/api/members');
                members = await membersRes.json();
                const statsRes = await fetch('/api/stats');
                const stats = await statsRes.json();
                const absenceRes = await fetch('/api/absence');
                const followupRes = await fetch('/api/followup');
                displayClasses(classes, stats.classes_stats || {});
                updateClassDropdowns();
                displayAbsences(await absenceRes.json());
                displayFollowups(await followupRes.json());
                displayMembers(members);
                displayStats(classes, stats.classes_stats || {});
                document.getElementById('todayAbsence').textContent = stats.total_absence || 0;
                document.getElementById('totalAbsence').textContent = stats.total_absence || 0;
                document.getElementById('pendingFollowup').textContent = stats.total_followup || 0;
                document.getElementById('totalFollowup').textContent = stats.total_followup || 0;
            } catch(e) { console.error(e); showMessage('خطأ في الاتصال', false); }
        }
        function displayClasses(classesList, stats) {
            const container = document.getElementById('classesContainer');
            container.innerHTML = classesList.map(c => {
                const s = stats[c['الفصل']] || { total: 10, absence_today: 0 };
                return `<div class="class-card" onclick="selectClass('${c['الفصل']}')">
                    <h3>${c['الفصل']}</h3>
                    <div>مسؤول: ${c['مسؤول الفصل'] || 'أمينة الخدمة'}</div>
                    <div>أعضاء: ${s.total} | غياب اليوم: ${s.absence_today}</div>
                </div>`;
            }).join('');
        }
        function selectClass(className) {
            document.getElementById('absenceClass').value = className;
            document.getElementById('followupClass').value = className;
            updateNamesByClass('absenceClass', 'absenceName');
            updateNamesByClass('followupClass', 'followupName');
        }
        function updateClassDropdowns() {
            const options = classes.map(c => `<option value="${c['الفصل']}">${c['الفصل']}</option>`).join('');
            document.getElementById('absenceClass').innerHTML = '<option value="">اختر الفصل</option>' + options;
            document.getElementById('followupClass').innerHTML = '<option value="">اختر الفصل</option>' + options;
        }
        function updateNamesByClass(classId, targetId) {
            const selectedClass = document.getElementById(classId).value;
            const classMembers = members.filter(m => m['الفصل'] === selectedClass);
            const names = classMembers.length ? classMembers.map(m => m['الاسم']) : ['بيتر جرجس', 'ماريا رفعت', 'يوسف ملاك', 'مريم سامي', 'كيرلس نصيف'];
            document.getElementById(targetId).innerHTML = '<option value="">اختر الاسم</option>' + names.map(n => `<option value="${n}">${n}</option>`).join('');
        }
        function displayAbsences(absences) {
            const tbody = document.querySelector('#absenceTable tbody');
            tbody.innerHTML = absences.map(a => `<tr><td>${a['التاريخ'] || ''}</td><td>${a['الاسم'] || ''}</td><td>${a['الفصل'] || ''}</td><td>${a['سبب الغياب'] || ''}</td></tr>`).join('');
        }
        function displayFollowups(followups) {
            const tbody = document.querySelector('#followupTable tbody');
            tbody.innerHTML = followups.map(f => `<tr><td>${f['التاريخ'] || ''}</td><td>${f['الاسم'] || ''}</td><td>${f['الفصل'] || ''}</td><td>${f['نوع الزيارة'] || ''}</td></tr>`).join('');
        }
        function displayMembers(membersList) {
            const tbody = document.querySelector('#membersTable tbody');
            tbody.innerHTML = membersList.map(m => `<tr><td>${m['الاسم'] || ''}</td><td>${m['الفصل'] || ''}</td><td>${m['دور الخدمة'] || ''}</td><td>${m['التليفون'] || ''}</td></tr>`).join('');
        }
        function displayStats(classesList, stats) {
            const tbody = document.querySelector('#statsTable tbody');
            tbody.innerHTML = classesList.map(c => {
                const s = stats[c['الفصل']] || { total: 10, absence_today: 0 };
                return `<tr><td>${c['الفصل']}</td><td>${c['مسؤول الفصل'] || 'أمينة الخدمة'}</td><td>${s.total}</td><td>${s.absence_today}</td></tr>`;
            }).join('');
        }
        function showTab(tabName) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
        }
        document.getElementById('absenceForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                date: document.getElementById('absenceDate').value,
                name: document.getElementById('absenceName').value,
                class: document.getElementById('absenceClass').value,
                reason: document.getElementById('absenceReason').value,
                contacted: 'لا', notes: ''
            };
            const res = await fetch('/api/add_absence', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
            const result = await res.json();
            showMessage(result.message, result.success);
            if(result.success) fetchData();
        });
        document.getElementById('followupForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                date: document.getElementById('followupDate').value,
                name: document.getElementById('followupName').value,
                class: document.getElementById('followupClass').value,
                visit_type: document.getElementById('visitType').value,
                status: 'معلق', report: ''
            };
            const res = await fetch('/api/add_followup', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
            const result = await res.json();
            showMessage(result.message, result.success);
            if(result.success) fetchData();
        });
        document.getElementById('absenceClass').addEventListener('change', () => updateNamesByClass('absenceClass', 'absenceName'));
        document.getElementById('followupClass').addEventListener('change', () => updateNamesByClass('followupClass', 'followupName'));
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('absenceDate').value = new Date().toISOString().split('T')[0];
            document.getElementById('followupDate').value = new Date().toISOString().split('T')[0];
            fetchData();
        });
    </script>
</body>
</html>
"""

# ============================================
# تشغيل التطبيق
# ============================================
if __name__ == '__main__':
    print("""
    ═══════════════════════════════════════════
    ✝ كنيسة الشهيدة دميانه ✝
    نظام إدارة الغياب والافتقاد
    ═══════════════════════════════════════════
    """)
    
    if init_sheets():
        print("""
    ✅ تم الاتصال بـ Google Sheets بنجاح
    🌐 شغل المتصفح على: http://localhost:5000
    """)
    else:
        print("❌ فشل الاتصال بـ Google Sheets")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
