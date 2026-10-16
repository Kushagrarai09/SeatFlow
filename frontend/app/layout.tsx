import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SeatFlow — Find your next experience",
  description:
    "Discover experiences, explore events, and get ready for your next unforgettable moment with SeatFlow.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
