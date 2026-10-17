#!/bin/bash
# Starts the Dexcom Stelo / FDA TEMPO AI Portal locally on port 8080
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export GCP_PROJECT="bu2-prod-data"
export GCP_LOCATION="us-central1"
export MODEL_ARMOR_TEMPLATE="cgm-tempo-coach-guardrail"

echo "Initializing database..."
python3 -m app.db

echo "Starting Dexcom Stelo / FDA TEMPO Metabolic AI Portal on http://localhost:8080 ..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
