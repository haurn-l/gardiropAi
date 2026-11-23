import type { ReactNode } from 'react';
import { ClothingDemoProvider } from './ClothingDemoContext';
import { ClothingServerProvider } from '../../wardrobe/data/ClothingServerProvider';
import { clothingApiOrigin } from '../../wardrobe/data/clothingApi';

/**
 * Örnek akışların oturumluk context sağlayıcılarını tek noktada birleştirir.
 * Sonraki paketler kendi ayrı modüllerini bu birleştirici içine ekler.
 */
export function DemoProvider({ children }: { children: ReactNode }) {
  const ClothingProvider = clothingApiOrigin ? ClothingServerProvider : ClothingDemoProvider;
  return <ClothingProvider>{children}</ClothingProvider>;
}
