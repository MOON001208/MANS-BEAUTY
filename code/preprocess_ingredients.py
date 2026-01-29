import pandas as pd
import re
import pickle
import numpy as np

# Defines
INPUT_FILE = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\product_ingredients.csv'
OUTPUT_FILE = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\product_ingredients_clean.plk'

# Common Comedogenic Ingredients (Placeholder List for Analysis)
TROUBLE_INGREDIENTS = {
    'isopropyl_myristate', 'isopropyl_palmitate', 'ethylhexyl_palmitate', 
    'cocoa_butter', 'coconut_oil', 'algae_extract', 'carrageenan', 
    'sodium_lauryl_sulfate', 'wheat_germ_oil'
}

def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Standardize
    text = text.replace('\n', ' ').strip()
    return text

def parse_multi_ingredients(row):
    """
    Parses strings like "[Product1] Ing1, Ing2 [Product2] Ing3, Ing4"
    Returns the ingredient text relevant to the main product name.
    """
    full_text = clean_text(row['ingredients_raw'])
    product_name = clean_text(row['product_name'])
    
    # Check if it has the [...] structure
    if not full_text:
        return ""
    
    # Regex to find [Name] Content
    # Looks for [ ... ] followed by text until next [ or end
    matches = re.findall(r'\[(.*?)\](.*?)(?=\[|$)', full_text)
    
    if not matches:
        return full_text # Return as is if no brackets found
        
    # Heuristic: Find the match where the name is most similar to product_name
    # Or simply: if only one match, return it. If multiple, try to exclude 'Cleanser', 'Toner' if main is 'Cushion'
    
    best_candidate = ""
    max_score = -1
    
    for sub_name, ing_text in matches:
        sub_name = sub_name.strip()
        ing_text = ing_text.strip()
        
        # Simple scoring: Overlap of words (Token overlap)
        main_tokens = set(product_name.split())
        sub_tokens = set(sub_name.split())
        
        score = len(main_tokens.intersection(sub_tokens))
        
        # Penalty for being a 'GIFT' or 'CLEANSER' if the main product doesn't say Cleanser
        if '클렌징' in sub_name and '클렌징' not in product_name:
            score -= 5
        if '증정' in sub_name:
            score -= 5
            
        if score > max_score:
            max_score = score
            best_candidate = ing_text
            
    # Fallback to the longest text if scoring is ambiguous or low?
    # Actually, often the first item is the main item.
    if max_score <= 0 and not best_candidate:
        # Just take the first one or the longest one
        longest = sorted(matches, key=lambda x: len(x[1]), reverse=True)[0]
        return longest[1].strip()
        
    return best_candidate

def get_ingredient_list(text):
    if not text:
        return []
    # Split by comma
    items = text.split(',')
    # Clean items
    cleaned = [item.strip() for item in items if item.strip()]
    return cleaned

def count_trouble_ingredients(ing_list):
    count = 0
    trouble_found = []
    for ing in ing_list:
        # Simple normalization for matching (remove spaces, lower)
        norm_ing = ing.lower().replace(" ", "")
        # Check against simple trouble list
        # This is non-trivial in Korean without a map, but we try partial match
        # Actually without a dictionary this is hard. We will return 0 for now or try basic english mappings if present.
        # Since text is Korean, we skip this unless we have a mapping.
        pass
    return 0

def main():
    print("Loading data...")
    # Load with header assumption based on previous inspection
    df = pd.read_csv(INPUT_FILE)
    
    # Rename columns if needed (based on inspection)
    # Expected: '상품이름', 'link', '전성분'
    # Check actual columns
    print(f"Columns found: {df.columns.tolist()}")
    
    if '상품이름' not in df.columns or '전성분' not in df.columns:
        print("Error: Expected columns '상품이름' and '전성분' not found.")
        # Try to infer by index
        df.columns = ['product_name', 'link', 'ingredients_raw']
    else:
        df = df.rename(columns={'상품이름': 'product_name', '전성분': 'ingredients_raw'})

    print("Processing ingredients...")
    # 1. Parse sets to get single ingredient string
    df['ingredients_clean_str'] = df.apply(parse_multi_ingredients, axis=1)
    
    # 2. Convert to list
    df['ingredients_list'] = df['ingredients_clean_str'].apply(get_ingredient_list)
    
    # 3. Basic Stats
    df['ingredient_count'] = df['ingredients_list'].apply(len)
    
    # 4. Preview
    print("\nProcessed Data Preview:")
    print(df[['product_name', 'ingredients_clean_str']].head())
    
    # 5. Save
    print(f"\nSaving to {OUTPUT_FILE}...")
    df.to_pickle(OUTPUT_FILE)
    print("Done.")

if __name__ == "__main__":
    main()
