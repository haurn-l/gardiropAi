import { Text as NativeText, StyleSheet, type TextProps } from 'react-native';
import { colors, fonts } from '../theme/tokens';

type Props = TextProps & { variant?: keyof typeof variants; muted?: boolean };
export function Text({ variant = 'body', muted, style, ...props }: Props) {
  return <NativeText {...props} style={[styles.base, variants[variant], muted && styles.muted, style]} />;
}
const styles = StyleSheet.create({
  base: { fontFamily: fonts.regular, color: colors.ink, fontSize: 15, lineHeight: 22 },
  muted: { color: colors.muted },
});
const variants = StyleSheet.create({
  body: {},
  caption: { fontSize: 12, lineHeight: 18 },
  label: { fontSize: 12, lineHeight: 18, fontWeight: '600' },
  title: { fontSize: 30, lineHeight: 36, fontWeight: '700', letterSpacing: -0.7 },
  heading: { fontSize: 24, lineHeight: 30, fontWeight: '700', letterSpacing: -0.5 },
  strong: { fontWeight: '600' },
});
