// Tailwind v4 uses a single PostCSS plugin; @tailwindcss/postcss replaces
// the v3 plugin chain. Pulling tailwind.config.ts is no longer required —
// theme + content come from the @import directive in globals.css.
const config = {
  plugins: { "@tailwindcss/postcss": {} },
};
export default config;
