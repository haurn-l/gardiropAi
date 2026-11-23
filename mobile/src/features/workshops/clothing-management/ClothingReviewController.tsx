import { useRef, useState } from 'react';
import { router, usePreventRemove } from 'expo-router';
import { ClothingReview } from '../../capture/components/ClothingReview';
import type { ClothingDraft } from '../../wardrobe/model/clothing.types';
import { createEmptyClothingDraft } from '../../wardrobe/model/clothingOptions';
import { useClothingDemo } from '../demo/ClothingDemoContext';
import { mockPhotoOptions } from './clothingDemoData';
import { MockPhotoPickerModal } from './MockPhotoPickerModal';

/**
 * Fotoğraf sonrası kıyafet onay ekranını oturumluk sağlayıcıya bağlayan controller'dır.
 * Kaydetme onayı olmadan kayıt oluşturmaz; başarılı eklemede geri yığınında onay ekranı bırakmaz.
 */
export function ClothingReviewController() {
  const { createItem } = useClothingDemo();
  const [imageUri, setImageUri] = useState(mockPhotoOptions[0].uri);
  const [draft, setDraft] = useState<ClothingDraft>(() => createEmptyClothingDraft());
  const [pickerVisible, setPickerVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const busyRef = useRef(false);
  // Kayıt beklerken sistem geri tuşu/geri hareketi ikinci bir gezinme başlatmamalı.
  const disablePrevention = usePreventRemove(busy);

  function leaveToList() {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/clothing-management');
    }
  }

  async function handleSave(validated: ClothingDraft) {
    if (busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError(undefined);
    try {
      await createItem(validated, imageUri);
      setBusy(false);
      disablePrevention();
      leaveToList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kıyafet eklenemedi.');
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function handleRetake() {
    if (busyRef.current) {
      return;
    }
    setDraft(createEmptyClothingDraft());
    setError(undefined);
    setPickerVisible(true);
  }

  function handleCancel() {
    if (!busyRef.current) {
      leaveToList();
    }
  }

  return (
    <>
      <ClothingReview
        imageUri={imageUri}
        draft={draft}
        onChange={setDraft}
        onSave={(validated) => { void handleSave(validated); }}
        onRetake={handleRetake}
        onCancel={handleCancel}
        busy={busy}
        error={error}
      />
      <MockPhotoPickerModal
        visible={pickerVisible}
        selectedUri={imageUri}
        onSelect={(uri) => {
          setImageUri(uri);
          setPickerVisible(false);
        }}
        onClose={() => setPickerVisible(false)}
      />
    </>
  );
}
