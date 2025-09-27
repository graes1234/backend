
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
 
# URL 형식
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from PIL import Image
from io import BytesIO
from model_loader import predict_fabric  # PIL Image 입력 받는 함수

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class FileUrl(BaseModel):
    file_url: str

@app.get("/")
def read_root():
    return {"message": "Server is running!"}

@app.post("/predict")
async def predict(data: FileUrl):
    try:
        # 1. 이미지 다운로드
        response = requests.get(data.file_url)
        response.raise_for_status()  # 실패 시 예외 발생

        # 2. 이미지 열기
        image = Image.open(BytesIO(response.content))

        # 3. 모델 추론
        # 기존 코드에서는 filepath 사용, URL 방식에서는 image 객체 사용
        results = predict_fabric(image)  # PIL Image 객체 전달
        #빈 배열일 경우
        if not results:
            results = []

        # 4. 안전하게 반환
        return {"predictions": results}

    except requests.exceptions.RequestException as e:
        # 다운로드 실패
        return {"predictions": [], "error": f"파일 다운로드 실패: {str(e)}"}
    except Exception as e:
        # PIL 열기, 모델 추론 등 기타 에러
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
"""
#formdata
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
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
        results = predict_fabric(filepath)
        if not results:
            results = []

        return {"filename": file.filename, "predictions": results}

    #except Exception as e:
        #return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}
    except requests.exceptions.RequestException as e:
        # 다운로드 실패
        return {"predictions": [], "error": f"파일 다운로드 실패: {str(e)}"}
    except Exception as e:
        # PIL 열기, 모델 추론 등 기타 에러
        return {"predictions": [], "error": f"서버 처리 중 에러: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)


