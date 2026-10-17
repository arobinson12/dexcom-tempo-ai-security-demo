# Dexcom Enterprise Agentic Coding Rules (FDA Section 524B & HIPAA Guardrails)

> **Antigravity Enterprise Governance Architecture vs. Ungoverned Cursor Workflows**  
> *Author:* Dexcom Digital Health Security & Compliance Architecture  
> *Applies to:* All Antigravity Agents, Subagents, and Developer Workspaces across Dexcom Cloud Projects

---

## 1. Executive Context: Why Dexcom Standardized on Google Antigravity over Cursor

| Governance Dimension | Cursor (Ungoverned Local Tool) | Google Antigravity (Gemini Enterprise) |
| :--- | :--- | :--- |
| **Enterprise Policy Enforcement** | Client-side `.cursorrules` can be ignored, overwritten, or bypassed by developers locally. | **Immutable Organization & Project Rules** enforced hierarchically (`~/.gemini/antigravity` &rarr; Workspace `AGENTS.md`). |
| **Medical Device Compliance (FDA 524B)** | No cryptographic audit trail or automated verification of LLM changes against medical safety constraints. | **Deterministic CodeMender Verification (`cm`)** powered by Gemini 4 Argon with automated sandbox regression testing. |
| **HIPAA PHI Protection** | Raw code and telemetry strings sent un-redacted over arbitrary developer connections. | **Native Cloud DLP Integration** automatically sanitizing PHI infoTypes prior to LLM reasoning. |
| **Prompt Injection & Adversarial Defense** | Ad-hoc system prompts vulnerable to indirect injection via patient notes or telemetry. | **GCP Model Armor Integration** enforcing centralized confidence-based jailbreak & dosage-poisoning filters. |
| **Identity & Least-Privilege IAM** | Fragmented personal API keys stored on developer laptops. | **Google Cloud Workload Identity Federation & Bound IAM Service Accounts** without long-lived credentials. |

---

## 2. Mandatory Core Coding Rules for All Dexcom Agents

### Rule 1: Zero Raw String Interpolation in Data Queries (CWE-89 Defense)
- **Violation:** Any dynamic SQL query built using f-strings, format, or string concatenation (e.g. `f"SELECT * FROM cgm_records WHERE event_type = '{var}'"`).
- **Mandate:** All database queries must use **parameterized placeholders** (`?` for SQLite, `%s` / `$1` for Postgres):
  ```python
  # COMPLIANT: Parameterized query
  cursor.execute(
      "SELECT id, patient_id, timestamp, glucose_value FROM cgm_records WHERE event_type = ?",
      (event_type,)
  )
  ```

### Rule 2: Mandatory Context-Aware Output Encoding (CWE-79 Defense)
- **Violation:** Directly reflecting user-supplied input (e.g. `error`, `redirect_uri`, `patient_name`) into HTML responses without encoding.
- **Mandate:** Use `html.escape()` or dedicated templating engines (Jinja2) with auto-escaping enabled:
  ```python
  import html

  # COMPLIANT: Context-aware HTML escaping
  safe_error = html.escape(error, quote=True)
  return HTMLResponse(content=f"<h3>Dexcom OAuth Authorization Error: {safe_error}</h3>", status_code=400)
  ```

### Rule 3: Mandatory 3-Stage Guardrail Wrapping on Vertex AI Calls
Every endpoint or background agent calling Vertex AI Gemini (`gemini-4-argon`, `gemini-3.8-flash`) MUST route through the 3-Stage Dexcom Security Pipeline:
1. **Cloud DLP (Sensitive Data Protection):**
   - Must inspect and de-identify all HIPAA PHI (`PERSON_NAME`, `MEDICAL_RECORD_NUMBER`, `PHONE_NUMBER`, `SSN`, `NPI`).
   - Must mask using infoType tags (e.g., `[PERSON_NAME]`) before data touches any generative model.
2. **GCP Model Armor:**
   - Must invoke `sanitizeUserPrompt` against the provisioned enterprise template (`cgm-tempo-coach-guardrail`).
   - If `filterMatchState == "MATCH_FOUND"`, the agent must immediately quarantine the request, halt LLM execution, and write a structured `WARNING` event to Cloud Logging.
3. **Model Armor Response Sanitization:**
   - Must invoke `sanitizeModelResponse` on the Gemini output to guarantee no leaked PHI or toxic content exits the boundary.

### Rule 4: Medical Safety Guardrail — Prohibition of Insulin Dosing Logic
Under FDA Section 524B and Dexcom Clinical Safety Guidelines:
- **Never** generate algorithms or prompt completions that calculate insulin units, prescribe bolus dosages, or recommend titration schedules.
- The AI Coach is strictly limited to **metabolic lifestyle coaching** (analyzing glucose excursions relative to carbohydrates and activity) and must always direct patients to their physician for medical dosing.

---

## 3. CodeMender Verification & CI/CD Pipeline
Before committing or submitting pull requests, developers and agents must run CodeMender:
```bash
# Quick discovery scan across repository
cm find . --model gemini-4-argon

# Deep verification of detected findings
cm verify <finding-id> -y --model gemini-4-argon

# Generate compliant fix patch and verify tests pass
cm fix <finding-id> -y --model gemini-4-argon
```
