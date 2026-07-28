import frappe


def seed_vehicle_makes():
    makes = [
        {"make_name": "Hyundai", "make_name_ar": "هيونداي", "country_of_origin": "South Korea"},
        {"make_name": "Toyota", "make_name_ar": "تويوتا", "country_of_origin": "Japan"},
        {"make_name": "Kia", "make_name_ar": "كيا", "country_of_origin": "South Korea"},
        {"make_name": "Mercedes-Benz", "make_name_ar": "مرسيدس بنز", "country_of_origin": "Germany"},
        {"make_name": "Ford", "make_name_ar": "فورد", "country_of_origin": "USA"},
        {"make_name": "Chevrolet", "make_name_ar": "شيفروليه", "country_of_origin": "USA"},
        {"make_name": "Nissan", "make_name_ar": "نيسان", "country_of_origin": "Japan"},
        {"make_name": "Mitsubishi", "make_name_ar": "ميتسوبيشي", "country_of_origin": "Japan"},
        {"make_name": "Isuzu", "make_name_ar": "ايسوزو", "country_of_origin": "Japan"},
        {"make_name": "Hino", "make_name_ar": "هينو", "country_of_origin": "Japan"},
        {"make_name": "BMW", "make_name_ar": "بي إم دبليو", "country_of_origin": "Germany"},
        {"make_name": "Lexus", "make_name_ar": "لكزس", "country_of_origin": "Japan"},
        {"make_name": "GMC", "make_name_ar": "جي إم سي", "country_of_origin": "USA"},
        {"make_name": "Dongfeng", "make_name_ar": "دونغفنغ", "country_of_origin": "China"},
        {"make_name": "Foton", "make_name_ar": "فوتون", "country_of_origin": "China"},
        {"make_name": "JAC", "make_name_ar": "جاك", "country_of_origin": "China"},
        {"make_name": "Great Wall", "make_name_ar": "جريت وول", "country_of_origin": "China"},
        {"make_name": "Changan", "make_name_ar": "تشانجان", "country_of_origin": "China"},
        {"make_name": "Volkswagen", "make_name_ar": "فولكس فاجن", "country_of_origin": "Germany"},
        {"make_name": "Suzuki", "make_name_ar": "سوزوكي", "country_of_origin": "Japan"},
        {"make_name": "Mazda", "make_name_ar": "مازدا", "country_of_origin": "Japan"},
    ]
    for m in makes:
        if not frappe.db.exists("Vehicle Make", m["make_name"]):
            doc = frappe.get_doc({"doctype": "Vehicle Make", **m, "status": "Active", "is_active": 1})
            doc.insert(ignore_permissions=True)
            print(f"  + Make: {m['make_name']}")
        else:
            print(f"  = Make: {m['make_name']} (exists)")


def seed_vehicle_models():
    # (make, model, model_ar, type, category, seats)
    models = [
        # Hyundai
        ("Hyundai", "Staria", "ستاريا", "Minibus", "Minibus", 11),
        ("Hyundai", "H1", "إتش ون", "Minibus", "Minibus", 12),
        ("Hyundai", "Starex", "ستاريكس", "Minibus", "Minibus", 12),
        ("Hyundai", "Grand Starex", "جراند ستاريكس", "Minibus", "Minibus", 12),
        ("Hyundai", "Sonata", "سوناتا", "Sedan", "Sedan", 5),
        ("Hyundai", "Accent", "أكسنت", "Sedan", "Sedan", 5),
        ("Hyundai", "Elantra", "إلنترا", "Sedan", "Sedan", 5),
        ("Hyundai", "Santa Fe", "سانتا في", "SUV", "SUV", 7),
        ("Hyundai", "Tucson", "توسان", "SUV", "SUV", 5),
        ("Hyundai", "Azera", "أزيرا", "Sedan", "Sedan", 5),
        ("Hyundai", "Grandeur", "جرانديور", "Sedan", "Sedan", 5),
        ("Hyundai", "Porter", "بورتر", "Truck", "Truck", 3),
        ("Hyundai", "County", "كونتي", "Bus", "Bus", 28),
        # Toyota
        ("Toyota", "HiAce", "هايس", "Minibus", "Minibus", 12),
        ("Toyota", "Coaster", "كوستر", "Bus", "Bus", 24),
        ("Toyota", "Land Cruiser", "لاند كروزر", "SUV", "SUV", 7),
        ("Toyota", "Prado", "برادو", "SUV", "SUV", 7),
        ("Toyota", "Fortuner", "فورتشنر", "SUV", "SUV", 7),
        ("Toyota", "Camry", "كامري", "Sedan", "Sedan", 5),
        ("Toyota", "Corolla", "كورولا", "Sedan", "Sedan", 5),
        ("Toyota", "Yaris", "يارس", "Sedan", "Sedan", 5),
        ("Toyota", "Avalon", "أفالون", "Sedan", "Sedan", 5),
        ("Toyota", "Hilux", "هايلوكس", "Truck", "Truck", 5),
        ("Toyota", "Dyna", "داينا", "Truck", "Truck", 3),
        ("Toyota", "Sienna", "سيينا", "Minivan", "Minivan", 7),
        ("Toyota", "Alphard", "ألفارد", "Minivan", "Minivan", 7),
        # Kia
        ("Kia", "K5", "كي 5", "Sedan", "Sedan", 5),
        ("Kia", "K8", "كي 8", "Sedan", "Sedan", 5),
        ("Kia", "Sorento", "سورينتو", "SUV", "SUV", 7),
        ("Kia", "Sportage", "سبورتاج", "SUV", "SUV", 5),
        ("Kia", "Carnival", "كارنيفال", "Minivan", "Minivan", 7),
        ("Kia", "Pregio", "بريجيو", "Minibus", "Minibus", 12),
        ("Kia", "Grandbird", "جراندبيرد", "Bus", "Bus", 28),
        ("Kia", "Bongo", "بونجو", "Truck", "Truck", 3),
        ("Kia", "Cerato", "سيراتو", "Sedan", "Sedan", 5),
        ("Kia", "Soul", "سول", "Hatchback", "Hatchback", 5),
        # Nissan
        ("Nissan", "Sunny", "صني", "Sedan", "Sedan", 5),
        ("Nissan", "Altima", "ألتيما", "Sedan", "Sedan", 5),
        ("Nissan", "Patrol", "باترول", "SUV", "SUV", 7),
        ("Nissan", "X-Trail", "إكس تريل", "SUV", "SUV", 5),
        ("Nissan", "Urvan", "أورفان", "Minibus", "Minibus", 12),
        ("Nissan", "Navara", "نافارا", "Truck", "Truck", 5),
        ("Nissan", "Kicks", "كيكس", "SUV", "SUV", 5),
        ("Nissan", "Sentra", "سنترا", "Sedan", "Sedan", 5),
        ("Nissan", "Maxima", "ماكسيما", "Sedan", "Sedan", 5),
        # Mitsubishi
        ("Mitsubishi", "Pajero", "باجيرو", "SUV", "SUV", 7),
        ("Mitsubishi", "L300", "إل 300", "Minibus", "Minibus", 10),
        ("Mitsubishi", "Attrage", "أتراج", "Sedan", "Sedan", 5),
        ("Mitsubishi", "Montero Sport", "مونتيرو سبورت", "SUV", "SUV", 7),
        ("Mitsubishi", "Outlander", "أوتلاندر", "SUV", "SUV", 5),
        ("Mitsubishi", "Canter", "كانتر", "Truck", "Truck", 3),
        ("Mitsubishi", "Rosa", "روزا", "Bus", "Bus", 24),
        # Mercedes-Benz
        ("Mercedes-Benz", "Sprinter", "سبرينتر", "Minibus", "Minibus", 15),
        ("Mercedes-Benz", "Actros", "أكتروس", "Truck", "Truck", 2),
        ("Mercedes-Benz", "C-Class", "سي كلاس", "Sedan", "Sedan", 5),
        ("Mercedes-Benz", "E-Class", "إي كلاس", "Sedan", "Sedan", 5),
        ("Mercedes-Benz", "S-Class", "إس كلاس", "Sedan", "Sedan", 5),
        ("Mercedes-Benz", "GLE", "جي إل إي", "SUV", "SUV", 7),
        ("Mercedes-Benz", "Vito", "فيتو", "Minivan", "Minivan", 8),
        ("Mercedes-Benz", "Metris", "ميترس", "Minivan", "Minivan", 8),
        # Ford
        ("Ford", "Transit", "ترانزيت", "Minibus", "Minibus", 12),
        ("Ford", "Taurus", "تورس", "Sedan", "Sedan", 5),
        ("Ford", "Expedition", "إكسبيديشن", "SUV", "SUV", 7),
        ("Ford", "Explorer", "إكسبلورر", "SUV", "SUV", 7),
        ("Ford", "F-150", "إف 150", "Truck", "Truck", 5),
        ("Ford", "Econoline", "إيكونولاين", "Minibus", "Minibus", 12),
        # Chevrolet
        ("Chevrolet", "Caprice", "كابرس", "Sedan", "Sedan", 5),
        ("Chevrolet", "Malibu", "ماليبو", "Sedan", "Sedan", 5),
        ("Chevrolet", "Tahoe", "تاهو", "SUV", "SUV", 7),
        ("Chevrolet", "Suburban", "سابر ban", "SUV", "SUV", 8),
        ("Chevrolet", "Express", "إكسبريس", "Minibus", "Minibus", 12),
        ("Chevrolet", "Traverse", "ترافيرس", "SUV", "SUV", 7),
        ("Chevrolet", "Equinox", "إكوينوكس", "SUV", "SUV", 5),
        # Isuzu
        ("Isuzu", "N-Series", "إن سيريس", "Truck", "Truck", 3),
        ("Isuzu", "F-Series", "إف سيريس", "Truck", "Truck", 3),
        ("Isuzu", "D-Max", "دي ماكس", "Truck", "Truck", 5),
        ("Isuzu", "MU-X", "إم يو إكس", "SUV", "SUV", 7),
        # Hino
        ("Hino", "300 Series", "300 سيريس", "Truck", "Truck", 3),
        ("Hino", "500 Series", "500 سيريس", "Truck", "Truck", 3),
        ("Hino", "700 Series", "700 سيريس", "Truck", "Truck", 2),
        ("Hino", "Poncho", "بونشو", "Bus", "Bus", 24),
        ("Hino", "Rainbow", "رينبو", "Bus", "Bus", 28),
        ("Hino", "RN", "آر إن", "Bus", "Bus", 24),
        # BMW
        ("BMW", "3 Series", "الفئة الثالثة", "Sedan", "Sedan", 5),
        ("BMW", "5 Series", "الفئة الخامسة", "Sedan", "Sedan", 5),
        ("BMW", "7 Series", "الفئة السابعة", "Sedan", "Sedan", 5),
        ("BMW", "X3", "إكس 3", "SUV", "SUV", 5),
        ("BMW", "X5", "إكس 5", "SUV", "SUV", 7),
        ("BMW", "X7", "إكس 7", "SUV", "SUV", 7),
        # Lexus
        ("Lexus", "ES", "إي إس", "Sedan", "Sedan", 5),
        ("Lexus", "LS", "إل إس", "Sedan", "Sedan", 5),
        ("Lexus", "RX", "آر إكس", "SUV", "SUV", 5),
        ("Lexus", "LX", "إل إكس", "SUV", "SUV", 7),
        ("Lexus", "LM", "إل إم", "Minivan", "Minivan", 7),
        # GMC
        ("GMC", "Yukon", "يوكن", "SUV", "SUV", 7),
        ("GMC", "Sierra", "سييرا", "Truck", "Truck", 5),
        ("GMC", "Savana", "سافانا", "Minibus", "Minibus", 12),
        # Dongfeng
        ("Dongfeng", "Captain", "كابتن", "Truck", "Truck", 3),
        ("Dongfeng", "Rich", "ريتش", "Minibus", "Minibus", 10),
        # Foton
        ("Foton", "Auman", "أومان", "Truck", "Truck", 3),
        ("Foton", "View", "فيو", "Truck", "Truck", 3),
        ("Foton", "Toano", "توانو", "Minibus", "Minibus", 14),
        # JAC
        ("JAC", "Sunray", "صن راي", "Minibus", "Minibus", 12),
        ("JAC", "N-Series", "إن سيريس", "Truck", "Truck", 3),
        ("JAC", "T6", "تي 6", "Truck", "Truck", 5),
        # Great Wall
        ("Great Wall", "Haval H6", "هافال إتش 6", "SUV", "SUV", 5),
        ("Great Wall", "Haval H9", "هافال إتش 9", "SUV", "SUV", 7),
        ("Great Wall", "Poer", "بوير", "Truck", "Truck", 5),
        # Volkswagen
        ("Volkswagen", "Crafter", "كرافتر", "Minibus", "Minibus", 12),
        ("Volkswagen", "Transporter", "ترانسبورتر", "Minivan", "Minivan", 8),
        ("Volkswagen", "Passat", "باسات", "Sedan", "Sedan", 5),
        ("Volkswagen", "Tiguan", "تيجوان", "SUV", "SUV", 5),
        ("Volkswagen", "Teramont", "تيرامونت", "SUV", "SUV", 7),
        # Suzuki
        ("Suzuki", "Ciaz", "سياز", "Sedan", "Sedan", 5),
        ("Suzuki", "Vitara", "فيتارا", "SUV", "SUV", 5),
        ("Suzuki", "Carry", "كيري", "Truck", "Truck", 2),
        ("Suzuki", "Ertiga", "إرتيجا", "Minivan", "Minivan", 7),
        ("Suzuki", "APV", "إيه بي في", "Minivan", "Minivan", 7),
        # Mazda
        ("Mazda", "CX-5", "سي إكس 5", "SUV", "SUV", 5),
        ("Mazda", "CX-9", "سي إكس 9", "SUV", "SUV", 7),
        ("Mazda", "Mazda 3", "مازدا 3", "Sedan", "Sedan", 5),
        ("Mazda", "Mazda 6", "مازدا 6", "Sedan", "Sedan", 5),
        ("Mazda", "BT-50", "بي تي 50", "Truck", "Truck", 5),
        # Changan
        ("Changan", "CS35", "سي إس 35", "SUV", "SUV", 5),
        ("Changan", "CS75", "سي إس 75", "SUV", "SUV", 5),
        ("Changan", "CS95", "سي إس 95", "SUV", "SUV", 7),
        ("Changan", "Eado", "إيادو", "Sedan", "Sedan", 5),
        ("Changan", "Star", "ستار", "Minibus", "Minibus", 8),
        ("Changan", "Honor", "شرف", "Truck", "Truck", 3),
    ]

    make_obj = frappe.db.get_value("Vehicle Make", {}, "name")
    if not make_obj:
        print("  ! No Vehicle Makes found — run seed_vehicle_makes() first")

    for make, model, model_ar, vtype, vcat, seats in models:
        if not frappe.db.exists("Vehicle Make", make):
            continue
        name = f"{make} {model}"
        if not frappe.db.exists("Vehicle Model", name):
            doc = frappe.get_doc({
                "doctype": "Vehicle Model",
                "model_name": name,
                "model_name_ar": model_ar,
                "vehicle_make": make,
                "vehicle_type": vtype,
                "vehicle_category": vcat,
                "seat_capacity": seats,
                "status": "Active",
                "is_active": 1,
            })
            doc.insert(ignore_permissions=True)
            print(f"  + Model: {name}")
        else:
            print(f"  = Model: {name} (exists)")


def run():
    print("=== Seeding Vehicle Makes ===")
    seed_vehicle_makes()
    print("\n=== Seeding Vehicle Models ===")
    seed_vehicle_models()
    frappe.db.commit()
    print("\n✅ Vehicle seeding complete")


if __name__ == "__main__":
    run()
