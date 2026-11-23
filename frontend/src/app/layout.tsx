import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/Navigation";

export const metadata: Metadata = {
  title: "Coach Tommy",
  description: "Une application web moderne pour l'entraînement",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body><Navigation>{children}</Navigation></body>
    </html>
  );
}
