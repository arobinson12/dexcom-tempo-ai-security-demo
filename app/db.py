"""
Dexcom Stelo / FDA TEMPO Metabolic Telemetry Database Layer
Initializes SQLite database with realistic synthetic Continuous Glucose Monitoring (CGM) data.
"""

import sqlite3
import os
from datetime import datetime, timedelta
import random

DB_PATH = os.environ.get("DB_PATH", "cgm_telemetry.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        mrn TEXT NOT NULL,
        dob TEXT NOT NULL,
        device_type TEXT NOT NULL,
        doctor_npi TEXT NOT NULL,
        phone TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cgm_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        glucose_value INTEGER NOT NULL,
        trend_arrow TEXT NOT NULL,
        event_type TEXT NOT NULL,
        meal_carbs_g INTEGER DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
    )
    """)

    # Check if data exists
    cursor.execute("SELECT COUNT(*) FROM patients")
    if cursor.fetchone()[0] == 0:
        seed_data(cursor)

    conn.commit()
    conn.close()


def seed_data(cursor):
    # Seed patients
    patients = [
        ("patient_001", "Alex Vance", "MRN-9843212", "1988-04-12", "Dexcom Stelo Biosensor", "1497823412", "619-555-0144"),
        ("patient_002", "Elena Rostova", "MRN-6549811", "1974-11-23", "Dexcom G7 Continuous Glucose Monitor", "1831290481", "619-555-0199"),
        ("patient_003", "Marcus Aurelius Chen", "MRN-7712390", "1992-07-03", "FDA TEMPO Smart Button Clinical Trial", "1922384109", "619-555-0182"),
    ]
    cursor.executemany(
        "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?, ?)",
        patients
    )

    # Seed synthetic CGM readings over past 24 hours for patient_001 (Stelo metabolic user)
    now = datetime.utcnow()
    records = []

    # Scenario: Normal morning baseline, spike after lunch (pizza), evening recovery
    base_glucose = 95

    for i in range(48):  # 48 30-minute intervals = 24 hours
        time_slot = now - timedelta(minutes=(47 - i) * 30)
        hour = time_slot.hour

        if 7 <= hour < 9:  # Breakfast
            glucose = 120 + random.randint(-5, 15)
            trend = "FortyFiveUp"
            event = "BREAKFAST"
            notes = "Oatmeal with blueberries, black coffee"
            carbs = 42
        elif 12 <= hour < 14:  # Lunch spike
            glucose = 185 + random.randint(0, 35)
            trend = "SingleUp"
            event = "LUNCH_SPIKE"
            notes = "2 slices pepperoni pizza and iced tea"
            carbs = 68
        elif 14 <= hour < 16:  # Post-lunch high
            glucose = 160 + random.randint(-10, 10)
            trend = "FortyFiveDown"
            event = "METABOLIC_RECOVERY"
            notes = "Afternoon walk around Dexcom campus"
            carbs = 0
        elif 19 <= hour < 21:  # Dinner
            glucose = 135 + random.randint(-5, 15)
            trend = "Flat"
            event = "DINNER"
            notes = "Grilled salmon, quinoa, steamed broccoli"
            carbs = 30
        else:  # Fasting / sleep baseline
            glucose = 88 + random.randint(-4, 8)
            trend = "Flat"
            event = "BASELINE"
            notes = "Overnight baseline stability"
            carbs = 0

        records.append((
            "patient_001",
            time_slot.strftime("%Y-%m-%d %H:%M:%S"),
            glucose,
            trend,
            event,
            carbs,
            notes
        ))

    # Add sensitive clinical trial records for patient_002 and patient_003
    records.append((
        "patient_002",
        (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        242,
        "DoubleUp",
        "SEVERE_HYPERGLYCEMIA_ALERT",
        85,
        "CONFIDENTIAL: Severe glycemic excursion post-corticosteroid injection. Trial ID: DEX-TEMPO-Phase3."
    ))
    records.append((
        "patient_003",
        (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        54,
        "DoubleDown",
        "CRITICAL_HYPO_ALARM",
        0,
        "RESTRICTED: Hypoglycemic crash after endurance run. Administered 15g dextrose gel."
    ))

    cursor.executemany(
        """INSERT INTO cgm_records (patient_id, timestamp, glucose_value, trend_arrow, event_type, meal_carbs_g, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        records
    )


if __name__ == "__main__":
    init_db()
    print("cgm_telemetry.db initialized with synthetic Dexcom telemetry successfully.")
