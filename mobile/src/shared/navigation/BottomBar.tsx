import { Pressable, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../theme/tokens';
import { Icon } from '../ui/Icon';
import { Text } from '../ui/Text';
import { bottomTabs } from './bottomBar.items';
import type { BottomBarProps } from './bottomBar.types';

// Ortak alt bar : Seçili sekmeyi üst ekrandan alır, kendi içinde useState tutmaz.
export function BottomBar({
  activeTab,
  onSelectTab,
  onAddPress,
  bottomInset,
}: BottomBarProps) {
  return (
    // Dış taşıyıcı: Sabit yükseklik verilmez alt alan en az space.sm kadar uygulanır.
    <View
      style={[
        styles.container,
        { paddingBottom: Math.max(bottomInset, space.sm) },
      ]}
    >
      {/* Üç ana sekme: bottomTabs listesi üzerinden eşit genişlik paylaşacak şekilde çizilir. */}
      {bottomTabs.map((item) => {
        const isSelected = activeTab === item.id;

        return (
          <Pressable
            key={item.id}
            accessibilityRole="tab"
            accessibilityLabel={item.label}
            accessibilityState={{ selected: isSelected }}
            // Tıklama anında üst ekranın fonksiyonunu bir kez çağırır; render sırasında çağırmaz.
            onPress={() => onSelectTab(item.id)}
            style={({ pressed }) => [
              styles.tabButton,
              pressed && styles.pressed,
            ]}
          >
            {/* İkon alanı: Seçili sekmenin arkasında açık turuncu (colors.accent) vurgu gösterilir. */}
            <View
              style={[
                styles.iconContainer,
                isSelected && styles.iconContainerSelected,
              ]}
            >
              <Icon
                name={item.icon}
                size={20}
                color={isSelected ? colors.ink : colors.muted}
              />
            </View>

            {/* Sekme etiketi: Seçili olduğunda koyu (colors.ink), diğer durumda soluk (muted) görünür. */}
            <Text
              variant="caption"
              muted={!isSelected}
              style={[styles.tabLabel, isSelected && styles.tabLabelSelected]}
            >
              {item.label}
            </Text>
          </Pressable>
        );
      })}

      {/* Sağdaki bağımsız + aksiyonu: Bir sekme değildir, seçili sekmeyi değiştirmez. */}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Kıyafet ekle"
        onPress={onAddPress}
        style={({ pressed }) => [styles.addButton, pressed && styles.pressed]}
      >
        <Icon name="plus" size={22} color={colors.onPrimary} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row', // Sekmeleri ve + butonunu yatayda yan yana diz.
    alignItems: 'center', // Elemanları dikey eksende ortala.
    gap: space.xs, // Elemanlar arası yatay boşluk.
    paddingTop: space.sm, // Üst iç boşluk.
    paddingHorizontal: space.sm, // Sağ ve sol kenar boşlukları.
    backgroundColor: colors.surface, // Alt barın yüzey rengi.
    borderTopWidth: 1, // Üst ayraç çizgisi kalınlığı.
    borderTopColor: colors.line, // Üst ayraç çizgisi rengi.
  },
  tabButton: {
    flex: 1, // Üç sekmenin eşit genişliği paylaşmasını sağlar.
    minWidth: 48, // Minimum 48x48 dokunma alanı kuralı.
    minHeight: 48,
    paddingVertical: space.xs,
    paddingHorizontal: space.xs,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xs, // İkon ve metin arasındaki dikey boşluk.
  },
  iconContainer: {
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    borderRadius: radius.full, // Tam yuvarlatılmış hap görünümü.
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconContainerSelected: {
    backgroundColor: colors.accent, // Seçili sekme ikonu arkasındaki açık turuncu alan.
  },
  tabLabel: {
    textAlign: 'center', // Uzun metinler alt satıra geçtiğinde ortalı dursun.
  },
  tabLabelSelected: {
    color: colors.ink, // Seçili sekme metni için okunaklı koyu ton.
    fontWeight: '600',
  },
  addButton: {
    minWidth: 48, // + butonu için minimum 48x48 dokunma alanı.
    minHeight: 48,
    borderRadius: radius.full, // Yuvarlak buton formu.
    backgroundColor: colors.primary, // Ana vurgu zemin rengi.
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: space.xs,
  },
  pressed: {
    opacity: 0.7, // Basılma anında görsel geri bildirim.
  },
});
