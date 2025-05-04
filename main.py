from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import os
import logging
import time
from typing import Optional
from contextlib import asynccontextmanager

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
EXCEL_PATH = "/home/ubuntu/apsrtc/Details of replaced PCs & Printers.xlsx"
RELOAD_INTERVAL = 60  # seconds

# Globals
depot_data = []
last_loaded = None

# Load Excel data
def load_data():
    global depot_data, last_loaded
    if last_loaded is None or time.time() - last_loaded > RELOAD_INTERVAL:
        if not os.path.exists(EXCEL_PATH):
            logger.error(f"Excel file not found at: {EXCEL_PATH}")
            depot_data = []
            return depot_data
        try:
            xls = pd.ExcelFile(EXCEL_PATH)
            if "Sheet3" not in xls.sheet_names:
                raise ValueError("Sheet3 not found in the Excel file")
            df = xls.parse("Sheet3")
            df = df.astype(str).replace("nan", "")
            depot_data = df.to_dict(orient="records")
            last_loaded = time.time()
            logger.info(f"Data loaded successfully - {len(depot_data)} records")
        except Exception as e:
            logger.error(f"Error reading Excel: {e}")
            depot_data = []
    return depot_data

# FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    global depot_data
    depot_data = load_data()
    if not depot_data:
        logger.warning("Depot data is empty at startup.")
    yield
    logger.info("Shutting down application")

app = FastAPI(lifespan=lifespan)

# Static and templates
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Routes
@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Details of replacement and procurement",
        "results": None,
        "search_performed": False,
        "error_message": None
    })

@app.post("/search", response_class=HTMLResponse)
async def search_unit(request: Request, unit: str = Form(...)):
    unit = unit.strip()
    data = load_data()

    if not data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "Details of replacement and procurement",
            "results": [],
            "search_performed": True,
            "search_term": unit,
            "error_message": "Excel data is missing or unreadable."
        })

    matches = [row for row in data if unit.lower() in str(row.get("Unit", "")).lower()]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Details of replacement and procurement",
        "results": matches,
        "search_performed": True,
        "search_term": unit,
        "error_message": None
    })

@app.get("/refresh", response_class=HTMLResponse)
async def refresh_data(request: Request):
    global depot_data
    depot_data = load_data()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Details of replacement and procurement",
        "results": None,
        "search_performed": False,
        "error_message": None
    })

@app.get("/suggest")
async def suggest_units(query: str = Query("")):
    data = load_data()
    unit_names = set()

    if data:
        for row in data:
            unit = str(row.get("Unit", "")).strip()
            if query.lower() in unit.lower():
                unit_names.add(unit)

    return JSONResponse(list(sorted(unit_names)))

@app.get("/health")
async def health():
    return {"status": "ok", "records_loaded": len(depot_data)}

# Run locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

