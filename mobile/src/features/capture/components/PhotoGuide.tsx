import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Header } from '../../../shared/ui/Header';
import { Icon, type IconName } from '../../../shared/ui/Icon';
import { Text } from '../../../shared/ui/Text';

export type PhotoGuideProps = {
  skipNextTime: boolean;
  onSkipChange: (value: boolean) => void;
  onContinue: () => void;
  onCancel: () => void;
};

const tips: readonly { icon: IconName; title: string; detail: string }[] = [
  { icon: 'shirt', title: 'Tek kıyafet', detail: 'Karede yalnızca eklemek istediğin tek parça yer alsın.' },
  { icon: 'image', title: 'Düz ve tek renk zemin', detail: 'Desensiz, sade bir arka plan veya zemin seç.' },
  { icon: 'sun', title: 'Yeterli ışık', detail: 'Rengi doğru gösterecek dengeli ve gölgesiz ışık kullan.' },
  { icon: 'camera', title: 'Tamamı kadrajda', detail: 'Kıyafetin yakası, kolları ve kenarları kesilmeden görünsün.' },
];

/**
 * Kıyafet eklemeden önce iyi fotoğraf koşullarını anlatan rehber ekranıdır.
 * "Bir daha gösterme" seçimi ekranı hemen kapatmaz; yalnızca bir sonraki tercih bilgisini bildirir.
 */
export function PhotoGuide({
  skipNextTime,
  onSkipChange,
  onContinue,
  onCancel,
}: PhotoGuideProps) {
  return (
    <SafeAreaView style={styles.screen}>
      <Header title="Fotoğraf rehberi" onBack={onCancel} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text muted>
          Kıyafetini daha net görmek için fotoğraf seçmeden önce şu noktalara dikkat et:
        </Text>

        <View style={styles.list}>
          {tips.map((tip) => (
            <View key={tip.title} style={styles.tipCard}>
              <View style={styles.iconBox} accessible={false}>
                <Icon name={tip.icon} size={20} color={colors.accentInk} />
              </View>
              <View style={styles.tipText}>
                <Text variant="label">{tip.title}</Text>
                <Text variant="caption" muted>
                  {tip.detail}
                </Text>
              </View>
            </View>
          ))}
        </View>

        <Pressable
          accessibilityRole="checkbox"
          accessibilityLabel="Bir daha gösterme"
          accessibilityState={{ checked: skipNextTime }}
          onPress={() => onSkipChange(!skipNextTime)}
          style={({ pressed }) => [styles.checkboxRow, pressed && styles.pressed]}
        >
          <View style={[styles.checkbox, skipNextTime && styles.checkboxChecked]}>
            {skipNextTime ? <Icon name="check" size={16} color={colors.onPrimary} /> : null}
          </View>
          <Text variant="label" style={styles.checkboxLabel}>
            Bir daha gösterme
          </Text>
        </Pressable>

        <View style={styles.actions}>
          <Button label="Devam et" onPress={onContinue} />
          <Button label="Vazgeç" variant="secondary" onPress={onCancel} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  list: { gap: space.sm },
  tipCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.md,
    padding: space.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  iconBox: {
    width: 40,
    height: 40,
    borderRadius: radius.full,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tipText: { flex: 1, gap: space.xs },
  checkboxRow: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    paddingVertical: space.xs,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.muted,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: { borderColor: colors.primary, backgroundColor: colors.primary },
  checkboxLabel: { flex: 1 },
  actions: { gap: space.sm },
  pressed: { opacity: 0.8 },
});
