/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      backgroundImage: {
        "arabesque-pattern": "url('/patterns/arabesque.png')",
      },
      fontFamily: {
        scheherazade: ["'Scheherazade New'", "serif"], // <-- your custom font
      },
      colors: {
        emerald: {
          50: "#ecfdf5",
          100: "#d1fae5",
          500: "#059669",
          600: "#047857",
          800: "#065f46",
        },
        gold: {
          500: "#D4AF37",
        },
      },
    },
  },
  plugins: [],
}
