import { StyleSheet, View } from 'react-native';
import { colors, space } from '../theme/tokens';
import type { HeaderProps } from './header.types';
import { IconButton } from './IconButton';
import { Text } from './Text';

export function Header({ title, subtitle, onBack, action }: HeaderProps) {
  return (
    // Dış taşıyıcı: İçindeki elemanları yatayda  yan yana dizer.
    <View style={styles.container}>

      {/* Sol Buton: Yalnızca onBack prop'u gelirse render edilir. Yoksa ekranda fazladan boşluk bırakmaz (null döner). */}
      {onBack ? (
        <IconButton icon="back" label="Geri dön" onPress={onBack} />
      ) : null}

      {/* Başlık Alanı: flex: 1 değeri sayesinde, sağ ve sol butonlardan arta kalan tüm boşluğu kaplar. Uzun metinler butonları dışarı itmez, alt satıra geçer. */}
      <View style={styles.titleContainer}>
        {/* accessibilityRole="header" ekran okuyuculara (görme engelliler için) buranın başlık olduğunu bildirir. */}
        <Text variant="heading" accessibilityRole="header">
          {title}
        </Text>

        {/* Alt Başlık: Yalnızca subtitle verilmişse render edilir. muted prop'u ile soluk renkte gösterilir. */}
        {subtitle ? (
          <Text variant="caption" muted>
            {subtitle}
          </Text>
        ) : null}
      </View>

      {/* Sağ Buton: action objesi verilmişse içerisindeki dinamik ikon, etiket ve tıklama fonksiyonuyla sağ butonu oluşturur. */}
      {action ? (
        <IconButton
          icon={action.icon}
          label={action.label}
          onPress={action.onPress}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row', // Elemanları  yan yana diz.
    alignItems: 'center', // Elemanları dikey eksende ortala.
    gap: space.md, // Yan yana duran elemanlar arasındaki standart boşluk.
    paddingHorizontal: space.lg, // Ekranın sağından ve solundan iç boşluk bırak.
    paddingVertical: space.md, // Üstten ve alttan iç boşluk bırak.
    backgroundColor: colors.background, // Uygulamanın ortak zemin rengini uygula.
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  titleContainer: {
    flex: 1,
    gap: space.xs, // Ana başlık ile alt başlık arasındaki dikey ufak boşluk.
  },
});
