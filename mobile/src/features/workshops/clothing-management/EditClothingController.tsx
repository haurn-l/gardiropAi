import { useRef, useState } from 'react';
import { router, useLocalSearchParams, usePreventRemove } from 'expo-router';
import type { ClothingDraft } from '../../wardrobe/model/clothing.types';
import { createEmptyClothingDraft } from '../../wardrobe/model/clothingOptions';
import { EditClothingScreen } from '../../wardrobe/screens/EditClothingScreen';
import { useClothingDemo } from '../demo/ClothingDemoContext';
import { isClothingDraftDirty, recordToClothingDraft } from '../demo/clothingDemo.helpers';

/**
 * Seçili kıyafet için ayrı bir düzenleme taslağı tutar.
 * Kaydedilmemiş değişiklik varsa geri düğmesi, Android sistem geri ve iOS geri hareketinde onay ister.
 */
export function EditClothingController() {
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { getItem, updateItem } = useClothingDemo();

  const item = id ? getItem(id) : undefined;
  const [draft, setDraft] = useState<ClothingDraft>(() =>
    item ? recordToClothingDraft(item) : createEmptyClothingDraft()
  );
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);
  const [busy, setBusy] = useState(false);
  const [allowExit, setAllowExit] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const busyRef = useRef(false);
  const repeatRef = useRef<(() => void) | null>(null);

  const isDirty = item ? isClothingDraftDirty(item, draft) : false;

  const disablePrevention = usePreventRemove((isDirty || busy) && !allowExit, ({ repeat }) => {
    if (busyRef.current) {
      return;
    }
    repeatRef.current = repeat;
    setShowDiscardDialog(true);
  });

  function navigateBack() {
    if (router.canGoBack()) {
      router.back();
    } else if (id) {
      router.replace({ pathname: '/clothing-management/[id]', params: { id } });
    } else {
      router.replace('/clothing-management');
    }
  }

  function leaveScreen() {
    setAllowExit(true);
    disablePrevention();
    navigateBack();
  }

  function handleRequestBack() {
    if (busyRef.current) {
      return;
    }
    if (isDirty) {
      repeatRef.current = null;
      setShowDiscardDialog(true);
      return;
    }
    leaveScreen();
  }

  function handleConfirmDiscard() {
    const repeat = repeatRef.current;
    repeatRef.current = null;
    setAllowExit(true);
    setShowDiscardDialog(false);
    disablePrevention();
    if (repeat) {
      repeat();
    } else {
      navigateBack();
    }
  }

  function handleCancelDiscard() {
    repeatRef.current = null;
    setShowDiscardDialog(false);
  }

  async function handleSubmit(validated: ClothingDraft) {
    if (!item || busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError(undefined);
    try {
      await updateItem(item.id, validated);
      leaveScreen();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Değişiklik kaydedilemedi.');
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <EditClothingScreen
      item={item}
      draft={draft}
      showDiscardDialog={showDiscardDialog}
      busy={busy}
      error={error}
      onChange={setDraft}
      onSubmit={(validated) => { void handleSubmit(validated); }}
      onRequestBack={handleRequestBack}
      onConfirmDiscard={handleConfirmDiscard}
      onCancelDiscard={handleCancelDiscard}
    />
  );
}
