/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#E6F5EF",
          100: "#C4E8D8",
          200: "#9FDABF",
          300: "#5DCAA5",
          400: "#1D9E75",
          500: "#178A66",
          600: "#0F6E56",
          700: "#0A5A46",
          800: "#085041",
          900: "#04342C",
        },
        // Nouveau système : surfaces sobres
        bg: "#FAFAF9",
        card: "#FFFFFF",
        line: "#E8E8E4",
        "line-subtle": "#F0F0EC",
        ink: {
          DEFAULT: "#18181B",
          muted: "#71717A",
          faint: "#A1A1AA",
          placeholder: "#D4D4D8",
        },
        success: { 50: "#ECFDF5", 600: "#059669", 700: "#047857" },
        warn: { 50: "#FFFBEB", 600: "#D97706", 700: "#B45309" },
        danger: { 50: "#FEF2F2", 600: "#DC2626", 700: "#B91C1C" },
        info: { 50: "#EFF6FF", 600: "#2563EB", 700: "#1D4ED8" },
        // Compatibilité : surface-* utilisé dans beaucoup de composants existants
        surface: {
          DEFAULT: "#FAFAF9",
          50: "#FAFAF9",
          100: "#F4F4F2",
          200: "#E8E8E4",
          300: "#D4D4D0",
          400: "#A1A1AA",
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "-apple-system", "sans-serif"],
        display: ['"Instrument Serif"', '"Fraunces"', "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        input: "6px",
        card: "8px",
        "card-lg": "12px",
        button: "6px",
        pill: "9999px",
      },
      spacing: {
        "4.5": "1.125rem",
        18: "4.5rem",
      },
      transitionDuration: {
        hover: "150ms",
        expand: "200ms",
      },
    },
  },
  plugins: [],
};
