from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "مرحباً بك في موقع Falaky.net!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # استخدام المنفذ الذي توفره منصة النشر
    app.run(host='0.0.0.0', port=port, debug=True)  # ربط السيرفر بـ 0.0.0.0 ليكون متاحاً خارجياً