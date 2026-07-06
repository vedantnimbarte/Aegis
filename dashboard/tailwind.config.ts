import type { Config } from "tailwindcss";

// Shares the landing site's design tokens (see ../frontend) so the marketing
// page and the product feel like one system.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "#07090E",
        ink: "#0B0E15",
        surface: "#0E121A",
        line: "#1B2130",
        cyan: "#22D3EE",
        "cyan-soft": "#67E8F9",
        signal: "#4ADE80",
        danger: "#FB5C6B",
        amber: "#F5B451",
        violet: "#A78BFA",
        fg: "#E6E9F0",
        muted: "#8A93A6",
        faint: "#5A6273",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.4", transform: "scale(0.85)" },
        },
        spin: { to: { transform: "rotate(360deg)" } },
      },
      animation: {
        "fade-up": "fade-up 0.5s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-dot": "pulse-dot 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
