# -- coding: utf-8 --
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS # 1. تم استيراد CORS
import swisseph as swe
from geopy.geocoders import Nominatim
import os
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime
import logging
import json # تمت إضافة استيراد JSON

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# 2. تفعيل CORS على التطبيق للسماح لجميع النطاقات بالوصول (يجب تقييدها في الإنتاج)
CORS(app) 
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# --- HOROSCOPE ADMIN CONFIGURATION ---
# المسار الذي سيتم حفظ البيانات اليومية فيه
HOROSCOPE_DATA_PATH = os.path.join(app.root_path, 'Static', 'daily_horoscopes.json')
# ⚠️ هام جداً: غيّر كلمة المرور الافتراضية هذه إلى كلمة سر قوية!
ADMIN_PASSWORD = 'YOUR_SECURE_ADMIN_PASSWORD' 
# -------------------------------------

PLANET_SYMBOLS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀",
    "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅",
    "Neptune": "♆", "Pluto": "♇", "Rahu": "☊", "Ketu": "☋"
}
PLANET_NAMES_ARABIC = {
    "Sun": "الشمس", "Moon": "القمر", "Mercury": "عطارد", "Venus": "الزهرة",
    "Mars": "المريخ", "Jupiter": "المشتري", "Saturn": "زحل", "Uranus": "أورانوس",
    "Neptune": "نبتون", "Pluto": "بلوتو", "Rahu": "الرأس (راهو)", "Ketu": "الذنب (كيتو)"
}
SIGN_SYMBOLS = {
    "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
    "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
    "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓"
}
SIGN_NAMES_ARABIC = [
    "الحمل", "الثور", "الجوزاء", "السرطان", "الأسد", "العذراء",
    "الميزان", "العقرب", "القوس", "الجدي", "الدلو", "الحوت"
]
SIGN_NAMES_ENGLISH = list(SIGN_SYMBOLS.keys())
HOUSE_NAMES_ARABIC = [
    "الأول (الطالع)", "الثاني", "الثالث", "الرابع (قاع السماء)", "الخامس", "السادس",
    "السابع (الهابط)", "الثامن", "التاسع", "العاشر (وسط السماء)", "الحادي عشر", "الثاني عشر"
]

# --- NEW HELPER FUNCTION ---
def read_horoscopes():
    """قراءة البيانات من ملف JSON مع دعم UTF-8."""
    try:
        with open(HOROSCOPE_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # في حالة عدم العثور على الملف أو تلفه، يتم إرجاع كائن فارغ
        return {}
# ---------------------------

def get_lat_lon(city, country):
    """Get latitude and longitude for a city using geocoding."""
    geolocator = Nominatim(user_agent="falaky_app")
    location = geolocator.geocode(f"{city}, {country}", language='ar') or \
               geolocator.geocode(f"{city}, {country}", language='en')
    return (location.latitude, location.longitude) if location else (None, None)

def fix_timezone_override(timezone_str, country):
    """
    Fix incorrect timezone detections from TimezoneFinder.
    Some countries have incorrect timezone mappings, so we override them here.
    """
    country_lower = country.lower().strip()
    
    # Syria fix: TimezoneFinder incorrectly returns "Europe/Moscow" for Syrian cities
    # Syria should use "Asia/Damascus" (UTC+3 permanent, no DST since Oct 2022)
    syria_names = ['syria', 'سوريا', 'syrian', 'syrian arab republic', 'سورية']
    if any(name in country_lower for name in syria_names):
        if timezone_str != 'Asia/Damascus':
            logging.info(f"Overriding timezone from {timezone_str} to Asia/Damascus for Syria")
            return 'Asia/Damascus'
    
    # Jordan fix: Ensure correct timezone for Jordan
    jordan_names = ['jordan', 'الأردن', 'jordanian']
    if any(name in country_lower for name in jordan_names):
        if timezone_str != 'Asia/Amman':
            logging.info(f"Overriding timezone from {timezone_str} to Asia/Amman for Jordan")
            return 'Asia/Amman'
    
    # Saudi Arabia fix: Ensure correct timezone for Saudi Arabia
    saudi_names = ['saudi arabia', 'السعودية', 'المملكة العربية السعودية', 'saudi', 'ksa']
    if any(name in country_lower for name in saudi_names):
        if timezone_str != 'Asia/Riyadh':
            logging.info(f"Overriding timezone from {timezone_str} to Asia/Riyadh for Saudi Arabia")
            return 'Asia/Riyadh'
    
    return timezone_str

def get_zodiac_info(deg):
    """Convert degree to zodiac sign information."""
    index = int(deg // 30) % 12
    sign_en = SIGN_NAMES_ENGLISH[index]
    degree_in_sign = deg % 30
    return {
        "sign_ar": SIGN_NAMES_ARABIC[index],
        "sign_symbol": SIGN_SYMBOLS[sign_en],
        "sign_index": index,
        "degree_in_sign": degree_in_sign,
        "sign_en": sign_en
    }

def get_house_number(lon_deg, houses_cusps):
    """
    Determine which house a celestial body is in based on its degree and house cusps.
    CORRECTED: Uses houses_cusps[0:12] for proper indexing.
    """
    if len(houses_cusps) < 12:
        return 1
    
    # CRITICAL FIX: Use [0:12] not [1:13] to get the correct house cusps
    cusps = list(houses_cusps[0:12])
    
    lon_deg = lon_deg % 360
    
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i + 1) % 12] % 360
        
        if start < end:
            # Normal case: house doesn't cross 0°
            if start <= lon_deg < end:
                return i + 1
        else:
            # Wraparound case: house crosses 0° Aries
            if lon_deg >= start or lon_deg < end:
                return i + 1
    
    return 1

def calculate_aspects(planets_deg):
    """Calculate major aspects between planets."""
    aspects = []
    planet_list = list(planets_deg.items())
    
    aspect_types = {
        'opposition': {'angle': 180, 'orb': 8, 'color': 'red', 'linewidth': 2},
        'trine': {'angle': 120, 'orb': 8, 'color': 'blue', 'linewidth': 1.5},
        'square': {'angle': 90, 'orb': 8, 'color': 'red', 'linewidth': 1.5},
        'sextile': {'angle': 60, 'orb': 6, 'color': 'blue', 'linewidth': 1},
    }
    
    for i in range(len(planet_list)):
        for j in range(i + 1, len(planet_list)):
            planet1_name, deg1 = planet_list[i]
            planet2_name, deg2 = planet_list[j]
            
            diff = abs(deg1 - deg2)
            if diff > 180:
                diff = 360 - diff
            
            for aspect_name, aspect_info in aspect_types.items():
                if abs(diff - aspect_info['angle']) <= aspect_info['orb']:
                    aspects.append({
                        'planet1': planet1_name,
                        'planet2': planet2_name,
                        'deg1': deg1,
                        'deg2': deg2,
                        'type': aspect_name,
                        'angle': aspect_info['angle'],
                        'color': aspect_info['color'],
                        'linewidth': aspect_info['linewidth']
                    })
    
    return aspects

def create_chart_image(planets_deg, houses_deg, ascendant_deg):
    """Create a visual representation of the astrological chart."""
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    
    ax.set_theta_zero_location('W')
    ax.set_theta_direction(1)
    
    rotation_offset = ascendant_deg
    
    inner_radius = 0.3
    outer_radius = 1.0
    
    # Draw zodiac signs
    for i in range(12):
        start_deg = i * 30
        
        rotated_start_deg = (start_deg - rotation_offset) % 360
        start_rad = np.deg2rad(rotated_start_deg)
        
        color = 'lightblue' if i % 2 == 0 else 'lightyellow'
        ax.bar(start_rad, outer_radius - inner_radius, width=np.deg2rad(30), bottom=inner_radius, 
               color=color, alpha=0.3, edgecolor='black', linewidth=1.0, align='edge')
        
        sign_center_deg = start_deg + 15
        rotated_center_deg = (sign_center_deg - rotation_offset) % 360
        sign_center_rad = np.deg2rad(rotated_center_deg)
        
        ax.text(sign_center_rad, outer_radius + 0.1, SIGN_SYMBOLS[SIGN_NAMES_ENGLISH[i]], 
                fontsize=16, ha='center', va='center', weight='bold')
    
    # Draw inner circle
    theta_full = np.linspace(0, 2*np.pi, 100)
    ax.plot(theta_full, [inner_radius] * 100, color='black', linewidth=1.5)
    
    # Draw house cusps
    for i, deg in enumerate(houses_deg):
        rotated_deg = (deg - rotation_offset) % 360
        theta = np.deg2rad(rotated_deg)
        ax.plot([theta, theta], [inner_radius, outer_radius], color='black', linestyle='-', linewidth=2.0)
        
        house_num = i + 1
        next_deg = houses_deg[(i + 1) % 12]
        mid_deg = deg + ((next_deg - deg) % 360) / 2
        
        rotated_mid_deg = (mid_deg - rotation_offset) % 360
        mid_rad = np.deg2rad(rotated_mid_deg)
        
        house_number_radius = inner_radius + 0.1
        ax.text(mid_rad, house_number_radius, str(house_num), fontsize=10, ha='center', va='center', 
                weight='bold', color='black')
    
    # Draw aspects
    aspects = calculate_aspects(planets_deg)
    aspect_radius = inner_radius - 0.05
    
    for aspect in aspects:
        rotated_deg1 = (aspect['deg1'] - rotation_offset) % 360
        rotated_deg2 = (aspect['deg2'] - rotation_offset) % 360
        theta1 = np.deg2rad(rotated_deg1)
        theta2 = np.deg2rad(rotated_deg2)
        
        num_points = 100
        t_vals = np.linspace(0, 1, num_points)
        x1 = aspect_radius * np.cos(theta1)
        y1 = aspect_radius * np.sin(theta1)
        x2 = aspect_radius * np.cos(theta2)
        y2 = aspect_radius * np.sin(theta2)
        
        xs = x1 + t_vals * (x2 - x1)
        ys = y1 + t_vals * (y2 - y1)
        
        rs = np.sqrt(xs**2 + ys**2)
        thetas = np.arctan2(ys, xs)
        
        ax.plot(thetas, rs, color=aspect['color'], linewidth=aspect['linewidth'], 
                alpha=0.6, linestyle='-', solid_capstyle='round')
    
    # Draw planets
    planet_positions = {}
    for name, deg in planets_deg.items():
        rotated_deg = (deg - rotation_offset) % 360
        theta = np.deg2rad(rotated_deg)
        
        radius = outer_radius - 0.15
        for other_name, other_pos in planet_positions.items():
            other_theta, other_radius = other_pos
            angle_diff = abs(theta - other_theta)
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            
            if angle_diff < np.deg2rad(10):
                radius = other_radius - 0.08 if other_radius > outer_radius - 0.2 else other_radius + 0.08
        
        planet_positions[name] = (theta, radius)
        
        ax.text(theta, radius, PLANET_SYMBOLS.get(name, '?'), 
                fontsize=14, ha='center', va='center', 
                color='black', weight='bold')
        
        info = get_zodiac_info(deg)
        degree_text = f"{int(info['degree_in_sign'])}°"
        ax.text(theta, radius - 0.06, degree_text, 
                fontsize=8, ha='center', va='center', color='darkblue')
    
    # Draw ASC line
    asc_theta = np.deg2rad(0)
    ax.plot([asc_theta, asc_theta], [0.0, outer_radius], color='black', linestyle='-', linewidth=3)
    ax.text(asc_theta, outer_radius + 0.05, 'ASC', fontsize=12, ha='center', va='center', 
            weight='bold', color='black')
    
    ax.set_rticks([])
    ax.set_xticks(np.deg2rad(np.arange(0, 360, 30)))
    ax.set_xticklabels([])
    ax.set_ylim(0, outer_radius + 0.2)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    img_data = base64.b64encode(buf.read()).decode('ascii')
    plt.close(fig)
    return img_data

def get_planet_degree(jd_ut, pid):
    """Get the degree position of a planet."""
    try:
        pos_calc = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH)
        if pos_calc and isinstance(pos_calc[0], (list, tuple)):
            return pos_calc[0][0]
        elif isinstance(pos_calc[0], (float, int)):
            return pos_calc[0]
    except Exception as e:
        logging.error(f"Error calculating planet {pid}: {e}")
    return -1.0

@app.route('/', methods=['GET', 'POST'])
def index():
    chart = None
    result_data = None
    input_data = request.form if request.method == 'POST' else None
    error = None
    dst_notice = None

    if request.method == 'POST':
        try:
            year = int(request.form['year'])
            month = int(request.form['month'])
            day = int(request.form['day'])
            hour = int(request.form['hour'])
            minute = int(request.form['minute'])
            city = request.form['city'].strip()
            country = request.form['country'].strip()

            lat, lon = get_lat_lon(city, country)
            if lat is None or lon is None:
                error = "لم نتمكن من العثور على المدينة/الدولة المدخلة. تحقق من الإملاء."
                return render_template('index.html', error=error, input_data=input_data)

            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lng=lon, lat=lat)
            if not timezone_str:
                error = "لم يتم العثور على منطقة زمنية لهذا الموقع."
                return render_template('index.html', error=error, input_data=input_data)
            
            # CRITICAL FIX: Apply timezone override for Syria, Jordan, Saudi Arabia
            timezone_str = fix_timezone_override(timezone_str, country)

            local_tz = pytz.timezone(timezone_str)
            naive_dt = datetime(year, month, day, hour, minute)
            dst_preference_str = request.form.get('dst_preference', 'true')
            user_prefers_dst = (dst_preference_str == 'true')
            
            try:
                local_dt = local_tz.localize(naive_dt, is_dst=None)
            except pytz.exceptions.AmbiguousTimeError:
                local_dt = local_tz.localize(naive_dt, is_dst=user_prefers_dst)
                dst_type = "التوقيت الصيفي (الحدوث الأول)" if user_prefers_dst else "التوقيت الشتوي (الحدوث الثاني)"
                dst_notice = f"ملاحظة: الوقت المدخل ({hour:02d}:{minute:02d}) يحدث مرتين في هذا التاريخ بسبب التوقيت الصيفي. تم استخدام {dst_type}."
                logging.info(f"Ambiguous time detected for {timezone_str}, using DST={user_prefers_dst}")
            except pytz.exceptions.NonExistentTimeError:
                error = f"الوقت المدخل ({hour:02d}:{minute:02d}) غير موجود في هذا التاريخ بسبب التوقيت الصيفي. الساعة تقدمت في هذا اليوم. يرجى إدخال وقت مختلف."
                logging.warning(f"Non-existent time for {timezone_str} at {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}")
                return render_template('index.html', error=error, input_data=input_data)
            
            utc_dt = local_dt.astimezone(pytz.utc)
            
            utc_offset = local_dt.strftime('%z')
            utc_offset_formatted = f"UTC{utc_offset[:3]}:{utc_offset[3:]}"
            
            dst_offset = local_dt.dst()
            is_dst_active = bool(dst_offset)
            dst_hours = dst_offset.total_seconds() / 3600 if dst_offset else 0
            
            if not dst_notice:
                if is_dst_active and dst_hours > 0:
                    dst_hours_str = f"{dst_hours:.1f}".rstrip('0').rstrip('.')
                    dst_notice = f"✓ التوقيت الصيفي نشط في هذا التاريخ. التوقيت المستخدم: {utc_offset_formatted} (يتضمن +{dst_hours_str} ساعة توقيت صيفي)"
                else:
                    dst_notice = f"التوقيت الشتوي (القياسي) نشط في هذا التاريخ. التوقيت المستخدم: {utc_offset_formatted}"
            else:
                dst_notice += f" التوقيت المستخدم: {utc_offset_formatted}"

            jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                                 utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)
            
            logging.info(f"Birth data: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d} in {city}, {country}")
            logging.info(f"Timezone: {timezone_str}, UTC Offset: {utc_offset_formatted}, DST Active: {is_dst_active}, DST Hours: {dst_hours}")
            logging.info(f"Local time: {local_dt}, UTC time: {utc_dt}")
            logging.info(f"Julian Day: {jd_ut}, Lat: {lat}, Lon: {lon}")

            house_system = request.form.get('house_system', 'P')
            houses_cusps_full, ascmc = swe.houses_ex(jd_ut, lat, lon, house_system.encode(), swe.FLG_SWIEPH)

            # Use ascmc[0] for true Ascendant
            ascendant_degree = ascmc[0]
            mc_degree = ascmc[1]
            
            logging.info(f"House system: {house_system}")
            logging.info(f"ASCMC array: {ascmc}")
            logging.info(f"Ascendant (AC) from ascmc[0]: {ascendant_degree:.2f}°")
            logging.info(f"MC from ascmc[1]: {mc_degree:.2f}°")
            
            # Handle Whole Sign house system
            if house_system == 'W':
                asc_deg = ascendant_degree
                asc_sign_index = int(asc_deg // 30)
                
                new_houses_cusps = []
                for i in range(12):
                    cusp_start_deg = ((asc_sign_index + i) % 12) * 30
                    new_houses_cusps.append(cusp_start_deg)
                    
                houses_cusps_full = tuple(new_houses_cusps)
                logging.info(f"Whole Sign houses calculated. ASC sign index: {asc_sign_index}")
            
            # Calculate IC and DC
            ic_degree = (mc_degree + 180) % 360
            dc_degree = (ascendant_degree + 180) % 360
            
            angles = {
                "AC": {"name_ar": "الطالع", "degree": ascendant_degree, "sign_info": get_zodiac_info(ascendant_degree)},
                "IC": {"name_ar": "قاع السماء", "degree": ic_degree, "sign_info": get_zodiac_info(ic_degree)},
                "MC": {"name_ar": "وسط السماء", "degree": mc_degree, "sign_info": get_zodiac_info(mc_degree)},
                "DC": {"name_ar": "الهابط", "degree": dc_degree, "sign_info": get_zodiac_info(dc_degree)},
            }
            
            planets_list = []
            planets_deg_for_chart = {}
            planet_ids = {
                "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
                "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
                "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
                "Pluto": swe.PLUTO
            }

            for name_en, pid in planet_ids.items():
                pos_deg = get_planet_degree(jd_ut, pid)
                if pos_deg == -1.0:
                    continue
                
                # CRITICAL: Use corrected get_house_number function
                house_num = get_house_number(pos_deg, houses_cusps_full)
                info = get_zodiac_info(pos_deg)
                
                planets_list.append({
                    "name_en": name_en,
                    "name_ar": PLANET_NAMES_ARABIC.get(name_en, name_en),
                    "symbol": PLANET_SYMBOLS.get(name_en),
                    "degree": pos_deg,
                    "degree_in_sign": info['degree_in_sign'],
                    "sign_ar": info['sign_ar'],
                    "sign_symbol": info['sign_symbol'],
                    "house": house_num,
                    "sign_en": info['sign_en'],
                })
                planets_deg_for_chart[name_en] = pos_deg
                
                logging.info(f"{name_en} at {pos_deg:.2f}° in {info['sign_ar']} ({info['sign_en']}), House {house_num}")

            # Calculate Rahu and Ketu
            rahu_pos = get_planet_degree(jd_ut, swe.MEAN_NODE)
            if rahu_pos != -1.0:
                house_num_rahu = get_house_number(rahu_pos, houses_cusps_full)
                info_rahu = get_zodiac_info(rahu_pos)
                
                planets_list.append({
                    "name_en": "Rahu",
                    "name_ar": PLANET_NAMES_ARABIC.get("Rahu"),
                    "symbol": PLANET_SYMBOLS.get("Rahu"),
                    "degree": rahu_pos,
                    "degree_in_sign": info_rahu['degree_in_sign'],
                    "sign_ar": info_rahu['sign_ar'],
                    "sign_symbol": info_rahu['sign_symbol'],
                    "house": house_num_rahu,
                    "sign_en": info_rahu['sign_en'],
                })
                planets_deg_for_chart["Rahu"] = rahu_pos
                logging.info(f"Rahu at {rahu_pos:.2f}° in {info_rahu['sign_ar']}, House {house_num_rahu}")
                
                ketu_pos = (rahu_pos + 180) % 360
                house_num_ketu = get_house_number(ketu_pos, houses_cusps_full)
                info_ketu = get_zodiac_info(ketu_pos)

                planets_list.append({
                    "name_en": "Ketu",
                    "name_ar": PLANET_NAMES_ARABIC.get("Ketu"),
                    "symbol": PLANET_SYMBOLS.get("Ketu"),
                    "degree": ketu_pos,
                    "degree_in_sign": info_ketu['degree_in_sign'],
                    "sign_ar": info_ketu['sign_ar'],
                    "sign_symbol": info_ketu['sign_symbol'],
                    "house": house_num_ketu,
                    "sign_en": info_ketu['sign_en'],
                })
                planets_deg_for_chart["Ketu"] = ketu_pos
                logging.info(f"Ketu at {ketu_pos:.2f}° in {info_ketu['sign_ar']}, House {house_num_ketu}")

            # Build houses info
            houses_info = []
            for i in range(12):
                info = get_zodiac_info(houses_cusps_full[i])
                houses_info.append({
                    "house": i + 1,
                    "name_ar": HOUSE_NAMES_ARABIC[i],
                    "degree": houses_cusps_full[i],
                    "degree_in_sign": info['degree_in_sign'],
                    "sign_ar": info['sign_ar'],
                    "sign_symbol": info['sign_symbol'],
                })

            result_data = {
                "angles": angles,
                "planets": planets_list,
                "location": f"{city}, {country}",
                "timezone": timezone_str,
                "local_time": local_dt.strftime("%Y-%m-%d %H:%M"),
                "utc_time": utc_dt.strftime("%Y-%m-%d %H:%M UTC"),
                "houses_deg": list(houses_cusps_full[0:12]),
                "houses_info": houses_info,
                "dst_notice": dst_notice,
                "house_system": house_system,
            }

            chart = create_chart_image(planets_deg_for_chart, result_data["houses_deg"], ascendant_degree)
            
            logging.info("Chart calculation completed successfully")

        except Exception as e:
            error = f"حدث خطأ غير متوقع: {e}"
            logging.error(f"Critical Error in POST Request: {e}", exc_info=True)

    return render_template('index.html',
                           result=result_data,
                           chart=chart,
                           error=error,
                           input_data=input_data)

# --- ROUTES FOR HOROSCOPE MANAGEMENT ---

# 1. مسار لوحة الإدارة (للعرض والتعديل)
@app.route('/admin/horoscopes', methods=['GET', 'POST'])
def admin_horoscopes():
    
    # التحقق من كلمة المرور عبر بارامتر في URL
    if request.args.get('password') != ADMIN_PASSWORD:
        return "غير مصرح به. أضف كلمة المرور في رابط URL: /admin/horoscopes?password=YOUR_PASSWORD", 401

    if request.method == 'POST':
        # التعامل مع حفظ البيانات المرسلة من نموذج HTML
        try:
            horoscopes = read_horoscopes()
            
            # تحديث محتوى التوقعات بناءً على البيانات المرسلة من النموذج
            for sign in horoscopes.keys():
                # نتوقع أن اسم الحقل في النموذج هو 'aries_content', 'taurus_content', إلخ.
                new_content = request.form.get(f'{sign}_content')
                if new_content is not None:
                    horoscopes[sign]['content'] = new_content
            
            # كتابة البيانات المحدثة إلى ملف JSON
            with open(HOROSCOPE_DATA_PATH, 'w', encoding='utf-8') as f:
                # ensure_ascii=False يضمن حفظ الأحرف العربية بشكل صحيح
                json.dump(horoscopes, f, ensure_ascii=False, indent=4)
                
            # إعادة التوجيه لمنع إعادة إرسال النموذج عند تحديث الصفحة
            return redirect(url_for('admin_horoscopes', password=ADMIN_PASSWORD))
        
        except Exception as e:
            logging.error(f"Error saving horoscopes: {e}", exc_info=True)
            return f"حدث خطأ أثناء الحفظ: {e}", 500

    # عرض نموذج التعديل (admin_horoscopes.html)
    horoscopes = read_horoscopes()
    # يتم تمرير horoscopes إلى admin_horoscopes.html
    return render_template('admin_horoscopes.html', horoscopes=horoscopes, admin_password=ADMIN_PASSWORD)


# 2. مسار API لجلب البيانات (للاستخدام في الواجهة الأمامية index.html)
@app.route('/api/horoscopes', methods=['GET'])
def api_horoscopes():
    """جلب بيانات الأبراج بصيغة JSON ليستخدمها JavaScript في الواجهة الأمامية."""
    horoscopes = read_horoscopes()
    # يتم استخدام jsonify لضمان إرسال رأس محتوى JSON الصحيح
    return jsonify(horoscopes)


# 3. المسار الجديد المطلوب (كمثال)
@app.route('/api/new_endpoint', methods=['GET'])
def new_api_endpoint():
    """3. مسار API جديد لتجربة CORS والوصول إلى بيانات مخصصة."""
    
    # يمكن هنا قراءة بيانات من قاعدة بيانات، أو إجراء عملية حسابية، أو جلب معلومات محددة.
    example_data = {
        "status": "success",
        "message_ar": "هذه نقطة نهاية API جديدة ومفعّلة بتقنية CORS.",
        "data_payload": {
            "version": "1.0.0",
            "test_value": 42
        }
    }
    
    # إرجاع البيانات بصيغة JSON
    return jsonify(example_data)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)