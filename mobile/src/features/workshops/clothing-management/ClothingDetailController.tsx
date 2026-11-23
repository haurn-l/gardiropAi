import { useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import type { RatingValue } from '../../../shared/ui/rating.types';
import type { ClothingStatus } from '../../wardrobe/model/clothingCard.types';
import { ClothingDetailScreen } from '../../wardrobe/screens/ClothingDetailScreen';
import { useClothingDemo } from '../demo/ClothingDemoContext';

/**
 * Seçili kıyafet kimliğine göre detay ekranını oturumluk sağlayıcıya bağlayan controller'dır.
 * Aynı işlem bitmeden ikinci isteği engeller; silme hatasında kaydı ekranda tutar.
 */
export function ClothingDetailController() {
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { getItem, updateItem, removeItem } = useClothingDemo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const busyRef = useRef(false);

  const item = id ? getItem(id) : undefined;

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
      router.replace('/clothing-management');
    }
  }

  function handleEdit(targetId: string) {
    router.push({ pathname: '/clothing-management/edit/[id]', params: { id: targetId } });
  }

  function handleChangeStatus(targetId: string, status: ClothingStatus) {
    if (!item || item.status === status) {
      return;
    }
    void runAction(async () => {
      await updateItem(targetId, { status });
    });
  }

  function handleToggleFavorite(targetId: string) {
    if (!item) {
      return;
    }
    void runAction(async () => {
      await updateItem(targetId, { favorite: !item.favorite });
    });
  }

  function handleRate(targetId: string, value: RatingValue | null) {
    if (!item || item.rating === value) {
      return;
    }
    void runAction(async () => {
      await updateItem(targetId, { rating: value });
    });
  }

  function handleDelete(targetId: string) {
    void runAction(async () => {
      await removeItem(targetId);
      handleBack();
    });
  }

  return (
    <ClothingDetailScreen
      item={item}
      busy={busy}
      error={error}
      onBack={handleBack}
      onEdit={handleEdit}
      onChangeStatus={handleChangeStatus}
      onToggleFavorite={handleToggleFavorite}
      onRate={handleRate}
      onDelete={handleDelete}
    />
  );
}
