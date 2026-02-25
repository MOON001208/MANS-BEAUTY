import os
import time
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_products_without_ingredients() -> list:
    """ingredients_raw가 비어있는 상품 목록 조회"""
    r1 = supabase.table("products").select("id, name, brand").eq("ingredients_raw", "").execute()
    r2 = supabase.table("products").select("id, name, brand").is_("ingredients_raw", "null").execute()
    all_products = {p['id']: p for p in r1.data + r2.data}
    return list(all_products.values())


def get_driver():
    """Selenium WebDriver 초기화"""
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def fetch_ingredient_with_selenium(driver, goods_no: str) -> str:
    """
    올리브영 상품 상세 페이지에서 전성분 추출.

    구조:
      1) #tab-panels > section > ul > li:nth-child(1) 탭 클릭
      2) Accordion_accordion-btn (상품정보 제공고시) 클릭
      3) tbody > tr 중 key가 '성분' 포함된 행의 두 번째 td 추출
    """
    url = f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={goods_no}"
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        time.sleep(2.5)

        # ── Step 1: 상품정보 제공고시 탭 클릭 ──
        tab_section = driver.find_element(By.CSS_SELECTOR, "#tab-panels")
        driver.execute_script("arguments[0].scrollIntoView(true);", tab_section)
        time.sleep(0.5)

        tab_li = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#tab-panels > section > ul > li:nth-child(1)")
        ))
        driver.execute_script("arguments[0].click();", tab_li)
        time.sleep(1.5)

        # ── Step 2: '상품정보 제공고시' 아코디언 버튼 클릭 ──
        accordion_btns = driver.find_elements(By.CSS_SELECTOR, "[class*='Accordion_accordion-btn']")
        if accordion_btns:
            driver.execute_script("arguments[0].click();", accordion_btns[0])
            time.sleep(2)

        # ── Step 3: 테이블 파싱으로 전성분 추출 ──
        li_html = driver.find_element(
            By.CSS_SELECTOR, "#tab-panels > section > ul > li:nth-child(1)"
        ).get_attribute("innerHTML")
        soup = BeautifulSoup(li_html, "html.parser")

        for row in soup.find_all("tr"):
            tds = row.find_all(["td", "th"])
            if len(tds) >= 2:
                key = tds[0].get_text(strip=True)
                # "화장품법에 따라 기재해야 하는 모든 성분" 또는 "전성분" 포함 행
                if "성분" in key:
                    val = tds[1].get_text(strip=True)
                    if len(val) > 10:
                        return val[:3000]

    except Exception as e:
        logging.warning(f"  [오류] {goods_no}: {e}")

    return ""


def main():
    logging.info("전성분 누락 상품 조회를 시작합니다...")
    products = get_products_without_ingredients()

    if not products:
        logging.info("전성분이 누락된 상품이 없습니다. 종료합니다.")
        return

    logging.info(f"총 {len(products)}개 상품의 전성분 수집을 시작합니다.")

    driver = None
    success_count = 0
    fail_count = 0
    try:
        driver = get_driver()

        for idx, product in enumerate(products, 1):
            goods_no = product['id']
            logging.info(f"[{idx}/{len(products)}] {product['brand']} - {product['name'][:40]}")

            ingredients = fetch_ingredient_with_selenium(driver, goods_no)

            if ingredients and len(ingredients) > 10:
                logging.info(f"  ✅ 수집 성공: {ingredients[:60]}...")
                try:
                    supabase.table("products").update(
                        {"ingredients_raw": ingredients}
                    ).eq("id", goods_no).execute()
                    logging.info(f"  💾 DB 업데이트 완료")
                    success_count += 1
                except Exception as e:
                    logging.error(f"  ❌ DB 업데이트 실패: {e}")
                    fail_count += 1
            else:
                logging.warning(f"  ⚠️ 전성분을 찾을 수 없습니다.")
                fail_count += 1

            time.sleep(1)

    except Exception as e:
        logging.error(f"전체 프로세스 중단: {e}")
    finally:
        if driver:
            driver.quit()

    logging.info(f"\n완료: 성공 {success_count}개 / 실패 {fail_count}개")


if __name__ == "__main__":
    main()
