import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Header } from '../shared/ui/Header';
import { Text } from '../shared/ui/Text';
import { colors } from '../shared/theme/tokens';

// Harun: burası görev kontrol ekranı. Asıl işi Header.tsx içinde yap.
export default function HeaderWorkshop() {
  const [backCount, setBackCount] = useState(0);
  const [filterCount, setFilterCount] = useState(0);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 24 }}>
        <Text variant="title">Üst bar atölyesi</Text>
        <Text muted>Her örnek aynı Header bileşenini farklı parametrelerle kullanır.</Text>
        <View style={{ gap: 12 }}>
          <Text variant="label">01 · YALNIZCA BAŞLIK</Text>
          <Header title="Gardırobum" />
          <Text variant="label">02 · GERİ BUTONU</Text>
          <Header title="Kıyafet detayları" onBack={() => setBackCount((value) => value + 1)} />
          <Text variant="label">03 · SAĞ AKSİYON VE ALT BAŞLIK</Text>
          <Header
            title="Kombinlerim"
            subtitle="Sevdiğin eşleşmeler burada."
            action={{
              icon: 'filter',
              label: 'Filtreleri aç',
              onPress: () => setFilterCount((value) => value + 1),
            }}
          />
          <Text variant="label">04 · UZUN BAŞLIK VE İKİ AKSİYON</Text>
          <Header
            title="Sonbaharda yeniden keşfetmek istediğim favori kıyafetlerim"
            subtitle="Küçük ekranda ve büyük yazı boyutunda da okunabilir olmalı."
            onBack={() => setBackCount((value) => value + 1)}
            action={{
              icon: 'filter',
              label: 'Filtreleri aç',
              onPress: () => setFilterCount((value) => value + 1),
            }}
          />
        </View>
        <Text accessibilityLiveRegion="polite">
          Geri çağrısı: {backCount} · Filtre çağrısı: {filterCount}
        </Text>
        <Text muted>
          Başlangıçta butonlar yoktur. Görev tamamlandığında ilgili örneklerde görünür ve sayaçları artırır.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
