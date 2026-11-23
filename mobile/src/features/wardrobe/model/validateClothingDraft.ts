import type { ClothingDraft } from './clothing.types';
import { clothingCategories, clothingSeasons } from './clothingOptions';

export type ClothingDraftErrors = Partial<Record<keyof ClothingDraft, string>>;

export type ClothingDraftValidationResult =
  | { valid: true; value: ClothingDraft }
  | { valid: false; errors: ClothingDraftErrors };

/**
 * Kıyafet form taslağını kurallara göre doğrular.
 * Girdi nesnesini değiştirmez; geçerli sonuçta tüm metin alanlarını kırpılmış döndürür.
 */
export function validateClothingDraft(draft: ClothingDraft): ClothingDraftValidationResult {
  const errors: ClothingDraftErrors = {};

  const name = draft.name.trim();
  const color = draft.color.trim();
  const subCategory = draft.subCategory.trim();
  const usage = draft.usage.trim();

  if (name.length < 2) {
    errors.name = 'Kıyafet adı en az 2 karakter olmalıdır.';
  } else if (name.length > 60) {
    errors.name = 'Kıyafet adı en fazla 60 karakter olabilir.';
  }

  if (color.length < 2) {
    errors.color = 'Renk en az 2 karakter olmalıdır.';
  } else if (color.length > 30) {
    errors.color = 'Renk en fazla 30 karakter olabilir.';
  }

  if (subCategory.length > 40) {
    errors.subCategory = 'Alt tür en fazla 40 karakter olabilir.';
  }

  if (usage.length > 50) {
    errors.usage = 'Kullanım alanı en fazla 50 karakter olabilir.';
  }

  if (!(clothingCategories as readonly string[]).includes(draft.category)) {
    errors.category = 'Geçerli bir kategori seçiniz.';
  }

  if (!(clothingSeasons as readonly string[]).includes(draft.season)) {
    errors.season = 'Geçerli bir mevsim seçiniz.';
  }

  if (typeof draft.hasPrint !== 'boolean') {
    errors.hasPrint = 'Desen bilgisi geçersiz.';
  }

  if (Object.keys(errors).length > 0) {
    return { valid: false, errors };
  }

  return {
    valid: true,
    value: {
      name,
      color,
      category: draft.category,
      season: draft.season,
      subCategory,
      hasPrint: draft.hasPrint,
      usage,
    },
  };
}
