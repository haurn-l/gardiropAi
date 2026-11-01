import { View } from 'react-native';
import { Text } from './Text';
import type { HeaderProps } from './header.types';

// Başlangıç görünümü; görev dalında geri ve sağ aksiyon desteği tamamlanacak.
export function Header({ title, subtitle }: HeaderProps) {
  return <View style={{ padding: 24, gap: 4 }}>
    <Text variant="heading">{title}</Text>
    {subtitle && <Text muted>{subtitle}</Text>}
  </View>;
}
