import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Icon } from '../../../shared/ui/Icon';
import { Text } from '../../../shared/ui/Text';

type WardrobeEmptyStateProps = {
  kind: 'empty-wardrobe' | 'no-matches';
  onAddClothing: () => void;
  onResetFilters: () => void;
};

/**
 * Gardıropta hiç kayıt olmaması ile aktif filtrelerin sonuç döndürmemesi
 * durumlarını birbirinden ayırarak kullanıcıya uygun eylemi sunar.
 */
export function WardrobeEmptyState({
  kind,
  onAddClothing,
  onResetFilters,
}: WardrobeEmptyStateProps) {
  const isWardrobeEmpty = kind === 'empty-wardrobe';

  return (
    <View style={styles.container}>
      <View style={styles.iconCircle} accessible={false}>
        <Icon name={isWardrobeEmpty ? 'wardrobe' : 'search'} size={28} color={colors.accentInk} />
      </View>

      <Text variant="heading" style={styles.centeredText}>
        {isWardrobeEmpty ? 'Gardırobun henüz boş' : 'Aramana uygun kıyafet yok'}
      </Text>

      <Text muted style={styles.centeredText}>
        {isWardrobeEmpty
          ? 'İlk kıyafetini ekleyerek gardırobunu oluşturmaya başlayabilirsin.'
          : 'Farklı bir arama terimi deneyebilir veya seçili filtreleri temizleyebilirsin.'}
      </Text>

      {isWardrobeEmpty ? (
        <Button label="Kıyafet ekle" icon="plus" onPress={onAddClothing} />
      ) : (
        <Button label="Filtreleri temizle" variant="secondary" onPress={onResetFilters} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: space.xl,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    gap: space.md,
  },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: radius.full,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  centeredText: {
      width : '100%',
    textAlign: 'center',
  },
});
