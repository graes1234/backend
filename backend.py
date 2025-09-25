from fastapi import FastAPI, Form
import base64
import os
from model_loader import predict_fabric

app = FastAPI()
os.makedirs("/tmp", exist_ok=True)

@app.get("/")
def root():
    return {"message": "서버 연결 확인 완료!"}

@app.post("/predict_base64")
async def predict_base64(fileName: str = Form(...), fileBase64: str = Form(...)):
    # 1️⃣ Base64 → 바이너리 디코딩
    file_bytes = base64.b64decode(fileBase64)

    # 2️⃣ 임시 파일 저장
    temp_path = f"/tmp/{fileName}"
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    # 3️⃣ 모델 추론
    results = predict_fabric(temp_path)

    return {"predictions": results}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)








