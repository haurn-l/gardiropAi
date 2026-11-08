import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { ClothingStatus } from '../model/clothingCard.types';

type StatusBadgeProps = {
  status: ClothingStatus;
};

// Durum bilgisini yalnızca renge bağlı bırakmamak için her durumu açık türkçe etiketle eşleştiriyoruz.
const statusConfig: Record<ClothingStatus, { label: string; color: string }> = {
  TEMIZ: { label: 'Temiz', color: colors.success },
  KIRLI: { label: 'Kirli', color: colors.danger },
  KULLANIM_DISI: { label: 'Kullanım dışı', color: colors.muted },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const current = statusConfig[status];

  return (
    // Sabit yükseklik vermiyoruz sistem yazı boyutu büyüdüğünde rozet metinle birlikte doğal uzar.
    <View style={[styles.badge, { borderColor: current.color }]}>
      <View style={[styles.dot, { backgroundColor: current.color }]} />
      <Text variant="caption" style={[styles.label, { color: current.color }]}>
        {current.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    paddingHorizontal: space.sm,
    paddingVertical: space.xs,
    borderRadius: radius.sm,
    borderWidth: 1,
    backgroundColor: colors.background,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radius.full,
  },
  label: {
    fontWeight: '600',
    flexShrink: 1,
  },
});
