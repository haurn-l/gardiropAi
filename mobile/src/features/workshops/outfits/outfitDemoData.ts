import type { RatingValue } from '../../../shared/ui/rating.types';
import type { OutfitRecord } from '../../outfits/model/outfit.types';
import { createOutfitRecord } from '../../outfits/model/outfitSnapshot';
import { initialClothingRecords } from '../clothing-management/clothingDemoData';

const outfitTitles = [
  'Hafta Sonu Kahve ve Yürüyüş Kombini',
  'Şehir İçi Akşam Buluşması İçin Katmanlı Siyah Kombin',
  'Minimal Ofis Günü',
  'Serin Sonbahar Yürüyüşü',
  'Pazar Brunch Rahatlığı',
  'Yağmurlu Gün Hazırlığı',
  'Kısa Seyahat ve Tren Yolculuğu Kombini',
  'Akşam Yemeği Şıklığı',
  'Spor Sonrası Rahat Geçiş',
  'Klasik Toplantı Günü',
  'Hafta İçi Hızlı Seçim',
  'Sergi ve Galeri Gezisi',
  'Kışlık Katmanlı Dış Mekan Kombini',
  'Sade Günlük Stil',
  'Bahar Akşamı Buluşması',
  'Kampüs ve Kütüphane Günü',
  'Uzun Gün İçin Konfor Odaklı Şehir Kombini',
  'Hafif Esintili Sahil Yürüyüşü',
  'Cuma Serbest Ofis',
  'Akşamüstü Sinema Planı',
  'Mevsim Geçişi Kombini',
  'Minimalist Siyah Ekru Uyumu',
  'Hafta Sonu Pazar Alışverişi',
  'Sıcak Gün İçin Hafif Katman',
  'Erken Sabah Kahve Molası',
  'Tarihsiz Arşiv Kaydı (Geçersiz Tarih Testi)',
] as const;

const ratingPattern: readonly (RatingValue | null)[] = [5, 4, null, 3, 5, 2, null, 4, 1];

function pickPieces(index: number) {
  const total = initialClothingRecords.length;
  const count = 2 + (index % 3);
  const selected = [];
  for (let offset = 0; offset < count; offset += 1) {
    selected.push(initialClothingRecords[(index + offset) % total]);
  }
  return selected;
}

function buildCreatedAt(index: number): string {
  // Son kayıt geçersiz tarih durumunu ("Tarih bilgisi yok") ve en sona düşmesini sınar.
  if (index === outfitTitles.length - 1) {
    return 'gecersiz-tarih';
  }
  const baseMs = Date.UTC(2026, 10, 22, 18, 0, 0);
  const offsetHours = index * 19;
  return new Date(baseMs - offsetHours * 60 * 60 * 1000).toISOString();
}

/**
 * Kombin geçmişi örnek akışı için oturumluk başlangıç kayıtlarıdır (26 kayıt).
 * Tüm parçalar kaynak kıyafetlerden bağımsız kopyalar (snapshot) olarak oluşturulur.
 */
export const initialOutfitRecords: readonly OutfitRecord[] = outfitTitles.map((title, index) =>
  createOutfitRecord({
    id: `out-${String(index + 1).padStart(2, '0')}`,
    name: title,
    createdAt: buildCreatedAt(index),
    rating: ratingPattern[index % ratingPattern.length],
    items: pickPieces(index),
  })
);
