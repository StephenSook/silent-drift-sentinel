import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});
const instrument = Instrument_Serif({
  variable: "--font-instrument",
  subsets: ["latin"],
  weight: ["400"],
});

const DESC =
  "An on-call AI agent that detects ML model drift, walks DataHub lineage to the upstream root cause, and writes a drift-causation object back onto the model.";

export const metadata: Metadata = {
  metadataBase: new URL("https://silent-drift-sentinel-web.vercel.app"),
  title: "Silent-Drift Sentinel",
  description: DESC,
  openGraph: {
    title: "Silent-Drift Sentinel",
    description: DESC,
    url: "https://silent-drift-sentinel-web.vercel.app",
    siteName: "Silent-Drift Sentinel",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Silent-Drift Sentinel",
    description: DESC,
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexMono.variable} ${instrument.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
