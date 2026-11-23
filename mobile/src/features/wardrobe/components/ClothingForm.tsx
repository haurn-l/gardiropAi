import { StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { Text } from '../../../shared/ui/Text';
import type { ClothingDraft } from '../model/clothing.types';
import {
  clothingCategories,
  clothingCategoryLabels,
  clothingSeasonLabels,
  clothingSeasons,
} from '../model/clothingOptions';
import { validateClothingDraft } from '../model/validateClothingDraft';
import { FormChoiceGroup, FormTextField } from './ClothingFormInputs';

export type ClothingFormProps = {
  value: ClothingDraft;
  onChange: (next: ClothingDraft) => void;
  onSubmit: (value: ClothingDraft) => void;
  busy?: boolean;
  error?: string;
  submitLabel?: string;
};

const categoryOptions = clothingCategories.map((category) => ({
  value: category,
  label: clothingCategoryLabels[category],
}));

const seasonOptions = clothingSeasons.map((season) => ({
  value: season,
  label: clothingSeasonLabels[season],
}));

const printOptions = [
  { value: false, label: 'Düz' },
  { value: true, label: 'Desenli' },
] as const;

/**
 * Kıyafet düzenleme ve fotoğraf sonrası onay ekranlarında ortak kullanılan formdur.
 * Kaydı doğrudan değiştirmez; geçersiz veya meşgul durumda gönderimi engeller.
 */
export function ClothingForm({
  value,
  onChange,
  onSubmit,
  busy = false,
  error,
  submitLabel = 'Kaydet',
}: ClothingFormProps) {
  const validation = validateClothingDraft(value);
  const errors = validation.valid ? {} : validation.errors;

  function patchDraft(patch: Partial<ClothingDraft>) {
    onChange({ ...value, ...patch });
  }

  function handleSubmit() {
    if (busy || !validation.valid) {
      return;
    }
    onSubmit(validation.value);
  }

  return (
    <View style={styles.form}>
      {error ? (
        <View style={styles.errorBanner}>
          <Text variant="caption" accessibilityLiveRegion="polite" style={styles.errorBannerText}>
            {error}
          </Text>
        </View>
      ) : null}
      <FormTextField
        label="Kıyafet adı"
        value={value.name}
        onChangeText={(name) => patchDraft({ name })}
        placeholder="Örn. Keten Gömlek"
        error={errors.name}
        disabled={busy}
      />
      <FormChoiceGroup
        label="Kategori"
        options={categoryOptions}
        value={value.category}
        onSelect={(category) => patchDraft({ category })}
        disabled={busy}
        error={errors.category}
      />
      <FormTextField
        label="Renk"
        value={value.color}
        onChangeText={(color) => patchDraft({ color })}
        placeholder="Örn. Ekru"
        error={errors.color}
        disabled={busy}
      />
      <FormTextField
        label="Alt tür (isteğe bağlı)"
        value={value.subCategory}
        onChangeText={(subCategory) => patchDraft({ subCategory })}
        placeholder="Örn. Gömlek, Sneaker"
        error={errors.subCategory}
        disabled={busy}
      />
      <FormChoiceGroup
        label="Mevsim"
        options={seasonOptions}
        value={value.season}
        onSelect={(season) => patchDraft({ season })}
        disabled={busy}
        error={errors.season}
      />
      <FormChoiceGroup
        label="Desen"
        options={printOptions}
        value={value.hasPrint}
        onSelect={(hasPrint) => patchDraft({ hasPrint })}
        disabled={busy}
        error={errors.hasPrint}
      />
      <FormTextField
        label="Kullanım alanı (isteğe bağlı)"
        value={value.usage}
        onChangeText={(usage) => patchDraft({ usage })}
        placeholder="Örn. Günlük, Ofis, Spor"
        error={errors.usage}
        disabled={busy}
      />
      <Button
        label={submitLabel}
        busy={busy}
        disabled={busy || !validation.valid}
        onPress={handleSubmit}
      />
    </View>
  );
}
const styles = StyleSheet.create({
  form: { gap: space.md },
  errorBanner: {
    padding: space.md,
    borderRadius: radius.md,
    backgroundColor: colors.dangerSoft,
  },
  errorBannerText: { color: colors.danger },
});
