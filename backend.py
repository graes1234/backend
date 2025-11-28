"""
#스트림 기준
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import sqlite3
from fastapi.responses import FileResponse, StreamingResponse
import json
from model_loader import predict_fabric
import asyncio
import time

app = FastAPI()
os.makedirs("uploads", exist_ok=True)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용 (Wix/로컬 테스트용)
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 경로
DB_PATH = "DB/fabrics.db"

# DB에서 세탁 정보 가져오기
def get_fabric_info(fabric_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT fabric, ko_name, wash_method, dry_method, special_note FROM fabric_care WHERE LOWER(fabric) = LOWER(?)",
        (fabric_name,),
    )
    result = cur.fetchone()
    conn.close()
    return result

@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.get("/")
def read_root():
    return {"message": "Server is running!"}

@app.post("/predict_stream")
async def predict_stream(file: UploadFile = File(...)):

    # 파일 저장
    file_bytes = await file.read()
    filepath = f"uploads/{file.filename}"
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    async def event_generator():
        # 1) 단계별 진행상태
        steps = [
            "🌐🔌💫서버 연결 중...",
            "🧠📦⏳모델 불러오는 중...",
            "🔍⚡📊결과 예측 중..."
        ]

        for step in steps:
            yield json.dumps({"status": step}) + "\n"
            await asyncio.sleep(0.3)

        # 2) 실제 모델 추론
        raw_results = predict_fabric(filepath)
        top3 = sorted(raw_results, key=lambda x: x.get("score", 0), reverse=True)[:3]
        predictions = [{"label": x["label"], "score": round(float(x["score"]), 4)} for x in top3]

        top_fabric = top3[0]["label"]
        info = get_fabric_info(top_fabric)

        response = {
            "filename": file.filename,
            "predictions": predictions,
            "predicted_fabric": top_fabric,
        }

        if info:
            response.update({
                "ko_name": info[1],
                "wash_method": info[2],
                "dry_method": info[3],
                "special_note": info[4],
            })

        # 3) 최종 JSON 한 줄
        yield json.dumps({"status": "✅🎉✨예측 완료!", "result": response}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/plain")

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        # 1. 파일 저장
        filepath = f"uploads/{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 2. 모델 추론
        raw_results = predict_fabric(filepath)
        print("🔥 raw_results:", raw_results)

        # 3. 예측 결과 정제 (Top3)
        # 예: raw_results = [{"label": "cotton", "score": 0.87}, {"label": "polyester", "score": 0.09}, ...]
        top3 = sorted(raw_results, key=lambda x: x.get("score", 0), reverse=True)[:3]
        predictions = [
            {"label": x["label"], "score": round(float(x["score"]), 4)} for x in top3
        ]

        # 4. Top1으로 DB 조회
        top_fabric = top3[0]["label"]
        info = get_fabric_info(top_fabric)

        # 5. 결과 생성
        response = {
            "filename": file.filename,
            "predictions": predictions,
            "predicted_fabric": top_fabric,
        }

        if info:
            response.update({
                "ko_name": info[1],
                "wash_method": info[2],
                "dry_method": info[3],
                "special_note": info[4]
            })
        else:
            response["error"] = "DB에서 해당 재질 정보를 찾을 수 없습니다."

        return response

    except Exception as e:
        print("❌ 서버 오류:", e)
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

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
        "special_note": info[4]
    }


# 서버 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sqlite3
from fastapi.responses import FileResponse, StreamingResponse
import json
from model_loader import predict_fabric, load_and_preprocess, run_inference, class_names
import asyncio
import time
from fastapi.staticfiles import StaticFiles

app = FastAPI()
os.makedirs("uploads", exist_ok=True)

model_ready = False

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 모든 도메인 허용 (Wix/로컬 테스트용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 경로
DB_PATH = "DB/fabrics.db"

# DB에서 세탁 정보 가져오기
def get_fabric_info(fabric_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT fabric, ko_name, wash_method, dry_method, special_note FROM fabric_care WHERE LOWER(fabric) = LOWER(?)",
        (fabric_name,),
    )
    result = cur.fetchone()
    conn.close()
    return result

@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.get("/")
async def read_root():
    index_path = os.path.join("../front", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Server is running!"}

@app.on_event("startup")
async def startup_event():
    global model_ready
    try:
        _ = model.predict(np.zeros((1, 224, 224, 3)))  # 더미 예측
        model_ready = True
    except:
        model_ready = False

@app.get("/server_ready")
async def server_ready():
    return {"ready": model_ready}

@app.post("/predict_stream")
async def predict_stream(file: UploadFile = File(...)):
    async def event_generator(): #event_stream
        # 1. 이미지 파일 저장
        yield json.dumps({"status": "📁⏳💾 이미지 저장 중..."}) + "\n"
        file_bytes = await file.read()
        filepath = f"uploads/{file.filename}"
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        await asyncio.sleep(0.1)

        # 2. 이미지 전처리
        yield json.dumps({"status": "🧼🧪🔧 이미지 전처리 중..."}) + "\n"
        x = load_and_preprocess(filepath)
        await asyncio.sleep(0.1)

        # 3. 예측 시작
        yield json.dumps({"status": "🔍⚡📊결과 예측 중..."}) + "\n"

        #  실제 모델 예측 (걸리는 시간 그대로 스트리밍에 반영됨)
        preds = run_inference(x)

        # 결과 상위 3개 정렬
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
            result.update({
                "ko_name": info[1],
                "wash_method": info[2],
                "dry_method": info[3],
                "special_note": info[4]
            })

        yield json.dumps({
            "status": "✅🎉✨ 예측 완료!",
            "result": result
        }) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        # 1. 파일 저장
        filepath = f"uploads/{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 2. 모델 추론
        raw_results = predict_fabric(filepath)
        print("🔥 raw_results:", raw_results)

        # 3. 예측 결과 정제 (Top3)
        # 예: raw_results = [{"label": "cotton", "score": 0.87}, {"label": "polyester", "score": 0.09}, ...]
        top3 = sorted(raw_results, key=lambda x: x.get("score", 0), reverse=True)[:3]
        predictions = [
            {"label": x["label"], "score": round(float(x["score"]), 4)} for x in top3
        ]

        # 4. Top1으로 DB 조회
        top_fabric = top3[0]["label"]
        info = get_fabric_info(top_fabric)

        # 5. 결과 생성
        response = {
            "filename": file.filename,
            "predictions": predictions,
            "predicted_fabric": top_fabric,
        }

        if info:
            response.update({
                "ko_name": info[1],
                "wash_method": info[2],
                "dry_method": info[3],
                "special_note": info[4]
            })
        else:
            response["error"] = "DB에서 해당 재질 정보를 찾을 수 없습니다."

        return response

    except Exception as e:
        print("❌ 서버 오류:", e)
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

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
        "special_note": info[4]
    }

# 서버 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)



