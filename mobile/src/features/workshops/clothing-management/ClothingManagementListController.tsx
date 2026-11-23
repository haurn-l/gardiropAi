import { useMemo, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Header } from '../../../shared/ui/Header';
import { Text } from '../../../shared/ui/Text';
import { WardrobeEmptyState } from '../../wardrobe/components/WardrobeEmptyState';
import { WardrobeList } from '../../wardrobe/components/WardrobeList';
import { WardrobeToolbar } from '../../wardrobe/components/WardrobeToolbar';
import { selectClothingItems } from '../../wardrobe/model/selectClothingItems';
import { toClothingCard } from '../../wardrobe/model/toClothingCard';
import {
  defaultWardrobeFilters,
  type WardrobeFilters,
} from '../../wardrobe/model/wardrobeFilters';
import { useClothingData } from '../../wardrobe/data/ClothingDataContext';

/**
 * Kıyafet yönetimi örnek akışının ana liste controller'ıdır.
 * Oturumluk kayıtları mevcut WardrobeList bileşenine bağlar ve teknik hata kontrolünü sunar.
 */
export function ClothingManagementListController() {
  const { items, skipPhotoGuide, simulateError, setSimulateError, updateItem, server } = useClothingData();
  const [filters, setFilters] = useState<WardrobeFilters>(defaultWardrobeFilters);
  const [error, setError] = useState<string | undefined>(undefined);
  const busyRef = useRef(false);

  const cards = useMemo(() => items.map(toClothingCard), [items]);
  const categories = useMemo(
    () => Array.from(new Set(cards.map((card) => card.categoryLabel))),
    [cards]
  );
  const visibleCards = useMemo(() => selectClothingItems(cards, filters), [cards, filters]);

  function handleOpen(id: string) {
    router.push({ pathname: '/clothing-management/[id]', params: { id } });
  }

  function handleAddClothing() {
    router.push(skipPhotoGuide ? '/clothing-management/review' : '/clothing-management/guide');
  }

  async function handleToggleFavorite(id: string) {
    const target = items.find((item) => item.id === id);
    if (!target || busyRef.current) {
      return;
    }
    busyRef.current = true;
    setError(undefined);
    try {
      await updateItem(id, { favorite: !target.favorite });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Favori güncellenemedi.');
    } finally {
      busyRef.current = false;
    }
  }

  const listHeader = (
    <View style={styles.headerBlock}>
      {!server ? <Text variant="caption" muted>Oturumluk örnek gardırop</Text> : null}
      <View style={styles.controls}>
        <Button label="Kıyafet ekle" icon="plus" disabled={server?.loading} onPress={handleAddClothing} />
        {server?.error ? <Button label="Tekrar dene" variant="secondary" onPress={server.reload} /> : null}
        {!server ? (
          <>
            <Button
              label={simulateError ? 'Hata simülasyonu: Açık' : 'Hata simülasyonu: Kapalı'}
              variant={simulateError ? 'danger' : 'secondary'}
              onPress={() => setSimulateError(!simulateError)}
            />
            <Button label="Geçersiz kayıt testi" variant="secondary" onPress={() => handleOpen('bilinmeyen-kayit')} />
          </>
        ) : null}
      </View>
      {server?.loading ? <Text variant="caption" muted>Gardırop yükleniyor…</Text> : null}
      {server?.error || error ? (
        <View style={styles.errorBox}>
          <Text variant="caption" accessibilityLiveRegion="polite" style={styles.errorText}>
            {server?.error ?? error}
          </Text>
        </View>
      ) : null}
      <WardrobeToolbar filters={filters} categories={categories} onChange={setFilters} />
      <Text variant="caption" muted accessibilityLiveRegion="polite">
        Gösterilen kıyafet: {visibleCards.length} / {cards.length}
      </Text>
    </View>
  );

  const emptyState = (
    <WardrobeEmptyState
      kind={cards.length === 0 ? 'empty-wardrobe' : 'no-matches'}
      onAddClothing={handleAddClothing}
      onResetFilters={() => setFilters(defaultWardrobeFilters)}
    />
  );

  return (
    <SafeAreaView style={styles.screen}>
      <Header
        title="Kıyafet yönetimi"
        onBack={server && !router.canGoBack() ? undefined
          : () => (router.canGoBack() ? router.back() : router.replace('/'))}
      />
      <WardrobeList
        items={visibleCards}
        onOpen={handleOpen}
        onToggleFavorite={(id) => { void handleToggleFavorite(id); }}
        header={listHeader}
        emptyState={server?.loading || server?.error ? undefined : emptyState}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  headerBlock: { gap: space.md, paddingBottom: space.xs },
  controls: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  errorBox: { padding: space.md, borderRadius: radius.md, backgroundColor: colors.dangerSoft },
  errorText: { color: colors.danger },
});
