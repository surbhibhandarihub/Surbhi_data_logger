
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import csv
import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import time
from fastapi import Query
from fastapi.responses import StreamingResponse
from io import StringIO
import sqlite3
from datetime import datetime
from fastapi.responses import PlainTextResponse

DB_NAME = "sensor_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            s1 REAL, s2 REAL, s3 REAL, s4 REAL,
            s5 REAL, s6 REAL, s7 REAL, s8 REAL,
            s9 REAL, s10 REAL, s11 REAL, s12 REAL,
            s13 REAL, s14 REAL, s15 REAL, s16 REAL
        )
    """)

    conn.commit()
    conn.close()

init_db()


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ------------------------
# STORAGE
# ------------------------
latest_data = []
last_update_time = 0


# ------------------------
# MODEL
# ------------------------
class SensorData(BaseModel):
    timestamp: str
    values: List[float]

# ------------------------
# DASHBOARD PAGE
# ------------------------
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ------------------------
# HISTORY PAGE
# ------------------------
@app.get("/history_page", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


# ------------------------
# RECEIVE DATA
# ------------------------
upload_counter = 0

@app.post("/upload")
def upload_data(data: SensorData):
    global latest_data, last_update_time

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sensor_data (
            timestamp,
            s1,s2,s3,s4,s5,s6,s7,s8,
            s9,s10,s11,s12,s13,s14,s15,s16
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.timestamp,
        *data.values
    ))

    conn.commit()
    conn.close()

    latest_data = {
        "timestamp": data.timestamp,
        "values": data.values
    }

    last_update_time = time.time()

    return {"message": "Data saved to DB"}

# ------------------------
# LATEST DATA
# ------------------------
latest_data = {
    "timestamp": "",
    "values": [0]*16
}

@app.get("/latest")
def get_latest():
    return latest_data



# ------------------------
# FULL HISTORY
# ------------------------
@app.get("/history")
def get_history(
    start: str = Query(None),
    end: str = Query(None),
    limit: int = 50
):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = "SELECT * FROM sensor_data"
    conditions = []
    params = []

    if start:
        conditions.append("timestamp >= ?")
        params.append(start)

    if end:
        conditions.append("timestamp <= ?")
        params.append(end)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    history = []

    for row in rows:
        history.append({
            "timestamp": row[1],
            "values": list(row[2:])
        })

    return {"history": history}

# ------------------------
# download
# ------------------------

@app.get("/download")
def download_data(start: str = None, end: str = None):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = "SELECT * FROM sensor_data"
    conditions = []
    params = []

    if start:
        conditions.append("timestamp >= ?")
        params.append(start)

    if end:
        conditions.append("timestamp <= ?")
        params.append(end)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    header = ["Timestamp"] + [f"Sensor {i}" for i in range(1, 17)]
    writer.writerow(header)

    for row in rows:
        timestamp = row[1]
        values = row[2:]
        writer.writerow([timestamp] + list(values))

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sensor_data.csv"
        },
    )


# ------------------------
# DEVICE STATUS
# ------------------------
@app.get("/status")
def device_status():
    global last_update_time

    if last_update_time == 0:
        return {"device": "disconnected"}

    current_time = time.time()
    diff = current_time - last_update_time

    # increase threshold to avoid render latency issue
    if diff > 10:
        return {"device": "disconnected"}
    else:
        return {"device": "connected"}


@app.get("/debug_time")
def debug_time():
    return {
        "last_update_time": last_update_time,
        "current_time": time.time(),
        "difference": time.time() - last_update_time
    }

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return PlainTextResponse("OK")
