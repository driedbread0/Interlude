export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#EFE9DE",
        paper: "#F8F3EA",
        porcelain: "#FFFDF8",
        ink: "#111418",
        "ink-soft": "#39414A",
        muted: "#737B85",
        rule: "#D8D1C5",
        "rule-strong": "#A8A096",
        cobalt: "#1F5EFF",
        "cobalt-deep": "#082E9B",
        "electric-blue": "#4F86FF",
        teal: "#00A887",
        "teal-deep": "#006C5A",
        violet: "#6E3FF2",
        warning: "#B4233C",
        "signal-ink": "#F8F3EA",
        "signal-panel": "#FFFDF8",
        "signal-rule": "#D8D1C5",
        "signal-muted": "#39414A",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui"],
        ui: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular"],
      },
      boxShadow: {
        panel: "0 16px 36px rgba(17, 20, 24, 0.07)",
        crisp: "0 1px 0 rgba(17, 20, 24, 0.08)",
        insetline: "inset 0 0 0 1px rgba(159, 168, 181, 0.42)",
      },
      transitionTimingFunction: {
        instrument: "cubic-bezier(0.2, 0.8, 0.2, 1)",
      },
    },
  },
  plugins: [],
};
