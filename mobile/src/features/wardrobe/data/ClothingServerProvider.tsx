import { useEffect, useState, type ReactNode } from 'react';
import { ClothingDataContext, type ClothingPhoto } from './ClothingDataContext';
import { confirmClothing, deleteClothing, listClothing, updateClothing } from './clothingApi';
import type { ClothingDraft, ClothingRecord } from '../model/clothing.types';

export function ClothingServerProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<readonly ClothingRecord[]>([]);
  const [skipPhotoGuide, setSkipPhotoGuide] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    void listClothing().then(
      (records) => {
        if (active) {
          setItems(records);
          setLoading(false);
        }
      },
      (err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Gardırop yüklenemedi.');
          setLoading(false);
        }
      },
    );
    return () => { active = false; };
  }, [attempt]);

  async function createItem(draft: ClothingDraft, photo?: ClothingPhoto) {
    if (!photo?.uploadId) {
      throw new Error('Gardıroba eklemek için önce fotoğraf yükle.');
    }
    const saved = await confirmClothing(photo.uploadId, draft);
    setItems((current) => current.some((item) => item.id === saved.id)
      ? current.map((item) => item.id === saved.id ? saved : item)
      : [...current, saved]);
    return saved;
  }

  async function updateItem(id: string, patch: Partial<ClothingRecord>) {
    const item = items.find((current) => current.id === id);
    if (!item) {
      throw new Error('Kıyafet bulunamadı.');
    }
    const saved = await updateClothing(item, patch);
    setItems((current) => current.map((entry) => entry.id === id ? saved : entry));
    return saved;
  }

  async function removeItem(id: string) {
    await deleteClothing(id);
    setItems((current) => current.filter((item) => item.id !== id));
  }

  return (
    <ClothingDataContext.Provider value={{
      items, skipPhotoGuide, setSkipPhotoGuide,
      simulateError: false,
      setSimulateError: () => {},
      getItem: (id) => items.find((item) => item.id === id),
      createItem, updateItem, removeItem,
      server: {
        loading, error,
        reload: () => {
          setLoading(true);
          setError(undefined);
          setAttempt((value) => value + 1);
        },
      },
    }}>
      {children}
    </ClothingDataContext.Provider>
  );
}
