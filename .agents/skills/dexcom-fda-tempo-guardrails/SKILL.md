---
name: dexcom-fda-tempo-guardrails
description: "Dexcom FDA Section 524B & HIPAA compliance skill for Antigravity agents. Packages reusable Cloud DLP de-identification, Model Armor prompt injection/threat defense, and non-prescriptive Vertex AI Gemini prompt engineering."
---

# Dexcom FDA TEMPO & HIPAA Guardrails Skill

This skill equips any Google Antigravity agent with the reusable architecture patterns, code templates, and security policies required to build compliant metabolic AI endpoints across Dexcom cloud projects.

## When to Activate This Skill
- When designing or refactoring endpoints that ingest Continuous Glucose Monitoring (CGM) telemetry or patient meal notes.
- When calling Vertex AI Gemini (`gemini-4-argon`, `gemini-3.8-flash`) in healthcare contexts.
- When remediating medical device cybersecurity vulnerabilities identified by CodeMender (`cm`).

---

## 1. Architectural Guardrail Flow

```
[Patient Meal Note / CGM Telemetry]
                │
                ▼
   ┌─────────────────────────┐
   │ Stage 1: Cloud DLP      │  ==> Inspects and masks HIPAA PHI
   │ (Sensitive Data Prot.)  │      (PERSON_NAME, MRN, SSN, PHONE, NPI)
   └────────────┬────────────┘
                │ De-identified Payload
                ▼
   ┌─────────────────────────┐
   │ Stage 2: GCP Model Armor│  ==> Evaluates Prompt Injection & Jailbreaks
   │ (cgm-tempo-guardrail)   │      Quarantines malicious overrides (Confidence LOW+)
   └────────────┬────────────┘
                │ Approved Prompt
                ▼
   ┌─────────────────────────┐
   │ Stage 3: Vertex Gemini  │  ==> Non-prescriptive Metabolic Insights
   │ (gemini-4-argon)        │      Strictly prohibits insulin dosage calculations
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │ Stage 4: Model Armor    │  ==> Sanitizes Model Response
   │ Response Sanitization   │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │ Stage 5: Cloud Logging  │  ==> Emits structured audit entry for SCC & SOC2
   └─────────────────────────┘
```

---

## 2. Reusable Code Templates

### A. Cloud DLP De-identification Pattern
```python
def deidentify_phi(raw_text: str, project_id: str) -> dict:
    url = f"https://dlp.googleapis.com/v2/projects/{project_id}/content:deidentify"
    payload = {
        "item": {"value": raw_text},
        "deidentifyConfig": {
            "infoTypeTransformations": {
                "transformations": [{
                    "primitiveTransformation": {"replaceWithInfoTypeConfig": {}}
                }]
            }
        },
        "inspectConfig": {
            "infoTypes": [
                {"name": "PERSON_NAME"},
                {"name": "MEDICAL_RECORD_NUMBER"},
                {"name": "US_SOCIAL_SECURITY_NUMBER"},
                {"name": "PHONE_NUMBER"},
                {"name": "US_HEALTHCARE_NPI"}
            ]
        }
    }
    # Invoke DLP API with project auth headers ...
```

### B. GCP Model Armor Prompt Defense Pattern
```python
def check_prompt_safety(prompt: str, project_id: str, template: str) -> bool:
    url = f"https://modelarmor.us-central1.rep.googleapis.com/v1/projects/{project_id}/locations/us-central1/templates/{template}:sanitizeUserPrompt"
    response = call_model_armor_api(url, {"userPromptData": {"text": prompt}})
    
    # If filterMatchState is MATCH_FOUND, block immediately
    if response.get("sanitizationResult", {}).get("filterMatchState") == "MATCH_FOUND":
        emit_audit_event("MODEL_ARMOR_BLOCKED", severity="WARNING", details=response)
        return False
    return True
```

### C. FDA Section 524B System Prompt Guardrail
```python
SYSTEM_INSTRUCTION = """
You are the Dexcom FDA TEMPO Metabolic Health AI Coach.
Analyze the physiological correlation between carbohydrate intake and glucose excursions.
FDA MANDATE: You must NEVER calculate insulin dosages or recommend insulin adjustments.
Direct all medical inquiries to the patient's prescribing physician.
"""
```

---

## 3. Pre-Merge Verification with CodeMender
Always run CodeMender prior to deploying endpoints:
```bash
cm find . --model gemini-4-argon
cm verify <finding-id> -y --model gemini-4-argon
```
