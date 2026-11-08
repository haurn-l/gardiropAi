import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { colors, radius } from '../../../shared/theme/tokens';
import { Icon } from '../../../shared/ui/Icon';

type GarmentImageProps = {
  imageUri?: string;
};

export function GarmentImage({ imageUri }: GarmentImageProps) {
  // Yalnızca hata veren URI değerini saklıyoruz; üst bileşen yeni bir imageUri gönderdiğinde
  // eşleşme bozulacağı için önceki hata kalıcı olmaz ve yeni görsel otomatik olarak tekrar denenir.
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const showFallback = !imageUri || failedUri === imageUri;

  return (
    <View style={styles.container}>
      {showFallback ? (
        <View style={styles.fallback} accessible={false}>
          <Icon name="shirt" size={36} color={colors.muted} />
        </View>
      ) : (
        <Image
          key={imageUri}
          source={{ uri: imageUri }}
          contentFit="cover"
          style={styles.image}
          onError={() => setFailedUri(imageUri)}
          accessible={false}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: colors.sand,
  },
  image: {
    width: '100%',
    height: '100%',
  },
  fallback: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
