"""
#formdata
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import requests
from model_loader import predict_fabric  # filepath 입력 받는 함수

app = FastAPI()
os.makedirs("uploads", exist_ok=True)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Server is running!"}

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        # 1. 서버에 파일 저장
        filepath = f"uploads/{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 2. 모델 추론
        raw_results = predict_fabric(filepath) 
        results = []

        for item in raw_results[:3]:  # Top-3
            label = item[0] if isinstance(item, (list, tuple)) and len(item) > 0 else str(item)
            results.append({"label": str(label)})

        return {
            "filename": file.filename,
            "predictions": results
        }
        
    except requests.exceptions.RequestException as e:
        # 다운로드 실패
        return {"predictions": [], "error": f"파일 다운로드 실패: {str(e)}"}
    except Exception as e:
        # PIL 열기, 모델 추론 등 기타 에러
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000)) 
    uvicorn.run(app, host="0.0.0.0", port=port)
     
#DB 추가
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
        "SELECT fabric, ko_name, wash_method, dry_method, special_note FROM fabric_care WHERE LOWER(fabric) = LOWER(?)",
        (fabric_name,),
    )
    result = cur.fetchone()
    conn.close()
    return result

# 루트 확인용
@app.get("/")
def read_root():
    return {"message": "Server is running!"}

# /predict 엔드포인트
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        # 1. 파일 저장
        filepath = f"uploads/{file.filename}"
        with open(filepath, "wb") as f:
            f.write(await file.read())

        # 2. 모델 추론 (라벨 + 확률 포함)
        raw_results = predict_fabric(filepath)
        print("🔥 raw_results:", raw_results)
        
        # 3. Top-3 정렬 (score 높은 순)
        top3 = sorted(raw_results, key=lambda x: x["score"], reverse=True)[:3]
        top3_list = [{"label": x["label"], "score": float(x["score"])} for x in top3]

        # 4. Top-1로 DB 조회
        top_fabric = top3[0]["label"]
        info = get_fabric_info(top_fabric)

        # 5. 결과 생성
        response = {
            "filename": file.filename,
            "predictions": top3_list,  # 👈 프론트에서 받는 key 이름 통일
            "predicted_fabric": top_fabric
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
        
        ###
        # 3. Top-3 추출
        top3 = raw_results[:3]
        top3_list = [{"label": item["label"], "probability": item["score"]} for item in top3]

        # 4. 상위 1개 DB 조회 (라벨 이름만 전달)
        top_fabric = top3[0]["label"]
        info = get_fabric_info(top_fabric)

        # 5. JSON 반환
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

        return response
        ###

# 서버 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)


##DB +
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

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import asyncio
import os
import json
import uvicorn
from model_loader import predict_fabric  # AI 예측 함수

# FastAPI 앱 초기화
app = FastAPI()
os.makedirs("uploads", exist_ok=True)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 모든 도메인 허용 (전시용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 경로 및 조회 함수
DB_PATH = "DB/fabrics.db"

def get_fabric_info(fabric_name: str):
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
def root():
    return {"message": "AI 섬유 분석 서버 가동 중"}

@app.post("/analyze_stream")
async def analyze_stream(file: UploadFile = File(...)):
    async def event_generator():
        try:
            steps = [
                "서버 연결 중...",
                "모델 불러오는 중...",
                "이미지 전처리 중...",
                "예측 계산 중..."
            ]
            for step in steps:
                yield f"data: {step}\n\n"
                await asyncio.sleep(0.8)

            # 파일을 한 번만 읽어 저장 (중복 읽기 방지)
            data = await file.read()
            filepath = f"uploads/{file.filename}"
            with open(filepath, "wb") as f:
                f.write(data)

            yield f"data: 결과 분석 중...\n\n"
            await asyncio.sleep(0.5)

            raw_results = predict_fabric(filepath)
            top3_list = []
            for item in raw_results[:3]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    top3_list.append({"label": item[0], "probability": item[1]})
                else:
                    top3_list.append({"label": str(item), "probability": None})

            top_fabric = top3_list[0]["label"] if top3_list else None
            info = get_fabric_info(top_fabric) if top_fabric else None

            if info:
                result = {
                    "predicted_fabric": top_fabric,
                    "ko_name": info[1],
                    "wash_method": info[2],
                    "dry_method": info[3],
                    "special_note": info[4],
                    "top3_predictions": top3_list,
                }
            else:
                result = {
                    "predicted_fabric": top_fabric,
                    "top3_predictions": top3_list,
                    "error": "DB에서 해당 재질 정보를 찾을 수 없습니다."
                }

            # 프론트가 감지하기 쉬운 형태로 전송
            yield f"data: [RESULT]{json.dumps(result, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: [ERROR]{str(e)}\n\n"

        yield f"data: 스트리밍 완료 ✅\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ✅ 일반 예측 (비동기 아님 — 단독 결과용)
@app.post("/predict")
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

        return response

    except Exception as e:
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)






