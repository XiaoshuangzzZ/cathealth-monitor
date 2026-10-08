/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      letterSpacing: {
        editorial: '0.2em',
      },
    },
  },
  plugins: [],
}
