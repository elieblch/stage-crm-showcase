import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stage CRM — Secrétaire de recherche de stage",
  description: "CRM intelligent pour trouver et décrocher le stage idéal en finance, conseil et stratégie",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
