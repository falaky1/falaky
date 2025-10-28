# -- get_interpretation.py --
import json
import os
import logging

# تهيئة ملف log (للمساعدة في تتبع الأخطاء)
logging.basicConfig(level=logging.INFO)

def get_planet_interpretation(planet_name, house, sign):
    """
    تقوم هذه الدالة بقراءة التفسيرات من ملف interpretations_ar.json
    بناءً على الكوكب (planet_name)، البيت (house)، والبرج (sign).
    """
    
    file_path = os.path.join(os.path.dirname(__file__), 'interpretations_ar.json')
    
    try:
        # قراءة محتوى الملف كنص أولاً لمعالجة مشاكل الترميز/BOM
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 💡 خطوة حاسمة: إزالة علامة BOM (Byte Order Mark) يدوياً إذا وجدت
        content = content.lstrip('\ufeff')
        
        # فك تشفير النص المعالج
        data = json.loads(content)
        
    except FileNotFoundError:
        logging.error(f"ملف التفسيرات غير موجود: {file_path}")
        return (f"خطأ: ملف التفسيرات (interpretations_ar.json) غير موجود للبيت {house}.", 
                f"خطأ: ملف التفسيرات (interpretations_ar.json) غير موجود للبرج {sign}.")
    except json.JSONDecodeError as e:
         logging.error(f"فشل فك تشفير JSON في ملف التفسيرات. تأكد من صحة الصياغة. الخطأ: {e}")
         return (f"خطأ: فشل قراءة JSON في ملف التفسيرات للبيت {house}.", 
                f"خطأ: فشل قراءة JSON في ملف التفسيرات للبرج {sign}.")


    # التأكد من تحويل اسم الكوكب والبرج إلى أحرف صغيرة للمطابقة مع مفاتيح JSON
    planet_key = planet_name.lower()
    sign_key = sign.lower()
    house_key = str(house)

    # الحصول على البيانات الخاصة بالكوكب
    planet_data = data.get(planet_key, {})
    
    # البحث عن تفسير البيت
    house_interp = planet_data.get("houses", {}).get(house_key)
    # البحث عن تفسير البرج
    sign_interp = planet_data.get("signs", {}).get(sign_key)
    
    # رسالة افتراضية
    default_house = f"لا يوجد تفسير محدد لـ {planet_name} في البيت {house} في ملف التفسيرات."
    default_sign = f"لا يوجد تفسير محدد لـ {planet_name} في برج {sign} في ملف التفسيرات."

    house_result = house_interp if house_interp else default_house
    sign_result = sign_interp if sign_interp else default_sign
    
    return house_result, sign_result