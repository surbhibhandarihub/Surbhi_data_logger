from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import csv
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from fastapi.templating import Jinja2Templates
from fastapi import Request
import time
from fastapi import Query
from fastapi.responses import StreamingResponse, PlainTextResponse
from io import StringIO

# 🔥 MongoDB
from pymongo import MongoClient

# =========================
# MONGODB CONFIG
# =========================
MONGO_URL = "YOUR_MONGODB_URL"

client = MongoClient(MONGO_URL)
db = client["sensor_db"]
collection = db["sensor_data"]

# =========================
# APP
# =========================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

latest_data = []
last_update_time = 0

# =========================
# MODEL
# =========================
class SensorData(BaseModel):
    timestamp: str
    values: List[float]

# =========================
# DASHBOARD
# =========================
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# =========================
# HISTORY PAGE
# =========================
@app.get("/history_page", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})

# =========================
# RECEIVE DATA
# =========================
@app.post("/upload")
def upload_data(data: SensorData):
    global latest_data, last_update_time

    try:
        doc = {
            "timestamp": data.timestamp,
            "values": data.values
        }

        collection.insert_one(doc)

    except Exception as e:
        print("MongoDB Error:", e)

    latest_data = {
        "timestamp": data.timestamp,
        "values": data.values
    }

    last_update_time = time.time()

    return {"message": "Data saved to MongoDB"}

# =========================
# LATEST DATA
# =========================
latest_data = {
    "timestamp": "",
    "values": [0]*16
}

@app.get("/latest")
def get_latest():
    doc = collection.find().sort("_id", -1).limit(1)

    for d in doc:
        return {
            "timestamp": d["timestamp"],
            "values": d["values"]
        }

    return latest_data

# =========================
# HISTORY
# =========================
@app.get("/history")
def get_history(start: str = Query(None), end: str = Query(None), limit: int = 50):

    query = {}

    if start:
        query["timestamp"] = {"$gte": start}

    if end:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end
        else:
            query["timestamp"] = {"$lte": end}

    data = list(
        collection.find(query).sort("_id", -1).limit(limit)
    )

    history = []

    for d in data:
        history.append({
            "timestamp": d["timestamp"],
            "values": d["values"]
        })

    return {"history": history}

# =========================
# DOWNLOAD CSV
# =========================
@app.get("/download")
def download_data(start: str = None, end: str = None):

    query = {}

    if start:
        query["timestamp"] = {"$gte": start}

    if end:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end
        else:
            query["timestamp"] = {"$lte": end}

    data = list(collection.find(query).sort("_id", -1))

    output = StringIO()
    writer = csv.writer(output)

    header = ["Timestamp"] + [f"Sensor {i}" for i in range(1, 17)]
    writer.writerow(header)

    for d in data:
        writer.writerow([d["timestamp"]] + d["values"])

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sensor_data.csv"},
    )

# =========================
# DEVICE STATUS
# =========================
@app.get("/status")
def device_status():
    global last_update_time

    if last_update_time == 0:
        return {"device": "disconnected"}

    if time.time() - last_update_time > 10:
        return {"device": "disconnected"}
    else:
        return {"device": "connected"}

# =========================
# DEBUG
# =========================
@app.get("/debug_time")
def debug_time():
    return {
        "last_update_time": last_update_time,
        "current_time": time.time(),
        "difference": time.time() - last_update_time
    }

# =========================
# HEALTH
# =========================
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return PlainTextResponse("OK")
