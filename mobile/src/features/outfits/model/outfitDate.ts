const TURKISH_MONTHS = [
  'Ocak',
  'Şubat',
  'Mart',
  'Nisan',
  'Mayıs',
  'Haziran',
  'Temmuz',
  'Ağustos',
  'Eylül',
  'Ekim',
  'Kasım',
  'Aralık',
] as const;

export const INVALID_OUTFIT_DATE_LABEL = 'Tarih bilgisi yok';

/**
 * ISO tarih metnini gerçek Date zaman damgasına dönüştürür.
 * Geçersiz veya boş tarihlerde null döndürür.
 */
export function parseOutfitTimestamp(iso: string): number | null {
  if (typeof iso !== 'string' || iso.trim().length === 0) {
    return null;
  }
  const timestamp = new Date(iso).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

/**
 * ISO tarih metnini Türkçe okunabilir tarih biçimine dönüştürür.
 * Geçersiz tarihlerde "Tarih bilgisi yok" metnini döndürür.
 */
export function formatOutfitDate(iso: string): string {
  const timestamp = parseOutfitTimestamp(iso);
  if (timestamp === null) {
    return INVALID_OUTFIT_DATE_LABEL;
  }
  const date = new Date(timestamp);
  const day = date.getDate();
  const month = TURKISH_MONTHS[date.getMonth()];
  const year = date.getFullYear();
  return `${day} ${month} ${year}`;
}
