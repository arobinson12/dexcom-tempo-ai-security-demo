#!/bin/bash
# Builds and deploys the Dexcom Stelo / FDA TEMPO Metabolic AI Portal to Cloud Run
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PROJECT_ID="bu2-prod-data"
REGION="us-central1"
SERVICE_NAME="dexcom-tempo-ai-security-demo"

echo "=========================================================="
echo "Deploying $SERVICE_NAME to Google Cloud Run ($REGION)"
echo "Project: $PROJECT_ID"
echo "=========================================================="

# Build and submit container via Cloud Build
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" --project="${PROJECT_ID}"

# Deploy to Cloud Run
gcloud run deploy "${SERVICE_NAME}" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  --platform managed \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=${REGION},MODEL_ARMOR_TEMPLATE=cgm-tempo-coach-guardrail" \
  --service-account "918024802560-compute@developer.gserviceaccount.com" \
  --memory 1Gi \
  --timeout 300

URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --project "${PROJECT_ID}" --format="value(status.url)")

echo "=========================================================="
echo "Deployment successful!"
echo "Service URL: ${URL}"
echo "=========================================================="
