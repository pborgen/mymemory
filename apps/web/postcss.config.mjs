// Explicit (empty) PostCSS config so Next.js does not walk up the directory
// tree and pick up an unrelated Tailwind config from a parent folder. This app
// uses plain CSS (app/globals.css), no Tailwind.
const config = {
  plugins: {},
};

export default config;
