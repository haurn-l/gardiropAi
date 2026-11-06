import { Pressable, StyleSheet } from 'react-native';
import { colors } from '../theme/tokens';
import { Icon, type IconName } from './Icon';

export function IconButton({
  icon,
  label,
  onPress,
  active = false,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
  active?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [styles.button, active && styles.active, pressed && { opacity: 0.6 }]}
    >
      <Icon
        name={icon}
        color={active ? colors.accentInk : colors.ink}
        filled={active && icon === 'heart'}
        size={20}
      />
    </Pressable>
  );
}
const styles = StyleSheet.create({
  button: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  active: { backgroundColor: colors.accent },
});
