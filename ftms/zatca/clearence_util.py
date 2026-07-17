import base64
import io
import json
import random
import time
import uuid
from datetime import date, datetime, timedelta

import frappe
import qrcode
import requests
from frappe import _
from frappe.utils import get_datetime
from requests.auth import HTTPBasicAuth

from ftms.zatca.common_util import (
    generate_invoice_hash,
    get_buyer_information,
    get_seller_information,
)
from ftms.zatca.utils import (
    get_previous_invoice_counter,
    get_previous_invoice_hash,
    get_prod_csid,
    time_formatter,
)

def generate_einvoice(doc, submit_now=True, skip_success_message=False):
    company = frappe.get_doc("Transportation Company", doc.company)
    is_test = doc.get("is_zatca_test") or doc.get("custom_is_zatca_test")
    zatca_enabled = company.get("enable_zatca_e_invoicing")
    if not zatca_enabled and not is_test:
        return
    company_country = company.get("country")
    if company_country and company_country != "Saudi Arabia":
        return
    if zatca_enabled and company.get("zatca_phase") != "ZATCA Phase 2":
        return

    config = _get_config(company, doc)
    customer_name = doc.get("customer")
    customer_type = "Individual"
    if customer_name and frappe.db.exists("Customer", customer_name):
        customer = frappe.get_doc("Customer", customer_name)
        customer_type = customer.customer_type

    invoice_data = _prepare_invoice_data(doc, config, customer_type)
    payload = {
        "invoiceHash": invoice_data["invoice_hash"],
        "uuid": invoice_data["uuid"],
        "invoice": invoice_data["invoice_base64"],
    }

    if customer_type == "Individual" and not submit_now:
        _set_field(doc, "zatca_submit_status", "PENDING")
        return

    try:
        if customer_type == "Company":
            response, zatca_time = _submit_clearance_request(config, payload)
            zatca_status_field = "clearanceStatus"
        elif customer_type == "Individual":
            response, zatca_time = _submit_reporting_request(config, payload)
            zatca_status_field = "reportingStatus"
        else:
            return
    except requests.exceptions.RequestException as e:
        frappe.throw("Error submitting to ZATCA: " + str(e))

    _save_transaction(doc, invoice_data, payload, response, config)
    _handle_response(doc, response, invoice_data, payload, zatca_status_field)

def _get_config(company, doc):
    is_test = doc.get("is_zatca_test") or doc.get("custom_is_zatca_test")
    compliance = doc.get("compliance_csid") or doc.get("custom_compliance")
    if is_test:
        csid = frappe.get_doc("Compliance CSID", compliance)
        compliance_csid = csid
    else:
        csid = frappe.get_doc("Production CSID", company.production_csid)
        compliance_csid = frappe.get_doc("Compliance CSID", csid.compliance_csid)
    csr_settings = frappe.get_doc("Zatca CSR Settings", compliance_csid.csr_settings)
    zatca_environment = frappe.get_doc("ZATCA Environment", csr_settings.zatca_environment)
    return {
        "production_csid": csid if not (doc.get("is_zatca_test") or doc.get("custom_is_zatca_test")) else None,
        "compliance_csid": compliance_csid,
        "csr_settings": csr_settings,
        "zatca_environment": zatca_environment,
        "company": company,
    }

def _prepare_invoice_data(doc, config, customer_type):
    invoice_type = "0100000" if customer_type == "Company" else "0200000"
    seller = get_seller_information(config["csr_settings"])
    customer_name = doc.get("customer")
    buyer = get_buyer_information(customer_name) if customer_name else {"organizationName": "Walk-in Customer"}
    previous_counter = get_previous_invoice_counter(config["production_csid"].name) if config["production_csid"] else random.randint(1, 20)
    previous_hash = get_previous_invoice_hash(config["production_csid"].name) if config["production_csid"] else generate_invoice_hash()
    invoice_counter = previous_counter + 1
    invoice_uuid = str(uuid.uuid4())
    posting_date = doc.get("posting_date") or doc.get("invoice_date")
    posting_time = doc.get("posting_time") or "12:00:00"
    invoice_date = posting_date.strftime("%Y-%m-%d") if isinstance(posting_date, date) else datetime.strptime(str(posting_date)[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    invoice_time = time_formatter(posting_time)
    return {
        "customer_type": customer_type,
        "invoice_type": invoice_type,
        "seller": seller,
        "buyer": buyer,
        "invoice_counter": invoice_counter,
        "previous_hash": previous_hash,
        "uuid": invoice_uuid,
        "invoice_date": invoice_date,
        "invoice_time": invoice_time,
        "invoice_hash": generate_invoice_hash(),  # placeholder - real hash from signed XML
        "invoice_base64": "",  # placeholder - real base64 from signed XML
    }

def _submit_clearance_request(config, payload):
    start = time.time()
    env = config["zatca_environment"]
    csid = config["compliance_csid"] if not config.get("production_csid") else config["production_csid"]
    resp = requests.post(
        env.invoice_clearance_api,
        headers=_get_headers(),
        auth=HTTPBasicAuth(csid.binary_security_token, csid.secret),
        json=payload,
        timeout=30,
    )
    return resp, {"duration": time.time() - start}

def _submit_reporting_request(config, payload):
    start = time.time()
    env = config["zatca_environment"]
    csid = config["compliance_csid"] if not config.get("production_csid") else config["production_csid"]
    resp = requests.post(
        env.invoice_reporting_api,
        headers=_get_headers(),
        auth=HTTPBasicAuth(csid.binary_security_token, csid.secret),
        json=payload,
        timeout=30,
    )
    return resp, {"duration": time.time() - start}

def _get_headers():
    return {
        "accept": "application/json",
        "Accept-Language": "en",
        "Clearance-Status": "1",
        "Accept-Version": "V2",
        "Content-Type": "application/json",
    }

def _save_transaction(doc, invoice_data, payload, response, config):
    response_data = response.json()
    txn = frappe.get_doc({
        "doctype": "Zatca Transactions",
        "invoice_id": doc.name,
        "invoice_uuid": invoice_data["uuid"],
        "invoice_icv": invoice_data["invoice_counter"],
        "invoice_hash": payload["invoiceHash"],
        "previous_invoice_hash": invoice_data["previous_hash"],
        "egs_serial_number": config["csr_settings"].csrserialnumber,
        "production_csid": config["production_csid"].name if config["production_csid"] else "",
        "request_body": str(payload),
        "response_code": response.status_code,
        "response_body": json.dumps(response_data) if isinstance(response_data, dict) else str(response_data),
        "transaction_time": frappe.utils.now_datetime(),
    })
    txn.insert(ignore_permissions=True)

def _handle_response(doc, response, invoice_data, payload, zatca_status):
    response_json = response.json()
    status = response_json.get(zatca_status)
    if response.status_code in [200, 202]:
        _handle_success(doc, response_json, invoice_data, payload, status)
    elif response.status_code in [400, 401, 500]:
        _handle_error(doc, status or "FAILED", json.dumps(response_json))
        if response.status_code == 401:
            frappe.throw("ZATCA: Invalid Credentials")
        elif response.status_code == 500:
            frappe.throw("ZATCA: Internal Server Error")
    else:
        _handle_error(doc, "FAILED", json.dumps(response_json))

def _handle_success(doc, response_json, invoice_data, payload, status):
    _set_field(doc, "invoice_type", invoice_data["invoice_type"])
    _set_field(doc, "invoice_hash", payload.get("invoiceHash"))
    _set_field(doc, "invoice_unique_identifier", invoice_data["uuid"])
    _set_field(doc, "invoice_icv", invoice_data["invoice_counter"])
    _set_field(doc, "zatca_submit_status", status)
    _set_field(doc, "zatca_submit_time", frappe.utils.now_datetime())
    _set_field(doc, "seller_name", invoice_data["seller"].get("organizationName"))
    _set_field(doc, "seller_vat", invoice_data["seller"].get("vatNumber"))
    _set_field(doc, "buyer_name", invoice_data["buyer"].get("organizationName"))
    _set_field(doc, "buyer_vat", invoice_data["buyer"].get("vatNumber"))
    cleared_invoice_xml = _get_cleared_invoice(response_json, payload, invoice_data["customer_type"])
    _save_xml(doc, cleared_invoice_xml)
    _save_qr(doc, cleared_invoice_xml)
    doc.save(ignore_permissions=True)

def _handle_error(doc, status, validation_results):
    _set_field(doc, "zatca_submit_status", status)
    _set_field(doc, "validation_results", validation_results)
    doc.save(ignore_permissions=True)

def _set_field(doc, fieldname, value):
    if hasattr(doc, fieldname) or fieldname in doc.as_dict():
        doc.set(fieldname, value)
    else:
        prefixed = "custom_" + fieldname
        if hasattr(doc, prefixed) or prefixed in doc.as_dict():
            doc.set(prefixed, value)

def _get_cleared_invoice(response_json, payload, customer_type):
    if customer_type == "Company":
        return base64.b64decode(response_json.get("clearedInvoice", "")).decode("utf-8") if response_json.get("clearedInvoice") else ""
    elif customer_type == "Individual":
        return base64.b64decode(payload.get("invoice", "")).decode("utf-8") if payload.get("invoice") else ""
    return ""

def _save_xml(doc, xml_content):
    if not xml_content:
        return
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": doc.name + ".xml",
        "content": xml_content,
        "is_private": False,
    })
    file_doc.insert()
    _set_field(doc, "invoice_xml", file_doc.file_url)

def _save_qr(doc, cleared_invoice_xml):
    if not cleared_invoice_xml:
        return
    import lxml.etree as etree
    namespaces = {
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    xml_tree = etree.fromstring(cleared_invoice_xml.encode("utf-8"))
    qr_code_data = None
    for doc_ref in xml_tree.findall(".//cac:AdditionalDocumentReference", namespaces):
        id_el = doc_ref.find("./cbc:ID", namespaces)
        if id_el is not None and id_el.text == "QR":
            embedded = doc_ref.find("./cac:Attachment/cbc:EmbeddedDocumentBinaryObject", namespaces)
            if embedded is not None:
                qr_code_data = embedded.text
                break
    if qr_code_data:
        try:
            qr_code_text = base64.b64decode(qr_code_data).decode("utf-8")
        except Exception:
            qr_code_text = qr_code_data
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_code_text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="PNG")
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": doc.name + ".png",
            "content": img_byte_arr.getvalue(),
            "is_private": False,
        })
        file_doc.insert()
        _set_field(doc, "invoice_qr_code", file_doc.file_url)

def _get_compliance_type(doc, customer_type):
    is_return = doc.get("is_return") or False
    is_debit = doc.get("is_debit_note") or False
    if customer_type == "Individual" and not is_return and not is_debit:
        return "1"
    elif customer_type == "Company" and not is_return and not is_debit:
        return "2"
    elif customer_type == "Individual" and is_return:
        return "3"
    elif customer_type == "Company" and is_return:
        return "4"
    elif customer_type == "Individual" and is_debit:
        return "5"
    elif customer_type == "Company" and is_debit:
        return "6"
    return "0"

def generate_einvoice_on_submit(doc, method=None):
    generate_einvoice(doc, submit_now=True)

@frappe.whitelist()
def resend_einvoice(doc):
    if isinstance(doc, str):
        doc = json.loads(doc)
    if isinstance(doc, dict):
        doc = frappe.get_doc(doc)
    generate_einvoice(doc)

@frappe.whitelist()
def bulk_resend_einvoices(invoice_names):
    if isinstance(invoice_names, str):
        invoice_names = json.loads(invoice_names)
    if not invoice_names:
        frappe.throw("Select at least one invoice")
    success = []
    failed = []
    skipped = []
    frappe.flags.zatca_bulk_report = True
    try:
        for name in invoice_names:
            try:
                doc = frappe.get_doc("Sales Invoice", name)
            except frappe.DoesNotExistError:
                failed.append({"name": name, "message": "Not found"})
                continue
            if doc.docstatus != 1:
                skipped.append({"name": name, "message": "Not submitted"})
                continue
            status = doc.get("zatca_submit_status") or doc.get("custom_zatca_submit_status")
            if status in ("REPORTED", "CLEARED"):
                skipped.append({"name": name, "message": f"Already {status}"})
                continue
            try:
                generate_einvoice(doc, skip_success_message=True)
                doc.reload()
                final_status = doc.get("zatca_submit_status") or doc.get("custom_zatca_submit_status")
                if final_status in ("REPORTED", "CLEARED"):
                    success.append(name)
                else:
                    skipped.append({"name": name, "message": "Not REPORTED/CLEARED"})
            except Exception as e:
                failed.append({"name": name, "message": str(e)})
    finally:
        frappe.flags.zatca_bulk_report = False
    return {"success": success, "failed": failed, "skipped": skipped}
