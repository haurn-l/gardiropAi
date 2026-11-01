// Tek tasarım kaynağı: bileşenler kendi renk paletlerini oluşturmaz.
export const colors = {
  background: '#F8F7F3', surface: '#FFFFFF', ink: '#23352D', muted: '#73796F',
  line: '#E5E6DD', primary: '#344D3C', soft: '#EDF0E7', accent: '#DDE7C7',
  sand: '#EDE7DD', danger: '#A34D3E', dangerSoft: '#F8EDE8', white: '#FFFFFF',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, huge: 48 };
export const radius = { sm: 8, md: 16, lg: 24, full: 999 };
export const fonts = { regular: 'DMSans', medium: 'DMSansMedium', bold: 'DMSansBold', serif: 'Cormorant' };
export const layout = { content: 1160, sidebar: 244, wide: 1000 };
