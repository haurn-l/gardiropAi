import { describe, expect, it } from 'vitest';
import type { ClothingCategory, ClothingDraft, ClothingSeason } from './clothing.types';
import { validateClothingDraft } from './validateClothingDraft';

const baseDraft: ClothingDraft = Object.freeze({
  name: '  Keten Gömlek  ',
  color: '  Ekru  ',
  category: 'UST_GIYIM',
  season: 'YAZ',
  subCategory: '  Gömlek  ',
  hasPrint: false,
  usage: '  Ofis  ',
});

describe('validateClothingDraft', () => {
  it('geçerli taslağı trimlenmiş metinlerle döndürür ve girdiyi değiştirmez', () => {
    const snapshot = { ...baseDraft };
    const result = validateClothingDraft(baseDraft);

    expect(baseDraft).toEqual(snapshot);
    expect(result).toEqual({
      valid: true,
      value: {
        name: 'Keten Gömlek',
        color: 'Ekru',
        category: 'UST_GIYIM',
        season: 'YAZ',
        subCategory: 'Gömlek',
        hasPrint: false,
        usage: 'Ofis',
      },
    });
  });

  it('alt ve üst uzunluk sınırlarını tam olarak kabul eder ve isteğe bağlı boş alanlara izin verir', () => {
    const minDraft: ClothingDraft = {
      name: 'Ab',
      color: 'Al',
      category: 'AKSESUAR',
      season: 'HER_MEVSIM',
      subCategory: '',
      hasPrint: true,
      usage: '',
    };
    const maxDraft: ClothingDraft = {
      name: 'a'.repeat(60),
      color: 'b'.repeat(30),
      category: 'DIS_GIYIM',
      season: 'KIS',
      subCategory: 'c'.repeat(40),
      hasPrint: false,
      usage: 'd'.repeat(50),
    };

    expect(validateClothingDraft(minDraft).valid).toBe(true);
    expect(validateClothingDraft(maxDraft).valid).toBe(true);
  });

  it('yalnızca boşluk, çok kısa veya çok uzun metinlerde ilgili alan hatalarını döndürür', () => {
    const shortResult = validateClothingDraft({
      ...baseDraft,
      name: '   a ',
      color: '   ',
    });

    expect(shortResult.valid).toBe(false);
    if (!shortResult.valid) {
      expect(shortResult.errors.name).toBeTruthy();
      expect(shortResult.errors.color).toBeTruthy();
    }

    const longResult = validateClothingDraft({
      ...baseDraft,
      name: 'a'.repeat(61),
      color: 'b'.repeat(31),
      subCategory: 'c'.repeat(41),
      usage: 'd'.repeat(51),
    });

    expect(longResult.valid).toBe(false);
    if (!longResult.valid) {
      expect(longResult.errors.name).toBeTruthy();
      expect(longResult.errors.color).toBeTruthy();
      expect(longResult.errors.subCategory).toBeTruthy();
      expect(longResult.errors.usage).toBeTruthy();
    }
  });

  it('izin verilmeyen kategori, mevsim ve desen türlerini reddeder', () => {
    const invalidDraft = {
      ...baseDraft,
      category: 'GECERSIZ' as unknown as ClothingCategory,
      season: 'YOK' as unknown as ClothingSeason,
      hasPrint: 'evet' as unknown as boolean,
    };

    const result = validateClothingDraft(invalidDraft);
    expect(result.valid).toBe(false);
    if (!result.valid) {
      expect(result.errors.category).toBeTruthy();
      expect(result.errors.season).toBeTruthy();
      expect(result.errors.hasPrint).toBeTruthy();
    }
  });
});
