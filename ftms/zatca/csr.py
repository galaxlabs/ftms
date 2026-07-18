from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path

import frappe
from frappe import _


@frappe.whitelist()
def generate_csr(csr_settings_name):
	doc = frappe.get_doc("Zatca CSR Settings", csr_settings_name)
	if doc.csr_generated:
		frappe.throw(_("CSR already generated. Create a new CSR Settings record to regenerate."))

	_validate_csr_fields(doc)

	private_key_pem, csr_pem = _generate_ecdsa_key_and_csr(doc)

	doc.csr_generated = 1
	doc.private_key = _pem_to_single_line(private_key_pem)
	doc.private_key_pem_format = private_key_pem
	doc.csr = _pem_to_single_line(csr_pem)
	doc.csr_pem_format = csr_pem
	doc.created_time = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

	return {
		"csr": doc.csr,
		"csr_pem": doc.csr_pem_format,
		"private_key": doc.private_key,
		"private_key_pem": doc.private_key_pem_format,
	}


def _validate_csr_fields(doc):
	required = {
		"csrcommonname": "Common Name (CN)",
		"csrorganizationidentifier": "Organization Identifier (VAT No)",
		"csrorganizationunitname": "Organization Unit Name",
		"csrorganizationname": "Organization Name",
		"csrlocationaddress": "Location Address",
		"csrindustrybusinesscategory": "Industry Business Category",
	}
	for field, label in required.items():
		if not doc.get(field):
			frappe.throw(_("{0} is required for CSR generation").format(label))
	if not doc.get("registration_number"):
		frappe.throw(_("Registration Number is required for CSR generation"))


def _pem_to_single_line(pem_text):
	lines = pem_text.strip().split("\n")
	result = []
	for line in lines:
		if line.startswith("-----"):
			continue
		result.append(line.strip())
	return "".join(result)


def _build_openssl_config(doc, csr_path, key_path):
	config_lines = [
		"[ req ]",
		"default_bits = 256",
		"default_keyfile = privkey.pem",
		"distinguished_name = req_distinguished_name",
		"req_extensions = v3_req",
		"prompt = no",
		"string_mask = utf8only",
		"",
		"[ req_distinguished_name ]",
		f"commonName = {doc.csrcommonname}",
		f"organizationIdentifier = {doc.csrorganizationidentifier}",
		f"organizationalUnitName = {doc.csrorganizationunitname}",
		f"organizationName = {doc.csrorganizationname}",
		f"countryName = SA",
		"",
		"[ v3_req ]",
		f"subjectAltName = otherName:1.3.6.1.4.1.311.20.2.3;UTF8:{doc.csrorganizationidentifier}",
		f"subjectKeyIdentifier = hash",
	]
	if doc.csrserialnumber:
		config_lines.insert(3, f"serial = {doc.csrserialnumber}")
	return "\n".join(config_lines)


def _generate_ecdsa_key_and_csr(doc):
	with tempfile.TemporaryDirectory() as tmpdir:
		tmp = Path(tmpdir)
		key_path = tmp / "ec-key.pem"
		csr_path = tmp / "ec-csr.pem"
		config_path = tmp / "csr.conf"

		config_path.write_text(_build_openssl_config(doc, csr_path, key_path))

		try:
			subprocess.run(
				[
					"openssl", "ecparam", "-genkey", "-name", "prime256v1",
					"-out", str(key_path),
				],
				check=True, capture_output=True, text=True, timeout=30,
			)
			subprocess.run(
				[
					"openssl", "req", "-new",
					"-key", str(key_path),
					"-out", str(csr_path),
					"-config", str(config_path),
				],
				check=True, capture_output=True, text=True, timeout=30,
			)
		except subprocess.CalledProcessError as e:
			frappe.log_error(f"OpenSSL failed: {e.stderr}", "CSR Generation Error")
			frappe.throw(_("CSR generation failed: {0}").format(e.stderr))
		except FileNotFoundError:
			frappe.throw(_("OpenSSL not found on server. Install openssl to generate CSR."))

		private_key_pem = key_path.read_text()
		csr_pem = csr_path.read_text()

	return private_key_pem, csr_pem
