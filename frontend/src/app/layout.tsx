import type { Metadata } from "next";
import type { ReactNode } from "react";
import "../styles/style.css";

export const metadata: Metadata = { title: "掌柜问数" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
