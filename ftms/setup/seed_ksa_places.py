from __future__ import annotations

import frappe


FEATURED_KSA_PLACES = [
    {"place_code": "KSA-MASJID-HARAM", "name_en": "Masjid al-Haram", "name_ar": "المسجد الحرام", "place_type": "Landmark", "region": "Makkah Region", "latitude": 21.4225, "longitude": 39.8262, "featured": 1},
    {"place_code": "KSA-MASJID-NABAWI", "name_en": "Prophet's Mosque", "name_ar": "المسجد النبوي", "place_type": "Landmark", "region": "Madinah Region", "latitude": 24.4672, "longitude": 39.6112, "featured": 1},
    {"place_code": "KSA-KINGDOM-TOWER", "name_en": "Kingdom Centre", "name_ar": "برج المملكة", "place_type": "Landmark", "region": "Riyadh Region", "latitude": 24.7111, "longitude": 46.6744, "featured": 1},
    {"place_code": "KSA-KAFD", "name_en": "King Abdullah Financial District", "name_ar": "مركز الملك عبدالله المالي", "place_type": "Business District", "region": "Riyadh Region", "latitude": 24.7670, "longitude": 46.6430, "featured": 1},
    {"place_code": "KSA-DIRIYAH", "name_en": "At-Turaif, Diriyah", "name_ar": "الطريف، الدرعية", "place_type": "Tourism", "region": "Riyadh Region", "latitude": 24.7333, "longitude": 46.5753, "featured": 1},
    {"place_code": "KSA-JEDDAH-CORNICHE", "name_en": "Jeddah Corniche", "name_ar": "كورنيش جدة", "place_type": "Tourism", "region": "Makkah Region", "latitude": 21.5433, "longitude": 39.1728, "featured": 1},
    {"place_code": "KSA-KING-ABDULAZIZ-AIRPORT", "name_en": "King Abdulaziz International Airport", "name_ar": "مطار الملك عبدالعزيز الدولي", "place_type": "Airport", "region": "Makkah Region", "latitude": 21.6796, "longitude": 39.1565, "featured": 1},
    {"place_code": "KSA-KING-KHALID-AIRPORT", "name_en": "King Khalid International Airport", "name_ar": "مطار الملك خالد الدولي", "place_type": "Airport", "region": "Riyadh Region", "latitude": 24.9578, "longitude": 46.6989, "featured": 1},
    {"place_code": "KSA-PRINCE-MOHAMMAD-AIRPORT", "name_en": "Prince Mohammad bin Abdulaziz International Airport", "name_ar": "مطار الأمير محمد بن عبدالعزيز الدولي", "place_type": "Airport", "region": "Madinah Region", "latitude": 24.5536, "longitude": 39.7050, "featured": 1},
    {"place_code": "KSA-KING-FAHD-AIRPORT", "name_en": "King Fahd International Airport", "name_ar": "مطار الملك فهد الدولي", "place_type": "Airport", "region": "Eastern Region", "latitude": 26.4712, "longitude": 49.7984, "featured": 1},
    {"place_code": "KSA-ALULA", "name_en": "AlUla", "name_ar": "العلا", "place_type": "Tourism", "region": "Madinah Region", "latitude": 26.6085, "longitude": 37.9232, "featured": 1},
    {"place_code": "KSA-HEGRA", "name_en": "Hegra (Al-Hijr)", "name_ar": "الحِجر", "place_type": "Tourism", "region": "Madinah Region", "latitude": 26.8206, "longitude": 37.9490, "featured": 1},
    {"place_code": "KSA-NEOM", "name_en": "NEOM", "name_ar": "نيوم", "place_type": "Tourism", "region": "Tabuk Region", "latitude": 27.9500, "longitude": 35.3000, "featured": 1},
    {"place_code": "KSA-THE-LINE", "name_en": "The Line", "name_ar": "ذا لاين", "place_type": "Tourism", "region": "Tabuk Region", "latitude": 28.0000, "longitude": 35.2000, "featured": 1},
    {"place_code": "KSA-RED-SEA", "name_en": "The Red Sea Project", "name_ar": "مشروع البحر الأحمر", "place_type": "Tourism", "region": "Tabuk Region", "latitude": 25.5500, "longitude": 36.7500, "featured": 1},
    {"place_code": "KSA-ITHRA", "name_en": "Ithra (King Abdulaziz Center for World Culture)", "name_ar": "إثراء", "place_type": "Landmark", "region": "Eastern Region", "latitude": 26.3436, "longitude": 50.1187, "featured": 1},
    {"place_code": "KSA-JUBAIL-INDUSTRIAL", "name_en": "Jubail Industrial City", "name_ar": "مدينة الجبيل الصناعية", "place_type": "Business District", "region": "Eastern Region", "latitude": 27.0047, "longitude": 49.6464, "featured": 1},
    {"place_code": "KSA-ABHA-HIGH-CITY", "name_en": "Abha High City", "name_ar": "المدينة العالية بأبها", "place_type": "Tourism", "region": "Asir Region", "latitude": 18.2167, "longitude": 42.5000, "featured": 1},
    {"place_code": "KSA-FARASAN", "name_en": "Farasan Islands", "name_ar": "جزر فرسان", "place_type": "Tourism", "region": "Jazan Region", "latitude": 16.7022, "longitude": 42.1186, "featured": 1},
]


def seed():
    if not frappe.db.exists("DocType", "KSA Place"):
        return
    for row in FEATURED_KSA_PLACES:
        if frappe.db.exists("KSA Place", row["place_code"]):
            continue
        frappe.get_doc({"doctype": "KSA Place", **row, "enabled": 1}).insert(ignore_permissions=True)
    frappe.db.commit()
