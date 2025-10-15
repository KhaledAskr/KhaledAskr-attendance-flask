import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import qrcode
import os

# === إعدادات Google Sheet ===
SHEET_ID = "1Nw88QraEgXYetl5r7jLguH28MZzGfHSi6uME06cFcM4"  # 🔹 ضع ID الشيت هنا
SHEET_NAME = "presence"
CREDENTIALS_FILE = "credentials.json"
OUTPUT_DIR = "qrcodes"

# === الاتصال بـ Google Sheets ===
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
client = gspread.authorize(creds)

ws = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
records = ws.get_all_records()
df = pd.DataFrame(records)
df.columns = [c.strip() for c in df.columns]

# === إنشاء مجلد الأكواد ===
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === توليد الأكواد ===
for idx, row in df.iterrows():
    student_id = str(row.get("ID", "")).strip()
    name = str(row.get("Name", "")).strip()

    if not student_id or not name:
        print(f"⏩ تخطي صف فارغ (السطر {idx+2})")
        continue

    qr_text = f"{student_id}|{name}"
    img = qrcode.make(qr_text)

    safe_name = name.replace(" ", "_")
    filename = f"{student_id}_{safe_name}.png"
    path = os.path.join(OUTPUT_DIR, filename)

    img.save(path)
    print(f"✅ تم إنشاء الكود: {filename}")

print("\n🎉 تم توليد جميع أكواد QR داخل المجلد:", OUTPUT_DIR)
