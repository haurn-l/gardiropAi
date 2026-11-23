import { router } from 'expo-router';
import { PhotoGuide } from '../../capture/components/PhotoGuide';
import { useClothingDemo } from '../demo/ClothingDemoContext';

/**
 * Fotoğraf rehberi ekranını oturumluk tercih ve onay akışına bağlayan controller'dır.
 */
export function PhotoGuideController() {
  const { skipPhotoGuide, setSkipPhotoGuide } = useClothingDemo();

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
