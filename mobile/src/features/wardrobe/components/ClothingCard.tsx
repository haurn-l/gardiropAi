import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Icon } from '../../../shared/ui/Icon';
import { Text } from '../../../shared/ui/Text';
import type { ClothingCardProps } from '../model/clothingCard.types';
import { clothingStatusLabels } from '../model/clothingStatus';
import { GarmentImage } from './GarmentImage';
import { StatusBadge } from './StatusBadge';

export function ClothingCard({ item, onOpen, onToggleFavorite }: ClothingCardProps) {
  const favoriteLabel = item.favorite
    ? `${item.name} favorilerden çıkar`
    : `${item.name} favorilere ekle`;

  return (
    // Kart kapsayıcısına sabit yükseklik vermiyoruz; uzun isimler ve büyütülmüş metinler aşağı doğru genişleyebilir.
    <View style={styles.card}>
      {/* Gövde alanı yalnızca detay açma olayını tetikler; favori butonu bu Pressable içine gömülmemiştir. */}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${item.name}, ${item.categoryLabel}, ${item.colorLabel}, ${clothingStatusLabels[item.status]}`}
        accessibilityHint="Kıyafet detaylarını açar."
        onPress={() => onOpen(item.id)}
        style={({ pressed }) => [styles.body, pressed && styles.pressed]}
      >
        <GarmentImage imageUri={item.imageUri} />

        <View style={styles.info}>
          {/* Kıyafet adını tek satıra zorlamıyoruz; dar ekranlarda kesilmeden alt satıra geçebilir. */}
          <Text variant="strong">{item.name}</Text>
          <Text variant="caption" muted>
            {item.categoryLabel} · {item.colorLabel}
          </Text>
          <StatusBadge status={item.status} />
        </View>
      </Pressable>

      {/* Favori butonu gövdeden bağımsız kardeş bileşen olarak konumlandırıldı; basıldığında detay ekranını açmaz. */}
      <Pressable
        accessibilityRole="togglebutton"
        accessibilityState={{ checked: item.favorite }}
        accessibilityLabel={favoriteLabel}
        onPress={() => onToggleFavorite(item.id)}
        style={({ pressed }) => [
          styles.favoriteButton,
          item.favorite && styles.favoriteActive,
          pressed && styles.pressed,
        ]}
      >
        <Icon
          name="heart"
          size={20}
          color={item.favorite ? colors.accentInk : colors.ink}
          filled={item.favorite}
        />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    position: 'relative',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    padding: space.sm,
  },
  body: {
    gap: space.sm,
  },
  info: {
    gap: space.xs,
    paddingTop: space.xs,
  },
  favoriteButton: {
    position: 'absolute',
    top: space.md,
    right: space.md,
    minWidth: 48,
    minHeight: 48,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  favoriteActive: {
    backgroundColor: colors.accent,
    borderColor: colors.primary,
  },
  pressed: {
    opacity: 0.82,
  },
});
