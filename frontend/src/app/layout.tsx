import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Application Entrainement",
  description: "Une application web moderne pour l'entraînement",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
