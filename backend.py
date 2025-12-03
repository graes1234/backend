from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import uvicorn
import os
import sqlite3
import json
import asyncio

from model_loader import (
    predict_fabric,
    load_and_preprocess,
    run_inference,
    class_names,
)

# =========================
# 경로 설정
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
IMAGE_DIR = os.path.join(BASE_DIR, "image")
DB_DIR_REPO = os.path.join(BASE_DIR, "DB")   # 📌 Read-Only DB folder

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DB_DIR_REPO, exist_ok=True)

# -------------------------
# /tmp 영역 (쓰기 가능한 저장소)
# -------------------------
RUNTIME_DIR = "/tmp/backend_runtime"
RUNTIME_DB_DIR = os.path.join(RUNTIME_DIR, "db")

os.makedirs(RUNTIME_DB_DIR, exist_ok=True)

# -------------------------
# DB 파일 경로 결정
# -------------------------
FABRIC_DB_PATH = os.path.join(DB_DIR_REPO, "fabrics.db")  # 📌 read-only
GUESTBOOK_DB = os.path.join(RUNTIME_DB_DIR, "guestbook.db")  # 📌 writable


# =========================
# FastAPI & CORS
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rkawk123.github.io",
        "https://*.github.io",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 이미지 서빙
app.mount("/image", StaticFiles(directory=IMAGE_DIR), name="demo-images")


# =========================
# DB 유틸
# =========================
def get_fabric_info(fabric_name: str):
    """세탁 정보 DB는 read-only에서 불러온다"""
    conn = sqlite3.connect(FABRIC_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT fabric, ko_name, wash_method, dry_method, special_note
        FROM fabric_care
        WHERE LOWER(fabric) = LOWER(?)
        """,
        (fabric_name,),
    )
    result = cur.fetchone()
    conn.close()
    return result


def init_guestbook_db():
    """방명록 DB는 /tmp 내부에 생성"""
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guestbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contactInfo TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


# =========================
# Startup Hook
# =========================
@app.on_event("startup")
def startup():
    os.makedirs(RUNTIME_DB_DIR, exist_ok=True)
    init_guestbook_db()


# =========================
# System APIs
# =========================
@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/")
def root():
    return {"message": "Prediction Server Running!"}


@app.get("/demo_files")
def get_demo_files():
    files = [
        f for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    return {"files": files}


# =========================
# Streaming Prediction
# =========================
@app.post("/predict_stream")
async def predict_stream(file: UploadFile = File(...), demo: str = Form("0")):
    try:
        # 저장
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        data = await file.read()
        with open(filepath, "wb") as f:
            f.write(data)

        async def event_gen():
            yield json.dumps({"status": "🔌⏳🌐 서버 연결 중..."}) + "\n"
            if demo == "1": await asyncio.sleep(1)

            yield json.dumps({"status": "📁⏳💾 이미지 저장 중..."}) + "\n"
            if demo == "1": await asyncio.sleep(1)

            yield json.dumps({"status": "🧼🧪🔧 이미지 전처리 중..."}) + "\n"
            x = load_and_preprocess(filepath)
            if demo == "1": await asyncio.sleep(1)

            yield json.dumps({"status": "🔍⚡📊 결과 예측 중..."}) + "\n"
            preds = run_inference(x)

            # Top3
            top3 = sorted(
                [
                    {"label": class_names[i], "score": float(preds[i])}
                    for i in range(len(class_names))
                ],
                key=lambda x: x["score"],
                reverse=True,
            )[:3]

            top_label = top3[0]["label"]
            info = get_fabric_info(top_label)

            result = {
                "filename": file.filename,
                "predictions": top3,
                "predicted_fabric": top_label
            }

            if info:
                result.update({
                    "ko_name": info[1],
                    "wash_method": info[2],
                    "dry_method": info[3],
                    "special_note": info[4],
                })

            yield json.dumps({"status": "✅🎉✨ 예측 완료!", "result": result}) + "\n"

        return StreamingResponse(event_gen(), media_type="text/plain")

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"stream error: {str(e)}"}
        )


# =========================
# 일반 예측 API
# =========================
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 모델 예측
        raw = predict_fabric(filepath)
        top3 = sorted(raw, key=lambda x: x["score"], reverse=True)[:3]

        top_label = top3[0]["label"]
        info = get_fabric_info(top_label)

        res = {
            "filename": file.filename,
            "predictions": top3,
            "predicted_fabric": top_label,
        }

        if info:
            res.update({
                "ko_name": info[1],
                "wash_method": info[2],
                "dry_method": info[3],
                "special_note": info[4],
            })

        return res

    except Exception as e:
        return {"error": f"predict error: {str(e)}"}


# =========================
# 방명록 API
# =========================
@app.post("/guestbook")
def add_guestbook(data: dict):
    name = data.get("name")
    contact = data.get("contactInfo")
    message = data.get("message")

    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO guestbook (name, contactInfo, message) VALUES (?, ?, ?)",
        (name, contact, message)
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()

    return {"id": entry_id, "success": True}


@app.get("/guestbook")
def get_guestbook():
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, contactInfo, message, created_at "
        "FROM guestbook ORDER BY id DESC"
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r[0], "name": r[1], "contactInfo": r[2],
            "message": r[3], "created_at": r[4]
        }
        for r in rows
    ]


@app.delete("/guestbook/{entry_id}")
def delete_guestbook(entry_id: int):
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM guestbook WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# =========================
# Run
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)


