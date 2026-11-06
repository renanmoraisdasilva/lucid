/*
 * Lucid mockup design tokens.
 * Single source of truth. Load immediately after the Tailwind Play CDN script,
 * before anything renders. Every screen links this file instead of inlining a
 * tailwind.config, so the palette cannot drift between mockups.
 */
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          bg: "#171512",
          sidebar: "#13120f",
          elevated: "#211e19",
          code: "#181613",
          border: "#26221c",
          "border-subtle": "#38332b",
          hover: "#2a2620",
        },
        amber: {
          accent: "#e9a34b",
          hover: "#f5b058",
          dim: "rgba(233, 163, 75, 0.15)",
          border: "rgba(233, 163, 75, 0.3)",
        },
        danger: {
          DEFAULT: "#e2685c",
          dim: "rgba(226, 104, 92, 0.12)",
          border: "rgba(226, 104, 92, 0.32)",
        },
        text: {
          primary: "#f3eee5",
          secondary: "#a8a094",
          muted: "#736b60",
        },
      },
      fontFamily: {
        sans: ["Geist", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
};
