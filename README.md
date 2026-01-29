# Gemini API 기반 리뷰 정규화 시스템

## 설치 방법

### 1. 필수 패키지 설치

```bash
pip install google-genai python-dotenv pandas tqdm
```

### 2. API 키 설정

#### 방법 1: .env 파일 사용 (권장)

1. `.env.example` 파일을 `.env`로 복사:
   ```bash
   copy .env.example .env
   ```

2. `.env` 파일을 열고 실제 API 키 입력:
   ```
   GEMINI_API_KEY=your_actual_api_key_here
   ```

3. `.env` 파일은 자동으로 `.gitignore`에 포함되어 GitHub에 올라가지 않습니다.

#### 방법 2: 환경변수 직접 설정

```powershell
$env:GEMINI_API_KEY = "your_api_key_here"
```

#### 방법 3: 코드에서 직접 전달

```python
normalizer = GeminiTextNormalizer(api_key="your_api_key_here")
```

## 사용법

### 샘플 테스트 (10개 리뷰)

```bash
cd c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석
python code/run_gemini_normalization.py --sample 10
```

### 제한된 처리 (100개)

```bash
python code/run_gemini_normalization.py --limit 100 --batch-size 20
```

### 전체 처리

```bash
python code/run_gemini_normalization.py
```

## GitHub 업로드 전 체크리스트

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] `.env.example` 파일에는 실제 API 키가 없는지 확인
- [ ] 코드에 하드코딩된 API 키가 없는지 확인

## 파일 구조

```
남성화장품시장분석/
├── .env.example          # API 키 설정 예시 (GitHub에 올림)
├── .env                  # 실제 API 키 (GitHub에 올리지 않음)
├── .gitignore           # .env 파일 제외 설정
├── code/
│   ├── gemini_text_normalizer.py    # 핵심 라이브러리
│   └── run_gemini_normalization.py  # 실행 스크립트
└── data/
    └── (데이터 파일들)
```

## 보안 주의사항

⚠️ **절대로 다음 파일들을 GitHub에 올리지 마세요:**
- `.env` (실제 API 키 포함)
- `*.plk`, `*.pkl` (데이터 파일)
- `*checkpoint*.plk` (체크포인트 파일)
