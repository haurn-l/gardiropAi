import { createContext, useContext, useState, type ReactNode } from 'react';
import type { ClothingDraft, ClothingRecord } from '../../wardrobe/model/clothing.types';
import { initialClothingRecords } from '../clothing-management/clothingDemoData';
import {
  buildNewClothingRecord,
  patchClothingRecordInList,
  removeClothingRecordFromList,
} from './clothingDemo.helpers';

export type ClothingDemoContextValue = {
  items: readonly ClothingRecord[];
  skipPhotoGuide: boolean;
  simulateError: boolean;
  setSkipPhotoGuide: (value: boolean) => void;
  setSimulateError: (value: boolean) => void;
  getItem: (id: string) => ClothingRecord | undefined;
  createItem: (draft: ClothingDraft, imageUri?: string) => Promise<ClothingRecord>;
  updateItem: (id: string, patch: Partial<ClothingRecord>) => Promise<ClothingRecord>;
  removeItem: (id: string) => Promise<void>;
};

type ClothingSessionMemory = {
  items: readonly ClothingRecord[];
  skipPhotoGuide: boolean;
  simulateError: boolean;
  nextId: number;
};

// Demo layout unmount olsa bile uygulama oturumu boyunca veriyi yalnızca RAM'de korur.
const sessionMemory: ClothingSessionMemory = {
  items: initialClothingRecords,
  skipPhotoGuide: false,
  simulateError: false,
  nextId: initialClothingRecords.length + 1,
};

const ClothingDemoContext = createContext<ClothingDemoContextValue | null>(null);

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Yalnızca örnek akışlar için oturumluk kıyafet verisini ve işlemlerini yönetir.
 * Gerçek servis yerine geçmez; hata simülasyonu açıkken kayıt listesini değiştirmeden hata döndürür.
 */
export function ClothingDemoProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<readonly ClothingRecord[]>(() => sessionMemory.items);
  const [skipPhotoGuide, setSkipPhotoGuideState] = useState(() => sessionMemory.skipPhotoGuide);
  const [simulateError, setSimulateErrorState] = useState(() => sessionMemory.simulateError);

  function setSkipPhotoGuide(value: boolean) {
    sessionMemory.skipPhotoGuide = value;
    setSkipPhotoGuideState(value);
  }

  function setSimulateError(value: boolean) {
    sessionMemory.simulateError = value;
    setSimulateErrorState(value);
  }

  function getItem(id: string): ClothingRecord | undefined {
    return items.find((item) => item.id === id);
  }

  async function createItem(draft: ClothingDraft, imageUri?: string): Promise<ClothingRecord> {
    await wait(160);
    if (sessionMemory.simulateError) {
      throw new Error('Kıyafet kaydedilemedi. Lütfen tekrar dene.');
    }
    const id = `cl-${String(sessionMemory.nextId++).padStart(2, '0')}`;
    const created = buildNewClothingRecord(id, draft, imageUri, new Date().toISOString());
    const next = [created, ...sessionMemory.items];
    sessionMemory.items = next;
    setItems(next);
    return created;
  }

  async function updateItem(
    id: string,
    patch: Partial<ClothingRecord>
  ): Promise<ClothingRecord> {
    await wait(140);
    if (sessionMemory.simulateError) {
      throw new Error('Değişiklik kaydedilemedi. Lütfen tekrar dene.');
    }
    const existing = sessionMemory.items.find((item) => item.id === id);
    if (!existing) {
      throw new Error('Güncellenecek kıyafet bulunamadı.');
    }
    const next = patchClothingRecordInList(sessionMemory.items, id, patch);
    sessionMemory.items = next;
    setItems(next);
    return { ...existing, ...patch };
  }

  async function removeItem(id: string): Promise<void> {
    await wait(160);
    if (sessionMemory.simulateError) {
      throw new Error('Kıyafet silinemedi. Lütfen tekrar dene.');
    }
    const existing = sessionMemory.items.find((item) => item.id === id);
    if (!existing) {
      throw new Error('Silinecek kıyafet bulunamadı.');
    }
    const next = removeClothingRecordFromList(sessionMemory.items, id);
    sessionMemory.items = next;
    setItems(next);
  }

  return (
    <ClothingDemoContext.Provider
      value={{
        items,
        skipPhotoGuide,
        simulateError,
        setSkipPhotoGuide,
        setSimulateError,
        getItem,
        createItem,
        updateItem,
        removeItem,
      }}
    >
      {children}
    </ClothingDemoContext.Provider>
  );
}

/**
 * Örnek controller'ların oturumluk kıyafet state'ine erişmesini sağlar.
 */
export function useClothingDemo(): ClothingDemoContextValue {
  const value = useContext(ClothingDemoContext);
  if (!value) {
    throw new Error('useClothingDemo yalnızca DemoProvider içinde kullanılabilir.');
  }
  return value;
}
