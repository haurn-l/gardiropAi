import { Text as NativeText, StyleSheet, type TextProps } from 'react-native';
import { colors, fonts } from '../theme/tokens';

type Props = TextProps & { variant?: keyof typeof variants; muted?: boolean };

export function Text({ variant = 'body', muted, style, ...props }: Props) {
  return <NativeText {...props} style={[styles.base, variants[variant], muted && styles.muted, style]} />;
}

const styles = StyleSheet.create({
  base: { fontFamily: fonts.regular, color: colors.ink, fontSize: 14, lineHeight: 22 },
  muted: { color: colors.muted },
});
const variants = StyleSheet.create({
  body: {}, caption: { fontSize: 12, lineHeight: 18 },
  label: { fontSize: 11, lineHeight: 16, letterSpacing: 1.8, fontFamily: fonts.bold },
  title: { fontSize: 42, lineHeight: 46, fontFamily: fonts.serif },
  heading: { fontSize: 28, lineHeight: 34, fontFamily: fonts.serif },
  strong: { fontFamily: fonts.bold },
});
