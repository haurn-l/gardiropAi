import type { IconName } from './Icon';

export type HeaderAction = { label: string; icon: IconName; onPress: () => void };
// Gezinme kararı üst ekrana aittir; Header yalnızca verilen olayları bildirir.
export type HeaderProps = {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  action?: HeaderAction;
};
