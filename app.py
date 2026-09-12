import os
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

# התאמת כיווניות ועיצוב (RTL)
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

# 2. חלק עליון: סמל הפקולטה לחקלאות וסמל מדעי התזונה
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 2px solid #2e7d32; margin-bottom: 18px; background-color: #ffffff; border-radius: 8px;">
    <div>
        <img src="https://study.agri.huji.ac.il/sites/default/files/agri-study/files/faculty-logo.jpg" alt="הפקולטה לחקלאות מזון וסביבה" style="height: 60px; max-width: 100%;">
    </div>
    <div style="text-align: left; line-height: 1.2;">
        <span style="font-size: 17px; font-weight: bold; color: #1b5e20; display: block;">האוניברסיטה העברית בירושלים</span>
        <span style="font-size: 14px; font-weight: 600; color: #333;">בית הספר למדעי התזונה</span>
        <span style="font-size: 12px; color: #666; display: block;">מסלולים 712-1212 | 712-1225</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 3. כפתורי גישה מהירה קבועים בראש העמוד
col1, col2, col3 = st.columns(3)
with col1:
    st.link_button("תקנון ונהלים", "https://studentsadmin.huji.ac.il/study", use_container_width=True)
with col2:
    st.link_button("שנתון הקורסים", "https://shnaton.huji.ac.il", use_container_width=True)
with col3:
    st.link_button("פורטל מידע אישי", "https://studentservices.huji.ac.il", use_container_width=True)

st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)

# 4. מיפוי קורסים בתואר
COURSES_MAP = {
    "כימיה כללית": "71011",
    "כימיה אורגנית": "71014",
    "גנטיקה": "71012",
    "חדוא": "71013",
    "חדו\"א": "71013",
    "אינפי": "71013",
    "ביוכימיה": "71015",
    "אנטומיה": "71016",
    "פיזיולוגיה": "71017",
    "סטטיסטיקה": "71018"
}

def get_office_updates():
    if os.path.exists("updates.txt"):
        with open("updates.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return "אין עדכונים חריגים מהמזכירות."

def fetch_shnaton_info(course_id):
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

# ניהול היסטוריית שיחה
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_query_time" not in st.session_state:
    st.session_state.last_query_time = 0.0

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_query = st.chat_input("שאל/י על קורס, מועדי בחינות, תקנון או נהלים...")

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

    matched_course_id = None
    for name, cid in COURSES_MAP.items():
        if name in user_query or cid in user_query:
            matched_course_id = cid
            break

    shnaton_data = ""
    if matched_course_id:
        shnaton_data = f"\nמידע שנשלף מהשנתון לקורס {matched_course_id}:\n" + fetch_shnaton_info(matched_course_id)

    office_updates = get_office_updates()

    prompt = f"""
אתה העוזר של מחזור מדעי התזונה באוניברסיטה העברית (נציג המחזור: נתנאל גוטליב).
ענה אך ורק על בסיס הנתונים הבאים וצרף קישורים רשמיים. 

עדכוני מזכירות אחרונים (עדיפות עליונה אם נוגעים לשאלה):
{office_updates}

קישורים רשמיים קבועים:
- תקנון לימודים ומינהל תלמידים: https://studentsadmin.huji.ac.il/study
- פרק 7 (בחינות ומועדים מיוחדים): https://studentsadmin.huji.ac.il/exams
- שנתון העברית: https://shnaton.huji.ac.il
- פורטל מידע אישי: https://studentservices.huji.ac.il
- מסלול מדעי התזונה (1212 ו-1225): https://info.huji.ac.il/bachelor/Nutrition-Sciences

מידע נקודתי שנשלף לשאילתה זו:
{shnaton_data}

כללים:
1. לשאלות אישיות או מורכבות: הפנה ישירות לנתנאל גוטליב, נציג המחזור.
2. לשאלות כלליות על בחינות ללא קורס ספציפי: הפנה למידע האישי ולשנתון, ובקש שם קורס ממוקד.
3. סגנון: ענייני, תמציתי (עד 3 משפטים) ובעברית.

שאלת הסטודנט: {user_query}
"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        reply = response.text
    except Exception:
        reply = "אירעה שגיאה בעיבוד השאילתה. ניתן לפנות ישירות לנתנאל, נציג המחזור."

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.write(reply)
