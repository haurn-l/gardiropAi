import type { ClothingRecord } from '../../wardrobe/model/clothing.types';

export type MockPhotoOption = {
  id: string;
  label: string;
  uri: string;
};

const SHIRT_URI =
  'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=600&q=80';
const JACKET_URI =
  'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=600&q=80';
const SWEATER_URI =
  'https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=600&q=80';
const SNEAKER_URI =
  'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=600&q=80';

/**
 * Fotoğraf onay ekranında "Tekrar çek" aksiyonu için kullanılan örnek fotoğraf listesidir.
 */
export const mockPhotoOptions: readonly MockPhotoOption[] = [
  { id: 'photo-shirt', label: 'Beyaz tişört fotoğrafı', uri: SHIRT_URI },
  { id: 'photo-jacket', label: 'Siyah ceket fotoğrafı', uri: JACKET_URI },
  { id: 'photo-sweater', label: 'Örgü kazak fotoğrafı', uri: SWEATER_URI },
  { id: 'photo-sneaker', label: 'Spor ayakkabı fotoğrafı', uri: SNEAKER_URI },
];

/**
 * Kıyafet yönetimi örnek akışı için oturumluk başlangıç kayıtlarıdır.
 */
export const initialClothingRecords: readonly ClothingRecord[] = [
  {
    id: 'cl-01',
    name: 'Keten Gömlek',
    imageUri: SHIRT_URI,
    category: 'UST_GIYIM',
    color: 'Ekru',
    season: 'YAZ',
    subCategory: 'Gömlek',
    hasPrint: false,
    usage: 'Günlük ve ofis',
    status: 'TEMIZ',
    favorite: true,
    rating: 5,
    createdAt: '2026-11-18T09:30:00.000Z',
  },
  {
    id: 'cl-02',
    name: 'Deri Ceket',
    imageUri: JACKET_URI,
    category: 'DIS_GIYIM',
    color: 'Siyah',
    season: 'SONBAHAR',
    subCategory: 'Biker ceket',
    hasPrint: false,
    usage: 'Akşam buluşması',
    status: 'TEMIZ',
    favorite: true,
    rating: 4,
    createdAt: '2026-11-19T14:15:00.000Z',
  },
  {
    id: 'cl-03',
    name: 'Yüksek Bel Kumaş Pantolon',
    category: 'ALT_GIYIM',
    color: 'Lacivert',
    season: 'HER_MEVSIM',
    subCategory: 'Kumaş pantolon',
    hasPrint: false,
    usage: 'Ofis',
    status: 'KIRLI',
    favorite: false,
    rating: 3,
    createdAt: '2026-11-20T11:00:00.000Z',
  },
  {
    id: 'cl-04',
    name: 'Örgü Yün Kazak',
    imageUri: SWEATER_URI,
    category: 'UST_GIYIM',
    color: 'Antrasit',
    season: 'KIS',
    subCategory: 'Triko kazak',
    hasPrint: true,
    usage: 'Hafta sonu',
    status: 'TEMIZ',
    favorite: false,
    rating: null,
    createdAt: '2026-11-20T16:45:00.000Z',
  },
  {
    id: 'cl-05',
    name: 'Koşu Ayakkabısı',
    imageUri: SNEAKER_URI,
    category: 'AYAKKABI',
    color: 'Kırmızı',
    season: 'ILKBAHAR',
    subCategory: 'Sneaker',
    hasPrint: true,
    usage: 'Spor',
    status: 'KULLANIM_DISI',
    favorite: false,
    rating: 2,
    createdAt: '2026-11-21T08:20:00.000Z',
  },
  {
    id: 'cl-06',
    name: 'Minimal Deri Kemer',
    category: 'AKSESUAR',
    color: 'Kahverengi',
    season: 'HER_MEVSIM',
    subCategory: 'Kemer',
    hasPrint: false,
    usage: 'Klasik',
    status: 'TEMIZ',
    favorite: false,
    rating: null,
    createdAt: '2026-11-21T18:10:00.000Z',
  },
];
