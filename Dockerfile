FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GCP_PROJECT=bu2-prod-data
ENV GCP_LOCATION=us-central1
ENV MODEL_ARMOR_TEMPLATE=cgm-tempo-coach-guardrail

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize seed database
RUN python3 -m app.db

EXPOSE 8080

CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
