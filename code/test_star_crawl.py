from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from pyshadow.main import Shadow
import time
import pandas as pd

def get_olive_young_reviews(target_url, target_count=32):
    options = Options()
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # options.add_argument("--headless")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.maximize_window()
    
    name_list, star_list, text_list = [], [], []
    collected_reviews = set()
    
    try:
        print(f"접속 중: {target_url}")
        driver.get(target_url)
        time.sleep(5) 
        
        shadow = Shadow(driver)
        
        # 리뷰 탭이 안 열려있을 경우를 대비해 클릭 시도 (선택적)
        try:
            review_tab = driver.find_element(By.ID, "reviewInfo")
            driver.execute_script("arguments[0].click();", review_tab)
            print("리뷰 탭 클릭 시도됨")
            time.sleep(3)
        except:
            pass

        no_new_count = 0 
        
        while len(name_list) < target_count:
            # pyshadow를 사용하여 shadow dom 내부의 div.inner 찾기
            # 유저의 기존 코드 형식 참고
            users = shadow.find_elements('div.inner')
            print(f"발견된 리뷰 요소 개수: {len(users)}")
            
            initial_count = len(name_list)
            
            for user in users:
                try:
                    # Shadow DOM 내부 요소들을 직접 찾기
                    # pyshadow의 find_elements는 shadow root를 넘나들며 검색 가능
                    
                    # 리뷰 텍스트 (oy-review-review-content 내부)
                    # 유저의 주피터 노트북 로직 참고하여 shadow root 직접 접근
                    content_host = user.find_element(By.CSS_SELECTOR, 'oy-review-review-content')
                    content_shadow = content_host.shadow_root
                    review_text = content_shadow.find_element(By.CSS_SELECTOR, 'div.content').text.strip()
                    
                    # 중복 체크
                    if not review_text or review_text in collected_reviews:
                        continue 
                    
                    # 작성자 (oy-review-review-user 내부)
                    user_host = user.find_element(By.CSS_SELECTOR, 'oy-review-review-user')
                    user_shadow = user_host.shadow_root
                    user_name = user_shadow.find_element(By.CSS_SELECTOR, 'div.info div.name').text.strip()

                    # 별점 (oy-review-star-icon 5개 확인)
                    star_icons = user.find_elements(By.CSS_SELECTOR, "oy-review-star-icon")
                    rating_score = 0
                    for icon in star_icons:
                        try:
                            icon_shadow = icon.shadow_root
                            path_el = icon_shadow.find_element(By.CSS_SELECTOR, 'path')
                            if path_el.get_attribute('fill') != 'none':
                                rating_score += 1
                        except:
                            continue
                    
                    name_list.append(user_name)
                    text_list.append(review_text.replace('\n', ' '))
                    star_list.append(rating_score)
                    collected_reviews.add(review_text)
                    
                    print(f"[{len(name_list)}] {user_name} | 별점: {rating_score} | {review_text[:20]}...")
                    
                    if len(name_list) >= target_count: break
                except Exception as e:
                    # print(f"리뷰 개별 수집 중 오류: {e}") # 로그 과다 방지를 위해 주석 처리
                    continue

            # 스크롤
            driver.execute_script("window.scrollBy(0, 2000);")
            time.sleep(4)
            
            if len(name_list) == initial_count:
                no_new_count += 1
                # 혹시 모르니 스크롤을 더 해봄
                driver.execute_script("window.scrollBy(0, 1000);")
            else:
                no_new_count = 0
                
            if no_new_count >= 5: # 조금 더 기다려봄
                print("더 이상 새로운 리뷰가 나타나지 않아 중단합니다.")
                break
                
        # 결과 저장
        df = pd.DataFrame({
            '작성자': name_list,
            '별점': star_list,
            '리뷰내용': text_list
        })
        df.to_csv("test_reviews.csv", index=False, encoding='utf-8-sig')
        print(f"\n총 {len(name_list)}개의 리뷰가 test_reviews.csv에 저장되었습니다.")

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    url = "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000207759&dispCatNo=1000001000700080011&trackingCd=Cat1000001000700080011_Small&t_page=%EC%B9%B4%ED%85%8C%EA%B3%A0%EB%A6%AC%EA%B4%80&t_click=%EC%BF%A0%EC%85%98%2F%ED%8C%8C%EC%9A%B4%EB%8D%B0%EC%9D%B4%EC%85%98_%EC%A0%84%EC%B2%B4__%EC%83%81%ED%92%88%EC%83%81%EC%84%B8&t_number=21&tab=review"
    get_olive_young_reviews(url, target_count=32)
