import { createContext, useContext, useState, type ReactNode } from 'react';
import type { RatingValue } from '../../../shared/ui/rating.types';
import type { OutfitRecord, OutfitSort } from '../../outfits/model/outfit.types';
import { initialOutfitRecords } from '../outfits/outfitDemoData';
import {
  prependOutfitToList,
  removeOutfitFromList,
  updateOutfitRatingInList,
} from './outfitDemo.helpers';

export type OutfitDemoContextValue = {
  items: readonly OutfitRecord[];
  sort: OutfitSort;
  simulateError: boolean;
  setSort: (next: OutfitSort) => void;
  setSimulateError: (value: boolean) => void;
  getOutfit: (id: string) => OutfitRecord | undefined;
  rateOutfit: (id: string, rating: RatingValue | null) => Promise<OutfitRecord>;
  removeOutfit: (id: string) => Promise<void>;
  addOutfit: (outfit: OutfitRecord) => void;
};

type OutfitSessionMemory = {
  items: readonly OutfitRecord[];
  sort: OutfitSort;
  simulateError: boolean;
};

// Demo layout unmount olsa bile uygulama oturumu boyunca kombin geçmişini yalnızca RAM'de korur.
const sessionMemory: OutfitSessionMemory = {
  items: initialOutfitRecords,
  sort: 'newest',
  simulateError: false,
};

const OutfitDemoContext = createContext<OutfitDemoContextValue | null>(null);

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Yalnızca örnek akışlar için oturumluk kombin geçmişini, sıralamasını ve işlemlerini yönetir.
 * Kıyafet silinse bile snapshot kopyaları korur; kombin silmek gardırop kıyafetlerini etkilemez.
 */
export function OutfitDemoProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<readonly OutfitRecord[]>(() => sessionMemory.items);
  const [sort, setSortState] = useState<OutfitSort>(() => sessionMemory.sort);
  const [simulateError, setSimulateErrorState] = useState(() => sessionMemory.simulateError);

  function setSort(next: OutfitSort) {
    sessionMemory.sort = next;
    setSortState(next);
  }

  function setSimulateError(value: boolean) {
    sessionMemory.simulateError = value;
    setSimulateErrorState(value);
  }

  function getOutfit(id: string): OutfitRecord | undefined {
    return items.find((outfit) => outfit.id === id);
  }

  async function rateOutfit(id: string, rating: RatingValue | null): Promise<OutfitRecord> {
    await wait(140);
    if (sessionMemory.simulateError) {
      throw new Error('Kombin puanı kaydedilemedi. Lütfen tekrar dene.');
    }
    const existing = sessionMemory.items.find((outfit) => outfit.id === id);
    if (!existing) {
      throw new Error('Puanlanacak kombin bulunamadı.');
    }
    const next = updateOutfitRatingInList(sessionMemory.items, id, rating);
    sessionMemory.items = next;
    setItems(next);
    return { ...existing, rating };
  }

  async function removeOutfit(id: string): Promise<void> {
    await wait(160);
    if (sessionMemory.simulateError) {
      throw new Error('Kombin silinemedi. Lütfen tekrar dene.');
    }
    const existing = sessionMemory.items.find((outfit) => outfit.id === id);
    if (!existing) {
      throw new Error('Silinecek kombin bulunamadı.');
    }
    const next = removeOutfitFromList(sessionMemory.items, id);
    sessionMemory.items = next;
    setItems(next);
  }

  function addOutfit(outfit: OutfitRecord) {
    const next = prependOutfitToList(sessionMemory.items, outfit);
    sessionMemory.items = next;
    setItems(next);
  }

  return (
    <OutfitDemoContext.Provider
      value={{
        items,
        sort,
        simulateError,
        setSort,
        setSimulateError,
        getOutfit,
        rateOutfit,
        removeOutfit,
        addOutfit,
      }}
    >
      {children}
    </OutfitDemoContext.Provider>
  );
}

/**
 * Örnek controller'ların oturumluk kombin geçmişine erişmesini sağlar.
 */
export function useOutfitDemo(): OutfitDemoContextValue {
  const value = useContext(OutfitDemoContext);
  if (!value) {
    throw new Error('useOutfitDemo yalnızca DemoProvider içinde kullanılabilir.');
  }
  return value;
}
