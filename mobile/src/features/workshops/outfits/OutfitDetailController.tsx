import { useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import type { RatingValue } from '../../../shared/ui/rating.types';
import { OutfitDetailScreen } from '../../outfits/screens/OutfitDetailScreen';
import { useOutfitDemo } from '../demo/OutfitDemoContext';

/**
 * Seçili kombin kimliğine göre detay ekranını oturumluk sağlayıcıya bağlayan controller'dır.
 * Aynı işlem bitmeden ikinci isteği engeller; silme hatasında kaydı ekranda korur.
 */
export function OutfitDetailController() {
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { getOutfit, rateOutfit, removeOutfit } = useOutfitDemo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const busyRef = useRef(false);

  const item = id ? getOutfit(id) : undefined;

  async function runAction(task: () => Promise<void>) {
    if (busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError(undefined);
    try {
      await task();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'İşlem tamamlanamadı.');
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function handleBack() {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/outfit-history');
    }
  }

  function handleRate(targetId: string, value: RatingValue | null) {
    if (!item || item.rating === value) {
      return;
    }
    void runAction(async () => {
      await rateOutfit(targetId, value);
    });
  }

  function handleDelete(targetId: string) {
    void runAction(async () => {
      await removeOutfit(targetId);
      handleBack();
    });
  }

  return (
    <OutfitDetailScreen
      item={item}
      busy={busy}
      error={error}
      onBack={handleBack}
      onRate={handleRate}
      onDelete={handleDelete}
    />
  );
}
