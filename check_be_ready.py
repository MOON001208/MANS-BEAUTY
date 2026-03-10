import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv('code/7_advanced_recommender/scraper/.env')
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

supabase: Client = create_client(url, key)

res = supabase.table('products').select('*').ilike('name', '%블루 파운데이션%').execute()
for p in res.data:
    print(f"ID: {p['id']}, Name: {p['name']}, Reviews: {p['review_count']}, Rating: {p['star_rating']}, Data URL: {p.get('product_url', '')}")
