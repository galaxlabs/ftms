from __future__ import annotations

import base64
import hashlib
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import frappe
from frappe import _


def _get_last_pih(company):
	last = frappe.db.get_value(
		"Zatca Transactions",
		{"company": company, "status": "Submitted"},
		"invoice_hash",
		order_by="transaction_date desc",
	)
	return last or hashlib.sha256(b"0").hexdigest()


def _generate_icv(company):
	last = frappe.db.get_value(
		"Zatca Transactions",
		{"company": company},
		"invoice_icv",
		order_by="transaction_date desc",
	)
	return (last or 0) + 1


def _tlv_encode(tag, value):
	value_bytes = value.encode("utf-8") if isinstance(value, str) else value
	tag_bytes = bytes([tag])
	length_bytes = len(value_bytes)
	if length_bytes < 128:
		length_bytes = bytes([length_bytes])
	else:
		length_bytes = bytes([0x81, length_bytes])
	return tag_bytes + length_bytes + value_bytes


def _tlv_qr_data(seller_name, vat_no, timestamp, total, vat_total):
	data = b""
	data += _tlv_encode(1, seller_name)
	data += _tlv_encode(2, vat_no)
	data += _tlv_encode(3, timestamp)
	data += _tlv_encode(4, f"{total:.2f}")
	data += _tlv_encode(5, f"{vat_total:.2f}")
	return data


@frappe.whitelist()
def generate_tlv_qr(invoice_name):
	invoice = frappe.get_doc("Trip Invoice", invoice_name)
	company_doc = frappe.get_doc("Transportation Company", invoice.company)
	seller_name = company_doc.company_name or company_doc.legal_name or ""
	vat_no = company_doc.vat_no or ""
	timestamp = invoice.invoice_date.strftime("%Y-%m-%dT00:00:00Z")
	total = invoice.grand_total or 0
	vat_total = invoice.vat_amount or 0
	tlv = _tlv_qr_data(seller_name, vat_no, timestamp, total, vat_total)
	return base64.b64encode(tlv).decode()


def _get_invoice_type(invoice):
	inv_type = getattr(invoice, "invoice_type", None)
	if inv_type == "Credit Note":
		return ("381", "Credit Note")
	elif inv_type == "Debit Note":
		return ("383", "Debit Note")
	return ("388", "Invoice")


def _billing_reference(invoice):
	ref = getattr(invoice, "return_against", None)
	if ref:
		return ref
	return None


def generate_invoice_xml(invoice, company_doc, csid_doc, invoice_counter, pih):
	item = (invoice.items or [{}])[0]
	item_name = item.get("item_name") or item.get("description") or "Transport Service"
	vat_rate = item.get("vat_rate", invoice.vat_rate or 15)
	net = float(item.get("amount", invoice.net_total or 0))
	vat_amt = float(item.get("vat_amount", invoice.vat_amount or 0))
	gross = float(item.get("total_amount", invoice.grand_total or 0))
	qty = int(item.get("qty", 1))
	unit_price = round(net / qty, 6) if qty > 0 else 0

	invoice_type_code, invoice_type_name = _get_invoice_type(invoice)
	uuid_str = str(uuid.uuid4())
	issue_date = invoice.invoice_date.strftime("%Y-%m-%d")
	issue_time = datetime.now(timezone.utc).strftime("%H:%M:%SZ")

	seller = {
		"name": escape(company_doc.company_name or ""),
		"vat": escape(company_doc.vat_no or ""),
		"cr": escape(company_doc.cr_no or ""),
		"address": escape(company_doc.address or ""),
	}
	customer_name = escape(invoice.customer or "Walk-in Customer")
	currency = company_doc.default_currency or "SAR"

	xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">
  <ext:UBLExtensions>
    <ext:UBLExtension>
      <ext:ExtensionURI>urn:fdc:gov:sa:2024</ext:ExtensionURI>
      <ext:ExtensionContent>
        <sig:UBLDocumentSignatures xmlns:sig="urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2"
                                    xmlns:sac="urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2"
                                    xmlns:sbc="urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2">
          <sac:SignatureInformation>
            <cbc:ID>urn:fdc:gov:sa:2024</cbc:ID>
            <sbc:ReferencedSignatureID>urn:fdc:gov:sa:2024</sbc:ReferencedSignatureID>
          </sac:SignatureInformation>
        </sig:UBLDocumentSignatures>
      </ext:ExtensionContent>
    </ext:UBLExtension>
  </ext:UBLExtensions>
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>urn:fdc:gov:sa:2024</cbc:CustomizationID>
  <cbc:ProfileID>{invoice_type_code}</cbc:ProfileID>
  <cbc:ProfileExecutionID>urn:fdc:gov:sa:2024:1.0</cbc:ProfileExecutionID>
  <cbc:ID>{escape(invoice.name)}</cbc:ID>
  <cbc:UUID>{uuid_str}</cbc:UUID>
  <cbc:IssueDate>{issue_date}</cbc:IssueDate>
  <cbc:IssueTime>{issue_time}</cbc:IssueTime>
  <cbc:InvoiceTypeCode name="{invoice_type_name}">{invoice_type_code}</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>
  <cbc:TaxCurrencyCode>{currency}</cbc:TaxCurrencyCode>
  <cac:AdditionalDocumentReference>
    <cbc:ID>ICV</cbc:ID>
    <cbc:UUID>{invoice_counter}</cbc:UUID>
  </cac:AdditionalDocumentReference>
  <cac:AdditionalDocumentReference>
    <cbc:ID>PIH</cbc:ID>
    <cbc:UUID>{pih}</cbc:UUID>
  </cac:AdditionalDocumentReference>
  <cac:Signature>
    <cbc:ID>urn:fdc:gov:sa:2024</cbc:ID>
    <cac:SignatoryParty>
      <cac:PartyIdentification>
        <cbc:ID>{seller['vat']}</cbc:ID>
      </cac:PartyIdentification>
      <cac:PartyName>
        <cbc:Name>{seller['name']}</cbc:Name>
      </cac:PartyName>
    </cac:SignatoryParty>
    <cac:DigitalSignatureAttachment>
      <cac:ExternalReference>
        <cbc:URI>#signature</cbc:URI>
      </cac:ExternalReference>
    </cac:DigitalSignatureAttachment>
  </cac:Signature>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyIdentification>
        <cbc:ID schemeID="CRN">{seller['cr']}</cbc:ID>
      </cac:PartyIdentification>
      <cac:PartyName>
        <cbc:Name>{seller['name']}</cbc:Name>
      </cac:PartyName>
      <cac:PostalAddress>
        <cbc:StreetName>{seller['address']}</cbc:StreetName>
      </cac:PostalAddress>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{seller['vat']}</cbc:CompanyID>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:PartyTaxScheme>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>{seller['name']}</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyName>
        <cbc:Name>{customer_name}</cbc:Name>
      </cac:PartyName>
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{currency}">{vat_amt:.2f}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="{currency}">{net:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="{currency}">{vat_amt:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{vat_rate}</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{currency}">{net:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{currency}">{net:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{currency}">{gross:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PrepaidAmount currencyID="{currency}">0.00</cbc:PrepaidAmount>
    <cbc:PayableAmount currencyID="{currency}">{gross:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="EA">{qty}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{currency}">{net:.2f}</cbc:LineExtensionAmount>
    <cac:TaxTotal>
      <cbc:TaxAmount currencyID="{currency}">{vat_amt:.2f}</cbc:TaxAmount>
    </cac:TaxTotal>
    <cac:Item>
      <cbc:Name>{item_name}</cbc:Name>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="{currency}">{unit_price:.6f}</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
</Invoice>"""

	return xml, uuid_str


def sign_invoice_xml(xml_string, private_key_pem):
	from lxml import etree

	root = etree.fromstring(xml_string.encode("utf-8"))
	ns = {
		"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
	}

	c14n_bytes = etree.tostring(root, method="c14n", exclusive=True, with_comments=False)
	digest = hashlib.sha256(c14n_bytes).digest()
	digest_b64 = base64.b64encode(digest).decode()

	try:
		from OpenSSL import crypto

		pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, private_key_pem)
		signature = crypto.sign(pkey, c14n_bytes, "sha256")
		sig_b64 = base64.b64encode(signature).decode()
	except ImportError:
		import subprocess

		with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as kf:
			kf.write(private_key_pem)
			key_path = kf.name
		with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin", delete=False) as df:
			df.write(c14n_bytes)
			data_path = df.name
		sig_path = data_path + ".sig"
		try:
			subprocess.run(
				["openssl", "dgst", "-sha256", "-sign", key_path, "-out", sig_path, data_path],
				check=True, capture_output=True, text=True, timeout=30,
			)
			with open(sig_path, "rb") as f:
				signature = f.read()
			sig_b64 = base64.b64encode(signature).decode()
		finally:
			for p in [key_path, data_path, sig_path]:
				try:
					Path(p).unlink(missing_ok=True)
				except Exception:
					pass

	# Build signed XML
	signed_xml = xml_string.replace(
		"</ext:UBLExtensions>",
		f"""<sac:SignatureInformation>
            <cbc:ID>urn:fdc:gov:sa:2024</cbc:ID>
            <sbc:ReferencedSignatureID>urn:fdc:gov:sa:2024</sbc:ReferencedSignatureID>
            <sig:DigitalSignature>
              <sig:SignatureDateTime>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</sig:SignatureDateTime>
              <sbc:ReferencedSignatureID>urn:fdc:gov:sa:2024</sbc:ReferencedSignatureID>
              <ds:Signature xmlns:ds='http://www.w3.org/2000/09/xmldsig#'>
                <ds:SignedInfo>
                  <ds:CanonicalizationMethod Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315'/>
                  <ds:SignatureMethod Algorithm='http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256'/>
                  <ds:Reference URI=''>
                    <ds:Transforms>
                      <ds:Transform Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315'/>
                    </ds:Transforms>
                    <ds:DigestMethod Algorithm='http://www.w3.org/2001/04/xmlenc#sha256'/>
                    <ds:DigestValue>{digest_b64}</ds:DigestValue>
                  </ds:Reference>
                </ds:SignedInfo>
                <ds:SignatureValue>{sig_b64}</ds:SignatureValue>
              </ds:Signature>
            </sig:DigitalSignature>
          </sac:SignatureInformation>
        </ext:ExtensionContent>
      </ext:UBLExtension>
    </ext:UBLExtensions>""",
	)

	return signed_xml, digest_b64
