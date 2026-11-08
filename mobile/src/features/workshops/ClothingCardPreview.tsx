import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, space } from '../../shared/theme/tokens';
import { Button } from '../../shared/ui/Button';
import { Header } from '../../shared/ui/Header';
import { Text } from '../../shared/ui/Text';
import { ClothingCard } from '../wardrobe/components/ClothingCard';
import type { ClothingCardItem } from '../wardrobe/model/clothingCard.types';

const VALID_SHIRT_URI =
  'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=500&q=80';

const VALID_JACKET_URI =
  'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=500&q=80';

const BROKEN_IMAGE_URI = 'https://invalid.gardiropai.local/broken-garment.jpg';

// Temiz, kirli/favori, kullanım dışı/uzun isim, eksik/bozuk görsel ve kaydırma testi için örnek veri.
const initialItems: ClothingCardItem[] = [
  {
    id: 'item-1',
    name: 'Keten Gömlek',
    imageUri: VALID_SHIRT_URI,
    categoryLabel: 'Üst Giyim',
    colorLabel: 'Ekru',
    status: 'TEMIZ',
    favorite: false,
  },
  {
    id: 'item-2',
    name: 'Deri Ceket',
    imageUri: VALID_JACKET_URI,
    categoryLabel: 'Dış Giyim',
    colorLabel: 'Kahverengi',
    status: 'KIRLI',
    favorite: true,
  },
  {
    id: 'item-3',
    name: 'Kışlık Kalın Örgü Boğazlı Yün Kazak',
    categoryLabel: 'Triko',
    colorLabel: 'Antrasit',
    status: 'KULLANIM_DISI',
    favorite: false,
  },
  {
    id: 'item-4',
    name: 'Pamuklu Tişört',
    imageUri: BROKEN_IMAGE_URI,
    categoryLabel: 'Üst Giyim',
    colorLabel: 'Turuncu',
    status: 'TEMIZ',
    favorite: false,
  },
  {
    id: 'item-5',
    name: 'Lacivert Tişört',
    imageUri: VALID_SHIRT_URI,
    categoryLabel: 'Üst Giyim',
    colorLabel: 'Lacivert',
    status: 'TEMIZ',
    favorite: true,
  },
];

export function ClothingCardPreview() {
  const [items, setItems] = useState<ClothingCardItem[]>(initialItems);
  const [favoriteCalls, setFavoriteCalls] = useState(0);
  const [isBrokenImageFixed, setIsBrokenImageFixed] = useState(false);
  const rows: ClothingCardItem[][] = [];

  for (let i = 0; i < items.length; i += 2) {
    rows.push(items.slice(i, i + 2));
  }

  function handleOpen(_id: string) {
    router.push({ pathname: '/navigation-preview', params: { kind: 'item' } });
  }

  function handleToggleFavorite(id: string) {
    setFavoriteCalls((count) => count + 1);
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, favorite: !item.favorite } : item))
    );
  }

  function toggleFirstFavoriteExternally() {
    setItems((current) =>
      current.map((item, index) => (index === 0 ? { ...item, favorite: !item.favorite } : item))
    );
  }

  function toggleBrokenImageUri() {
    const nextFixed = !isBrokenImageFixed;
    setIsBrokenImageFixed(nextFixed);
    setItems((current) =>
      current.map((item) =>
        item.id === 'item-4'
          ? { ...item, imageUri: nextFixed ? VALID_SHIRT_URI : BROKEN_IMAGE_URI }
          : item
      )
    );
  }

  return (
    <SafeAreaView style={styles.screen}>
      <Header
        title="Kıyafet kartı örnekleri"
        subtitle="Görev 03 · Görsel, durum rozeti ve favori"
        onBack={() => (router.canGoBack() ? router.back() : router.replace('/'))}
      />
      <ScrollView contentContainerStyle={styles.content}>
        <Text accessibilityLiveRegion="polite">Favori çağrısı: {favoriteCalls}</Text>
        <Button
          label="Favoriyi dışarıdan değiştir"
          variant="secondary"
          onPress={toggleFirstFavoriteExternally}
        />
        <Button
          label={isBrokenImageFixed ? 'Görseli tekrar bozuk URI yap' : 'Bozuk görseli geçerli URI yap'}
          variant="secondary"
          onPress={toggleBrokenImageUri}
        />
        {rows.map((pair) => (
          <View key={pair[0].id} style={styles.row}>
            <ClothingCard item={pair[0]} onOpen={handleOpen} onToggleFavorite={handleToggleFavorite} />
            {pair[1] ? (
              <ClothingCard item={pair[1]} onOpen={handleOpen} onToggleFavorite={handleToggleFavorite} />
            ) : (
              <View style={styles.emptyColumn} />
            )}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, gap: space.md },
  row: { flexDirection: 'row', gap: space.md, alignItems: 'stretch' },
  emptyColumn: { flex: 1 },
});