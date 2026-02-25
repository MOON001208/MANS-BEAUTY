"""
성분 데이터 정확한 셀렉터 및 tr 번호 확인
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

GOODS_NO = "A000000198001"

options = webdriver.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

url = f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={GOODS_NO}"
driver.get(url)
time.sleep(3)

# 탭 클릭
tab_section = driver.find_element(By.CSS_SELECTOR, "#tab-panels")
driver.execute_script("arguments[0].scrollIntoView(true);", tab_section)
time.sleep(0.5)
tab_li = wait.until(EC.element_to_be_clickable(
    (By.CSS_SELECTOR, "#tab-panels > section > ul > li:nth-child(1)")
))
driver.execute_script("arguments[0].click();", tab_li)
time.sleep(2)

# 상품정보 제공고시 아코디언 클릭
accordion_btn = driver.find_elements(By.CSS_SELECTOR, "[class*='Accordion_accordion-btn']")[0]
driver.execute_script("arguments[0].click();", accordion_btn)
time.sleep(2)

# 아코디언 내부 HTML 파싱
li_html = driver.find_element(By.CSS_SELECTOR, "#tab-panels > section > ul > li:nth-child(1)").get_attribute("innerHTML")
soup = BeautifulSoup(li_html, "html.parser")

# 모든 tr 파악
rows = soup.find_all("tr")
print(f"tr 개수: {len(rows)}\n")
for i, row in enumerate(rows):
    tds = row.find_all(["td", "th"])
    if len(tds) >= 2:
        key = tds[0].get_text(strip=True)[:30]
        val = tds[1].get_text(strip=True)[:80]
    elif len(tds) == 1:
        key = tds[0].get_text(strip=True)[:30]
        val = ""
    else:
        continue
    print(f"  tr[{i+1}] key='{key}' | val='{val}'")

driver.quit()
print("\n완료")
