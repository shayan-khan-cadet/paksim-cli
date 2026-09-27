#!/usr/bin/env python3
"""
PAKSIM-CLI Backend - FastAPI proxy for paksims.info
Deployed on Render. Bypasses CORS for the web frontend.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import re
import os

app = FastAPI(title="PAKSIM-CLI API", version="1.0.0")

# CORS — allow your GitHub Pages site + localhost for dev
origins = [
    "https://shayan-khan-cadet.github.io",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LookupRequest(BaseModel):
    query: str


SEARCH_URL = "https://paksims.info/search.php"

HEADERS = {
    "Host": "paksims.info",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://paksims.info/",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://paksims.info",
}

COOKIES = {
    "_ga": "GA1.1.1024773666.1782293225",
    "_ga_BH10FCDBP2": "GS2.1.s1782374087$o3$g0$t1782374087$j60$l0$h0",
}


@app.get("/")
def root():
    return {"status": "ok", "service": "PAKSIM-CLI API", "version": "1.0.0"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/lookup")
async def lookup(req: LookupRequest):
    query = re.sub(r"[^0-9]", "", req.query)

    if not (len(query) == 13 or 11 <= len(query) <= 15):
        raise HTTPException(status_code=400, detail="Invalid format. Use 13-digit CNIC or 11-15 digit SIM.")

    try:
        resp = requests.post(
            SEARCH_URL,
            headers=HEADERS,
            cookies=COOKIES,
            data={"q": query},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {str(e)[:100]}")
