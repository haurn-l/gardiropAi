import { createContext, useContext } from 'react';
import type { ClothingDraft, ClothingRecord } from '../model/clothing.types';

export type ClothingPhoto = { uri: string; uploadId?: string };

export type ClothingData = {
  items: readonly ClothingRecord[];
  skipPhotoGuide: boolean;
  simulateError: boolean;
  setSkipPhotoGuide: (value: boolean) => void;
  setSimulateError: (value: boolean) => void;
  getItem: (id: string) => ClothingRecord | undefined;
  createItem: (draft: ClothingDraft, photo?: ClothingPhoto) => Promise<ClothingRecord>;
  updateItem: (id: string, patch: Partial<ClothingRecord>) => Promise<ClothingRecord>;
  removeItem: (id: string) => Promise<void>;
  server?: { loading: boolean; error?: string; reload: () => void };
};

export const ClothingDataContext = createContext<ClothingData | null>(null);

export function useClothingData(): ClothingData {
  const value = useContext(ClothingDataContext);
  if (!value) {
    throw new Error('Kıyafet verisi sağlayıcısı bulunamadı.');
  }
  return value;
}
