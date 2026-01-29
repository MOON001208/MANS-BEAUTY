# -*- coding: utf-8 -*-
"""
[Gemini API 기반 텍스트 정규화 모듈]

한국어 화장품 리뷰의 맞춤법 교정 및 텍스트 정규화를 수행합니다.
Google Gemini API를 사용하여 배치 처리를 지원합니다.

사용법:
    from gemini_text_normalizer import GeminiTextNormalizer
    
    normalizer = GeminiTextNormalizer()
    corrected = normalizer.normalize_single("피부가 조아지넴")
    # 결과: "피부가 좋아지네요"
"""

import os
import json
import time
import re
from typing import List, Dict, Optional, Union
from tqdm import tqdm


class GeminiTextNormalizer:
    """
    Gemini API를 사용한 한국어 리뷰 맞춤법 교정 및 정규화 클래스
    
    Attributes:
        client: Gemini API 클라이언트
        model: 사용할 Gemini 모델명
        temperature: 생성 다양성 제어 (낮을수록 일관된 출력)
        max_retries: API 오류 시 최대 재시도 횟수
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
        temperature: float = 0.2,
        max_retries: int = 3
    ):
        """
        GeminiTextNormalizer 초기화
        
        Args:
            api_key: Gemini API 키 (None이면 환경변수 GEMINI_API_KEY 사용)
            model: 사용할 Gemini 모델명
            temperature: 생성 다양성 제어 (0.0 ~ 1.0)
            max_retries: API 오류 시 최대 재시도 횟수
        """
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai 패키지가 필요합니다. "
                "'pip install google-genai' 명령으로 설치하세요."
            )
        
        # .env 파일에서 환경변수 로드 (선택적)
        try:
            from dotenv import load_dotenv
            load_dotenv()  # .env 파일이 있으면 자동 로드
        except ImportError:
            pass  # python-dotenv가 없어도 환경변수로 작동
        
        # API 키 설정
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        elif not os.environ.get("GEMINI_API_KEY"):
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다.\n"
                "다음 중 하나의 방법으로 API 키를 설정하세요:\n"
                "1. .env 파일에 GEMINI_API_KEY=your_key 추가\n"
                "2. 환경변수로 설정: $env:GEMINI_API_KEY='your_key'\n"
                "3. 코드에서 직접 전달: GeminiTextNormalizer(api_key='your_key')"
            )
        
        self.client = genai.Client()
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        
        # 시스템 프롬프트 정의
        self._system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        """맞춤법 교정을 위한 시스템 프롬프트 생성"""
        return """당신은 한국어 화장품 리뷰를 교정하는 전문가입니다.

## 교정 규칙
1. **맞춤법 교정**: 띄어쓰기, 철자 오류, 문법 오류를 교정합니다.
2. **속어 변환**: 비표준어, 인터넷 용어를 표준어로 변환합니다.
   - 예: "조아요" → "좋아요", "넘" → "너무", "앜" → "아"
3. **감정 유지**: 원래 리뷰의 의미와 감정을 반드시 유지합니다.
4. **최소 수정**: 과도하게 수정하지 않습니다. 필요한 부분만 교정합니다.

## 입출력 형식
- 입력: JSON 배열 [{"id": 1, "text": "원본텍스트"}, ...]
- 출력: JSON 배열 [{"id": 1, "text": "교정된텍스트"}, ...]
- 반드시 동일한 id를 유지하고, 유효한 JSON만 출력하세요.
- 다른 설명 없이 JSON 배열만 출력하세요."""
    
    def _create_batch_prompt(self, texts: List[Dict[int, str]]) -> str:
        """배치 처리를 위한 프롬프트 생성"""
        return json.dumps(texts, ensure_ascii=False, indent=None)
    
    def _parse_json_response(self, response_text: str) -> List[Dict]:
        """
        Gemini 응답에서 JSON 배열 추출 및 파싱
        
        Args:
            response_text: Gemini API 응답 텍스트
            
        Returns:
            파싱된 JSON 배열 (리스트)
        """
        # JSON 코드 블록에서 추출 시도
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            response_text = json_match.group(1)
        
        # 직접 JSON 배열 추출 시도
        array_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response_text)
        if array_match:
            response_text = array_match.group(0)
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 텍스트: {response_text[:500]}...")
            return []
    
    def _call_api_with_retry(self, prompt: str) -> str:
        """
        재시도 로직이 포함된 API 호출
        
        Args:
            prompt: 사용자 프롬프트
            
        Returns:
            API 응답 텍스트
        """
        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[
                        {"role": "user", "parts": [{"text": self._system_prompt}]},
                        {"role": "model", "parts": [{"text": "네, 이해했습니다. JSON 형식으로 교정된 리뷰를 출력하겠습니다."}]},
                        {"role": "user", "parts": [{"text": prompt}]}
                    ],
                    config={
                        "temperature": self.temperature,
                    }
                )
                return response.text
                
            except Exception as e:
                wait_time = (2 ** attempt) + 1  # Exponential backoff
                print(f"API 오류 (시도 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    print(f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    raise
        
        return ""
    
    def normalize_single(self, text: str) -> str:
        """
        단일 리뷰 텍스트 정규화
        
        Args:
            text: 교정할 원본 텍스트
            
        Returns:
            교정된 텍스트
        """
        if not text or not isinstance(text, str) or len(text.strip()) < 2:
            return text
        
        batch_input = [{"id": 1, "text": text}]
        prompt = self._create_batch_prompt(batch_input)
        
        response_text = self._call_api_with_retry(prompt)
        parsed = self._parse_json_response(response_text)
        
        if parsed and len(parsed) > 0:
            return parsed[0].get("text", text)
        return text
    
    def normalize_batch(
        self, 
        texts: List[str], 
        batch_size: int = 20,
        delay_between_batches: float = 1.0,
        show_progress: bool = True
    ) -> List[str]:
        """
        여러 리뷰 텍스트 배치 정규화
        
        Args:
            texts: 교정할 텍스트 리스트
            batch_size: 한 번의 API 호출에 처리할 텍스트 수
            delay_between_batches: 배치 간 대기 시간 (초)
            show_progress: 진행률 표시 여부
            
        Returns:
            교정된 텍스트 리스트 (원본과 동일한 순서)
        """
        results = [""] * len(texts)
        
        # 유효한 텍스트만 필터링
        valid_items = [
            (i, t) for i, t in enumerate(texts) 
            if t and isinstance(t, str) and len(t.strip()) >= 2
        ]
        
        # 짧은 텍스트는 원본 유지
        for i, t in enumerate(texts):
            if not t or not isinstance(t, str) or len(t.strip()) < 2:
                results[i] = t if t else ""
        
        # 배치 처리
        num_batches = (len(valid_items) + batch_size - 1) // batch_size
        iterator = range(0, len(valid_items), batch_size)
        
        if show_progress:
            iterator = tqdm(iterator, total=num_batches, desc="맞춤법 교정 진행률")
        
        for batch_start in iterator:
            batch_items = valid_items[batch_start:batch_start + batch_size]
            
            # 배치 입력 준비
            batch_input = [
                {"id": idx, "text": text} 
                for idx, text in batch_items
            ]
            
            prompt = self._create_batch_prompt(batch_input)
            
            try:
                response_text = self._call_api_with_retry(prompt)
                parsed = self._parse_json_response(response_text)
                
                # 응답을 결과에 매핑
                response_map = {item["id"]: item["text"] for item in parsed}
                
                for original_idx, original_text in batch_items:
                    corrected = response_map.get(original_idx, original_text)
                    
                    # 안전장치: AI가 텍스트를 너무 길게 늘렸다면 원본 유지
                    if len(corrected) > len(original_text) * 2 or len(corrected) > len(original_text) + 50:
                        results[original_idx] = original_text
                    else:
                        results[original_idx] = corrected
                        
            except Exception as e:
                print(f"배치 처리 오류: {e}")
                # 오류 시 원본 유지
                for original_idx, original_text in batch_items:
                    results[original_idx] = original_text
            
            # 배치 간 대기 (속도 제한 방지)
            if batch_start + batch_size < len(valid_items):
                time.sleep(delay_between_batches)
        
        return results


def test_normalizer():
    """테스트 함수: 샘플 리뷰로 정규화 기능 테스트"""
    test_reviews = [
        "피부가 너무 조아지넴 ㅋㅋㅋ",
        "발림성이 넘 좋음!! 완전 추천해여~~",
        "가격대비 괜찬은듯? 근데 향이 좀 쎔",
        "촉촉하고 끈적임 없어서 굿굿",
        "도움이 돼요 1명이 도움이됨",
    ]
    
    print("=" * 60)
    print(" Gemini Text Normalizer 테스트")
    print("=" * 60)
    
    try:
        normalizer = GeminiTextNormalizer()
        
        print("\n[단일 리뷰 테스트]")
        single_result = normalizer.normalize_single(test_reviews[0])
        print(f"원본: {test_reviews[0]}")
        print(f"교정: {single_result}")
        
        print("\n[배치 리뷰 테스트]")
        batch_results = normalizer.normalize_batch(test_reviews, batch_size=5)
        
        for original, corrected in zip(test_reviews, batch_results):
            print(f"원본: {original}")
            print(f"교정: {corrected}")
            print("-" * 40)
            
    except Exception as e:
        print(f"테스트 오류: {e}")
        print("GEMINI_API_KEY 환경변수가 설정되어 있는지 확인하세요.")


if __name__ == "__main__":
    test_normalizer()
