module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/**/*.py",
    "./accounts/**/*.py",
    "./assessments/**/*.py",
    "./question_bank/**/*.py",
    "./attempts/**/*.py",
    "./grading/**/*.py",
    "./results/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          gold: "#D4AF37",
        },
      },
    },
  },
  plugins: [],
};
