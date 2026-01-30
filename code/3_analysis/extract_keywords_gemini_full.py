
import pandas as pd
from google import genai
from google.genai import types
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment variables.")

client = genai.Client(api_key=api_key)

# Prompt Templates
BATCH_PROMPT_TEMPLATE = """
한국 화장품 리뷰 분석가로서 다음 각 리뷰에 대해 가장 중요한 상위 7개 키워드(명사 또는 설명 형용사)를 식별합니다.
제품 특징(커버력, 향기, 질감), 사용자 경험 또는 특정 구매 이유(선물, 여행)에 중점을 둡니다.
'사용', '제품', '구매'와 같은 일반적인 단어를 제외하세요.

반드시 모든 리뷰에 대해 3가지 이상의 키워드를 무조건 도출하세요.

특히, 사용감, 색상(얼굴에 색이 잘 맞는지), 유튜버 언급(스완,덱스, 문장군 등등), 커버력, 선물여부 같은 중요 키워드는 반드시 있으면 포함하세요.

Reviews:
{reviews_json}

각 객체에 'id'와 'keywords'(문자열 목록)가 있는 객체의 JSON 배열만 반환합니다.
Example:
[
  {{"id": 0, "keywords": ["커버력", "촉촉함", "지속력", "선물", "남편"]}},
  {{"id": 1, "keywords": ["들뜸", "건조함", "배송빠름"]}}
]
"""

def extract_keywords_batch(reviews_batch):
    """
    Extracts keywords for a batch of reviews using Gemini.
    """
    try:
        # Prepare input JSON
        batch_input = [
            {"id": i, "text": r[:200]} # Limit text length to save tokens
            for i, r in reviews_batch
        ]
        
        prompt = BATCH_PROMPT_TEMPLATE.format(reviews_json=json.dumps(batch_input, ensure_ascii=False))
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Parse JSON
        result = json.loads(response.text)
        
        # Map back to IDs to ensure order (though usually preserved)
        keyword_map = {item['id']: item.get('keywords', []) for item in result}
        
        return [keyword_map.get(i, []) for i, _ in reviews_batch]
        
    except Exception as e:
        print(f"Batch Error: {e}")
        # print details to debug
        import traceback
        traceback.print_exc()
        return [[] for _ in reviews_batch] # Return empty lists on failure

def main():
    base_path = Path(r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data')
    input_file = base_path / 'review_attributes_gemini.plk'
    output_file = base_path / 'review_keywords_gemini3.pkl'
    checkpoint_file = base_path / 'keyword_extraction_checkpoint3.pkl'

    print(f"Loading data from {input_file}...")
    df = pd.read_pickle(input_file)
    
    # Initialize or Load Checkpoint
    if checkpoint_file.exists():
        print(f"Resuming from checkpoint: {checkpoint_file}")
        with open(checkpoint_file, 'rb') as f:
            checkpoint_data = pd.read_pickle(f)
            processed_data = checkpoint_data['data']
            last_index = checkpoint_data['last_index']
    else:
        processed_data = [] # List of (index, keywords)
        last_index = 0
    
    # Check if we are already done
    if last_index >= len(df):
        print("Processing already complete.")
    else:
        print(f"Starting processing from index {last_index} / {len(df)}")
        
        batch_size = 20
        # Iterate in batches
        for start_idx in range(last_index, len(df), batch_size):
            end_idx = min(start_idx + batch_size, len(df))
            batch_slice = df.iloc[start_idx:end_idx]
            
            # Prepare batch: list of (index, text)
            # Use 'gemini_normalized' if available, else '리뷰내용_정제'
            text_col = 'gemini_normalized' if 'gemini_normalized' in df.columns else '리뷰내용_정제'
            reviews_batch = [(idx, str(row[text_col])) for idx, row in batch_slice.iterrows()]
            
            # Call API
            keywords_batch = extract_keywords_batch(reviews_batch)
            
            # Store results
            for i, keywords in enumerate(keywords_batch):
                global_idx = reviews_batch[i][0]
                processed_data.append({'index': global_idx, 'gemini_keywords': keywords})
            
            # Save Checkpoint every 5 batches (100 reviews)
            if (start_idx // batch_size) % 5 == 0:
                print(f"Saving checkpoint at index {end_idx}...")
                pd.to_pickle({'data': processed_data, 'last_index': end_idx}, checkpoint_file)
                
            print(f"Processed {end_idx}/{len(df)} reviews...")
            time.sleep(1) # Rate limit buffer
            
        # Final Save
        print("Processing complete. Saving final file.")
        pd.to_pickle({'data': processed_data, 'last_index': len(df)}, checkpoint_file)

    # Merge back to DataFrame
    print("Merging results...")
    results_df = pd.DataFrame(processed_data)
    results_df.set_index('index', inplace=True)
    
    # Update main DF
    df['gemini_keywords'] = results_df['gemini_keywords']
    
    # Save final output
    df.to_pickle(output_file)
    print(f"Saved final data to {output_file}")
    
    # Remove checkpoint
    if checkpoint_file.exists():
        # os.remove(checkpoint_file) # Optional: keep it for safety for now
        print("Checkpoint file kept for safety.")

if __name__ == "__main__":
    main()
