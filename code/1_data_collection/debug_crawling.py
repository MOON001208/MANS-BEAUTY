"""
크롤링 디버깅 - 페이지 구조 확인
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import pandas as pd
from pyshadow.main import Shadow

options = Options()
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

def debug_page_structure():
    print("=" * 60)
    print("페이지 구조 디버깅")
    print("=" * 60)

    try:
        info = pd.read_pickle('화장품최종본all.plk')
        name = info.loc[0, '이름']
        link = info.loc[0, 'url'] + '&tab=review'

        print(f"\n테스트 URL: {link}")

        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        driver.get(link)

        print("\n페이지 로딩 대기 중 (10초)...")
        time.sleep(10)

        # 페이지 타이틀 확인
        print(f"\n페이지 타이틀: {driver.title}")

        # Shadow DOM 확인
        print("\n1. Shadow DOM 요소 확인...")
        shadow = Shadow(driver)

        # div.inner 찾기
        try:
            inner_divs = shadow.find_elements('div.inner')
            print(f"   ✓ div.inner 요소 개수: {len(inner_divs)}")
        except Exception as e:
            print(f"   ✗ div.inner 찾기 실패: {e}")

        # oy-review 관련 요소 찾기
        print("\n2. oy-review 관련 요소 확인...")
        try:
            review_users = driver.find_elements(By.CSS_SELECTOR, 'oy-review-review-user')
            print(f"   ✓ oy-review-review-user 개수: {len(review_users)}")
        except Exception as e:
            print(f"   ✗ oy-review-review-user 찾기 실패: {e}")

        try:
            review_contents = driver.find_elements(By.CSS_SELECTOR, 'oy-review-review-content')
            print(f"   ✓ oy-review-review-content 개수: {len(review_contents)}")
        except Exception as e:
            print(f"   ✗ oy-review-review-content 찾기 실패: {e}")

        # 리뷰 탭 활성화 확인
        print("\n3. 리뷰 탭 확인...")
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, 'ul.tab li')
            print(f"   ✓ 탭 개수: {len(tabs)}")
            for i, tab in enumerate(tabs):
                print(f"     탭 {i+1}: {tab.text}")
        except Exception as e:
            print(f"   ✗ 탭 찾기 실패: {e}")

        # 페이지 소스 일부 저장
        print("\n4. 페이지 소스 일부 저장...")
        page_source = driver.page_source
        with open('page_source_debug.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        print("   ✓ page_source_debug.html 저장 완료")

        # 스크린샷 저장
        print("\n5. 스크린샷 저장...")
        driver.save_screenshot('screenshot_debug.png')
        print("   ✓ screenshot_debug.png 저장 완료")

        # 리뷰 영역으로 스크롤
        print("\n6. 리뷰 영역으로 스크롤 시도...")
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(3)

        # 다시 확인
        try:
            inner_divs = shadow.find_elements('div.inner')
            print(f"   ✓ 스크롤 후 div.inner 요소 개수: {len(inner_divs)}")
        except Exception as e:
            print(f"   ✗ 스크롤 후 div.inner 찾기 실패: {e}")

        driver.quit()
        print("\n" + "=" * 60)
        print("디버깅 완료")
        print("=" * 60)

    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    debug_page_structure()
