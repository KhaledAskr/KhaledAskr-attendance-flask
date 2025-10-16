# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
import os, json, base64, gspread, pandas as pd
from google.oauth2 import service_account
from functools import wraps

# ===============================
# إعداد Flask
# ===============================
app = Flask(__name__)
app.secret_key = "secret-key-attendance"  # يمكنك تغييره لاحقاً

SHEET_ID = "1Nw88QraEgXYetl5r7jLguH28MZzGfHSi6uME06cFcM4"
SHEET_NAME = "presence"

# ===============================
# الاتصال بـ Google Sheets
# ===============================
def gsheet_client():
    creds_b64 = os.environ.get("GOOGLE_CREDS_BASE64")
    if not creds_b64:
        raise FileNotFoundError("⚠️ لم يتم العثور على GOOGLE_CREDS_BASE64 في Render")

    try:
        # فك الترميز Base64 وإعادة بناء JSON الأصلي
        creds_json = base64.b64decode(creds_b64).decode("utf-8")
        creds_dict = json.loads(creds_json)

        creds = service_account.Credentials.from_service_account_info(creds_dict)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print("❌ خطأ أثناء تحميل المفاتيح:", e)
        raise

# ===============================
# دوال مساعدة
# ===============================
def open_presence_sheet():
    client = gsheet_client()
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet(SHEET_NAME)

def read_all_records():
    ws = open_presence_sheet()
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    return df

def mark_student(qr_data):
    df = read_all_records()
    parts = qr_data.split("-")
    if len(parts) < 2:
        raise ValueError("⚠️ الكود غير صالح")
    student_id = parts[0].strip()
    session_col = "session 1"

    idx = df.index[df["ID"] == student_id].tolist()
    if not idx:
        raise ValueError("⚠️ الطالب غير موجود")

    # تحديث العمود
    ws = open_presence_sheet()
    row = idx[0] + 2  # +2 لأن Google Sheet يبدأ من 1 وفيه صف العناوين
    col = df.columns.get_loc(session_col) + 1
    ws.update_cell(row, col, "✅")
    print(f"✅ تم تسجيل حضور الطالب {student_id}")

# ===============================
# حساب ملخص التقرير
# ===============================
def calculate_summary(df):
    sessions = [col for col in df.columns if "session" in col and "date" not in col]
    summary = []
    for _, row in df.iterrows():
        attended = sum(1 for c in sessions if str(row[c]).strip() == "✅")
        total = len(sessions)
        rate = round((attended / total) * 100, 2) if total else 0
        summary.append({
            "ID": row["ID"],
            "Name": row["Name"],
            "Section": row.get("رقم السكشن", ""),
            "Attended": attended,
            "Absent": total - attended,
            "Rate": rate
        })
    return summary

# ===============================
# نظام الدخول البسيط
# ===============================
DEFAULT_USER = {"username": "admin", "password": "1234"}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]
        if user == DEFAULT_USER["username"] and pw == DEFAULT_USER["password"]:
            session["user"] = user
            return redirect(url_for("index"))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج", "info")
    return redirect(url_for("login"))

# ===============================
# الصفحات
# ===============================
@app.route("/")
@login_required
def index():
    df = read_all_records()
    total = len(df)
    return render_template("index.html", total=total)

@app.route("/scan_qr")
@login_required
def scan_qr():
    return render_template("scan_qr.html")

@app.route("/mark", methods=["POST"])
@login_required
def mark_attendance():
    try:
        qr_data = request.form.get("qr_data")
        mark_student(qr_data)
        flash("✅ تم تسجيل الحضور بنجاح", "success")
    except Exception as e:
        flash(f"⚠️ حدث خطأ أثناء التسجيل: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/report")
@login_required
def report():
    df = read_all_records()
    stats = calculate_summary(df)
    return render_template("report.html", stats=stats)

# ===============================
# التشغيل
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
