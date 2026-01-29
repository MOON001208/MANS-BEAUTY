"""
리뷰 크롤링 수정 버전 - 리뷰 탭 클릭 방식
전체 상품에 대해 크롤링 실행
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
from pyshadow.main import Shadow

options = Options()
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
# 필요시 headless 모드로 실행하려면 아래 주석 해제
# options.add_argument("--headless")
# options.add_argument("--disable-gpu")
# options.add_argument("--no-sandbox")

def click_review_tab(driver):
    """리뷰 탭 클릭"""
    try:
        # 방법 1: 텍스트로 찾기
        review_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '리뷰')]"))
        )
        review_tab.click()
        print("   ✓ 리뷰 탭 클릭 성공 (방법 1)")
        time.sleep(3)
        return True
    except:
        pass

    try:
        # 방법 2: a 태그로 찾기
        review_tab = driver.find_element(By.XPATH, "//a[contains(text(), '리뷰')]")
        driver.execute_script("arguments[0].click();", review_tab)
        print("   ✓ 리뷰 탭 클릭 성공 (방법 2)")
        time.sleep(3)
        return True
    except:
        pass

    try:
        # 방법 3: CSS selector
        review_tab = driver.find_element(By.CSS_SELECTOR, "[href*='review'], [data-tab='review']")
        driver.execute_script("arguments[0].click();", review_tab)
        print("   ✓ 리뷰 탭 클릭 성공 (방법 3)")
        time.sleep(3)
        return True
    except:
        pass

    print("   ✗ 리뷰 탭을 찾지 못했습니다")
    return False

def scroll_and_crawl(driver, target_count=100):
    """리뷰 수집 함수 - target_count만큼 수집"""
    name_list, skin_list, star_list = [], [], []
    date_list, good_list, text_list = [], [], []
    collected_reviews = set()

    # 바닥 확인 실패 횟수 카운트 (연속 3번 바닥이면 진짜 종료)
    no_new_count = 0

    while len(name_list) < target_count:
        try:
            shadow = Shadow(driver)
            users = shadow.find_elements('div.inner')

            initial_count = len(name_list)  # 루프 시작 전 수집 개수

            for user in users:
                try:
                    user_hosts = user.find_elements(By.CSS_SELECTOR, 'oy-review-review-user')
                    text_hosts = user.find_elements(By.CSS_SELECTOR, 'oy-review-review-content')

                    if not user_hosts or not text_hosts:
                        continue

                    text_shadow = text_hosts[0].shadow_root
                    t_el = text_shadow.find_elements(By.CSS_SELECTOR, 'div.content')
                    review_text = t_el[0].text.strip() if t_el else ""

                    # 중복 체크 및 빈 내용 제외
                    if not review_text or review_text in collected_reviews:
                        continue

                    user_host = user_hosts[0]
                    user_shadow = user_host.shadow_root
                    n_el = user_shadow.find_elements(By.CSS_SELECTOR, 'div.info div.name')
                    s_el = user_shadow.find_elements(By.CSS_SELECTOR, 'div.info div.skin-types')
                    star_icons = user.find_elements(By.CSS_SELECTOR, "div.meta div.rating oy-review-star-icon")
                    rating_score = 0
                    for icon in star_icons:
                        try:
                            icon_shadow = icon.shadow_root
                            path_el = icon_shadow.find_element(By.CSS_SELECTOR, "path")
                            if path_el.get_attribute("fill") != "none":
                                rating_score += 1
                        except:
                            continue
                    date = user.find_elements(By.CSS_SELECTOR, 'div.common-info span.date')
                    goods_option = user.find_elements(By.CSS_SELECTOR, 'div.goods-option')

                    name_list.append(n_el[0].text if n_el else "이름없음")
                    skin_list.append(s_el[0].text.replace('\n', ',') if s_el else None)
                    text_list.append(review_text.replace('\n', ' '))
                    star_list.append(rating_score)
                    date_list.append(date[0].text if date else None)
                    good_list.append(goods_option[0].text if goods_option else None)

                    collected_reviews.add(review_text)

                    if len(name_list) >= target_count:
                        break
                except:
                    continue

            # 무한스크롤
            driver.execute_script("window.scrollBy(0, 2000);")  # 스크롤 폭을 조금 더 크게
            time.sleep(4)  # 네트워크 속도에 따라 3~4초 권장

            # 수집된 개수가 늘지 않았다면?
            if len(name_list) == initial_count:
                no_new_count += 1
                print(f"새로운 리뷰 로딩 대기 중... ({no_new_count}/3)")
            else:
                no_new_count = 0  # 새 데이터 수집되면 카운트 초기화

            if no_new_count >= 3:  # 3번 연속으로 새 리뷰가 없으면 종료
                print("더 이상 불러올 리뷰가 없어 수집을 종료합니다.")
                break

            print(f"현재 수집된 리뷰: {len(name_list)}개...")

        except Exception as e:
            print(f"크롤링 중 오류: {e}")
            break

    return name_list, skin_list, star_list, date_list, good_list, text_list


def main_crawling():
    """전체 상품 크롤링 실행"""
    print("=" * 70)
    print("올리브영 리뷰 크롤링 시작 (수정 버전)")
    print("=" * 70)

    driver = None
    all_data = []

    try:
        # 데이터 파일 읽기
        print("\n1. 데이터 파일 로딩...")
        info = pd.read_pickle('화장품최종본all.plk')
        name_list = info.loc[:, '이름'].to_list()
        link_list = info.loc[:, 'url'].to_list()  # &tab=review 제거
        ratings = info.loc[:, '리뷰수'].str.replace(",", "").str.extract('([0-9]+)')[0].astype(int).to_list()

        print(f"   ✓ 총 {len(info)}개 상품 로드")
        print(f"   ✓ 목표 리뷰 수: {sum(ratings)}개")

        # Chrome 드라이버 초기화
        print("\n2. 브라우저 실행...")
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        print("   ✓ 드라이버 초기화 완료")

        # 각 상품별 크롤링
        print("\n3. 크롤링 시작...\n")
        start_time = time.time()

        for idx, (name, link, rate) in enumerate(zip(name_list, link_list, ratings), 1):
            try:
                print(f"\n[{idx}/{len(name_list)}] >>> {name} 상품 수집 시작")
                print(f"목표 리뷰 수: {rate}개")
                print(f"링크: {link[:80]}...")

                # 해당 상품 페이지 접속
                driver.get(link)
                time.sleep(5)  # 페이지 로딩 대기

                # 리뷰 탭 클릭
                if not click_review_tab(driver):
                    print(f"⚠ 리뷰 탭 클릭 실패 - 다음 상품으로 이동")
                    continue

                # 리뷰 수집
                names, skins, stars, dates, goods, texts = scroll_and_crawl(driver, target_count=rate)

                # 수집된 데이터를 리스트에 임시 저장
                for j in range(len(names)):
                    all_data.append({
                        '상품이름': name,
                        '상품링크': link,
                        '작성자': names[j],
                        '피부타입': skins[j],
                        '별점': stars[j],
                        '날짜': dates[j],
                        '옵션': goods[j],
                        '리뷰내용': texts[j]
                    })

                print(f"✓ 성공: {len(names)}개의 리뷰 수집 완료")
                print(f"   현재까지 총 수집: {len(all_data)}개")

            except Exception as e:
                print(f"✗ 오류 발생: {link}에서 데이터 수집 중 문제가 생겼습니다.")
                print(f"   오류 내용: {e}")
                continue

        # 결과 저장
        print("\n" + "=" * 70)
        print("크롤링 완료 - 데이터 저장 중...")
        print("=" * 70)

        df = pd.DataFrame(all_data)

        # CSV와 Pickle 형식으로 저장
        df.to_csv('화장품리뷰_수정본.csv', index=False, encoding='utf-8-sig')
        df.to_pickle('화장품리뷰_수정본.plk')

        elapsed_time = time.time() - start_time

        print(f"\n최종 결과:")
        print(f"  - 총 수집 리뷰: {len(df)}개")
        print(f"  - 처리 상품: {len(name_list)}개")
        print(f"  - 소요 시간: {elapsed_time/60:.1f}분")
        print(f"\n저장 파일:")
        print(f"  - 화장품리뷰_수정본.csv")
        print(f"  - 화장품리뷰_수정본.plk")
        print("\n✓✓ 크롤링 완료! ✓✓")
        print("=" * 70)

    except FileNotFoundError:
        print("\n✗ 오류: '화장품최종본all.plk' 파일을 찾을 수 없습니다.")
        print("   현재 디렉토리에 파일이 있는지 확인하세요.")
    except Exception as e:
        print(f"\n✗ 치명적 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("\n브라우저 종료 중...")
            driver.quit()


if __name__ == "__main__":
    main_crawling()
