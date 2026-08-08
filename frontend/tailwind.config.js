/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      // Matches the live ecg.com.gh brand palette (navy header/hero, red accents/CTAs, yellow highlights)
      colors: {
        ecg: {
          navy: '#050d9e',
          navyDark: '#03086b',
          red: '#e10303',
          yellow: '#faf208',
        },
      },
      fontFamily: {
        sans: ['Poppins', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
