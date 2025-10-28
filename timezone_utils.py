from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from datetime import datetime
import pytz

def get_timezone_info(city_name, date=None):
    # تحديد الإحداثيات من اسم المدينة
    geolocator = Nominatim(user_agent="falaky_app")
    location = geolocator.geocode(city_name)

    if not location:
        raise ValueError(f"لا يمكن إيجاد الموقع الجغرافي لـ: {city_name}")

    lat, lon = location.latitude, location.longitude

    # تحديد اسم المنطقة الزمنية
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=lon, lat=lat)

    if not timezone_str:
        raise ValueError("لم يتم التعرف على المنطقة الزمنية.")

    # تحويل التاريخ إلى datetime
    if date:
        naive_dt = datetime.strptime(date, "%Y-%m-%d")
    else:
        naive_dt = datetime.utcnow()

    timezone = pytz.timezone(timezone_str)
    local_dt = timezone.localize(naive_dt, is_dst=None)

    offset = local_dt.utcoffset().total_seconds() / 3600

    return {
        "city": city_name,
        "timezone_name": timezone_str,
        "datetime": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "utc_offset_hours": offset
    }