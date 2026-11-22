import type { ClothingCardItem } from '../../wardrobe/model/clothingCard.types';

const SHIRT_URI =
  'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=500&q=80';
const JACKET_URI =
  'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=500&q=80';
const BROKEN_URI = 'https://invalid.gardiropai.local/broken-garment.jpg';

/**
 * Gardırop listesi, arama ve filtre önizlemesi için en az 30 benzersiz kayıt içeren örnek veri kümesidir.
 * Türkçe karakter aramalarını, üç farklı durumu, favorileri ve eksik/bozuk görselleri test eder.
 */
export const wardrobePreviewItems: readonly ClothingCardItem[] = [
  { id: 'w-01', name: 'İpek Gömlek', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Ekru', status: 'TEMIZ', favorite: true },
  { id: 'w-02', name: 'Kışlık Kaşe Mont', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Siyah', status: 'TEMIZ', favorite: false },
  { id: 'w-03', name: 'Yüksek Bel Kumaş Pantolon', categoryLabel: 'Alt Giyim', colorLabel: 'Lacivert', status: 'TEMIZ', favorite: true },
  { id: 'w-04', name: 'Boğazlı Yün Kazak', imageUri: BROKEN_URI, categoryLabel: 'Triko', colorLabel: 'Antrasit', status: 'KIRLI', favorite: false },
  { id: 'w-05', name: 'Su Geçirmez Trençkot', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Bej', status: 'TEMIZ', favorite: true },
  { id: 'w-06', name: 'Organik Pamuklu Tişört', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Beyaz', status: 'KIRLI', favorite: false },
  { id: 'w-07', name: 'Ketenden Yazlık Şort', categoryLabel: 'Alt Giyim', colorLabel: 'Çağla Yeşili', status: 'TEMIZ', favorite: false },
  { id: 'w-08', name: 'Deri Biker Ceket', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Kahverengi', status: 'KULLANIM_DISI', favorite: true },
  { id: 'w-09', name: 'Çizgili Polo Yaka Tişört', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'İndigo', status: 'TEMIZ', favorite: false },
  { id: 'w-10', name: 'Kalın Örgü Hırka', categoryLabel: 'Triko', colorLabel: 'Krem', status: 'TEMIZ', favorite: true },
  { id: 'w-11', name: 'Klasik Kesim Kot Pantolon', categoryLabel: 'Alt Giyim', colorLabel: 'Mavi', status: 'KIRLI', favorite: false },
  { id: 'w-12', name: 'Kapüşonlu Sweatshirt', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Gri', status: 'TEMIZ', favorite: false },
  { id: 'w-13', name: 'Şişme Yelek', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Haki', status: 'TEMIZ', favorite: false },
  { id: 'w-14', name: 'Kaşmir V Yaka Kazak', categoryLabel: 'Triko', colorLabel: 'Bordo', status: 'KULLANIM_DISI', favorite: true },
  { id: 'w-15', name: 'Pileli Midi Etek', categoryLabel: 'Alt Giyim', colorLabel: 'Zümrüt Yeşili', status: 'TEMIZ', favorite: false },
  { id: 'w-16', name: 'Saten Gece Bluzu', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Şampanya', status: 'KIRLI', favorite: true },
  { id: 'w-17', name: 'Kot Ceket', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Açık Mavi', status: 'TEMIZ', favorite: false },
  { id: 'w-18', name: 'Kargo Cepli Pantolon', categoryLabel: 'Alt Giyim', colorLabel: 'Toprak', status: 'TEMIZ', favorite: false },
  { id: 'w-19', name: 'Yarım Fermuarlı Triko', categoryLabel: 'Triko', colorLabel: 'füme', status: 'KIRLI', favorite: false },
  { id: 'w-20', name: 'Keten Uzun Kollu Gömlek', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Gökyüzü Mavisi', status: 'TEMIZ', favorite: true },
  { id: 'w-21', name: 'Kruvaze Blazer Ceket', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Ekose Gri', status: 'TEMIZ', favorite: false },
  { id: 'w-22', name: 'Eşofman Altı', categoryLabel: 'Alt Giyim', colorLabel: 'Siyah', status: 'KIRLI', favorite: false },
  { id: 'w-23', name: 'İnce Mevsimlik Triko', categoryLabel: 'Triko', colorLabel: 'Lila', status: 'TEMIZ', favorite: false },
  { id: 'w-24', name: 'Oduncu Gömleği', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Kırmızı Siyah', status: 'KULLANIM_DISI', favorite: false },
  { id: 'w-25', name: 'Rüzgarlık Yağmurluk', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Sarı', status: 'TEMIZ', favorite: true },
  { id: 'w-26', name: 'Kadife Pantolon', categoryLabel: 'Alt Giyim', colorLabel: 'Tarçın', status: 'TEMIZ', favorite: false },
  { id: 'w-27', name: 'Saç Örgülü Yün Süveter', categoryLabel: 'Triko', colorLabel: 'Hardal', status: 'TEMIZ', favorite: false },
  { id: 'w-28', name: 'Bisiklet Yaka Uzun Tişört', imageUri: SHIRT_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Zeytin Yeşili', status: 'KIRLI', favorite: false },
  { id: 'w-29', name: 'Uzun Kışlık Parka', imageUri: JACKET_URI, categoryLabel: 'Dış Giyim', colorLabel: 'Lacivert', status: 'KULLANIM_DISI', favorite: false },
  { id: 'w-30', name: 'Geniş Paça Keten Pantolon', categoryLabel: 'Alt Giyim', colorLabel: 'Kırık Beyaz', status: 'TEMIZ', favorite: true },
  { id: 'w-31', name: 'Fitilli Triko Atlet', categoryLabel: 'Triko', colorLabel: 'Turuncu', status: 'TEMIZ', favorite: false },
  { id: 'w-32', name: 'Oversize Baskılı Tişört', imageUri: BROKEN_URI, categoryLabel: 'Üst Giyim', colorLabel: 'Füme', status: 'TEMIZ', favorite: false },
];
