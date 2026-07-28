import re
import json
import os
import frappe


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

DOCUMENT_TYPES = [
    "National ID",
    "Iqama",
    "Passport",
    "GCC ID",
    "Residency",
    "Visa",
    "Driver License",
    "Other",
]


ID_FORMATS = {
    "SA": {
        "country": "Saudi Arabia",
        "alpha_2": "SA",
        "documents": {
            "National ID": {
                "label": "National ID ( بطاقة الأحوال )",
                "pattern": r"^[12]\d{9}$",
                "placeholder": "1234567890",
                "length": 10,
                "description": "10 digits, starts with 1 (Saudi male) or 2 (Saudi female)",
            },
            "Iqama": {
                "label": "Iqama ( إقامة )",
                "pattern": r"^[2]\d{9}$",
                "placeholder": "2123456789",
                "length": 10,
                "description": "10 digits, starts with 2",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
                "description": "1 letter followed by 8 digits",
            },
            "GCC ID": {
                "label": "GCC National ID",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
                "description": "10-15 digits",
            },
            "Residency": {
                "label": "Residency Permit",
                "pattern": r"^\d{10}$",
                "placeholder": "1234567890",
                "length": 10,
                "description": "10 digits",
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
                "description": "8-12 digits",
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{10}$",
                "placeholder": "1234567890",
                "length": 10,
                "description": "10 digits",
            },
        },
    },
    "AE": {
        "country": "United Arab Emirates",
        "alpha_2": "AE",
        "documents": {
            "National ID": {
                "label": "Emirates ID",
                "pattern": r"^\d{3}-\d{4}-\d{7}-\d{1}$",
                "placeholder": "784-1990-1234567-1",
                "length": 18,
                "description": "Format: 784-YYYY-NNNNNNN-C",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
                "description": "1 letter followed by 8 digits",
            },
            "GCC ID": {
                "label": "GCC National ID",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Residency": {
                "label": "Residency / Visa",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,15}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{8,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
        },
    },
    "PK": {
        "country": "Pakistan",
        "alpha_2": "PK",
        "documents": {
            "National ID": {
                "label": "CNIC (Computerized National ID)",
                "pattern": r"^\d{5}-\d{7}-\d{1}$",
                "placeholder": "12345-1234567-1",
                "length": 15,
                "description": "Format: XXXXX-XXXXXXX-X",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]{2}\d{7}$",
                "placeholder": "AB1234567",
                "length": 9,
                "description": "2 letters followed by 7 digits",
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{5,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
        },
    },
    "IN": {
        "country": "India",
        "alpha_2": "IN",
        "documents": {
            "National ID": {
                "label": "Aadhaar",
                "pattern": r"^\d{12}$",
                "placeholder": "123456789012",
                "length": 12,
                "description": "12 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{7}$",
                "placeholder": "A1234567",
                "length": 8,
                "description": "1 letter followed by 7 digits",
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^[A-Za-z]{2}\d{2}\d{4}\d{7}$",
                "placeholder": "HR0612345678901",
                "length": 16,
                "description": "State code + RTO + year + number",
            },
        },
    },
    "GB": {
        "country": "United Kingdom",
        "alpha_2": "GB",
        "documents": {
            "National ID": {
                "label": "National Insurance Number",
                "pattern": r"^[A-Za-z]{2}\d{6}[A-Za-z]$",
                "placeholder": "AB123456C",
                "length": 9,
                "description": "2 letters, 6 digits, 1 letter",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^\d{9}$",
                "placeholder": "123456789",
                "length": 9,
                "description": "9 digits",
            },
            "Visa": {
                "label": "BRP / Visa",
                "pattern": r"^[A-Za-z0-9]{8,12}$",
                "placeholder": "AB123456C",
                "length": 9,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^[A-Za-z]{5}\d{1}[A-Za-z]{2}\d{6}[A-Za-z0-9]{2,5}$",
                "placeholder": "MORGA657054SM9IJ",
                "length": 16,
            },
        },
    },
    "US": {
        "country": "United States",
        "alpha_2": "US",
        "documents": {
            "National ID": {
                "label": "SSN",
                "pattern": r"^\d{3}-\d{2}-\d{4}$",
                "placeholder": "123-45-6789",
                "length": 11,
                "description": "Format: XXX-XX-XXXX",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^\d{9}$",
                "placeholder": "123456789",
                "length": 9,
                "description": "9 digits",
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^[A-Za-z0-9]{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^[A-Za-z0-9]{6,16}$",
                "placeholder": "D1234567",
                "length": 8,
                "description": "Varies by state",
            },
        },
    },
    "EG": {
        "country": "Egypt",
        "alpha_2": "EG",
        "documents": {
            "National ID": {
                "label": "National ID (رقم قومي)",
                "pattern": r"^\d{14}$",
                "placeholder": "12345678901234",
                "length": 14,
                "description": "14 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
                "description": "1 letter followed by 8 digits",
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{9,14}$",
                "placeholder": "1234567890",
                "length": 10,
            },
        },
    },
    "BH": {
        "country": "Bahrain",
        "alpha_2": "BH",
        "documents": {
            "National ID": {
                "label": "CPR (Central Population Register)",
                "pattern": r"^\d{9}$",
                "placeholder": "123456789",
                "length": 9,
                "description": "9 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
            "GCC ID": {
                "label": "GCC National ID",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Residency": {
                "label": "Residency Permit",
                "pattern": r"^\d{9}$",
                "placeholder": "123456789",
                "length": 9,
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{9}$",
                "placeholder": "123456789",
                "length": 9,
            },
        },
    },
    "QA": {
        "country": "Qatar",
        "alpha_2": "QA",
        "documents": {
            "National ID": {
                "label": "Qatar ID (QID)",
                "pattern": r"^\d{11}$",
                "placeholder": "12345678901",
                "length": 11,
                "description": "11 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
            "GCC ID": {
                "label": "GCC National ID",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Residency": {
                "label": "Residency Permit (RP)",
                "pattern": r"^\d{11}$",
                "placeholder": "12345678901",
                "length": 11,
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{11}$",
                "placeholder": "12345678901",
                "length": 11,
            },
        },
    },
    "KW": {
        "country": "Kuwait",
        "alpha_2": "KW",
        "documents": {
            "National ID": {
                "label": "Civil ID",
                "pattern": r"^\d{12}$",
                "placeholder": "123456789012",
                "length": 12,
                "description": "12 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
            "GCC ID": {
                "label": "GCC National ID",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Residency": {
                "label": "Residency Permit",
                "pattern": r"^\d{12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
        },
    },
    "OM": {
        "country": "Oman",
        "alpha_2": "OM",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{10}$",
                "placeholder": "1234567890",
                "length": 10,
                "description": "10 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
            "GCC ID": {
                "label": "GCC National ID",
                "pattern": r"^\d{10,15}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Residency": {
                "label": "Residency Permit",
                "pattern": r"^\d{10}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^\d{8,12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^\d{10}$",
                "placeholder": "1234567890",
                "length": 10,
            },
        },
    },
    "YE": {
        "country": "Yemen",
        "alpha_2": "YE",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{9,12}$",
                "placeholder": "123456789",
                "length": 9,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "JO": {
        "country": "Jordan",
        "alpha_2": "JO",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{10}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "LB": {
        "country": "Lebanon",
        "alpha_2": "LB",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{8,12}$",
                "placeholder": "12345678",
                "length": 8,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]{2}\d{7}$",
                "placeholder": "AB1234567",
                "length": 9,
            },
        },
    },
    "IQ": {
        "country": "Iraq",
        "alpha_2": "IQ",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{8,16}$",
                "placeholder": "12345678",
                "length": 8,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "SY": {
        "country": "Syria",
        "alpha_2": "SY",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{11}$",
                "placeholder": "12345678901",
                "length": 11,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "SD": {
        "country": "Sudan",
        "alpha_2": "SD",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{8,16}$",
                "placeholder": "12345678",
                "length": 8,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "TR": {
        "country": "Turkey",
        "alpha_2": "TR",
        "documents": {
            "National ID": {
                "label": "TC Kimlik No",
                "pattern": r"^\d{11}$",
                "placeholder": "12345678901",
                "length": 11,
                "description": "11 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "U12345678",
                "length": 9,
            },
        },
    },
    "PH": {
        "country": "Philippines",
        "alpha_2": "PH",
        "documents": {
            "National ID": {
                "label": "PhilSys National ID",
                "pattern": r"^\d{12}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z0-9]{11}$",
                "placeholder": "AB123456789",
                "length": 11,
            },
        },
    },
    "BD": {
        "country": "Bangladesh",
        "alpha_2": "BD",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{10,17}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "LK": {
        "country": "Sri Lanka",
        "alpha_2": "LK",
        "documents": {
            "National ID": {
                "label": "NIC",
                "pattern": r"^\d{9}[VXvx]|\d{12}$",
                "placeholder": "123456789V",
                "length": 10,
                "description": "9 digits + letter, or 12 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "NP": {
        "country": "Nepal",
        "alpha_2": "NP",
        "documents": {
            "National ID": {
                "label": "National ID",
                "pattern": r"^\d{8,16}$",
                "placeholder": "12345678",
                "length": 8,
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^\d{8}$",
                "placeholder": "12345678",
                "length": 8,
            },
        },
    },
    "ID": {
        "country": "Indonesia",
        "alpha_2": "ID",
        "documents": {
            "National ID": {
                "label": "NIK (KTP)",
                "pattern": r"^\d{16}$",
                "placeholder": "1234567890123456",
                "length": 16,
                "description": "16 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "MY": {
        "country": "Malaysia",
        "alpha_2": "MY",
        "documents": {
            "National ID": {
                "label": "MyKad (NRIC)",
                "pattern": r"^\d{6}-\d{2}-\d{4}$",
                "placeholder": "881203-01-1234",
                "length": 14,
                "description": "Format: YYMMDD-PP-NNNN",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "SG": {
        "country": "Singapore",
        "alpha_2": "SG",
        "documents": {
            "National ID": {
                "label": "NRIC",
                "pattern": r"^[STFGstfg]\d{7}[A-Za-z]$",
                "placeholder": "S1234567A",
                "length": 9,
                "description": "1 letter + 7 digits + 1 letter",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z]\d{8}$",
                "placeholder": "A12345678",
                "length": 9,
            },
        },
    },
    "CN": {
        "country": "China",
        "alpha_2": "CN",
        "documents": {
            "National ID": {
                "label": "身份证 (Resident ID)",
                "pattern": r"^\d{18}$",
                "placeholder": "123456789012345678",
                "length": 18,
                "description": "18 digits",
            },
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z0-9]{9}$",
                "placeholder": "E12345678",
                "length": 9,
            },
        },
    },
    "DEFAULT": {
        "country": "",
        "alpha_2": "",
        "documents": {
            "Passport": {
                "label": "Passport",
                "pattern": r"^[A-Za-z0-9]{5,20}$",
                "placeholder": "A12345678",
                "length": 9,
                "description": "5-20 alphanumeric characters",
            },
            "National ID": {
                "label": "National ID",
                "pattern": r"^[A-Za-z0-9]{4,25}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Visa": {
                "label": "Visa Number",
                "pattern": r"^[A-Za-z0-9]{4,20}$",
                "placeholder": "123456789012",
                "length": 12,
            },
            "Residency": {
                "label": "Residency Permit",
                "pattern": r"^[A-Za-z0-9]{4,20}$",
                "placeholder": "1234567890",
                "length": 10,
            },
            "Driver License": {
                "label": "Driver License",
                "pattern": r"^[A-Za-z0-9]{4,20}$",
                "placeholder": "1234567890",
                "length": 10,
            },
        },
    },
}


def _load_json(filename, default=None):
    cache_key = f"ftms_country_{filename}"
    cached = frappe.cache().get_value(cache_key)
    if cached is not None:
        return cached

    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = default if default is not None else {}

    frappe.cache().set_value(cache_key, data)
    return data


def load_countries():
    return _load_json("countries.json", {})


def _norm(value):
    return (value or "").strip().lower()


def find_country(alpha_2=None, country_name=None):
    countries = load_countries()
    if alpha_2:
        return countries.get(alpha_2.upper(), {})

    name = _norm(country_name)
    if not name:
        return {}

    for code, record in countries.items():
        names = [
            record.get("country_name"),
            record.get("official_name"),
            record.get("native"),
            code,
        ]
        if name in {_norm(n) for n in names if n}:
            return record
    return {}


def get_id_format(alpha_2, doc_type=None):
    alpha_2 = (alpha_2 or "").upper()
    country_format = ID_FORMATS.get(alpha_2, ID_FORMATS["DEFAULT"])
    documents = country_format.get("documents", {})

    if doc_type:
        fmt = documents.get(doc_type, documents.get("Passport"))
        if fmt:
            return {**fmt, "country": country_format["country"], "alpha_2": alpha_2}
        fallback = ID_FORMATS["DEFAULT"]["documents"].get(doc_type) or ID_FORMATS["DEFAULT"]["documents"].get("Passport")
        return {**fallback, "country": country_format["country"], "alpha_2": alpha_2}

    return {
        "country": country_format["country"],
        "alpha_2": alpha_2,
        "documents": {k: v for k, v in documents.items()},
    }


def validate_document(alpha_2, doc_type, value):
    if not value:
        return {"valid": False, "error": "No value provided", "format": None}

    fmt = get_id_format(alpha_2, doc_type)
    pattern = fmt.get("pattern")

    if pattern:
        valid = bool(re.match(pattern, value.strip()))
    else:
        valid = bool(value.strip())

    return {
        "valid": valid,
        "format": fmt,
        "error": None if valid else f"Invalid format. Expected: {fmt.get('description', fmt.get('label', ''))}",
    }


@frappe.whitelist(allow_guest=True)
def get_country_list():
    countries = load_countries()
    out = []
    for code, record in sorted(countries.items(), key=lambda x: x[1].get("country_name", "")):
        out.append({
            "alpha_2": code,
            "alpha_3": record.get("alpha_3"),
            "country_name": record.get("country_name"),
            "phone_code": record.get("phone_code"),
            "currency": record.get("currency"),
            "currency_symbol": record.get("currency_symbol"),
        })
    return out


@frappe.whitelist(allow_guest=True)
def get_document_types():
    return DOCUMENT_TYPES


@frappe.whitelist(allow_guest=True)
def get_document_format(alpha_2=None, country_name=None, doc_type=None):
    if alpha_2:
        country = find_country(alpha_2=alpha_2)
    elif country_name:
        country = find_country(country_name=country_name)
        alpha_2 = country.get("alpha_2")
    else:
        return {"error": "alpha_2 or country_name required"}

    return get_id_format(alpha_2, doc_type=doc_type)


@frappe.whitelist(allow_guest=True)
def validate_document_number(alpha_2=None, country_name=None, doc_type=None, value=None):
    if not value:
        return {"valid": False, "error": "Document number is required"}

    if alpha_2:
        pass
    elif country_name:
        country = find_country(country_name=country_name)
        alpha_2 = country.get("alpha_2")
    else:
        return {"valid": False, "error": "Country is required"}

    return validate_document(alpha_2, doc_type, value)


@frappe.whitelist(allow_guest=True)
def get_country_info(alpha_2):
    country = find_country(alpha_2=alpha_2)
    if not country:
        return {}
    return {
        "country_name": country.get("country_name"),
        "alpha_2": country.get("alpha_2"),
        "alpha_3": country.get("alpha_3"),
        "phone_code": country.get("phone_code"),
        "currency": country.get("currency"),
        "currency_symbol": country.get("currency_symbol"),
        "language": country.get("language"),
        "capital": country.get("capital"),
        "region": country.get("region"),
        "timezones": country.get("timezones"),
        "native": country.get("native"),
        "id_format": get_id_format(alpha_2, doc_type="National ID"),
    }
