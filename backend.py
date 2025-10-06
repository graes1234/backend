
"""
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tensorflow.keras.models import load_model
from PIL import Image
import numpy as np
import io
import os

app = FastAPI()

# CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모델 경로 (GitHub에서 이미 포함시킨 모델)
MODEL_PATH = "final_model.keras"  # GitHub에서 프로젝트에 올린 경로

# 모델 로드
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"{MODEL_PATH} 파일이 존재하지 않습니다. GitHub에서 모델이 포함되어 있는지 확인하세요.")

model = load_model(MODEL_PATH)

# 클래스 이름 (대문자)
CLASS_NAMES = [
    "ACRYLIC", "DENIM", "COTTON", "FUR", "LINEN",
    "NYLON", "POLYESTER", "PUFFER", "RAYON",
    "SLIK", "SPANDEX", "VELVET", "WOOL"
]

@app.get("/")
def root():
    return {"message": "백엔드 연결 확인 완료! 🎉"}

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")
    img = img.resize((224, 224))
    x = np.array(img) / 255.0
    x = np.expand_dims(x, axis=0)

    preds = model.predict(x)
    class_index = int(np.argmax(preds))
    label = CLASS_NAMES[class_index]
    confidence = float(preds[0][class_index])

    return {
        "filename": file.filename,
        "size_bytes": len(contents),
        "label": label,
        "class_index": class_index,
        "confidence": confidence
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
### formdata 형식
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from model_loader import predict_fabric

app = FastAPI() #fastAPI 서버 객체 생성
os.makedirs("uploads", exist_ok=True)

# CORS 설정 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

@app.get("/")
def read_root():
    return {"message": "Server is running!"}

# /predict 엔드포인트
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    filepath = f"uploads/{file.filename}"
    with open(filepath, "wb") as f:
        f.write(await file.read())

    # 모델 추론
    results = predict_fabric(filepath)

    return {
        "filename": file.filename,
        "predictions": results   # 전체 Top-3 리스트 반환
    }

#서버 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

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
  """  
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
    allow_origins=["*"],   # 모든 도메인 허용 (Wix/로컬 테스트용)
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
        "SELECT fabric, ko_name, wash_method, dry_method, special_note FROM fabric_care WHERE fabric = ?",
        (fabric_name,),
    )
    result = cur.fetchone()
    conn.close()
    return result


# 루트 확인용 엔드포인트
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

        # 2. 모델 추론 (라벨 포함)
        raw_results = predict_fabric(filepath) #?
        
        # 3. Top-3 추출
        top3 = raw_results[:3]
        top3_list = [{"label": item[0], "probability": item[1]} for item in top3]

        # 4. 상위 1개 DB 조회
        top_fabric = top3[0][0]
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

    except Exception as e:
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

# 서버 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

"""
# /predict : 이미지 업로드 → AI 예측 → DB 조회
@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    # 1. 업로드 파일 저장
    filepath = f"uploads/{file.filename}"
    with open(filepath, "wb") as f:
        f.write(await file.read())

    # 2. AI 모델 예측
    results = predict_fabric(filepath)  ##?

    # 3. 결과 형식 확인 및 변환
    if isinstance(results, list):
        # 클래스 순서와 결과 확률을 짝지어서 dict로 변환
        fabric_labels = ["acrylic", "cotton", "denim", "fur", "linen", "nylon", "polyester", "silk", "wool"]
        if isinstance(results[0], list):  # 2차원 배열인 경우
            results = results[0]
        results = dict(zip(fabric_labels, results))

    # 4. 가장 확률 높은 재질명 선택
    predicted_fabric = max(results, key=results.get)
    
    """
    # 3. 가장 확률 높은 재질명 선택
    predicted_fabric = max(results, key=results.get)

    # 4. DB에서 해당 재질 정보 가져오기
    info = get_fabric_info(predicted_fabric)
   """

    # 5. 반환값 구성
    if info:
        response = {
            "filename": file.filename,
            "predicted_fabric": predicted_fabric,
            "ko_name": info[1],
            "wash_method": info[2],
            "dry_method": info[3],
            "special_note": info[4],
            "predictions": results  # 전체 예측 확률 포함
        }
    else:
        response = {
            "filename": file.filename,
            "predicted_fabric": predicted_fabric,
            "error": "DB에서 해당 재질 정보를 찾을 수 없습니다.",
            "predictions": results
        }

    return response

# 서버 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
"""







