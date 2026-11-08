import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { BottomBar } from '../../shared/navigation/BottomBar';
import { bottomTabs } from '../../shared/navigation/bottomBar.items';
import type { BottomTabId } from '../../shared/navigation/bottomBar.types';
import { Header } from '../../shared/ui/Header';
import { Text } from '../../shared/ui/Text';
import { Button } from '../../shared/ui/Button';
import { colors, space } from '../../shared/theme/tokens';
import type { PreviewId } from './navigationPreviews';

const screenActions: Record<BottomTabId, { label: string; target: PreviewId }> = {
  wardrobe: { label: 'Kıyafet detayını aç', target: 'item' },
  outfits: { label: 'Kombin detayını aç', target: 'outfit' },
  conversations: { label: 'Yeni sohbet', target: 'chat' },
};

// Harun yalnızca BottomBar'ı tamamlar. Durumu ve gerçek Stack geçişlerini bu ekran yönetir.
export function BottomBarWorkshop() {
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<BottomTabId>('wardrobe');
  const [tabCalls, setTabCalls] = useState(0);
  const [addCalls, setAddCalls] = useState(0);
  const tab = bottomTabs.find((item) => item.id === activeTab)!;
  const action = screenActions[activeTab];
  const openPreview = (kind: PreviewId) => router.push({ pathname: '/navigation-preview', params: { kind } });
  function selectTab(id: BottomTabId) {
    setActiveTab(id);
    setTabCalls((value) => value + 1);
  }
  function addClothing() {
    setAddCalls((value) => value + 1);
    openPreview('capture');
  }
  function selectExternally() {
    const next = (bottomTabs.findIndex((item) => item.id === activeTab) + 1) % bottomTabs.length;
    setActiveTab(bottomTabs[next].id);
  }
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <Header title="Alt bar atölyesi" subtitle="Görev 02 · Seçim, dokunma ve ekran geçişleri" />
        <Text variant="heading">{tab.label}</Text>
        <Text accessibilityLiveRegion="polite">
          Sekme çağrısı: {tabCalls} · Ekle çağrısı: {addCalls}
        </Text>
        <Button label={action.label} onPress={() => openPreview(action.target)} />
        <Button label="Sekmeyi dışarıdan değiştir" variant="secondary" onPress={selectExternally} />
        <Text muted>Dışarıdan seçim sayacı artırmaz; alt bar yeni activeTab değerini göstermelidir.</Text>
        <Button
          label="Üst bar atölyesini aç"
          variant="secondary"
          onPress={() => router.push('/header-workshop')}
        />
        <Button
          label="Kıyafet kartı örnekleri"
          variant="secondary"
          onPress={() => router.push('/clothing-preview')}
        />

        <View style={styles.notes}>
          <Text variant="strong">Kontrol sırası</Text>
          <Text>1. Üç sekmeye sırayla bas; başlık, seçili görünüm ve sayaç birlikte güncellensin.</Text>
          <Text>2. Aktif sekmeye tekrar bas; sayaç yalnızca bir artsın.</Text>
          <Text>3. + ile eklemeyi aç, geri dön; son seçili sekme korunsun.</Text>
          <Text>4. Sohbetler → Yeni sohbet: iç ekranda alt bar bulunmasın.</Text>
          <Text>5. Bu alanı kaydır; alt bar ekranın altında sabit kalsın.</Text>
          <Text>6. 320 px genişlikte ve büyük sistem yazısında etiketler ile butonları kontrol et.</Text>
        </View>
      </ScrollView>
      <BottomBar
        activeTab={activeTab}
        onSelectTab={selectTab}
        onAddPress={addClothing}
        bottomInset={insets.bottom}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, gap: space.lg },
  notes: { gap: space.lg, paddingVertical: space.xl },
});
