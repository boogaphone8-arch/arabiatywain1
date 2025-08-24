import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify

app = Flask(__name__)

# 🔹 المسار الكامل لملف JSON
SERVICE_ACCOUNT_FILE = '/data/user/0/ru.iiec.pydroid3/files/pydroid3/service_account.json'

# 🔹 اسم الشيت كما هو بالضبط مع الفراغات
SHEET_NAME = 'بلاغ السيارات'

# إعداد الاتصال مع Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

@app.route('/add_report', methods=['POST'])
def add_report():
    try:
        data = request.json
        # افترض أن البيانات تأتي على شكل JSON بترتيب الأعمدة
        row = [
            data.get('تم الاتصال', ''),
            data.get('نوع السيارة', ''),
            data.get('الموديل', ''),
            data.get('اللون', ''),
            data.get('رقم اللوحة', ''),
            data.get('رقم الشاسي', ''),
            data.get('المكان', ''),
            data.get('رقم الهاتف', ''),
            data.get('الملاحظات', '')
        ]
        sheet.append_row(row)
        return jsonify({'status': 'success', 'message': 'تم إضافة البلاغ للشيت'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    # لتشغيل Flask محلياً
    app.run(host='0.0.0.0', port=5000)