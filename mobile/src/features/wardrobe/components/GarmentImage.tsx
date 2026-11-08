import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { colors, radius } from '../../../shared/theme/tokens';
import { Icon } from '../../../shared/ui/Icon';

type GarmentImageProps = {
  imageUri?: string;
};

export function GarmentImage({ imageUri }: GarmentImageProps) {
  return (
    <View style={styles.container}>
      <GarmentImageContent key={imageUri ?? ''} imageUri={imageUri} />
    </View>
  );
}

function GarmentImageContent({ imageUri }: GarmentImageProps) {
  // URI değişince key bu durumu sıfırlar; eski bir adrese dönüş de yeni yükleme denemesidir.
  const [failed, setFailed] = useState(false);
  if (!imageUri || failed) {
    return (
      <View style={styles.fallback} accessible={false}>
        <Icon name="shirt" size={36} color={colors.muted} />
      </View>
    );
  }
  return (
    <Image
      source={{ uri: imageUri }}
      contentFit="cover"
      style={styles.image}
      onError={() => setFailed(true)}
      accessible={false}
    />
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
