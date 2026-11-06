import type { IconName } from './Icon';

export type HeaderAction = { label: string; icon: IconName; onPress: () => void };
// Harun: gezinme kararı bu bileşenin dışında verilir; burada router kullanma.
export type HeaderProps = {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  action?: HeaderAction;
};
