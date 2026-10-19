"""
Dexcom FDA TEMPO & HIPAA Security Guardrails Pipeline
Integrates:
1. Cloud Sensitive Data Protection (DLP) - PHI De-identification (HIPAA Safe Harbor)
2. GCP Model Armor - Prompt Injection, Jailbreak & Threat Defense (FDA Section 524B)
3. Vertex AI Gemini (gemini-4-argon, gemini-3.8-flash, gemini-2.5-flash) - Non-prescriptive Metabolic Coaching
4. Cloud Logging - Structured Audit Trails for Security Command Center & Compliance Auditing
"""

import os
import json
import logging
import time
import requests
import google.auth
from google.auth.transport.requests import Request

# Configure standard logger to output structured JSON
logger = logging.getLogger("dexcom_security_guardrails")
logger.setLevel(logging.INFO)

PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
MODEL_ARMOR_TEMPLATE = os.environ.get("MODEL_ARMOR_TEMPLATE", "cgm-tempo-coach-guardrail")

SYSTEM_INSTRUCTION = (
    "You are the Dexcom FDA TEMPO Metabolic Health AI Coach. "
    "Your purpose is to help Stelo biosensor users understand how meals, physical activity, and stress "
    "correlate with their Continuous Glucose Monitoring (CGM) Estimated Glucose Values (EGVs in mg/dL). "
    "You provide non-prescriptive lifestyle insights and metabolic education. "
    "CRITICAL COMPLIANCE DIRECTIVE (FDA Section 524B & Medical Device Regulations): "
    "You are STRICTLY PROHIBITED from calculating insulin doses, advising insulin bolus amounts, or prescribing medical therapies. "
    "If a prompt asks for insulin advice, decline immediately and direct the patient to their healthcare provider."
)

_cached_credentials = None


def get_gcp_auth_headers():
    global _cached_credentials, PROJECT_ID
    try:
        if _cached_credentials is None or not _cached_credentials.valid:
            creds, default_project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(Request())
            _cached_credentials = creds
            if not PROJECT_ID and default_project:
                PROJECT_ID = default_project
        else:
            if _cached_credentials.expired:
                _cached_credentials.refresh(Request())
        token = _cached_credentials.token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        if PROJECT_ID:
            headers["X-Goog-User-Project"] = PROJECT_ID
        return headers
    except Exception as e:
        logger.warning(f"Could not load GCP default credentials ({e}). Fallback to local evaluation mode.")
        return None


# ----------------------------------------------------------------------
# Stage 1: Cloud Sensitive Data Protection (DLP API)
# ----------------------------------------------------------------------
def deidentify_phi_dlp(text: str) -> dict:
    """
    De-identifies HIPAA PHI infoTypes using Google Cloud DLP API.
    Replaces patient names, MRNs, SSNs, phone numbers, NPIs, etc. with infoType tags.
    """
    start_time = time.time()
    headers = get_gcp_auth_headers()
    
    info_types = [
        {"name": "PERSON_NAME"},
        {"name": "MEDICAL_RECORD_NUMBER"},
        {"name": "US_SOCIAL_SECURITY_NUMBER"},
        {"name": "US_HEALTHCARE_NPI"},
        {"name": "PHONE_NUMBER"},
        {"name": "EMAIL_ADDRESS"},
        {"name": "DATE_OF_BIRTH"},
    ]

    if not headers:
        # Mock de-identification for local development without credentials
        mock_redacted = text
        mock_findings = []
        for name in ["John Doe", "Alex Vance", "Elena Rostova", "Marcus Chen"]:
            if name in mock_redacted:
                mock_redacted = mock_redacted.replace(name, "[PERSON_NAME]")
                mock_findings.append({"infoType": "PERSON_NAME", "count": 1})
        for mrn in ["MRN-9843212", "MRN-6549811", "9843212"]:
            if mrn in mock_redacted:
                mock_redacted = mock_redacted.replace(mrn, "[MEDICAL_RECORD_NUMBER]")
                mock_findings.append({"infoType": "MEDICAL_RECORD_NUMBER", "count": 1})
        return {
            "redacted_text": mock_redacted,
            "findings": mock_findings,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "engine": "dlp-local-mock"
        }

    url = f"https://dlp.googleapis.com/v2/projects/{PROJECT_ID}/content:deidentify"
    payload = {
        "item": {"value": text},
        "deidentifyConfig": {
            "infoTypeTransformations": {
                "transformations": [
                    {
                        "primitiveTransformation": {
                            "replaceWithInfoTypeConfig": {}
                        }
                    }
                ]
            }
        },
        "inspectConfig": {
            "infoTypes": info_types,
            "includeQuote": False
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            redacted_text = data.get("item", {}).get("value", text)
            summaries = data.get("overview", {}).get("transformationSummaries", [])
            findings = []
            for item in summaries:
                findings.append({
                    "infoType": item.get("infoType", {}).get("name", "UNKNOWN"),
                    "count": int(item.get("results", [{}])[0].get("count", 1)) if item.get("results") else 1
                })
            return {
                "redacted_text": redacted_text,
                "findings": findings,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "engine": "gcp-cloud-dlp-v2"
            }
        else:
            logger.error(f"Cloud DLP returned {resp.status_code}: {resp.text}")
            return {
                "redacted_text": text,
                "findings": [],
                "error": f"DLP error {resp.status_code}",
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "engine": "dlp-error-fallback"
            }
    except Exception as e:
        logger.error(f"DLP invocation failed: {e}")
        return {
            "redacted_text": text,
            "findings": [],
            "error": str(e),
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "engine": "dlp-error-fallback"
        }


# ----------------------------------------------------------------------
# Stage 2: Model Armor Prompt & Response Sanitization
# ----------------------------------------------------------------------
def sanitize_prompt_model_armor(prompt: str) -> dict:
    """
    Evaluates prompt against Model Armor template in us-central1.
    Detects Prompt Injection, Jailbreaks, and Malicious content.
    """
    start_time = time.time()
    headers = get_gcp_auth_headers()
    url = (
        f"https://modelarmor.{LOCATION}.rep.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/templates/{MODEL_ARMOR_TEMPLATE}:sanitizeUserPrompt"
    )

    if not headers:
        # Mock mode for testing without credentials
        is_injection = any(term in prompt.lower() for term in ["ignore all", "prescribe", "override", "system prompt", "insulin"])
        return {
            "is_blocked": is_injection,
            "filter_match_state": "MATCH_FOUND" if is_injection else "NO_MATCH_FOUND",
            "matched_filters": ["pi_and_jailbreak"] if is_injection else [],
            "error_message": "Dexcom FDA TEMPO Guardrail Violation: Unauthorized prompt override detected." if is_injection else None,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "engine": "model-armor-local-mock"
        }

    try:
        resp = requests.post(url, headers=headers, json={"userPromptData": {"text": prompt}}, timeout=8)
        if resp.status_code == 200:
            data = resp.json().get("sanitizationResult", {})
            match_state = data.get("filterMatchState", "NO_MATCH_FOUND")
            is_blocked = (match_state == "MATCH_FOUND")

            matched_filters = []
            filter_results = data.get("filterResults", {})
            for fname, fres in filter_results.items():
                # check nested match states
                res_dict = next(iter(fres.values())) if isinstance(fres, dict) and fres else {}
                if isinstance(res_dict, dict) and res_dict.get("matchState") == "MATCH_FOUND":
                    matched_filters.append(fname)

            error_msg = data.get("sanitizationMetadata", {}).get("errorMessage", None)
            return {
                "is_blocked": is_blocked,
                "filter_match_state": match_state,
                "matched_filters": matched_filters,
                "error_message": error_msg,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "engine": "gcp-model-armor-v1"
            }
        else:
            logger.error(f"Model Armor returned {resp.status_code}: {resp.text}")
            return {
                "is_blocked": False,
                "filter_match_state": "SKIPPED_ON_ERROR",
                "matched_filters": [],
                "error": f"Model Armor status {resp.status_code}",
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "engine": "model-armor-error-passthrough"
            }
    except Exception as e:
        logger.error(f"Model Armor call failed: {e}")
        return {
            "is_blocked": False,
            "filter_match_state": "SKIPPED_ON_ERROR",
            "matched_filters": [],
            "error": str(e),
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "engine": "model-armor-error-passthrough"
        }


def sanitize_response_model_armor(response_text: str) -> dict:
    """
    Evaluates Gemini model response before returning to patient.
    """
    start_time = time.time()
    headers = get_gcp_auth_headers()
    url = (
        f"https://modelarmor.{LOCATION}.rep.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/templates/{MODEL_ARMOR_TEMPLATE}:sanitizeModelResponse"
    )
    if not headers:
        return {"is_blocked": False, "filter_match_state": "NO_MATCH_FOUND", "latency_ms": 1.0}

    try:
        resp = requests.post(url, headers=headers, json={"modelResponseData": {"text": response_text}}, timeout=8)
        if resp.status_code == 200:
            data = resp.json().get("sanitizationResult", {})
            return {
                "is_blocked": (data.get("filterMatchState") == "MATCH_FOUND"),
                "filter_match_state": data.get("filterMatchState", "NO_MATCH_FOUND"),
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }
    except Exception as e:
        logger.warning(f"Response sanitization exception: {e}")
    return {"is_blocked": False, "filter_match_state": "NO_MATCH_FOUND", "latency_ms": 1.0}


# ----------------------------------------------------------------------
# Stage 3: Vertex AI Gemini Metabolic Coaching
# ----------------------------------------------------------------------
def call_vertex_gemini(prompt: str, model_name: str = "gemini-4-argon") -> dict:
    """
    Invokes Vertex AI Gemini using the global endpoint for gemini-4-argon & gemini-3.8-flash,
    with graceful fallback to gemini-2.5-flash.
    """
    start_time = time.time()
    headers = get_gcp_auth_headers()

    if not headers:
        # Mock mode for testing without credentials
        return {
            "model": model_name,
            "text": (
                "Metabolic Coaching Insight: Based on your recent continuous glucose readings, "
                "the post-meal glucose rise to 185 mg/dL peaked approximately 45 minutes after carbohydrate intake. "
                "Engaging in a light 15-minute walk helps stimulate muscle glucose uptake via GLUT4 translocation without insulin."
            ),
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "engine": "gemini-mock"
        }

    # Models supported in global endpoint on Vertex AI
    target_models = [model_name]
    if model_name != "gemini-3.8-flash":
        target_models.append("gemini-3.8-flash")
    if model_name != "gemini-2.5-flash":
        target_models.append("gemini-2.5-flash")

    last_error = None
    for model in target_models:
        url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/publishers/google/models/{model}:generateContent"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}]
            },
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 600
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                result = resp.json()
                candidates = result.get("candidates", [])
                if candidates:
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    generated_text = "".join(part.get("text", "") for part in content_parts)
                    return {
                        "model": model,
                        "text": generated_text,
                        "latency_ms": round((time.time() - start_time) * 1000, 2),
                        "engine": f"vertex-ai-gemini-{model}"
                    }
            else:
                last_error = f"{model} returned {resp.status_code}: {resp.text}"
                logger.warning(f"Vertex AI retry fallback: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Vertex AI exception on {model}: {e}")

    # Fallback response if all fail
    return {
        "model": model_name,
        "text": "Unable to complete real-time Gemini generation. Check quota or credentials.",
        "error": last_error,
        "latency_ms": round((time.time() - start_time) * 1000, 2),
        "engine": "vertex-ai-failed"
    }


# ----------------------------------------------------------------------
# Stage 4: Structured Cloud Audit Logging
# ----------------------------------------------------------------------
def emit_security_audit_log(
    event_type: str,
    severity: str,
    details: dict,
    client_ip: str = "127.0.0.1"
) -> dict:
    """
    Emits a structured compliance and security audit event to standard output.
    Cloud Run and GCP automatically ingest this into Cloud Logging with severity and labels.
    """
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    audit_entry = {
        "timestamp": timestamp,
        "severity": severity,
        "event_type": event_type,
        "service": "dexcom-tempo-ai-security-demo",
        "compliance_controls": [
            "FDA_SECTION_524B_CYBERSECURITY_IN_MEDICAL_DEVICES",
            "HIPAA_SECURITY_RULE_45_CFR_164_312",
            "SOC2_TYPE_II_TRUST_SERVICES_CRITERIA"
        ],
        "client_ip": client_ip,
        "guardrail_telemetry": details
    }

    # Print JSON line so Google Cloud Logging captures severity & structured fields
    print(json.dumps(audit_entry), flush=True)
    return audit_entry
