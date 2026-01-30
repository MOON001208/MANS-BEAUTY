# Gemini 모델 파인튜닝 가이드

## 📋 목차
1. [학습 데이터 준비](#1-학습-데이터-준비)
2. [Google AI Studio에서 파인튜닝](#2-google-ai-studio에서-파인튜닝)
3. [파인튜닝된 모델 사용](#3-파인튜닝된-모델-사용)
4. [비용 및 제한사항](#4-비용-및-제한사항)

---

## 1. 학습 데이터 준비

### 1-1. 학습 데이터 생성

```powershell
cd c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석
python code/prepare_finetune_data.py
```

**출력 파일**:
- `finetune_data/gemini_train_YYYYMMDD_HHMMSS.jsonl` (학습용)
- `finetune_data/gemini_val_YYYYMMDD_HHMMSS.jsonl` (검증용)

### 1-2. JSONL 형식 확인

```json
{"text_input": "피부가 조아지넴 ㅋㅋ", "output": "피부가 좋아지네요"}
{"text_input": "발림성이 넘 좋음!!", "output": "발림성이 너무 좋아요"}
```

---

## 2. Google AI Studio에서 파인튜닝

### 2-1. Google AI Studio 접속

1. 웹사이트 방문: https://aistudio.google.com/
2. Google 계정으로 로그인

### 2-2. 새 튜닝 작업 생성

1. 왼쪽 메뉴에서 **"Tuned models"** 클릭
2. **"New tuned model"** 버튼 클릭
3. 다음 정보 입력:

   | 항목 | 설정 값 |
   |------|---------|
   | **Base model** | `gemini-1.5-flash` 또는 `gemini-1.5-pro` |
   | **Task type** | Text generation |
   | **Training data** | `gemini_train_*.jsonl` 업로드 |
   | **Validation data** | `gemini_val_*.jsonl` 업로드 (선택) |
   | **Epochs** | 3-5 (기본값) |
   | **Learning rate** | Auto (기본값) |

4. **"Start tuning"** 클릭

### 2-3. 학습 진행 모니터링

- 학습 시간: 데이터 크기에 따라 **30분 ~ 수 시간**
- 진행 상황은 "Tuned models" 페이지에서 확인 가능
- 완료되면 이메일 알림 수신

---

## 3. 파인튜닝된 모델 사용

### 3-1. 모델 이름 확인

Google AI Studio에서 파인튜닝 완료 후:
- 모델 이름 예시: `tunedModels/review-normalizer-abc123`

### 3-2. 코드에서 사용

#### 방법 1: `gemini_text_normalizer.py` 수정

```python
# gemini_text_normalizer.py의 __init__ 메서드에서
def __init__(
    self, 
    api_key: Optional[str] = None,
    model: str = "tunedModels/review-normalizer-abc123",  # 파인튜닝된 모델
    temperature: float = 0.2,
    max_retries: int = 3
):
    # ... 기존 코드
```

#### 방법 2: 실행 시 모델 지정

```python
# run_gemini_normalization.py에서
normalizer = GeminiTextNormalizer(
    model="tunedModels/review-normalizer-abc123"
)
```

#### 방법 3: 환경변수로 설정

`.env` 파일에 추가:
```
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=tunedModels/review-normalizer-abc123
```

코드 수정:
```python
model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
normalizer = GeminiTextNormalizer(model=model)
```

### 3-3. 테스트 실행

```powershell
python code/run_gemini_normalization.py --sample 10
```

---

## 4. 비용 및 제한사항

### 4-1. 파인튜닝 비용 (2024년 기준)

| 항목 | 비용 |
|------|------|
| **학습 (Training)** | 무료 (일정 한도 내) |
| **추론 (Inference)** | 기본 모델보다 약간 높음 |

> ⚠️ 최신 가격은 [Google AI Pricing](https://ai.google.dev/pricing) 참조

### 4-2. 제한사항

- **최소 학습 데이터**: 100개 이상 권장
- **최대 학습 데이터**: 10,000개 (무료 티어)
- **입력 길이**: 최대 8,192 토큰
- **출력 길이**: 최대 2,048 토큰

### 4-3. 모범 사례

✅ **권장사항**:
- 고품질 데이터 500~2,000개 사용
- 학습/검증 데이터 8:2 비율
- 다양한 오류 패턴 포함

❌ **피해야 할 것**:
- 중복 데이터
- 너무 짧은 텍스트 (<10자)
- 너무 긴 텍스트 (>500자)

---

## 5. 트러블슈팅

### 문제 1: "Invalid training data format"

**원인**: JSONL 형식 오류

**해결**:
```powershell
# 파일 형식 확인
Get-Content finetune_data\gemini_train_*.jsonl | Select-Object -First 5
```

### 문제 2: "Insufficient training examples"

**원인**: 학습 데이터 부족

**해결**:
```python
# prepare_finetune_data.py에서 max_examples 증가
examples = create_training_examples(
    df, 
    max_examples=2000  # 1000 → 2000
)
```

### 문제 3: "Model not found"

**원인**: 모델 이름 오류

**해결**:
- Google AI Studio에서 정확한 모델 이름 복사
- `tunedModels/` 접두사 확인

---

## 6. 다음 단계

파인튜닝 완료 후:

1. ✅ 샘플 데이터로 성능 테스트
2. ✅ 기본 모델과 성능 비교
3. ✅ 전체 데이터셋 처리
4. ✅ 결과 분석 및 추가 튜닝

---

## 📚 참고 자료

- [Google AI Studio](https://aistudio.google.com/)
- [Gemini Tuning Guide](https://ai.google.dev/docs/model_tuning_guidance)
- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
