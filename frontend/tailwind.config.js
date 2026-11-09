/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#1e3a8a',    // blue-900
          primary: '#2563eb', // blue-600
          secondary: '#60a5fa', // blue-400
          accent: '#f59e0b',  // amber-500
          surface: '#f0f9ff', // blue-50
        }
      }
    },
  },
  plugins: [],
}