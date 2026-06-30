/** @type {import('tailwindcss').Config} */
module.exports = {
  // Escanea todos los templates de Django para generar solo las clases usadas.
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
  ],
  // Modo oscuro por clase (.dark) — fuente de verdad del frontend actual.
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Primario = violeta del design system (mismas tonalidades que el CDN).
        primary: {
          50: "#f5f3ff", 100: "#ede9fe", 200: "#ddd6fe", 300: "#c4b5fd",
          400: "#a78bfa", 500: "#8b5cf6", 600: "#7c3aed", 700: "#6d28d9",
          800: "#5b21b6", 900: "#4c1d95",
        },
      },
      fontFamily: {
        sans: ["Geist", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    // base:false → DaisyUI NO impone fondo/reset global; conservamos el look slate
    // y el dark mode por clase existentes. Solo aporta componentes (btn, badge, etc.).
    base: false,
    logs: false,
    themes: [
      {
        nequi: {
          "primary": "#7c3aed",
          "primary-content": "#ffffff",
          "secondary": "#64748b",
          "secondary-content": "#ffffff",
          "accent": "#10b981",
          "neutral": "#1e293b",
          "neutral-content": "#ffffff",
          "base-100": "#ffffff",
          "base-200": "#f1f5f9",
          "base-300": "#e2e8f0",
          "base-content": "#0f172a",
          "info": "#7c3aed",
          "success": "#10b981",
          "warning": "#f59e0b",
          "error": "#f43f5e",
          "--rounded-box": "0.875rem",
          "--rounded-btn": "0.625rem",
        },
      },
      {
        nequidark: {
          "primary": "#8b5cf6",
          "primary-content": "#ffffff",
          "secondary": "#94a3b8",
          "secondary-content": "#0f172a",
          "accent": "#34d399",
          "neutral": "#0f172a",
          "neutral-content": "#e2e8f0",
          "base-100": "#1e293b",
          "base-200": "#0f172a",
          "base-300": "#334155",
          "base-content": "#e2e8f0",
          "info": "#a78bfa",
          "success": "#34d399",
          "warning": "#fbbf24",
          "error": "#fb7185",
          "--rounded-box": "0.875rem",
          "--rounded-btn": "0.625rem",
        },
      },
    ],
  },
};
