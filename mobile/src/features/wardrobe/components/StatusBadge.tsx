import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Text } from '../../../shared/ui/Text';
import type { ClothingStatus } from '../model/clothingCard.types';
import { clothingStatusLabels } from '../model/clothingStatus';

type StatusBadgeProps = {
  status: ClothingStatus;
};

const statusColors: Record<ClothingStatus, string> = {
  TEMIZ: colors.success,
  KIRLI: colors.danger,
  KULLANIM_DISI: colors.muted,
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const color = statusColors[status];

  return (
    // Sabit yükseklik vermiyoruz sistem yazı boyutu büyüdüğünde rozet metinle birlikte doğal uzar.
    <View style={[styles.badge, { borderColor: color }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text variant="caption" style={[styles.label, { color }]}>
        {clothingStatusLabels[status]}
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
