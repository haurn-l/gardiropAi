import { View } from 'react-native';
import { Text } from './Text';
import type { HeaderProps } from './header.types';

/**
 * HARUN GÖREV 01 — tekrar kullanılabilir üst bar.
 * Sözleşme: ./header.types.ts içindeki HeaderProps değişmeyecek.
 * title zorunlu; subtitle, onBack ve action isteğe bağlıdır.
 *
 * 1. Dış View yatay yerleşsin. Başlık alanı kalan genişliği alsın.
 * 2. onBack varsa solda IconButton göster; yoksa boş yer bırakma.
 *    Kaynak: ./IconButton. icon="back", label="Geri dön".
 *    Basılınca props içindeki onBack() çağrılır. Burada router kullanma.
 * 3. title için ./Text bileşenini variant="heading" ile kullan.
 *    accessibilityRole="header" ekle. Uzun başlık butonları itmesin.
 * 4. subtitle varsa başlığın altında variant="caption", muted göster.
 * 5. action varsa sağda IconButton oluştur. icon, label ve onPress
 *    değerleri action.icon, action.label, action.onPress alanlarından gelir.
 * 6. Stilleri StyleSheet.create ile tanımla. Tema kaynağı
 *    ../theme/tokens içindeki colors, space ve radius değerleridir.
 *
 * Veri çekme veya gezinme kararını bu bileşene ekleme.
 * onBack/action.onPress işlevlerini render sırasında çağırma; tıklamaya bağla.
 * IconButton dokunma alanını 44x44 olarak sağlar.
 * Kontrol ekranı: src/app/index.tsx; butonlar tamamlanınca sayaçlar artmalı.
 * Kabul koşulları: docs/harun/01-header.md.
 * Aşağıdaki çalışır yer tutucuyu uygulamanla değiştir.
 */
export function Header({ title, subtitle }: HeaderProps) {
  return <View style={{ padding: 24, gap: 4 }}>
    <Text variant="heading">{title}</Text>
    {subtitle && <Text muted>{subtitle}</Text>}
  </View>;
}
