export const mindQTokens = {
  colors: {
    background: 'var(--background)',
    foreground: 'var(--foreground)',
    primary: '#1d4ed8',
    secondary: '#9333ea',
    accent: '#f97316',
    success: '#16a34a',
    warning: '#facc15',
    danger: '#dc2626',
    muted: 'var(--muted)',
    border: 'var(--border)',
  },
  radii: {
    xs: '6px',
    sm: '10px',
    md: '16px',
    lg: '24px',
  },
  typography: {
    family: 'var(--font-sans, "Inter", "IBM Plex Sans Arabic", sans-serif)',
    mono: 'var(--font-mono, "JetBrains Mono", monospace)',
    weights: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },
};

export type MindQTokens = typeof mindQTokens;
