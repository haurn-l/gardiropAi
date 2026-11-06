import { Platform } from 'react-native';

// Açık turuncu ana vurgu; metin ve ikonlar için ayrı, okunaklı koyu ton.
export const colors = {
  background: '#FAFAFC',
  surface: '#FFFFFF',
  ink: '#27252A',
  muted: '#77747D',
  line: '#EAE8ED',
  primary: '#FFAB7A',
  onPrimary: '#39251B',
  accentInk: '#A64720',
  soft: '#F1F1F4',
  accent: '#FFF0E6',
  sand: '#F5F0EC',
  danger: '#B8443D',
  dangerSoft: '#FCEDEC',
  success: '#387A60',
  white: '#FFFFFF',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, huge: 48 };
export const radius = { sm: 10, md: 16, lg: 22, full: 999 };
// Cihazın kendi fontu: iOS'ta SF, Android'de sistem sans-serif. Ek font indirilmez.
export const fonts = {
  regular: Platform.OS === 'ios' ? 'System' : 'sans-serif',
  medium: Platform.OS === 'ios' ? 'System' : 'sans-serif-medium',
  bold: Platform.OS === 'ios' ? 'System' : 'sans-serif',
};
export const layout = { content: 1160, sidebar: 244, wide: 1000 };
