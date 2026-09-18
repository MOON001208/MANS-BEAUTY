# MEN'S BEAUTY PICK web

Node.js 24 / Next.js 정적 웹입니다. 운영 절차는 상위 README를 참고하세요.

1. `.env.example`을 `.env.local`로 복사합니다.
2. Supabase URL과 공개용 publishable 키를 설정합니다. 관리자 키는 빌드가 거부합니다.
3. `npm ci`, `npm run dev`로 개발 서버를 실행합니다.
4. `npm test`, `npm run lint`, `npm run build`로 검증합니다.
5. `npm start`는 Python 정적 서버로 `out`을 localhost:3000에 제공합니다.

한글 Windows 경로에서 발생하던 Turbopack 빌드 오류를 피하기 위해 webpack을 사용합니다. Vercel에서는 기본 설정, GitHub Pages에서는 `DEPLOY_TARGET=github-pages`를 지정합니다. 환경변수 변경 후에는 반드시 다시 빌드·배포해야 합니다.

상품 조회는 ID 커서로 전체 목록을 읽습니다. 화면의 분석 리뷰 수는 프로필에 기록된 실제 분석 건수입니다. 상세 화면에는 최신 저장 리뷰 30개를 보여주며 닉네임은 조회하지 않습니다.
