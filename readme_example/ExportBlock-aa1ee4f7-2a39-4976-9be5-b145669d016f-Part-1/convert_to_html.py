
import markdown
import os

# 파일 경로 설정 (현재 스크립트 위치 기준)
base_dir = os.path.dirname(os.path.abspath(__file__))
md_filename = 'Market_Analysis_Report_Final.md'
html_filename = 'Market_Analysis_Report_Final.html'

md_path = os.path.join(base_dir, md_filename)
html_path = os.path.join(base_dir, html_filename)

# CSS 스타일 (GitHub Markdown 스타일 + 깔끔한 보고서 스타일)
css_style = """
<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        line-height: 1.6;
        color: #24292e;
        max-width: 900px;
        margin: 0 auto;
        padding: 40px;
        background-color: #ffffff;
    }
    h1, h2, h3 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
    h1 { font-size: 2.2em; margin-bottom: 24px; }
    h2 { font-size: 1.7em; margin-top: 30px; margin-bottom: 16px; }
    h3 { font-size: 1.4em; margin-top: 24px; margin-bottom: 12px; }
    p { margin-bottom: 16px; }
    table {
        border-collapse: collapse;
        width: 100%;
        margin-bottom: 20px;
        display: block;
        overflow-x: auto;
    }
    table th, table td {
        padding: 8px 13px;
        border: 1px solid #dfe2e5;
    }
    table th { background-color: #f6f8fa; font-weight: 600; }
    table tr:nth-child(2n) { background-color: #f6f8fa; }
    blockquote {
        padding: 0 1em;
        color: #6a737d;
        border-left: 0.25em solid #dfe2e5;
        margin: 0 0 16px 0;
    }
    img {
        max-width: 100%;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-radius: 8px;
        margin: 20px 0;
    }
    code {
        background-color: rgba(27,31,35,.05);
        border-radius: 3px;
        font-size: 85%;
        margin: 0;
        padding: .2em .4em;
    }
    hr {
        height: 0.25em;
        padding: 0;
        margin: 24px 0;
        background-color: #e1e4e8;
        border: 0;
    }
    @media print {
        body { 
            padding: 20px; 
            max-width: 100%; 
            font-size: 12pt;
        }
        h1, h2, h3, h4, h5 { 
            page-break-after: avoid; 
            break-after: avoid;
        }
        img { 
            page-break-inside: avoid; 
            break-inside: avoid;
            max-height: 85vh; /* 이미지가 한 페이지를 넘지 않도록 제한 */
            display: block;
            margin: 10px auto;
        }
        p {
            page-break-inside: avoid;
            orphans: 3;
            widows: 3;
        }
        table {
            page-break-inside: avoid;
            break-inside: avoid;
        }
        /* 제목 바로 다음에 오는 요소(이미지 등)가 떨어지지 않도록 설정 */
        h1 + *, h2 + *, h3 + * {
            page-break-before: avoid;
        }
        /* 특정 구간 강제 페이지 넘김 방지용 컨테이너 (필요시) */
        .no-break {
            page-break-inside: avoid;
        }
    }
</style>
"""

# HTML 템플릿
html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>남성 화장품 시장 분석 보고서</title>
    {}
</head>
<body>
{}
</body>
</html>
"""

# 변환 수행
try:
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 마크다운 -> HTML 변환 (테이블 등 확장 기능 포함)
    html_content = markdown.markdown(text, extensions=['extra', 'tables'])

    # 최종 HTML 생성
    final_html = html_template.format(css_style, html_content)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"변환 완료! 파일 저장됨: {html_path}")

except Exception as e:
    print(f"오류 발생: {e}")
