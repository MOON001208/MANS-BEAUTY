import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MEN'S BEAUTY PICK | 남성 화장품 추천 시스템",
  description: "올리브영 맨즈 뷰티 톤로션/BB, 쿠션/파운데이션 상품 추천 및 리뷰 분석",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <div style={{ position: 'relative', zIndex: 1 }}>
          {children}
        </div>
      </body>
    </html>
  );
}
