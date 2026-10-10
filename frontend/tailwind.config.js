/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0a',
        surface: '#171717',
        'surface-light': '#262626',
        primary: '#3b82f6',
        secondary: '#6b7280',
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
        critical: '#b91c1c',
        info: '#3b82f6',
        text: '#f3f4f6',
        'text-muted': '#9ca3af',
        border: '#374151',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
