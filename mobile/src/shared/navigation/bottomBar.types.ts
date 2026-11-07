import type { IconName } from '../ui/Icon';

export type BottomTabId = 'wardrobe' | 'outfits' | 'conversations';
export type BottomTab = { id: BottomTabId; label: string; icon: IconName };

// Seçili sekme ve gezinme kararı üst ekrana aittir; bar yalnızca olayı bildirir.
export type BottomBarProps = {
  activeTab: BottomTabId | null;
  onSelectTab: (tabId: BottomTabId) => void;
  onAddPress: () => void;
  bottomInset: number;
};
