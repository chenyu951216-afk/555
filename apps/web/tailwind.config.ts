import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f7f6f2",
        ink: "#202124",
        graphite: "#5f6368",
        line: "#dedbd3",
        teal: "#176b69",
        rose: "#a23b4b",
      },
      boxShadow: {
        soft: "0 12px 36px rgba(32, 33, 36, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
