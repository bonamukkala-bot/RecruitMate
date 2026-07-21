/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50 : "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          900: "#312e81"
        },
        surface: {
          50 : "#f8f7f4",
          100: "#f1f0ed",
          200: "#e8e6e1",
          300: "#d4d2cc",
          400: "#b8b6b0",
          500: "#8c8a84",
          600: "#6b6965",
          700: "#4a4845",
          800: "#2e2c2a",
          900: "#1a1916",
          950: "#0d0c0b"
        }
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"]
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "24px"
      },
      boxShadow: {
        "card"   : "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)",
        "card-md": "0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)",
        "card-lg": "0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.05)"
      },
      animation: {
        "fade-in"   : "fadeIn 0.4s ease-out",
        "slide-up"  : "slideUp 0.3s ease-out",
        "slide-down": "slideDown 0.3s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite"
      },
      keyframes: {
        fadeIn: {
          "0%"  : { opacity: "0" },
          "100%": { opacity: "1" }
        },
        slideUp: {
          "0%"  : { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)",   opacity: "1" }
        },
        slideDown: {
          "0%"  : { transform: "translateY(-8px)", opacity: "0" },
          "100%": { transform: "translateY(0)",    opacity: "1" }
        }
      }
    }
  },
  plugins: []
}