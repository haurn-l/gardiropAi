/**
 * Kıyafet kartının kullanılabilirlik ve temizlik durumunu sabit değerlerle sınırlar.
 * Görünüm katmanında renk ve etiket eşleştirmesi bu tip üzerinden güvenli şekilde yapılır.
 */
export type ClothingStatus = 'TEMIZ' | 'KIRLI' | 'KULLANIM_DISI';

/**
 * Gardırop listesindeki tek bir kıyafet kartının arayüz veri modelidir.
 * Sunucu DTO yapısından veya veritabanı şemasından bağımsız bir görünüm sözleşmesi sağlar.
 */
export type ClothingCardItem = {
  id: string;
  name: string;
  imageUri?: string;
  categoryLabel: string;
  colorLabel: string;
  status: ClothingStatus;
  favorite: boolean;
};

/**
 * Kıyafet kartı bileşeninin üst ekrandan alacağı veri ve olay sözleşmesidir.
 * Favori durumu kart içinde tutulmaz; tek doğruluk kaynağı olarak üst ekrandan yönetilir.
 */
export type ClothingCardProps = {
  item: ClothingCardItem;
  onOpen: (id: string) => void;
  onToggleFavorite: (id: string) => void;
};
