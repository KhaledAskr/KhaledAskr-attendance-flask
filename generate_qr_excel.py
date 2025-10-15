import pandas as pd
import qrcode
import os

# === إعدادات ===
EXCEL_FILE = "system_MUT1.xlsx"   # 🔹 اسم ملف الإكسل
SHEET_NAME = "presence"           # 🔹 اسم الشيت داخل الملف
OUTPUT_DIR = "qrcodes"            # 🔹 مجلد حفظ الأكواد

# === تحميل البيانات ===
if not os.path.exists(EXCEL_FILE):
    raise FileNotFoundError(f"⚠️ لم يتم العثور على الملف {EXCEL_FILE}")

df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
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

    # اسم الملف (مثلاً 12345_Ahmed_Ali.png)
    safe_name = name.replace(" ", "_")
    filename = f"{student_id}_{safe_name}.png"
    path = os.path.join(OUTPUT_DIR, filename)
    
    img.save(path)
    print(f"✅ تم إنشاء الكود: {filename}")

print("\n🎉 تم توليد جميع أكواد QR داخل المجلد:", OUTPUT_DIR)
