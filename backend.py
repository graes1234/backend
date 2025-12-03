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
# 기본 경로 설정
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 업로드 / 이미지 / DB 경로
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
IMAGE_DIR = os.path.join(BASE_DIR, "image")
DB_DIR = os.path.join(BASE_DIR, "DB")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

BASE_RUNTIME_DIR = "/tmp/backend_runtime"
DB_DIR = os.path.join(BASE_RUNTIME_DIR, "db")

os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "fabrics.db")         # 읽기용은 복사해둠
GUESTBOOK_DB = os.path.join(DB_DIR, "guestbook.db")  # 쓰기용 DB는 여기 저장됨


# =========================
# FastAPI 앱 / CORS
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rkawk123.github.io",
        "https://rkawk123.github.io/",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데모 이미지 정적 서빙
app.mount("/image", StaticFiles(directory=IMAGE_DIR), name="demo-images")


# =========================
# DB 유틸
# =========================
def get_fabric_info(fabric_name: str):
    """세탁 정보 DB에서 원단 정보 조회"""
    conn = sqlite3.connect(DB_PATH)
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
    """방명록 DB 초기화 (테이블 없으면 생성)"""
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
# 스타트업 훅
# =========================
@app.on_event("startup")
def on_startup():
    # 디렉토리 보장
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(DB_DIR, exist_ok=True)

    # 방명록 DB 초기화
    init_guestbook_db()


# =========================
# 기본 / 헬스체크
# =========================
@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/")
async def read_root():
    """
    단순 상태 확인용 엔드포인트.
    (front/index.html은 GitHub Pages에서 서빙하므로 서버에서는 JSON만 반환)
    """
    return {"message": "Server is running!"}


# =========================
# 데모 파일 목록
# =========================
@app.get("/demo_files")
def get_demo_files():
    files = [
        f
        for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    return {"files": files}


# =========================
# 스트리밍 예측
# =========================
@app.post("/predict_stream")
async def predict_stream(file: UploadFile = File(...), demo: str = Form("0")):
    try:
        # 1. 파일 저장
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        file_bytes = await file.read()
        with open(filepath, "wb") as f:
            f.write(file_bytes)

        async def event_generator():
            # 0. 서버 연결
            yield json.dumps({"status": "🔌⏳🌐 서버 연결 중..."}) + "\n"
            if demo == "1":
                await asyncio.sleep(1)

            # 1. 이미지 저장 완료
            yield json.dumps({"status": "📁⏳💾 이미지 저장 중..."}) + "\n"
            if demo == "1":
                await asyncio.sleep(1)

            # 2. 전처리
            yield json.dumps({"status": "🧼🧪🔧 이미지 전처리 중..."}) + "\n"
            x = load_and_preprocess(filepath)
            if demo == "1":
                await asyncio.sleep(1)

            # 3. 예측
            yield json.dumps({"status": "🔍⚡📊 결과 예측 중..."}) + "\n"
            if demo == "1":
                await asyncio.sleep(1)

            preds = run_inference(x)

            # 4. 결과 정리
            top3 = [
                {"label": class_names[i], "score": float(preds[i])}
                for i in range(len(class_names))
            ]
            top3 = sorted(top3, key=lambda x: x["score"], reverse=True)[:3]

            top_fabric = top3[0]["label"]
            info = get_fabric_info(top_fabric)

            result = {
                "filename": file.filename,
                "predictions": top3,
                "predicted_fabric": top_fabric,
            }

            if info:
                result.update(
                    {
                        "ko_name": info[1],
                        "wash_method": info[2],
                        "dry_method": info[3],
                        "special_note": info[4],
                    }
                )

            yield json.dumps(
                {"status": "✅🎉✨ 예측 완료!", "result": result}
            ) + "\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"},
        )

    except Exception as e:
        # 스트리밍 에러는 한 번에 JSON으로 반환
        return JSONResponse(
            status_code=500,
            content={"error": f"stream predict error: {str(e)}"},
        )


# =========================
# 일반 예측
# =========================
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        # 1. 파일 저장
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 2. 모델 추론
        raw_results = predict_fabric(filepath)
        print("🔥 raw_results:", raw_results)

        if not raw_results:
            return {
                "predictions": [],
                "error": "모델이 유효한 결과를 반환하지 않았습니다.",
            }

        # 3. Top3 정리
        top3 = sorted(
            raw_results, key=lambda x: x.get("score", 0), reverse=True
        )[:3]
        predictions = [
            {"label": x["label"], "score": round(float(x["score"]), 4)}
            for x in top3
        ]

        # 4. Top1으로 세탁 정보 조회
        top_fabric = top3[0]["label"]
        info = get_fabric_info(top_fabric)

        response = {
            "filename": file.filename,
            "predictions": predictions,
            "predicted_fabric": top_fabric,
        }

        if info:
            response.update(
                {
                    "ko_name": info[1],
                    "wash_method": info[2],
                    "dry_method": info[3],
                    "special_note": info[4],
                }
            )
        else:
            response["error"] = "DB에서 해당 재질 정보를 찾을 수 없습니다."

        return response

    except Exception as e:
        print("❌ 서버 오류:", e)
        return {
            "predictions": [],
            "error": f"서버 처리 중 에러: {str(e)}",
        }


# =========================
# 세탁 정보 단독 조회
# =========================
@app.get("/fabric_info/{fabric_name}")
def fabric_info(fabric_name: str):
    info = get_fabric_info(fabric_name)
    if not info:
        raise HTTPException(status_code=404, detail="Fabric not found")
    return {
        "fabric": info[0],
        "ko_name": info[1],
        "wash_method": info[2],
        "dry_method": info[3],
        "special_note": info[4],
    }


# =========================
# 방명록 API
# =========================
@app.post("/guestbook")
def add_guestbook(data: dict):
    name = data.get("name")
    contact = data.get("contactInfo")
    message = data.get("message")

    if not name or not message:
        raise HTTPException(status_code=400, detail="name, message 필수입니다.")

    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO guestbook (name, contactInfo, message) VALUES (?, ?, ?)",
        (name, contact, message),
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()

    return {"id": last_id, "success": True}


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

    result = []
    for r in rows:
        result.append(
            {
                "id": r[0],
                "name": r[1],
                "contactInfo": r[2],
                "message": r[3],
                "created_at": r[4],
            }
        )
    return result


@app.delete("/guestbook/{entry_id}")
def delete_guestbook(entry_id: int):
    conn = sqlite3.connect(GUESTBOOK_DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM guestbook WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# =========================
# 로컬 실행용
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

