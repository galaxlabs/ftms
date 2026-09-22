from __future__ import annotations

import base64
import json

import requests

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class DocumentAIProviderError(RuntimeError):
	pass


def extract_image(*, api_key, model, prompt, schema, command, image_bytes, mime_type, timeout):
	if not api_key:
		raise DocumentAIProviderError("OpenAI API key is not configured")
	data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
	payload = {
		"model": model,
		"temperature": 0,
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
					{"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
				],
			}
		],
		"response_format": {
			"type": "json_schema",
			"json_schema": {"name": command, "strict": True, "schema": schema},
		},
	}
	try:
		response = requests.post(
			OPENAI_CHAT_COMPLETIONS_URL,
			headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
			json=payload,
			timeout=timeout,
		)
	except requests.RequestException as exc:
		raise DocumentAIProviderError("OpenAI document extraction request failed") from exc
	if response.status_code != 200:
		raise DocumentAIProviderError(f"OpenAI document extraction returned HTTP {response.status_code}")
	try:
		return parse_chat_completion(response.json())
	except (KeyError, TypeError, ValueError) as exc:
		raise DocumentAIProviderError("OpenAI returned an invalid structured extraction") from exc


def parse_chat_completion(payload):
	message = payload["choices"][0]["message"]
	if message.get("refusal"):
		raise ValueError("The model refused the document extraction")
	content = message["content"]
	if isinstance(content, list):
		content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
	content = str(content).strip()
	if content.startswith("```"):
		content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
	result = json.loads(content)
	if not isinstance(result, dict):
		raise ValueError("Extraction result must be a JSON object")
	return result
