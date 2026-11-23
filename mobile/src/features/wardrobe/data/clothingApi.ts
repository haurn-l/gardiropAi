import { File } from 'expo-file-system';
import { fetch } from 'expo/fetch';
import { Platform } from 'react-native';
import type { ClothingDraft, ClothingRecord } from '../model/clothing.types';

type ApiClothing = Omit<ClothingRecord, 'id' | 'imageUri' | 'rating' | 'usage' | 'createdAt' | 'name' |
  'color' | 'subCategory' | 'hasPrint'> & {
  id: number;
  imageUrl: string | null;
  name: string | null;
  color: string | null;
  subCategory: string | null;
  hasPrint: boolean | null;
  tags: string[];
  userRating: ClothingRecord['rating'];
};

type ApiPhotoDraft = { uploadId: string; imageUrl: string };

export const clothingApiOrigin = process.env.EXPO_PUBLIC_API_URL?.trim().replace(/\/+$/, '');
const clothesPath = '/api/clothes';

function toUrl(path: string): string {
  return new URL(path, clothingApiOrigin).toString();
}

async function request(path: string, options?: Parameters<typeof fetch>[1]) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(toUrl(path), { ...options, signal: controller.signal });
    if (!response.ok) {
      const error = await response.json().catch(() => ({})) as { message?: string };
      throw new Error(error.message || `İstek tamamlanamadı (HTTP ${response.status}).`);
    }
    return response;
  } catch (error) {
    if (error instanceof TypeError || controller.signal.aborted) {
      throw new Error('Backend bağlantısı kurulamadı. Wi-Fi ve API adresini kontrol et.');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function requestJson<T>(path: string, options?: Parameters<typeof fetch>[1]): Promise<T> {
  return (await request(path, options)).json() as Promise<T>;
}

function detailsBody(draft: ClothingDraft, additionalTags: readonly string[] = []) {
  const { name, color, category, season, subCategory, hasPrint, usage } = draft;
  const tags = usage ? [usage, ...additionalTags] : [...additionalTags];
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, color, category, season, subCategory, hasPrint, tags }),
  };
}

function toClothing(item: ApiClothing): ClothingRecord {
  return {
    id: String(item.id),
    imageUri: item.imageUrl ? toUrl(item.imageUrl) : undefined,
    name: item.name ?? 'Kıyafet',
    color: item.color ?? '',
    subCategory: item.subCategory ?? '',
    hasPrint: item.hasPrint ?? false,
    season: item.season,
    category: item.category,
    status: item.status,
    favorite: item.favorite,
    rating: item.userRating,
    usage: item.tags[0] ?? '',
    tags: item.tags,
  };
}

export async function listClothing(): Promise<ClothingRecord[]> {
  return (await requestJson<ApiClothing[]>(`${clothesPath}/all`)).map(toClothing);
}

export async function uploadClothingPhoto(uri: string) {
  const form = new FormData();
  if (Platform.OS === 'web') {
    const blob = await (await globalThis.fetch(uri)).blob();
    form.append('photo', blob, 'kiyafet.jpg');
  } else {
    form.append('photo', new File(uri));
  }
  const draft = await requestJson<ApiPhotoDraft>(`${clothesPath}/photo-drafts`, {
    method: 'POST', body: form,
  });
  return { uploadId: draft.uploadId, uri: toUrl(draft.imageUrl) };
}

export async function discardClothingPhoto(uploadId: string): Promise<void> {
  await request(`${clothesPath}/photo-drafts/${uploadId}`, { method: 'DELETE' });
}

export async function confirmClothing(uploadId: string, details: ClothingDraft) {
  const item = await requestJson<ApiClothing>(`${clothesPath}/photo-drafts/${uploadId}/confirm`, {
    method: 'POST', ...detailsBody(details),
  });
  return toClothing(item);
}

export async function updateClothing(current: ClothingRecord, patch: Partial<ClothingRecord>) {
  const path = `${clothesPath}/${current.id}`;
  if (patch.status !== undefined) {
    return toClothing(await requestJson<ApiClothing>(`${path}/status?status=${patch.status}`, { method: 'PUT' }));
  }
  if (patch.favorite !== undefined) {
    return toClothing(await requestJson<ApiClothing>(`${path}/favorite?favorite=${patch.favorite}`, { method: 'PUT' }));
  }
  if (patch.rating !== undefined) {
    const response = patch.rating === null
      ? await requestJson<ApiClothing>(`${path}/rate`, { method: 'DELETE' })
      : await requestJson<ApiClothing>(`${path}/rate?ratingScore=${patch.rating}`, { method: 'PATCH' });
    return toClothing(response);
  }
  return toClothing(await requestJson<ApiClothing>(`${path}/details`, {
    method: 'PUT', ...detailsBody({ ...current, ...patch }, current.tags?.slice(1)),
  }));
}

export async function deleteClothing(id: string): Promise<void> {
  await request(`${clothesPath}/${id}`, { method: 'DELETE' });
}
