import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import streamlit as st
import google.generativeai as genai

# הגדרות עמוד
st.set_page_config(
    page_title="עוזר מחזור מדעי התזונה - הפקולטה לחקלאות",
    page_icon="🎓",
    layout="centered"
)

st.markdown("""
<style>
    .stApp { direction: rtl; text-align: right; }
    .stTextInput input { direction: rtl; text-align: right; }
    .stChatMessage { direction: rtl; text-align: right; }
    div[data-testid="stLinkButton"] a {
        text-align: center !important;
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

# 1. אבטחת מפתח API
api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("שגיאה: מפתח API אינו מוגדר בהגדרות הסודיות (Secrets).")
    st.stop()

genai.configure(api_key=api_key)

# 2. כותרת עליונה וסמלים
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 2px solid #2e7d32; margin-bottom: 18px; background-color: #ffffff; border-radius: 8px;">
    <div>
        <img src="https://study.agri.huji.ac.il/sites/default/files/agri-study/files/faculty-logo.jpg" alt="הפקולטה לחקלאות מזון וסביבה" style="height: 60px; max-width: 100%;">
    </div>
    <div style="text-align: left; line-height: 1.2;">
        <span style="font-size: 17px; font-weight: bold; color: #1b5e20; display: block;">האוניברסיטה העברית בירושלים</span>
        <span style="font-size: 14px; font-weight: 600; color: #333;">בית הספר למדעי התזונה</span>
        <span style="font-size: 12px; color: #666; display: block;">חוג 712 | מסלולים 1212 ו-1225</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 3. כפתורי שנתון מפוצלים וגישה מהירה
col_r1_1, col_r1_2 = st.columns(2)
with col_r1_1:
    st.link_button("שנתון מסלול 1212 (חד-חוגי)", "https://shnaton.huji.ac.il/roadmap/712-1212", use_container_width=True)
with col_r1_2:
    st.link_button("שנתון מסלול 1225 (עם אגרו-אינפורמטיקה)", "https://shnaton.huji.ac.il/roadmap/712-1225", use_container_width=True)

col_r2_1, col_r2_2 = st.columns(2)
with col_r2_1:
    st.link_button("תקנון ונהלים (מינהל תלמידים)", "https://studentsadmin.huji.ac.il/study", use_container_width=True)
with col_r2_2:
    st.link_button("פורטל מידע אישי לסטודנט", "https://studentservices.huji.ac.il", use_container_width=True)

st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)

# 4. טעינת קובצי הקורסים
def load_json_file(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                pass
    return {}

c_1212_mand = load_json_file("courses_1212_mandatory.json")
c_1212_elec = load_json_file("courses_1212_elective.json")
c_1225_mand = load_json_file("courses_1225_mandatory.json")
c_1225_elec_dept = load_json_file("courses_1225_elective_dept.json")
c_1225_elec_agro = load_json_file("courses_1225_elective_agro.json")

ALL_COURSES = {}
for d in [c_1212_mand, c_1212_elec, c_1225_mand, c_1225_elec_dept, c_1225_elec_agro]:
    ALL_COURSES.update(d)

def get_office_updates():
    if os.path.exists("updates.txt"):
        with open("updates.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return "אין עדכונים חריגים מהמזכירות."

@st.cache_data(ttl=86400)
def fetch_shnaton_info(course_id):
    """שליפה מהשנתון עם שמירה בזיכרון מטמון ל-24 שעות"""
    url = f"https://shnaton.huji.ac.il/course/{course_id}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            return soup.get_text(separator=" ", strip=True)[:1500]
    except Exception:
        pass
    return f"לצפייה בפרטי הקורס המלאים בשנתון: {url}"

@st.cache_data(ttl=86400)
def get_ai_response(query_text, course_data, updates_text):
    """מנגנון עיבוד עם Cache: שאלות חוזרות נשלפות ב-0 טוקנים מהזיכרון"""
    prompt = f"""
אתה העוזר של מחזור מדעי התזונה באוניברסיטה העברית (נציג המחזור: נתנאל גוטליב).
ענה אך ורק על בסיס הנתונים הבאים וצרף קישורים רשמיים.

מבנה המסלולים והקורסים:
- מסלול 712-1212 (מדעי התזונה 4 שנתי):
  * מפת מסלול ישירה: https://shnaton.huji.ac.il/roadmap/712-1212
  * קורסי חובה: {list(c_1212_mand.keys())}
  * קורסי חובת בחירה: {list(c_1212_elec.keys())}

- מסלול 712-1225 (מדעי התזונה עם חטיבה באגרו-אינפורמטיקה):
  * מפת מסלול ישירה: https://shnaton.huji.ac.il/roadmap/712-1225
  * קורסי חובה: {list(c_1225_mand.keys())}
  * קורסי חובת בחירה חוג: {list(c_1225_elec_dept.keys())}
  * קורסי חובת בחירה חטיבה באגרו: {list(c_1225_elec_agro.keys())}

עדכוני מזכירות אחרונים:
{updates_text}

קישורים רשמיים כלליים:
- תקנון לימודים: https://studentsadmin.huji.ac.il/study
- פרק 7 (בחינות ומועדים מיוחדים): https://studentsadmin.huji.ac.il/exams
- שנתון העברית: https://shnaton.huji.ac.il
- פורטל מידע אישי: https://studentservices.huji.ac.il

מידע שנשלף מהשנתון עבור קורס ספציפי (אם נשאל):
{course_data}

כללים:
1. הפניה לשנתון לפי מסלול: אם השאלה נוגעת למסלול 1212 צרף את הקישור הישיר https://shnaton.huji.ac.il/roadmap/712-1212, ואם היא נוגעת למסלול 1225 צרף את הקישור הישיר https://shnaton.huji.ac.il/roadmap/712-1225.
2. אבחנה בחובת בחירה של 1225: הקפד להבדיל בבירור בין קורסי חובת בחירה של החוג לבין קורסי חובת בחירה של חטיבת אגרו-אינפורמטיקה.
3. לפניות אישיות: הפנה ישירות לנתנאל גוטליב, נציג המחזור.
4. סגנון: ענייני, תמציתי (עד 3 משפטים) ובעברית.

שאלת הסטודנט: {query_text}
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text if response.text else "לא התקבלה תשובה, אנא נסח מחדש."

# ניהול היסטוריית שיחה
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_query_time" not in st.session_state:
    st.session_state.last_query_time = 0.0

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_query = st.chat_input("שאל/י על קורס, חובת בחירה, מסלול 1212/1225, תקנון...")

if user_query:
    current_time = time.time()
    if current_time - st.session_state.last_query_time < 3.0:
        st.warning("נא להמתין מספר שניות בין שאילתות.")
        st.stop()
    if len(user_query.strip()) > 250:
        st.warning("השאלה ארוכה מדי. נא לקצר עד 250 תווים.")
        st.stop()

    st.session_state.last_query_time = current_time
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("user"):
        st.write(user_query)

    # זיהוי מספר קורס בן 5 ספרות או שם קורס
    matched_course_id = None
    number_match = re.search(r'\b\d{5}\b', user_query)
    if number_match:
        matched_course_id = number_match.group(0)
    else:
        for name, cid in ALL_COURSES.items():
            if name in user_query:
                matched_course_id = cid
                break

    shnaton_data = ""
    if matched_course_id:
        shnaton_data = f"\nמידע שנשלף מהשנתון לקורס {matched_course_id}:\n" + fetch_shnaton_info(matched_course_id)

    office_updates = get_office_updates()

    # שליפה דרך פונקציית ה-Cache
    try:
        reply = get_ai_response(user_query.strip(), shnaton_data, office_updates)
    except Exception:
        reply = "אירעה שגיאה בעיבוד השאילתה. ניתן לפנות ישירות לנתנאל, נציג המחזור."

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.write(reply)
