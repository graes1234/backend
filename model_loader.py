
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
import os

# 모델 경로
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ROOT_DIR, "final_model_1.keras")

# 모델 로드
model = load_model(MODEL_PATH)

# 클래스 이름 목록 (모델 학습 시 사용한 순서대로)
class_names = [
    "ACRYLIC", "COTTON", "DENIM", "FUR", "LINEN", "NYLON", 
    "POLYESTER", "PUFFER", "RAYON", "SLIK", "SPANDEX", "VELVET", "WOOL"
]

def predict_fabric(filepath: str):
    # 2. 이미지 불러오기 & 전처리
    img = image.load_img(filepath, target_size=(224, 224))  # 모델 입력 크기에 맞춤
    x = image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = x / 255.0  # 정규화

    # 3. 추론
    preds = model.predict(x)[0]
    # 확률 기반 결과 리스트로, 소수점 2자리
    results = [{"label": class_names[i], "score": round(float(preds[i]), 2)} for i in range(len(class_names))]
    # 점수 높은 순으로 정렬 후 상위 3개만
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:3]
    return results

