// Tailwind CSS v4 runs as a PostCSS plugin; it writes plain static CSS, so the strict
// CSP (no inline styles in production) is unaffected.
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
