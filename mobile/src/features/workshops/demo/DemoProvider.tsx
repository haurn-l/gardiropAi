import type { ReactNode } from 'react';
import { ClothingDemoProvider } from './ClothingDemoContext';

/**
 * Örnek akışların oturumluk context sağlayıcılarını tek noktada birleştirir.
 * Sonraki paketler kendi ayrı modüllerini bu birleştirici içine ekler.
 */
export function DemoProvider({ children }: { children: ReactNode }) {
  return <ClothingDemoProvider>{children}</ClothingDemoProvider>;
}
