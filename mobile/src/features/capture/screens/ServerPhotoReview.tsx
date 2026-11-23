import * as ImagePicker from 'expo-image-picker';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { router, usePreventRemove } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { ClothingReview } from '../components/ClothingReview';
import { useClothingData } from '../../wardrobe/data/ClothingDataContext';
import { discardClothingPhoto, uploadClothingPhoto } from '../../wardrobe/data/clothingApi';
import { createEmptyClothingDraft } from '../../wardrobe/model/clothingOptions';
import type { ClothingDraft } from '../../wardrobe/model/clothing.types';

type UploadedPhoto = Awaited<ReturnType<typeof uploadClothingPhoto>>;

function discard(photo?: UploadedPhoto) {
  if (photo) {
    void discardClothingPhoto(photo.uploadId).catch(() => {});
  }
}

async function preparePhoto(asset: ImagePicker.ImagePickerAsset): Promise<string> {
  const context = ImageManipulator.manipulate(asset.uri);
  if (Math.max(asset.width, asset.height) > 1600) {
    context.resize(asset.width >= asset.height ? { width: 1600 } : { height: 1600 });
  }
  const image = await context.renderAsync();
  try {
    return (await image.saveAsync({ format: SaveFormat.JPEG, compress: 0.82 })).uri;
  } finally {
    image.release();
    context.release();
  }
}

export function ServerPhotoReview() {
  const { createItem } = useClothingData();
  const [photo, setPhoto] = useState<UploadedPhoto>();
  const [draft, setDraft] = useState<ClothingDraft>(createEmptyClothingDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const busyRef = useRef(false);
  const currentPhoto = useRef<UploadedPhoto | undefined>(undefined);
  const disablePrevention = usePreventRemove(busy);

  useEffect(() => () => discard(currentPhoto.current), []);

  async function run(task: () => Promise<void>) {
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

  async function pickPhoto(source: 'camera' | 'library') {
    await run(async () => {
      if (source === 'camera' && Platform.OS !== 'web' &&
          !(await ImagePicker.requestCameraPermissionsAsync()).granted) {
        throw new Error('Fotoğraf çekmek için kamera izni ver.');
      }
      const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'] };
      const result = source === 'camera'
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);
      if (result.canceled) {
        return;
      }
      const uploaded = await uploadClothingPhoto(await preparePhoto(result.assets[0]));
      discard(currentPhoto.current);
      currentPhoto.current = uploaded;
      setPhoto(uploaded);
    });
  }

  function leave() {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/clothing-management');
    }
  }

  async function save(details: ClothingDraft) {
    await run(async () => {
      await createItem(details, photo);
      currentPhoto.current = undefined;
      disablePrevention();
      leave();
    });
  }

  return (
    <ClothingReview imageUri={photo?.uri} draft={draft} onChange={setDraft}
      onSave={(details) => { void save(details); }}
      onRetake={() => { void pickPhoto('camera'); }}
      onPickFromGallery={() => { void pickPhoto('library'); }}
      onCancel={() => { if (!busyRef.current) leave(); }}
      busy={busy} error={error} />
  );
}
