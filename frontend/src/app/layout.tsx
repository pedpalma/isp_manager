import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "ISP Manager",
  description: "Painel de gestão do ISP Manager",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased selection:bg-neutral-900 selection:text-neutral-50">
        {children}
      </body>
    </html>
  );
}
