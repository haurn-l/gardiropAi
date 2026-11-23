import type { ClothingDraft, ClothingRecord } from '../../wardrobe/model/clothing.types';

/**
 * Mevcut kıyafet kaydından form düzenlemesi için ayrı bir taslak kopyası üretir.
 */
export function recordToClothingDraft(record: ClothingRecord): ClothingDraft {
  return {
    name: record.name,
    color: record.color,
    category: record.category,
    season: record.season,
    subCategory: record.subCategory,
    hasPrint: record.hasPrint,
    usage: record.usage,
  };
}

/**
 * Düzenleme taslağında orijinal kayda göre kaydedilmemiş değişiklik olup olmadığını döndürür.
 */
export function isClothingDraftDirty(
  original: ClothingRecord,
  draft: ClothingDraft
): boolean {
  return (
    original.name !== draft.name ||
    original.color !== draft.color ||
    original.category !== draft.category ||
    original.season !== draft.season ||
    original.subCategory !== draft.subCategory ||
    original.hasPrint !== draft.hasPrint ||
    original.usage !== draft.usage
  );
}

/**
 * Doğrulanmış taslak ve fotoğraf adresinden yeni bir kıyafet kaydı oluşturur.
 */
export function buildNewClothingRecord(
  id: string,
  draft: ClothingDraft,
  imageUri: string | undefined,
  createdAt: string
): ClothingRecord {
  return {
    ...draft,
    id,
    ...(imageUri ? { imageUri } : {}),
    status: 'TEMIZ',
    favorite: false,
    rating: null,
    createdAt,
  };
}

/**
 * Belirli bir kimliğe sahip kaydı girdiyi değiştirmeden günceller.
 */
export function patchClothingRecordInList(
  records: readonly ClothingRecord[],
  id: string,
  patch: Partial<ClothingRecord>
): ClothingRecord[] {
  return records.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

/**
 * Belirli bir kimliğe sahip kaydı listeden immutable biçimde çıkarır.
 */
export function removeClothingRecordFromList(
  records: readonly ClothingRecord[],
  id: string
): ClothingRecord[] {
  return records.filter((item) => item.id !== id);
}
