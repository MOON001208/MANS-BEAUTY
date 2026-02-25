import os
import re
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SHADE_OPTION_PATTERNS = {
    "21": ["1호", "001", "21호", "21", "라이트베이지", "라이트", "아이보리"],
    "23": ["2호", "002", "23호", "23", "베이지", "뉴트럴베이지", "내추럴베이지"],
    "25": ["3호", "003", "25호", "25", "샌드베이지", "샌드", "탠", "앰버베이지"],
}

def extract_shade_options(reviews_data):
    shade_options = {}
    for r in reviews_data:
        opt = r.get("option_name", "")
        if not opt: continue
        opt_lower = opt.lower()
        
        for shade, patterns in SHADE_OPTION_PATTERNS.items():
            if any(p.lower() in opt_lower for p in patterns):
                # Clean up option string (trimming and formatting)
                clean_opt = re.sub(r'[\(\[\{].*?[\)\]\}]', '', opt).strip()
                if not clean_opt:
                    clean_opt = opt.strip()
                if shade not in shade_options or len(clean_opt) > len(shade_options[shade]):
                    shade_options[shade] = clean_opt
    return shade_options

def main():
    print("패치 스크립트 실행 시작...")
    # Fetch all products
    products = supabase.table("products").select("id").execute().data or []
    
    for idx, p in enumerate(products):
        pid = p["id"]
        # Fetch reviews for this product
        reviews = supabase.table("reviews").select("option_name").eq("product_id", pid).execute().data or []
        
        shade_opts = extract_shade_options(reviews)
        if shade_opts:
            supabase.table("products").update({"shade_options": shade_opts}).eq("id", pid).execute()
            print(f"[{idx+1}/{len(products)}] 제품 {pid} 업데이트 완료: {shade_opts}")
        else:
            print(f"[{idx+1}/{len(products)}] 제품 {pid} 업데이트 건너뜀 (해당 호수 없음)")
            
    print("패치 완료!")

if __name__ == "__main__":
    main()
