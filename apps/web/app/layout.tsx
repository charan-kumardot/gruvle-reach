import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Gruvle Reach — Founder Growth OS",
    template: "%s · Gruvle Reach",
  },
  description:
    "Find the people, opportunities and actions that move your product forward. Gruvle Reach researches your market, finds high-fit customers and investors, and turns them into a prioritized action plan.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} data-scroll-behavior="smooth">
      <body className="min-h-full flex flex-col bg-ambient">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
