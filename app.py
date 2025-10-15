from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "attendance_secret_123"

# ----------------- إعداد Google Sheets -----------------
SHEET_ID = "1Nw88QraEgXYetl5r7jLguH28MZzGfHSi6uME06cFcM4"  # 🔹 ضع هنا ID الشيت الخاص بك
SHEET_NAME = "presence"  # 🔹 اسم الورقة داخل Google Sheet
CREDENTIALS_FILE = "credentials.json"

# ----------------- تحميل إعدادات المستخدم -----------------
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        cfg = {"admin_user": "admin", "admin_pass": "1234"}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return cfg
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ----------------- الاتصال بـ Google Sheets -----------------

from google.oauth2 import service_account

def gsheet_client():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("⚠️ ملف مفاتيح Google غير موجود: credentials.json")
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise FileNotFoundError("⚠️ لم يتم العثور على متغير GOOGLE_CREDS في إعدادات Render")

    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
    return client

    
    
def open_presence_sheet():
    client = gsheet_client()
    sheet = client.open_by_key(SHEET_ID)
    ws = sheet.worksheet(SHEET_NAME)
    return ws

# ----------------- دوال الحضور -----------------
def read_all_records():
    ws = open_presence_sheet()
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df.columns = [c.strip() for c in df.columns]  # تنظيف أسماء الأعمدة
    return df


def mark_attendance_in_sheet(student_id, session_num):
    try:
        ws = open_presence_sheet()
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [c.strip() for c in df.columns]  # إزالة المسافات الزائدة

        if student_id not in df["ID"].astype(str).values:
            return False, f"🚫 الطالب برقم الجلوس {student_id} غير موجود في الشيت."

        idx = df.index[df["ID"].astype(str) == str(student_id)][0]

        # دالة للبحث الذكي عن العمود
        def find_col(name):
            for c in df.columns:
                if name.replace(" ", "").lower() == c.replace(" ", "").lower():
                    return c
            return None

        col = find_col(f"session {session_num}")
        date_col = find_col(f"date session {session_num}")

        if not col or not date_col:
            return False, f"⚠️ لم يتم العثور على أعمدة الجلسة {session_num} في الشيت."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.update_cell(idx + 2, df.columns.get_loc(col) + 1, 1)
        ws.update_cell(idx + 2, df.columns.get_loc(date_col) + 1, now)

        return True, f"✅ تم تسجيل حضور الطالب {df.loc[idx, 'Name']} بنجاح."
    except Exception as e:
        return False, f"حدث خطأ أثناء التسجيل: {e}"


def calculate_summary(df):
    df.columns = [c.strip() for c in df.columns]

    def find_col(name):
        for c in df.columns:
            if name.replace(" ", "").lower() == c.replace(" ", "").lower():
                return c
        return None

    section_col = find_col("رقم السكشن") or "غير محدد"
    sessions = [c for c in df.columns if c.replace(" ", "").startswith("session")]

    summary = []
    for _, row in df.iterrows():
        attended = int(sum([row[c] == 1 for c in sessions if c in df.columns]))
        total = len(sessions)
        rate = round(attended / total * 100, 2) if total else 0
        summary.append({
            "ID": row.get("ID", ""),
            "Name": row.get("Name", ""),
            "Section": row.get(section_col, "غير محدد") if section_col in df.columns else "غير محدد",
            "Attended": attended,
            "Absent": total - attended,
            "Rate": rate
        })
    return summary

# ----------------- نظام الدخول -----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = load_config()
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == cfg["admin_user"] and pw == cfg["admin_pass"]:
            session["logged_in"] = True
            session["user"] = user
            return redirect(url_for("index"))
        else:
            flash("❌ اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح ✅", "info")
    return redirect(url_for("login"))

# ----------------- الصفحة الرئيسية -----------------
@app.route("/")
@login_required
def index():
    df = read_all_records()
    sessions = list(range(1, 13))
    return render_template("index.html", sessions=sessions)

# ----------------- تسجيل الحضور -----------------
@app.route("/mark", methods=["POST"])
@login_required
def mark_attendance():
    sid = request.form.get("student_id", "").strip()
    session_number = request.form.get("session_num", "").strip()
    if not sid or not session_number:
        flash("⚠️ برجاء إدخال رقم الجلوس واختيار الجلسة", "danger")
        return redirect(url_for("index"))
    ok, msg = mark_attendance_in_sheet(sid, int(session_number))
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("index"))

# ----------------- صفحة التقارير -----------------
@app.route("/report")
@login_required
def report():
    df = read_all_records()
    stats = calculate_summary(df)
    return render_template("report.html", stats=stats)

# ----------------- تنزيل Excel -----------------
@app.route("/export")
@login_required
def export():
    df = read_all_records()
    stats = calculate_summary(df)
    out = pd.DataFrame(stats)
    filename = "attendance_report.xlsx"
    out.to_excel(filename, index=False)
    flash("📥 تم إنشاء ملف Excel بنجاح", "success")
    return redirect(url_for("report"))

# ----------------- صفحة الإعدادات -----------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    cfg = load_config()
    if request.method == "POST":
        cfg["admin_user"] = request.form.get("username")
        cfg["admin_pass"] = request.form.get("password")
        save_config(cfg)
        flash("✅ تم تحديث بيانات الدخول بنجاح", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", cfg=cfg)

# ----------------- صفحة مسح QR -----------------
@app.route("/scan_qr")
@login_required
def scan_qr():
    return render_template("scan_qr.html")

# ----------------- صفحة فحص الطالب -----------------
@app.route("/verify_student", methods=["GET", "POST"])
@login_required
def verify_student():
    student = None
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        if sid:
            df = read_all_records()
            row = df[df["ID"].astype(str) == sid]
            if not row.empty:
                student = row.iloc[0].to_dict()
            else:
                flash(f"🚫 لا يوجد طالب بهذا الرقم ({sid})", "danger")
        else:
            flash("⚠️ من فضلك أدخل رقم الجلوس", "warning")
    return render_template("verify_student.html", student=student)

# ----------------- تشغيل التطبيق -----------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
