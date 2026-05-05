/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0d0d14",
          raised: "#13131e",
          overlay: "#1a1a28",
          border: "rgba(255,255,255,0.08)",
        },
        accent: {
          DEFAULT: "#5b8af5",
          glow: "rgba(91,138,245,0.25)",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}

