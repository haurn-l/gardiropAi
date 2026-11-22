import { Pressable, StyleSheet, TextInput, View } from 'react-native';
import { colors, fonts, radius, space } from '../../../shared/theme/tokens';
import { Icon } from '../../../shared/ui/Icon';
import { Text } from '../../../shared/ui/Text';
import type { ClothingStatus } from '../model/clothingCard.types';
import { clothingStatusLabels } from '../model/clothingStatus';
import type { WardrobeFilters } from '../model/wardrobeFilters';
import { FilterChip } from './FilterChip';

export type WardrobeToolbarProps = {
  filters: WardrobeFilters;
  categories: readonly string[];
  onChange: (next: WardrobeFilters) => void;
};

const statusOptions: readonly ClothingStatus[] = ['TEMIZ', 'KIRLI', 'KULLANIM_DISI'];

/**
 * Arama, kategori, durum ve favori filtrelerini kontrollü olarak yönetir.
 * İçeride ikinci bir state tutulmaz; her değişiklik diğer alanlar korunarak üst ekrana bildirilir.
 */
export function WardrobeToolbar({ filters, categories, onChange }: WardrobeToolbarProps) {
  function updateFilters(patch: Partial<WardrobeFilters>) {
    onChange({ ...filters, ...patch });
  }

  return (
    <View style={styles.container}>
      <View style={styles.searchBox}>
        <Icon name="search" size={18} color={colors.muted} />
        <TextInput
          value={filters.query}
          onChangeText={(query) => updateFilters({ query })}
          placeholder="Kıyafet, kategori veya renk ara"
          placeholderTextColor={colors.muted}
          accessibilityLabel="Kıyafet ara"
          returnKeyType="search"
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />
        {filters.query.length > 0 ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Aramayı temizle"
            onPress={() => updateFilters({ query: '' })}
            style={({ pressed }) => [styles.clearButton, pressed && styles.pressed]}
          >
            <Icon name="close" size={18} color={colors.ink} />
          </Pressable>
        ) : null}
      </View>

      <View style={styles.group}>
        <Text variant="caption" muted>
          Kategori
        </Text>
        <View style={styles.chipRow}>
          <FilterChip
            label="Tümü"
            selected={filters.category === null}
            onPress={() => updateFilters({ category: null })}
          />
          {categories.map((category) => (
            <FilterChip
              key={category}
              label={category}
              selected={filters.category === category}
              onPress={() =>
                updateFilters({ category: filters.category === category ? null : category })
              }
            />
          ))}
        </View>
      </View>

      <View style={styles.group}>
        <Text variant="caption" muted>
          Durum ve favoriler
        </Text>
        <View style={styles.chipRow}>
          <FilterChip
            label="Tümü"
            selected={filters.status === null}
            onPress={() => updateFilters({ status: null })}
          />
          {statusOptions.map((status) => (
            <FilterChip
              key={status}
              label={clothingStatusLabels[status]}
              selected={filters.status === status}
              onPress={() => updateFilters({ status: filters.status === status ? null : status })}
            />
          ))}
          <FilterChip
            label="Yalnızca favoriler"
            icon="heart"
            selected={filters.favoritesOnly}
            onPress={() => updateFilters({ favoritesOnly: !filters.favoritesOnly })}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: space.md },
  searchBox: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    paddingLeft: space.md,
    paddingRight: space.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  input: {
    flex: 1,
    fontFamily: fonts.regular,
    fontSize: 15,
    color: colors.ink,
    paddingVertical: space.sm,
  },
  clearButton: {
    minWidth: 48,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.full,
  },
  group: { gap: space.xs },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  pressed: { opacity: 0.75 },
});
