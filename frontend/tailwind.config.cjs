/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        display: ['"Inter"', 'system-ui', 'sans-serif'],
        body: ['"Inter"', 'system-ui', 'sans-serif'],
      },
      colors: {
        utem: {
          blue: '#005DA4',
          blueDark: '#003B73',
          blueLight: '#4BA3FF',
          green: '#009639',
          gray: '#E5E9EC',
          dark: '#1E1E1E',
          blackish: '#0F1115',
          skySoft: '#B6DCFE',
          aquaSoft: '#8FF0C4',
          grayBlue: '#6E7E91',
          // NUEVOS: Colores morados para ciencia de datos
          purple: '#8A2BE2',
          purpleDark: '#6A1BB8',
          purpleLight: '#A855F7',
          magenta: '#D946EF',
          teal: '#0D9488',
        },
      },
      boxShadow: {
        subtle: '0 8px 18px -10px rgba(0,0,0,0.08)',
        glow: '0 0 20px rgba(138, 43, 226, 0.3)',
        glowBlue: '0 0 20px rgba(0, 93, 164, 0.3)',
      },
      borderRadius: {
        md: '10px',
        xl: '16px',
      },
      // NUEVO: Gradientes personalizados
      backgroundImage: {
        'gradient-utem': 'linear-gradient(135deg, #005DA4 0%, #8A2BE2 100%)',
        'gradient-utem-reverse': 'linear-gradient(135deg, #8A2BE2 0%, #005DA4 100%)',
        'gradient-utem-soft': 'linear-gradient(135deg, #B6DCFE 0%, #E9D5FF 100%)',
        'gradient-card': 'linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)',
        'gradient-purple-blue': 'linear-gradient(135deg, #A855F7 0%, #4BA3FF 100%)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
