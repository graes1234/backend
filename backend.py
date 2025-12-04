# ============================================
# 📌 최종 통합 FastAPI 백엔드 (앱 + 웹 OK)
# ============================================

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

# ------------------------------------
# 📌 기본 경로 설정
# ------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
IMAGE_DIR = os.path.join(BASE_DIR, "image")
DB_DIR = os.path.join(BASE_DIR, "DB")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# -------- DB 파일 --------
FABRIC_DB_PATH = os.path.join(DB_DIR, "fabrics.db")
GUESTBOOK_DB = os.path.join(DB_DIR, "guestbook.db")

# ------------------------------------
# 📌 FastAPI 생성 + CORS 전체 허용
# ------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 앱 + 웹 모두 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 이미지 정적파일 경로
app.mount("/image", StaticFiles(directory=IMAGE_DIR), name="demo-images")


# ------------------------------------
# 📌 DB 유틸
# ------------------------------------
def get_fabric_info(fabric_name: str):
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


# 방명록 초기화
def init_guestbook_db():
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS guestbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contactInfo TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_guestbook_db()


# ------------------------------------
# 📌 기본 API
# ------------------------------------
@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/")
def root():
    return {"message": "Fabric AI Backend Running!"}


@app.get("/demo_files")
def get_demo_files():
    files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith((".jpg", ".png"))]
    return {"files": files}


# ------------------------------------
# 📌 스트리밍 예측 (앱에서 사용)
# ------------------------------------
@app.post("/predict_stream")
async def predict_stream(file: UploadFile = File(...), demo: str = Form("0")):

    filepath = os.path.join(UPLOAD_DIR, file.filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())

    async def event_gen():

        yield json.dumps({"status": "🔌⏳🌐 서버 연결 중..."}) + "\n"
        if demo == "1": await asyncio.sleep(1)

        yield json.dumps({"status": "📁⏳💾 이미지 저장 중..."}) + "\n"
        if demo == "1": await asyncio.sleep(1)

        yield json.dumps({"status": "🧼🧪🔧 이미지 전처리 중..."}) + "\n"
        x = load_and_preprocess(filepath)

        yield json.dumps({"status": "🔍⚡📊 결과 예측 중..."}) + "\n"
        preds = run_inference(x)

        top3 = sorted(
            [{"label": class_names[i], "score": float(preds[i])} for i in range(len(class_names))],
            key=lambda x: x["score"],
            reverse=True
        )[:3]

        top_label = top3[0]["label"]
        info = get_fabric_info(top_label)

        result = {
            "filename": file.filename,
            "predictions": top3,
            "predicted_fabric": top_label,
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


# ------------------------------------
# 📌 일반 예측
# ------------------------------------
@app.post("/predict")
async def predict(file: UploadFile = File(...)):

    filepath = os.path.join(UPLOAD_DIR, file.filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())

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


# ------------------------------------
# 📌 앱에서 반드시 필요한 세탁정보 API
# ------------------------------------
@app.get("/fabric_info/{fabric}")
def fabric_info(fabric: str):
    info = get_fabric_info(fabric)
    if not info:
        raise HTTPException(status_code=404, detail="Fabric not found")

    return {
        "fabric": info[0],
        "ko_name": info[1],
        "wash_method": info[2],
        "dry_method": info[3],
        "special_note": info[4]
    }


# ------------------------------------
# 📌 방명록 API
# ------------------------------------
@app.post("/guestbook")
def guestbook_add(data: dict):
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO guestbook (name, contactInfo, message) VALUES (?, ?, ?)",
        (data["name"], data.get("contactInfo"), data["message"])
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"success": True, "id": new_id}


@app.get("/guestbook")
def guestbook_get():
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, name, contactInfo, message, created_at FROM guestbook ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "contactInfo": r[2], "message": r[3], "created_at": r[4]}
        for r in rows
    ]


@app.delete("/guestbook/{entry_id}")
def guestbook_delete(entry_id: int):
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM guestbook WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ------------------------------------
# 📌 RUN
# ------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
