import { StyleSheet, View } from 'react-native';
import { colors, space } from '../theme/tokens';
import { Text } from '../ui/Text';
import type { BottomBarProps } from './bottomBar.types';

/**
 * HARUN GÖREV 02 — kontrollü alt bar.
 * Sözleşme: ./bottomBar.types.ts içindeki BottomBarProps değişmeyecek.
 * Liste: ./bottomBar.items.ts içindeki bottomTabs; üç sekmeyi map ile çiz.
 *
 * 1. Dış View yatay olsun; üç sekme eşit genişliği paylaşsın.
 * 2. Her sekme React Native Pressable olsun. Ortak ../ui/Icon ve ../ui/Text
 *    kullan; ikon adı item.icon, görünen yazı item.label alanından gelir.
 * 3. Seçili durum: props.activeTab === item.id. Yeni useState ekleme.
 *    accessibilityRole="tab", accessibilityLabel={item.label} ve
 *    accessibilityState={{ selected: seçiliMi }} değerlerini bağla.
 * 4. Basılınca props.onSelectTab(item.id) çağır. Render sırasında çağırma.
 *    Aktif sekmeye tekrar basış da tek olay üretmeli; uzun basış ekleme.
 * 5. En sağa + butonu koy: icon="plus", accessibilityRole="button",
 *    accessibilityLabel="Kıyafet ekle", onPress={props.onAddPress}.
 *    + bir sekme değildir; seçili sekmeyi kendi içinde değiştirme.
 * 6. Her dokunma alanı en az 48x48 olsun. Metin büyüyebilsin; bara sabit
 *    yükseklik verme. Alt boşluk en az Math.max(props.bottomInset, space.sm).
 * 7. Tema: colors.surface, line, accent, ink, muted, primary, onPrimary.
 *    Inline renk kodu, yeni ikon/font/navigasyon paketi ekleme.
 *
 * Burada router, API, ekran görünürlüğü veya konumlandırma kararı yok.
 * Atölye zaten barı kaydırma alanının dışında tutar ve detaylarda göstermez.
 * Stil kararı için StyleSheet kullan. İstersen sekme öğesini ayrı dosyaya çıkar.
 * Kontrol ekranı: features/workshops/BottomBarWorkshop.tsx.
 * Kabul listesi ve çalışma sırası: docs/harun/02-bottom-bar.md.
 */
export function BottomBar({ bottomInset }: BottomBarProps) {
  return (
    <View style={[styles.placeholder, { paddingBottom: Math.max(bottomInset, space.sm) }]}>
      <Text variant="caption" muted>
        Harun: alt barı burada tamamla.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  placeholder: {
    padding: space.lg,
    backgroundColor: colors.surface,
    borderTopColor: colors.line,
    borderTopWidth: 1,
  },
});
