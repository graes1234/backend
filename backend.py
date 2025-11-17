from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import uvicorn
import os
from model_loader import predict_fabric  # AI 예측 함수

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

@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.get("/")
def read_root():
    return {"message": "Server is running!"}

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import sqlite3
import uvicorn
import os
import json
import uuid
from model_loader import predict_fabric  # AI 예측 함수

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

@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.get("/")
def read_root():
    return {"message": "Server is running!"}

status_store = {}

@app.post("/predict_stream")
async def predict_stream(file: UploadFile = File(...)):

    # 작업 ID 생성
    task_id = str(uuid.uuid4())
    status_store[task_id] = "시작 대기 중..."

    async def event_generator():
        # 1. 파일 저장
        status_store[task_id] = "이미지 저장 중..."
        yield f"data: {status_store[task_id]}\n\n"
        await asyncio.sleep(0.3)

        file_path = f"uploads/{task_id}_{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # 2. 전처리
        status_store[task_id] = "전처리 중..."
        yield f"data: {status_store[task_id]}\n\n"
        await asyncio.sleep(0.3)

        # 3. 특징 추출
        status_store[task_id] = "특징 추출 중..."
        yield f"data: {status_store[task_id]}\n\n"
        await asyncio.sleep(0.3)

        # 4. 예측 실행
        status_store[task_id] = "예측 중..."
        yield f"data: {status_store[task_id]}\n\n"
        await asyncio.sleep(0.3)

        # 5. 실제 예측
        fabric, conf = predict_fabric(file_path)

        # 예측값 저장
        status_store[task_id] = {
            "fabric_name": fabric,
            "confidence": conf
        }

        yield f"data: DONE:{task_id}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
    
@app.get("/predict_result/{task_id}")
async def predict_result(task_id: str):
    if task_id not in status_store:
        return JSONResponse({"error": "invalid task id"}, status_code=404)
    
    result = status_store[task_id]
    if isinstance(result, dict):
        return JSONResponse(result)
    else:
        return JSONResponse({"status": result})
"""

"""
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    async def event_stream():
        try:
            # 1. 서버 연결
            yield "data: 서버 연결 중...\n\n"
            await asyncio.sleep(0.2)

            # 2. 파일 저장
            yield "data: 파일 저장 중...\n\n"
            data = await file.read()
            filepath = f"uploads/{file.filename}"
            with open(filepath, "wb") as f:
                f.write(data)
            await asyncio.sleep(0.2)

            # 3. 이미지 전처리 시작
            yield "data: 이미지 전처리 중...\n\n"
            await asyncio.sleep(0.2)

            # 4. 모델 예측 시작
            yield "data: 예측 계산 중...\n\n"
            raw_results = predict_fabric(filepath)   # 실제 모델 호출
            await asyncio.sleep(0.2)

            # 5. Top3 정리
            yield "data: 예측 결과 정리 중...\n\n"
            top3_list = []
            for item in raw_results[:3]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    top3_list.append({"label": item[0], "probability": item[1]})
                else:
                    top3_list.append({"label": str(item), "probability": None})

            top_fabric = top3_list[0]["label"]

            # 6. DB 조회
            yield "data: 재질 정보 조회 중...\n\n"
            info = get_fabric_info(top_fabric)
            await asyncio.sleep(0.2)

            # 7. 최종 JSON 생성
            if info:
                result = {
                    "filename": file.filename,
                    "top3_predictions": top3_list,
                    "predicted_fabric": top_fabric,
                    "ko_name": info[1],
                    "wash_method": info[2],
                    "dry_method": info[3],
                    "special_note": info[4]
                }
            else:
                result = {
                    "filename": file.filename,
                    "top3_predictions": top3_list,
                    "predicted_fabric": top_fabric,
                    "error": "DB에서 해당 재질 정보를 찾을 수 없습니다."
                }

            # 8. JSON을 마지막 SSE로 보내기
            yield f"data: [RESULT]{json.dumps(result, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: [ERROR]{str(e)}\n\n"

        yield "data: 스트리밍 완료\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
"""

"""
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
"""





