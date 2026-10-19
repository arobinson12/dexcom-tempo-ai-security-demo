#!/bin/bash
# Builds and deploys the Dexcom Stelo / FDA TEMPO Metabolic AI Portal to Cloud Run
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="dexcom-tempo-ai-security-demo"

if [ -z "$PROJECT_ID" ]; then
  echo "Error: GCP_PROJECT is not set and no active gcloud project found."
  echo "Usage: GCP_PROJECT=<your-project-id> ./deploy_cloud_run.sh"
  exit 1
fi

echo "=========================================================="
echo "Deploying $SERVICE_NAME to Google Cloud Run ($REGION)"
echo "Project: $PROJECT_ID"
echo "=========================================================="

# Build and submit container via Cloud Build
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest" --project="${PROJECT_ID}"

# Deploy to Cloud Run
DEPLOY_ARGS=(
  --image "gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"
  --platform managed
  --region "${REGION}"
  --project "${PROJECT_ID}"
  --allow-unauthenticated
  --set-env-vars "GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=${REGION},MODEL_ARMOR_TEMPLATE=cgm-tempo-coach-guardrail"
  --memory 1Gi
  --timeout 300
)

if [ -n "$SERVICE_ACCOUNT" ]; then
  DEPLOY_ARGS+=(--service-account "$SERVICE_ACCOUNT")
fi

gcloud run deploy "${SERVICE_NAME}" "${DEPLOY_ARGS[@]}"

URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --project "${PROJECT_ID}" --format="value(status.url)")

echo "=========================================================="
echo "Deployment successful!"
echo "Service URL: ${URL}"
echo "=========================================================="
