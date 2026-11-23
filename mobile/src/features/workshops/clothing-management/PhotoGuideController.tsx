import { router } from 'expo-router';
import { PhotoGuide } from '../../capture/components/PhotoGuide';
import { useClothingData } from '../../wardrobe/data/ClothingDataContext';

/**
 * Fotoğraf rehberi ekranını oturumluk tercih ve onay akışına bağlayan controller'dır.
 */
export function PhotoGuideController() {
  const { skipPhotoGuide, setSkipPhotoGuide } = useClothingData();

  function handleCancel() {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/clothing-management');
    }
  }

  return (
    <PhotoGuide
      skipNextTime={skipPhotoGuide}
      onSkipChange={setSkipPhotoGuide}
      onContinue={() => router.replace('/clothing-management/review')}
      onCancel={handleCancel}
    />
  );
}
