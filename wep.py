import streamlit as st
import requests
from datetime import datetime
import csv
import os

st.markdown("""
<style>
:root {
    color-scheme: light !important;
}

/* خلفية الصفحة */
[data-testid="stAppViewContainer"] {
    background-color: #FFF8F0 !important;
}

/* العنوان الرئيسي */
h1 {
    color: #000000 !important;
    text-shadow: none !important;
    background: none !important;
}

/* expander header (شفافة بخط أسود) */
.streamlit-expanderHeader {
    background-color: transparent !important;
    color: #000000 !important;
    border: 1px solid #000000 !important;
    border-radius: 10px !important;
    font-weight: bold !important;
}

/* محتوى expander (شفاف بخط أسود) */
.streamlit-expanderContent {
    background-color: transparent !important;
    color: #000000 !important;
    border-radius: 10px !important;
}



/* النص العام */
body {
    background-color: #FFF8F0 !important;
    color: #000000 !important;
}

/* تناسب العرض مع الموبايل */
</style>

<meta name="viewport" content="width=device-width, initial-scale=1.0">
""", unsafe_allow_html=True)


# ====== Telegram Bot ======
BOT_TOKEN = "7517001841:AAFZZQM1hiprXxhPhK4GMfFwu-eP-DkOdMU"
CHAT_ID = "8108209758"

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

# ====== دوال السجل الافتقاد(CSV) ======
def save_record1(message1):
    timestamp1 = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    row1 = [timestamp1, message1]

    file_exists1 = os.path.isfile("records.csv1")
    with open("records.csv1", "a", newline="", encoding="utf-8") as f1:
        writer1 = csv.writer(f1)
        if not file_exists1:  # أول مرة: نكتب الهيدر
            writer1.writerow(["التاريخ", "الرسالة"])
        writer1.writerow(row1)

def load_records1():
    if not os.path.isfile("records.csv1"):
        return []
    with open("records.csv1", "r", encoding="utf-8") as f:
        reader1 = csv.reader(f)
        next(reader1, None)  # تجاهل الهيدر
        return list(reader1)
    
    # ====== دوال السجل الغياب(CSV) ======
def save_record2(message2):
    timestamp2 = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    row2 = [timestamp2, message2]

    file_exists2 = os.path.isfile("records.csv2")
    with open("records.csv2", "a", newline="", encoding="utf-8") as f2:
        writer2 = csv.writer(f2)
        if not file_exists2:  # أول مرة: نكتب الهيدر
            writer2.writerow(["التاريخ", "الرسالة"])
        writer2.writerow(row2)

def load_records2():
    if not os.path.isfile("records.csv2"):
        return []
    with open("records.csv2", "r", encoding="utf-8") as f:
        reader2 = csv.reader(f)
        next(reader2, None)  # تجاهل الهيدر
        return list(reader2)


# ====== إعداد الصفحة ======
st.set_page_config(page_title="كنيسة الشهيدة دميانة", page_icon="✝️", layout="wide")

# ====== CSS ======
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background-color: #FFF8F0;
    }
    [data-testid="stHeader"], [data-testid="stSidebar"] {
        background: rgba(0,0,0,0);
    }
    h1 { color: #2E4053; }
    .stButton button {
        background-color: #32CD32; 
        font-size: 20px;
        border-radius: 10px;
        padding: 10px 25px;
        border: none;
    }
    .stCheckbox label { color: #1A5276; font-size: 18px; }
    .stTextArea textarea {
        background-color: #FDEBD0;
        border-radius: 10px;
        font-size: 16px;
        padding: 10px 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ====== Session ======
query_params = st.query_params
if "page" not in query_params:
    query_params["page"] = "1"

page_str = query_params["page"]
if not page_str.isdigit():
    page_str = "1"
page = int(page_str)

# ====== الصفحة الرئيسية ======
if page == 1:
    st.markdown("<h1 style='text-align: center;'>كنيسة الشهيدة دميانة</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align: center; position:relative; top:240px;'>
            <a href="?page=2" target="_self">
                <button style='font-size:25px; padding:10px 40px; background-color:#32CD32; color:black; border:none; border-radius:12px; cursor:pointer;'>
                    التالي
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

elif page == 2:
    st.markdown(
        """
        <div style='text-align:center; margin-bottom:20px;'>
            <a href="?page=3" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    فصل 1
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div style='text-align:center; margin-bottom:20px;'>
            <a href="?page=3" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                   الفصل2
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div style='text-align:center; margin-bottom:20px;'>
            <a href="?page=3" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    الفصل3
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div style='text-align:center; margin-bottom:20px;'>
            <a href="?page=3" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    الفصل4
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

# ====== القائمة ======
elif page == 3:
    st.markdown("<h1 style='text-align: center;'>الفصل1</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align:center; margin-bottom:20px;'>
            <a href="?page=5" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    📋 الافتقاد والغياب
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div style='text-align:center;'>
            <a href="?page=4" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    📜 سجل الافتقاد والغياب
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

elif page == 4:
    st.markdown("<h1 style='text-align: center;'>سجلات الفصل1</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align:center; margin-bottom:20px;'>
            <a href="?page=9" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    📋 سجل الغياب
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div style='text-align:center;'>
            <a href="?page=8" target="_self">
                <button style='width:250px; font-size:20px; padding:10px 25px; background-color:#6C757D; color:white; border:none; border-radius:8px; cursor:pointer;'>
                    📜 سجل الافتقاد
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
# ====== صفحة القائمة الداخلية ======
elif page == 5:
    col1, col2, col3 = st.columns(3)

    st.markdown(
        """
        <div style='text-align: left; position:relative; top:10px; margin-left:0;'>
            <a href="?page=2" target="_self">
                <button style='font-size:20px; padding:10px 25px; background-color:#FF0000; color:black; border:none; border-radius:8px; cursor:pointer;'>
                    رجوع
                </button>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

    with col1:
        with st.expander("📌 الغياب"):
            st.markdown(
                """
                <div style='text-align: center; position:relative; top:-10px; margin-left:-250px;'>
                    <a href="?page=7" target="_self">
                        <button style='font-size:20px; padding:10px 25px; background-color:#D3D3D3; color:black; border:none; border-radius:8px; cursor:pointer;'>
                            ميخائيل
                        </button>
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )
    with col3:
        with st.expander("📋 الافتقاد"):
            st.markdown(
                """
                <div style='text-align: center; position:relative; top:-10px; margin-left:-250px;'>
                    <a href="?page=6" target="_self">
                        <button style='font-size:20px; padding:10px 25px; background-color:#D3D3D3; color:black; border:none; border-radius:8px; cursor:pointer;'>
                            ميخائيل
                        </button>
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

# ====== صفحة ميخائيل في الافتقاد ======
elif page == 6:
    person = "ميخائيل في الافتقاد"
    st.markdown("<h1 style='text-align: center;'>افتقاد - ميخائيل</h1>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col2:
        nermine = st.checkbox("نرمين")
        irene = st.checkbox("إيريني")
        notes = st.text_area("📝 ملاحظات إضافية", "")

        col_btn1, col_btn2 = st.columns([1,1])
        with col_btn1:
            if st.button("Submit"):
                if nermine and irene:
                    msg = f"{person}\nتم اختيار في الافتقاد: نرمين و إيريني"
                elif nermine and not irene:
                    msg = f"{person}\nتم اختيار في الافتقاد: نرمين فقط و لم يتم اختيار ايريني"
                elif irene and not nermine:
                    msg = f"{person}\nتم اختيار في الافتقاد: إيريني فقط و لم يتم اختيار نرمين"
                else:
                    msg = f"{person}\nلم يتم اختيار أي شخص في الافتقاد"

                if notes.strip():
                    msg += f"\n📝 ملاحظات: {notes}"

                # إرسال للتيليجرام
                send_to_telegram(msg)

                # تسجيل في CSV
                save_record1(msg)

                st.success("✅ تم إرسال الرسالة على التلجرام وتم تسجيلها")

        with col_btn2:
            st.markdown(
                """
                <a href="?page=2" target="_self">
                    <button style='font-size: 20px;padding: 10px 25px; background-color:#FF0000; color:black; border:none; border-radius: 10px; cursor:pointer;'>
                        رجوع
                    </button>
                </a>
                """,
                unsafe_allow_html=True
            )

# ====== صفحة ميخائيل في الغياب======

elif page == 7:
    person = "ميخائيل في الغياب"
    st.markdown("<h1 style='text-align: center;'>غياب - ميخائيل</h1>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col2:
        nermine = st.checkbox("نرمين")
        irene = st.checkbox("إيريني")
        notes = st.text_area("📝 ملاحظات إضافية", "")

        col_btn1, col_btn2 = st.columns([1,1])
        with col_btn1:
            if st.button("Submit"):
                if nermine and irene:
                    msg = f"{person}\nحضرت ايريني و النرمين"
                elif nermine and not irene:
                    msg = f"{person}\nحضرت نرمين ولم تحضر ايريني"
                elif irene and not nermine:
                    msg = f"{person}\nحضرت ايريني و لم تحضر نرمين"
                else:
                    msg = f"{person}\nلم يحضر اي احد"

                if notes.strip():
                    msg += f"\n📝 ملاحظات: {notes}"

                # إرسال للتيليجرام
                send_to_telegram(msg)

                # تسجيل في CSV
                save_record2(msg)

                st.success("✅ تم إرسال الرسالة على التلجرام وتم تسجيلها")

        with col_btn2:
            st.markdown(
                """
                <a href="?page=2" target="_self">
                    <button style='font-size: 20px;padding: 10px 25px; background-color:#FF0000; color:black; border:none; border-radius: 10px; cursor:pointer;'>
                        رجوع
                    </button>
                </a>
                """,
                unsafe_allow_html=True
            )

# ====== صفحة السجل ======
elif page == 8:
    st.markdown("<h1 style='text-align: center;'>📋 سجل الافتقاد</h1>", unsafe_allow_html=True)

    records = load_records1()

    if len(records) == 0:
        st.info("ℹ️ لا توجد أي سجلات حتى الآن")
    else:
        for i, (timestamp, rec) in enumerate(records, start=1):
            st.markdown(
                f"""
                <div style='background-color:#f8f9fa; border:1px solid #ddd; border-radius:10px;
                            padding:15px; margin-bottom:10px;'>
                    <h4 style='color:#2c3e50;'>📌 سجل رقم {i}</h4>
                    <p style='font-size:14px; color:#555;'>🕒 {timestamp}</p>
                    <p style='font-size:16px; color:#333;'>{rec}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

elif page == 9:
    st.markdown("<h1 style='text-align: center;'>📋 سجل الغياب</h1>", unsafe_allow_html=True)

    records1 = load_records2()

    if len(records1) == 0:
        st.info("ℹ️ لا توجد أي سجلات حتى الآن")
    else:
        for i1, (timestamp1, rec1) in enumerate(records1, start=1):
            st.markdown(
                f"""
                <div style='background-color:#f8f9fa; border:1px solid #ddd; border-radius:10px;
                            padding:15px; margin-bottom:10px;'>
                    <h4 style='color:#2c3e50;'>📌 سجل رقم {i1}</h4>
                    <p style='font-size:14px; color:#555;'>🕒 {timestamp1}</p>
                    <p style='font-size:16px; color:#333;'>{rec1}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
