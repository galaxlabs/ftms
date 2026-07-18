from __future__ import annotations

import frappe


KSA_CITIES = [
    # Central Region (Riyadh)
    {"city_name": "Riyadh", "city_name_ar": "الرياض", "region": "Riyadh Region", "region_ar": "منطقة الرياض", "latitude": 24.7136, "longitude": 46.6753},
    {"city_name": "Al Kharj", "city_name_ar": "الخرج", "region": "Riyadh Region", "region_ar": "منطقة الرياض", "latitude": 24.1556, "longitude": 47.3347},
    {"city_name": "Al Majma'ah", "city_name_ar": "المجمعة", "region": "Riyadh Region", "region_ar": "منطقة الرياض", "latitude": 25.9039, "longitude": 45.3410},
    {"city_name": "Al Zulfi", "city_name_ar": "الزلفي", "region": "Riyadh Region", "region_ar": "منطقة الرياض", "latitude": 26.2969, "longitude": 44.8172},
    {"city_name": "Al Quway'iyah", "city_name_ar": "القويعية", "region": "Riyadh Region", "region_ar": "منطقة الرياض"},
    {"city_name": "Wadi ad-Dawasir", "city_name_ar": "وادي الدواسر", "region": "Riyadh Region", "region_ar": "منطقة الرياض"},
    {"city_name": "Hawtat Bani Tamim", "city_name_ar": "حوطة بني تميم", "region": "Riyadh Region", "region_ar": "منطقة الرياض"},
    {"city_name": "Afif", "city_name_ar": "عفيف", "region": "Riyadh Region", "region_ar": "منطقة الرياض"},
    {"city_name": "Al Duwadimi", "city_name_ar": "الدوادمي", "region": "Riyadh Region", "region_ar": "منطقة الرياض"},
    {"city_name": "Shaqra", "city_name_ar": "شقراء", "region": "Riyadh Region", "region_ar": "منطقة الرياض"},

    # Western Region (Makkah)
    {"city_name": "Makkah", "city_name_ar": "مكة المكرمة", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة", "latitude": 21.4225, "longitude": 39.8262},
    {"city_name": "Jeddah", "city_name_ar": "جدة", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة", "latitude": 21.4858, "longitude": 39.1925},
    {"city_name": "Taif", "city_name_ar": "الطائف", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة", "latitude": 21.4373, "longitude": 40.3768},
    {"city_name": "Rabigh", "city_name_ar": "رابغ", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة"},
    {"city_name": "Al Qunfudhah", "city_name_ar": "القنفذة", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة"},
    {"city_name": "Al Lith", "city_name_ar": "الليث", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة"},
    {"city_name": "Turubah", "city_name_ar": "تربة", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة"},
    {"city_name": "Khulais", "city_name_ar": "خليص", "region": "Makkah Region", "region_ar": "منطقة مكة المكرمة"},

    # Western Region (Madinah)
    {"city_name": "Madinah", "city_name_ar": "المدينة المنورة", "region": "Madinah Region", "region_ar": "منطقة المدينة المنورة", "latitude": 24.4672, "longitude": 39.6108},
    {"city_name": "Yanbu", "city_name_ar": "ينبع", "region": "Madinah Region", "region_ar": "منطقة المدينة المنورة", "latitude": 24.0861, "longitude": 38.0639},
    {"city_name": "Badr", "city_name_ar": "بدر", "region": "Madinah Region", "region_ar": "منطقة المدينة المنورة"},
    {"city_name": "Al Ula", "city_name_ar": "العلا", "region": "Madinah Region", "region_ar": "منطقة المدينة المنورة"},
    {"city_name": "Khaybar", "city_name_ar": "خيبر", "region": "Madinah Region", "region_ar": "منطقة المدينة المنورة"},
    {"city_name": "Al Hinakiyah", "city_name_ar": "الحناكية", "region": "Madinah Region", "region_ar": "منطقة المدينة المنورة"},

    # Eastern Region
    {"city_name": "Dammam", "city_name_ar": "الدمام", "region": "Eastern Region", "region_ar": "المنطقة الشرقية", "latitude": 26.3927, "longitude": 50.1520},
    {"city_name": "Al Khobar", "city_name_ar": "الخبر", "region": "Eastern Region", "region_ar": "المنطقة الشرقية", "latitude": 26.2172, "longitude": 50.1971},
    {"city_name": "Dhahran", "city_name_ar": "الظهران", "region": "Eastern Region", "region_ar": "المنطقة الشرقية", "latitude": 26.2667, "longitude": 50.1522},
    {"city_name": "Ahsa", "city_name_ar": "الأحساء", "region": "Eastern Region", "region_ar": "المنطقة الشرقية", "latitude": 25.3833, "longitude": 49.6000},
    {"city_name": "Hafr Al Batin", "city_name_ar": "حفر الباطن", "region": "Eastern Region", "region_ar": "المنطقة الشرقية"},
    {"city_name": "Jubail", "city_name_ar": "الجبيل", "region": "Eastern Region", "region_ar": "المنطقة الشرقية", "latitude": 27.0047, "longitude": 49.6464},
    {"city_name": "Qatif", "city_name_ar": "القطيف", "region": "Eastern Region", "region_ar": "المنطقة الشرقية"},
    {"city_name": "Khafji", "city_name_ar": "الخفجي", "region": "Eastern Region", "region_ar": "المنطقة الشرقية"},
    {"city_name": "Ras Tanura", "city_name_ar": "رأس تنورة", "region": "Eastern Region", "region_ar": "المنطقة الشرقية"},

    # Northern Region (Tabuk)
    {"city_name": "Tabuk", "city_name_ar": "تبوك", "region": "Tabuk Region", "region_ar": "منطقة تبوك", "latitude": 28.3833, "longitude": 36.5667},
    {"city_name": "Tayma", "city_name_ar": "تيماء", "region": "Tabuk Region", "region_ar": "منطقة تبوك"},
    {"city_name": "Duba", "city_name_ar": "ضباء", "region": "Tabuk Region", "region_ar": "منطقة تبوك"},
    {"city_name": "Haql", "city_name_ar": "حقل", "region": "Tabuk Region", "region_ar": "منطقة تبوك"},

    # Northern Region (Northern Borders)
    {"city_name": "Arar", "city_name_ar": "عرعر", "region": "Northern Borders Region", "region_ar": "منطقة الحدود الشمالية"},
    {"city_name": "Rafha", "city_name_ar": "رفحاء", "region": "Northern Borders Region", "region_ar": "منطقة الحدود الشمالية"},
    {"city_name": "Turaif", "city_name_ar": "طريف", "region": "Northern Borders Region", "region_ar": "منطقة الحدود الشمالية"},

    # Northern Region (Al Jawf)
    {"city_name": "Sakaka", "city_name_ar": "سكاكا", "region": "Al Jawf Region", "region_ar": "منطقة الجوف"},
    {"city_name": "Qurayyat", "city_name_ar": "القريات", "region": "Al Jawf Region", "region_ar": "منطقة الجوف"},
    {"city_name": "Tabarjal", "city_name_ar": "طبرجل", "region": "Al Jawf Region", "region_ar": "منطقة الجوف"},

    # Southern Region (Asir)
    {"city_name": "Abha", "city_name_ar": "أبها", "region": "Asir Region", "region_ar": "منطقة عسير", "latitude": 18.2167, "longitude": 42.5000},
    {"city_name": "Khamis Mushayt", "city_name_ar": "خميس مشيط", "region": "Asir Region", "region_ar": "منطقة عسير"},
    {"city_name": "Muhayil", "city_name_ar": "محايل", "region": "Asir Region", "region_ar": "منطقة عسير"},
    {"city_name": "Bisha", "city_name_ar": "بيشة", "region": "Asir Region", "region_ar": "منطقة عسير"},
    {"city_name": "Sarat Abidah", "city_name_ar": "سراة عبيدة", "region": "Asir Region", "region_ar": "منطقة عسير"},

    # Southern Region (Jazan)
    {"city_name": "Jazan", "city_name_ar": "جازان", "region": "Jazan Region", "region_ar": "منطقة جازان", "latitude": 16.8892, "longitude": 42.5706},
    {"city_name": "Sabya", "city_name_ar": "صبياء", "region": "Jazan Region", "region_ar": "منطقة جازان"},
    {"city_name": "Abu Arish", "city_name_ar": "أبو عريش", "region": "Jazan Region", "region_ar": "منطقة جازان"},
    {"city_name": "Samtah", "city_name_ar": "صامطة", "region": "Jazan Region", "region_ar": "منطقة جازان"},
    {"city_name": "Farasan", "city_name_ar": "فرسان", "region": "Jazan Region", "region_ar": "منطقة جازان"},

    # Southern Region (Najran)
    {"city_name": "Najran", "city_name_ar": "نجران", "region": "Najran Region", "region_ar": "منطقة نجران", "latitude": 17.4917, "longitude": 44.1272},
    {"city_name": "Sharurah", "city_name_ar": "شرورة", "region": "Najran Region", "region_ar": "منطقة نجران"},
    {"city_name": "Habuna", "city_name_ar": "حبونا", "region": "Najran Region", "region_ar": "منطقة نجران"},

    # Southern Region (Al Bahah)
    {"city_name": "Al Bahah", "city_name_ar": "الباحة", "region": "Al Bahah Region", "region_ar": "منطقة الباحة"},
    {"city_name": "Baljurashi", "city_name_ar": "بلجرشي", "region": "Al Bahah Region", "region_ar": "منطقة الباحة"},
    {"city_name": "Al Mandaq", "city_name_ar": "المندق", "region": "Al Bahah Region", "region_ar": "منطقة الباحة"},

    # Ha'il
    {"city_name": "Ha'il", "city_name_ar": "حائل", "region": "Ha'il Region", "region_ar": "منطقة حائل", "latitude": 27.5167, "longitude": 41.6833},
    {"city_name": "Ba'qa", "city_name_ar": "بقعاء", "region": "Ha'il Region", "region_ar": "منطقة حائل"},

    # Qassim
    {"city_name": "Buraidah", "city_name_ar": "بريدة", "region": "Qassim Region", "region_ar": "منطقة القصيم", "latitude": 26.3333, "longitude": 43.9667},
    {"city_name": "Unaizah", "city_name_ar": "عنيزة", "region": "Qassim Region", "region_ar": "منطقة القصيم"},
    {"city_name": "Al Rass", "city_name_ar": "الرس", "region": "Qassim Region", "region_ar": "منطقة القصيم"},
    {"city_name": "Al Bukayriyah", "city_name_ar": "البكيرية", "region": "Qassim Region", "region_ar": "منطقة القصيم"},
    {"city_name": "Al Badayea", "city_name_ar": "البدائع", "region": "Qassim Region", "region_ar": "منطقة القصيم"},
]


def seed():
    """Insert KSA cities if missing."""
    if not frappe.db.exists("DocType", "KSA City"):
        return
    count = 0
    for c in KSA_CITIES:
        if not frappe.db.exists("KSA City", c["city_name"]):
            doc = frappe.get_doc({
                "doctype": "KSA City",
                **c,
            })
            doc.flags.ignore_permissions = True
            doc.insert()
            count += 1
    if count:
        frappe.db.commit()
