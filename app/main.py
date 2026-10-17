"""
Dexcom Stelo / FDA TEMPO Metabolic AI Coach & Telemetry Portal
FastAPI Application Entrypoint
"""

import os
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from app.db import init_db, get_db_connection
from app.security_guardrails import (
    deidentify_phi_dlp,
    sanitize_prompt_model_armor,
    sanitize_response_model_armor,
    call_vertex_gemini,
    emit_security_audit_log
)

app = FastAPI(
    title="Dexcom Stelo / FDA TEMPO Metabolic AI Coach & Telemetry Portal",
    version="1.0.0",
    description="Demonstrating CodeMender, Google Antigravity, Cloud DLP, and Model Armor"
)

# Ensure database is seeded on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Dexcom Stelo Metabolic AI Portal</h1><p>Frontend loading...</p>")


@app.get("/api/v1/health")
def healthcheck():
    return {
        "status": "healthy",
        "service": "dexcom-tempo-ai-security-demo",
        "model_armor_template": "cgm-tempo-coach-guardrail",
        "models": ["gemini-4-argon", "gemini-3.8-flash", "gemini-2.5-flash"]
    }


@app.get("/api/v1/egvs/recent")
def get_recent_egvs(patient_id: str = "patient_001", limit: int = 24):
    """
    Returns recent CGM records for telemetry charts (safe parameterized query).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, patient_id, timestamp, glucose_value, trend_arrow, event_type, meal_carbs_g, notes 
           FROM cgm_records 
           WHERE patient_id = ? 
           ORDER BY timestamp DESC LIMIT ?""",
        (patient_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return {"records": [dict(r) for r in reversed(rows)]}


# ==============================================================================
# VULNERABILITY 1: SQL Injection in CGM Export (Intentional for Act 1 CodeMender)
# Legacy endpoint written without Antigravity Security Skill enforcement (CWE-89)
# ==============================================================================
@app.get("/api/v1/egvs/export")
def export_cgm_records(event_type: str = Query("BREAKFAST")):
    """
    Export CGM records filtered by event type.
    VULNERABILITY: Directly interpolates user-controlled 'event_type' into SQLite query string.
    An attacker can supply: ' OR '1'='1 -- to dump unauthorized records across all patients!
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # VULNERABLE CODE PATTERN:
    query = f"SELECT id, patient_id, timestamp, glucose_value, trend_arrow, event_type, notes FROM cgm_records WHERE event_type = '{event_type}'"
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        results = [dict(r) for r in rows]
    except Exception as e:
        conn.close()
        return JSONResponse(status_code=500, content={"error": "Database query execution error", "details": str(e)})

    conn.close()
    return {
        "event_type": event_type,
        "record_count": len(results),
        "executed_query": query,
        "records": results
    }


# ==============================================================================
# VULNERABILITY 2: Reflected XSS in OAuth Callback (Intentional for Act 1 CodeMender)
# Legacy endpoint written without Antigravity Security Skill enforcement (CWE-79)
# ==============================================================================
@app.get("/api/v1/oauth/callback", response_class=HTMLResponse)
def oauth_callback(error: Optional[str] = Query(None), code: Optional[str] = Query(None)):
    """
    OAuth authorization callback handler.
    VULNERABILITY: Directly reflects unescaped 'error' query parameter in HTML response.
    An attacker can pass: ?error=<script>alert('Dexcom XSS')</script>
    """
    if error:
        # VULNERABLE CODE PATTERN: Unsanitized reflection into HTML response
        html_content = f"<h3>Dexcom OAuth Authorization Error: {error}</h3>"
        return HTMLResponse(content=html_content, status_code=400)

    return HTMLResponse(
        content="<h3>Dexcom OAuth Authorization Successful</h3><p>Session token issued.</p>",
        status_code=200
    )


# ==============================================================================
# ACT 2: 3-Stage AI Guardrail Pipeline (Cloud DLP + Model Armor + Vertex AI Gemini)
# ==============================================================================
class CoachAnalysisRequest(BaseModel):
    patient_note: str
    recent_egvs: Optional[List[int]] = None
    guardrails_enabled: bool = True
    model_name: str = "gemini-4-argon"


@app.post("/api/v1/coach/analyze")
def analyze_metabolic_coaching(req: CoachAnalysisRequest, request: Request):
    """
    Executes the 3-Stage Runtime Security Pipeline:
    Stage 1: Cloud DLP de-identification (HIPAA PHI redaction)
    Stage 2: Model Armor prompt inspection (Prompt Injection / Jailbreak / Poisoning defense)
    Stage 3: Vertex AI Gemini metabolic insight generation + Model Armor response sanitization
    Stage 4: Structured Cloud Audit Logging
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    raw_prompt = req.patient_note
    if req.recent_egvs:
        raw_prompt += f" Recent Continuous Glucose readings (last 3 hrs): {req.recent_egvs} mg/dL."

    # Scenario A: Guardrails are OFF (Legacy / Ungoverned baseline)
    if not req.guardrails_enabled:
        audit_entry = emit_security_audit_log(
            event_type="UNGOVERNED_AI_INVOCATION",
            severity="WARNING",
            details={
                "guardrails_enabled": False,
                "warning": "Cloud DLP and Model Armor were bypassed. Raw PHI and potential injection sent to LLM.",
                "raw_input_snippet": raw_prompt[:120]
            },
            client_ip=client_ip
        )
        gemini_result = call_vertex_gemini(raw_prompt, model_name=req.model_name)
        return {
            "guardrails_enabled": False,
            "stage_1_dlp": {
                "status": "BYPASSED",
                "redacted_text": raw_prompt,
                "findings": []
            },
            "stage_2_model_armor": {
                "status": "BYPASSED",
                "is_blocked": False,
                "filter_match_state": "SKIPPED"
            },
            "stage_3_gemini": gemini_result,
            "audit_log": audit_entry
        }

    # Scenario B: Guardrails are ON (Dexcom Enterprise Antigravity Standard)

    # 1. Cloud DLP HIPAA De-identification
    dlp_result = deidentify_phi_dlp(raw_prompt)
    clean_prompt = dlp_result.get("redacted_text", raw_prompt)

    # 2. Model Armor Prompt Sanitization
    armor_result = sanitize_prompt_model_armor(clean_prompt)

    if armor_result.get("is_blocked"):
        # Threat detected! Immediately halt execution before calling Gemini
        block_msg = armor_result.get("error_message") or "Request blocked by Model Armor: Prompt Injection / Threat detected."
        audit_entry = emit_security_audit_log(
            event_type="MODEL_ARMOR_SECURITY_INTERVENTION",
            severity="WARNING",
            details={
                "verdict": "BLOCKED",
                "matched_filters": armor_result.get("matched_filters"),
                "dlp_findings_count": len(dlp_result.get("findings", [])),
                "blocked_reason": block_msg
            },
            client_ip=client_ip
        )
        return {
            "guardrails_enabled": True,
            "stage_1_dlp": dlp_result,
            "stage_2_model_armor": armor_result,
            "stage_3_gemini": {
                "status": "HALTED_BY_GUARDRAIL",
                "model": req.model_name,
                "text": f"🛡️ [SECURITY INTERVENTION] {block_msg}",
                "latency_ms": 0.0
            },
            "audit_log": audit_entry
        }

    # 3. Vertex AI Gemini Execution (Model Armor approved)
    gemini_result = call_vertex_gemini(clean_prompt, model_name=req.model_name)

    # 4. Model Armor Response Sanitization
    response_armor = sanitize_response_model_armor(gemini_result.get("text", ""))

    # 5. Emit compliance audit event
    audit_entry = emit_security_audit_log(
        event_type="CGM_COACHING_COMPLIANCE_AUDIT",
        severity="INFO",
        details={
            "verdict": "PASSED",
            "model": gemini_result.get("model"),
            "dlp_redactions": dlp_result.get("findings"),
            "model_armor_prompt_latency_ms": armor_result.get("latency_ms"),
            "model_armor_response_latency_ms": response_armor.get("latency_ms"),
            "gemini_latency_ms": gemini_result.get("latency_ms")
        },
        client_ip=client_ip
    )

    return {
        "guardrails_enabled": True,
        "stage_1_dlp": dlp_result,
        "stage_2_model_armor": armor_result,
        "stage_3_gemini": gemini_result,
        "stage_3_response_armor": response_armor,
        "audit_log": audit_entry
    }
