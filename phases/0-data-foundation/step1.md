# Step 1: 백엔드 의존성 설치 및 환경 설정

## 목표
Petro-AX 백엔드의 Python 의존성을 설치하고, 환경 변수 관리 구조를 세팅한다.

## 작업

### 1. requirements.txt 업데이트
`backend/requirements.txt`에 아래 패키지를 추가한다:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
httpx==0.27.2
pandas==2.2.3
numpy==1.26.4
xgboost==2.1.1
scikit-learn==1.5.2
chromadb==0.5.7
google-generativeai==0.8.3
joblib==1.4.2
pytest==8.3.3
pytest-asyncio==0.24.0
```

### 2. 환경 변수 설정 파일
`backend/.env.example` 파일을 생성한다:

```env
# Required API Keys
GEMINI_API_KEY=your-gemini-api-key
EIA_API_KEY=your-eia-api-key
FRED_API_KEY=your-fred-api-key

# Optional API Keys
NEWS_API_KEY=your-newsapi-key
GNEWS_API_KEY=your-gnews-api-key

# App Settings
APP_ENV=development
LOG_LEVEL=INFO
DATA_CACHE_DIR=data
```

### 3. config.py 업데이트
`backend/app/core/config.py`를 업데이트하여 모든 API 키와 설정을 관리한다:
- pydantic-settings의 `BaseSettings`를 사용
- `.env` 파일에서 자동 로드
- 필수 키(GEMINI, EIA, FRED)가 없으면 시작 시 경고 출력

### 4. main.py 업데이트
`backend/app/main.py`에 CORS 미들웨어를 추가한다:
- `http://localhost:5173` (프론트엔드 개발 서버) 허용
- Health check 엔드포인트(`GET /health`)가 config 로딩 상태도 반환하도록 수정

### 5. 데이터 디렉토리 구조 생성
```
backend/data/
├── raw/           # 원시 API 응답 캐시
└── processed/     # 전처리된 데이터
backend/ml/
└── models/        # 학습된 모델 파일
```
각 디렉토리에 `.gitkeep` 파일을 생성한다.

## AC (Acceptance Criteria)
1. `cd backend && pip install -r requirements.txt`가 에러 없이 완료된다
2. `backend/app/core/config.py`에서 `Settings` 클래스가 `.env`를 읽어온다
3. `cd backend && uvicorn app.main:app --port 8000` 으로 서버가 정상 기동된다
4. `GET /health` 응답에 config 상태가 포함된다
5. `backend/data/raw/`, `backend/data/processed/`, `backend/ml/models/` 디렉토리가 존재한다
