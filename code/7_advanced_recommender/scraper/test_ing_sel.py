from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def fetch_with_selenium():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    
    goods_no = "A000000198001"
    url = f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={goods_no}"
    print("Loading", url)
    driver.get(url)
    time.sleep(3)
    
    # 1. 클릭 등 인터랙션이 필요한지?
    # 상품정보 제공 고시 버튼 또는 탭 클릭이 필요할 수 있음
    try:
        # 탭 중 "상품정보제공고시" 탭을 찾아서 클릭
        tab = driver.find_element(By.XPATH, "//*[contains(text(), '상품정보제공고시')]")
        if tab:
            driver.execute_script("arguments[0].click();", tab)
            print("Clicked 상품정보제공고시")
            time.sleep(2)
    except Exception as e:
        print("상품정보제공고시 탭/버튼 클릭 안됨:", e)
        pass

    source = driver.page_source
    if "전성분" in source:
        print("전성분 is in the page source!")
        # let's find the text
        import re
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(source, "html.parser")
        for dt in soup.find_all("dt"):
            if "전성분" in dt.get_text() or "전 성분" in dt.get_text():
                dd = dt.find_next_sibling(["dd", "td"])
                if dd:
                    print("INGREDIENTS (by dt):", dd.get_text(strip=True)[:100])
                    break
        for th in soup.find_all("th"):
            if "전성분" in th.get_text() or "전 성분" in th.get_text():
                td = th.find_next_sibling("td")
                if td:
                    print("INGREDIENTS (by th):", td.get_text(strip=True)[:100])
                    break
    else:
        print("전성분 is still NOT in the page source!")

    # Check network requests (Performance logs)
    # Actually, let's just use the rendered source.
    driver.quit()

fetch_with_selenium()
