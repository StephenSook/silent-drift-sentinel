import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Silent-Drift Sentinel",
    short_name: "Sentinel",
    description:
      "On-call AI agent that detects ML model drift, walks DataHub lineage to the cause, and writes it back onto the model.",
    start_url: "/dashboard",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0c0d10",
    theme_color: "#0c0d10",
    icons: [
      { src: "/icon-512.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
