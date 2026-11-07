import type { BottomTab } from './bottomBar.types';

// Sıra çizimlerdeki ana ekranlara karşılık gelir. + ayrı bir aksiyondur.
export const bottomTabs = [
  { id: 'wardrobe', label: 'Gardırobum', icon: 'wardrobe' },
  { id: 'outfits', label: 'Kombinlerim', icon: 'grid' },
  { id: 'conversations', label: 'Sohbetler', icon: 'chat' },
] as const satisfies readonly BottomTab[];
