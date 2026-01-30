
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
from tqdm import tqdm

# 1. Load Data
file_path = r"c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\final_review.plk"
print(f"Loading data from {file_path}...")
df = pd.read_pickle(file_path)

# 2. Preprocess: Clean URLs and Get unique products
# Remove '&review=...' from the URL
df['상품링크_clean'] = df['상품링크'].apply(lambda x: x.split('=review')[0] if isinstance(x, str) else x)

# Drop duplicates based on the clean URL
products_df = df[['상품이름', '상품링크_clean']].drop_duplicates(subset=['상품링크_clean'])
print(f"Total unique products found after cleaning URLs: {len(products_df)}")

# 3. Selenium Setup
options = webdriver.ChromeOptions()
# options.add_argument('--headless') # Run in headless mode if desired
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 4. Collection Loop
results = []

print("Starting scraping...")
for index, row in tqdm(products_df.iterrows(), total=products_df.shape[0]):
    product_name = row['상품이름']
    url = row['상품링크_clean']
    
    ingredient_info = "수집실패" # Default value
    
    try:
        driver.get(url)
        time.sleep(2) # Wait for page load
        
        # Scroll down twice
        body = driver.find_element(By.TAG_NAME, 'body')
        for _ in range(2):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.5)
            
        # Click the specific button (Tab)
        # #tab-panels > section > ul > li:nth-child(1) > button
        button_selector = "#tab-panels > section > ul > li:nth-child(1) > button"
        wait = WebDriverWait(driver, 10)
        button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector)))
        button.click()
        
        time.sleep(1) # Wait for tab content to render
        
        # Extract ingredients
        # #tab-panels > section > ul > li:nth-child(1) > div > div > table > tbody > tr:nth-child(7) > td
        data_selector = "#tab-panels > section > ul > li:nth-child(1) > div > div > table > tbody > tr:nth-child(7) > td"
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, data_selector)))
        
        ingredient_info = element.text
        
    except Exception as e:
        # print(f"Error scraping {product_name}: {e}")
        pass
    
    results.append({
        '상품이름': product_name,
        '상품링크': url,
        '전성분': ingredient_info
    })
    
    # Optional: Delay to be polite
    time.sleep(1)

driver.quit()

# 5. Create DataFrame and Save
result_df = pd.DataFrame(results)

# Save to the same directory
output_path = r"c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\data\product_ingredients.csv"
result_df.to_csv(output_path, index=False, encoding='utf-8-sig') # utf-8-sig for Korean Excel compatibility

print(f"Scraping completed. Saved to {output_path}")
print(result_df.head())