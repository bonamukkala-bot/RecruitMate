/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50 : "#EDEFF3",
          100: "#D6DAE3",
          200: "#AEB6C7",
          300: "#7C889F",
          400: "#4F5D78",
          500: "#12203A",
          600: "#0F1B31",
          700: "#0B1526",
          800: "#08101C",
          900: "#050A12"
        },
        stone: {
          50 : "#F7F8F5",
          100: "#ECEEE6",
          200: "#DEE0D6",
          300: "#C9CCBE",
          400: "#ABAE9E",
          500: "#8A8D7C",
          600: "#6B6E5F",
          700: "#4E5044",
          800: "#34362D",
          900: "#1E1F19"
        },
        ledger: {
          50 : "#EAF0F8",
          100: "#CFE0F0",
          200: "#9FC0E0",
          300: "#6E96C0",
          400: "#4A76AC",
          500: "#2A4B7C",
          600: "#21406B",
          700: "#1A3457",
          800: "#132743",
          900: "#0F2038"
        },
        verified: {
          50 : "#E7F3EE",
          100: "#C7E5D8",
          200: "#8FCAAF",
          300: "#5FA98D",
          400: "#398D71",
          500: "#1F6E58",
          600: "#195944",
          700: "#164F40",
          800: "#0F3A2F",
          900: "#0A281F"
        },
        brick: {
          50 : "#F7E9E6",
          100: "#EBC7C0",
          200: "#DDA195",
          300: "#C97C6B",
          400: "#B85846",
          500: "#A23B2E",
          600: "#8A3126",
          700: "#7A2C22",
          800: "#5C2118",
          900: "#3F1710"
        },
        gold: {
          50 : "#FBF1DD",
          100: "#F3DBA3",
          200: "#EAC575",
          300: "#DDAE4C",
          400: "#D19C30",
          500: "#C68A1E",
          600: "#A9740F",
          700: "#8F6212",
          800: "#6B490D",
          900: "#493109"
        }
      },
      fontFamily: {
        sans: ["Public Sans", "system-ui", "sans-serif"],
        display: ["Fraunces", "serif"],
        mono: ["IBM Plex Mono", "monospace"]
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "24px"
      },
      boxShadow: {
        "card"   : "0 1px 2px 0 rgb(18 32 58 / 0.04)",
        "card-md": "0 2px 6px -1px rgb(18 32 58 / 0.06)",
        "card-lg": "0 8px 16px -4px rgb(18 32 58 / 0.08)"
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