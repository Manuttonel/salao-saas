/** @type {import('tailwindcss').Config} */

// Todas as cores vêm de variáveis CSS (definidas em src/styles/index.css, uma
// paleta por tema). Assim as MESMAS classes (bg-card, text-ink, bg-brand-600...)
// mudam de aparência sozinhas quando a pessoa troca de tema — nenhuma página
// precisa saber qual tema está ativo.
// O "<alpha-value>" permite usar transparência, ex.: bg-brand-600/40.
const cor = (nome) => `rgb(var(--${nome}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        page: cor("page"),          // fundo da página
        card: cor("card"),          // fundo de cartões
        card2: cor("card2"),        // superfície secundária (campos, hover)
        line: cor("line"),          // bordas e divisórias
        ink: cor("ink"),            // texto principal
        muted: cor("muted"),        // texto secundário
        onbrand: cor("onbrand"),    // texto sobre a cor principal
        accent: cor("accent"),      // dourado (Glow), azul-marinho (Dark)
        "accent-soft": cor("accent-soft"),
        brand: {
          50: cor("brand-50"),
          100: cor("brand-100"),
          500: cor("brand-500"),
          600: cor("brand-600"),
          700: cor("brand-700"),
        },
      },
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
      },
      boxShadow: {
        card: "var(--shadow-card)",
      },
    },
  },
  plugins: [],
};
