from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
import sqlite3
import uvicorn
import os
import json
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
    async def event_generator():
        try:
            # 1. 상태 메시지 SSE
            steps = [
                "서버 연결 중...",
                "모델 불러오는 중...",
                "이미지 전처리 중...",
                "예측 계산 중..."
            ]
            for step in steps:
                yield f"data: {step}\n\n"
                await asyncio.sleep(0.7)

            # 2. 파일 저장
            data = await file.read()
            filepath = f"uploads/{file.filename}"
            with open(filepath, "wb") as f:
                f.write(data)

            # 3. 모델 예측
            raw_results = predict_fabric(filepath)
            top3_list = []
            for item in raw_results[:3]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    top3_list.append({"label": item[0], "probability": item[1]})
                else:
                    top3_list.append({"label": str(item), "probability": None})

            # 4. DB 조회
            top_fabric = top3_list[0]["label"] if top3_list else None
            info = get_fabric_info(top_fabric) if top_fabric else None

            # 5. 최종 결과 생성
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

            # 6. 프론트가 기존처럼 처리할 수 있도록 [RESULT]로 전송
            yield f"data: [RESULT]{json.dumps(result, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: [ERROR]{str(e)}\n\n"

        yield f"data: 스트리밍 완료 ✅\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

"""
async def predict(file: UploadFile = File(...)):
    try:
        filepath = f"uploads/{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        raw_results = predict_fabric(filepath)

        if not raw_results or not isinstance(raw_results, list):
            raise ValueError("모델 반환값이 올바르지 않습니다.")

        top3_list = []
        for item in raw_results[:3]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                top3_list.append({"label": item[0], "probability": item[1]})
            else:
                top3_list.append({"label": str(item), "probability": None})

        top_fabric = top3_list[0]["label"]
        info = get_fabric_info(top_fabric)

        if info:
            response = {
                "filename": file.filename,
                "top3_predictions": top3_list,
                "predicted_fabric": top_fabric,
                "ko_name": info[1],
                "wash_method": info[2],
                "dry_method": info[3],
                "special_note": info[4]
            }
        else:
            response = {
                "filename": file.filename,
                "top3_predictions": top3_list,
                "predicted_fabric": top_fabric,
                "error": "DB에서 해당 재질 정보를 찾을 수 없습니다."
            }

        return {"result_text": html_output}

    except Exception as e:
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}
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










