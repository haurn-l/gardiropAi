import { useMemo, useState, type ReactElement } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';
import { colors, radius, space } from '../../../shared/theme/tokens';
import { Button } from '../../../shared/ui/Button';
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog';
import { Text } from '../../../shared/ui/Text';
import { ConversationRow } from '../components/ConversationRow';
import type { ConversationRecord } from '../model/chat.types';
import { sortConversationsByUpdated } from '../model/chatHelpers';

export type ConversationsScreenProps = {
  conversations: readonly ConversationRecord[];
  onOpen: (id: string) => void;
  onCreate: () => void;
  onDelete?: (id: string) => void;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  busy?: boolean;
  actionError?: string;
  header?: ReactElement;
};

const ItemSeparator = () => <View style={styles.separator} />;

/**
 * Sohbet geçmişini son güncelleme sırasına göre listeler; yükleniyor, hata ve boş durumları sunar.
 */
export function ConversationsScreen({
  conversations,
  onOpen,
  onCreate,
  onDelete,
  loading = false,
  error,
  onRetry,
  busy = false,
  actionError,
  header,
}: ConversationsScreenProps) {
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const sorted = useMemo(() => sortConversationsByUpdated(conversations), [conversations]);
  const hasData = !loading && !error && sorted.length > 0;
  const deleteTarget = deleteTargetId
    ? sorted.find((item) => item.id === deleteTargetId)
    : undefined;

  const listHeader =
    header || hasData ? (
      <View style={styles.headerBlock}>
        {header}
        {hasData ? (
          <>
            <Button label="Yeni sohbet başlat" icon="sparkle" disabled={busy} onPress={onCreate} />
            <Text variant="caption" muted accessibilityLiveRegion="polite">
              Toplam sohbet: {sorted.length}
            </Text>
          </>
        ) : null}
      </View>
    ) : undefined;
  let emptyContent: ReactElement;
  if (loading) {
    emptyContent = (
      <View style={styles.stateCard} accessibilityLiveRegion="polite">
        <ActivityIndicator size="large" color={colors.accentInk} />
        <Text variant="label">Sohbetler yükleniyor...</Text>
      </View>
    );
  } else if (error) {
    emptyContent = (
      <View style={[styles.stateCard, styles.errorCard]} accessibilityLiveRegion="polite">
        <Text variant="heading" style={styles.errorTitle}>
          Sohbetler yüklenemedi
        </Text>
        <Text muted style={styles.centered}>
          {error}
        </Text>
        {onRetry ? <Button label="Tekrar dene" onPress={onRetry} /> : null}
      </View>
    );
  } else {
    emptyContent = (
      <View style={styles.stateCard}>
        <Text variant="heading">Henüz sohbet yok</Text>
        <Text muted style={styles.centered}>
          Gardırobundaki temiz parçalardan kombin önerisi almak için yeni bir sohbet başlat.
        </Text>
        <Button label="Yeni sohbet başlat" icon="sparkle" disabled={busy} onPress={onCreate} />
      </View>
    );
  }
  return (
    <>
      <FlatList
        data={hasData ? sorted : []}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ConversationRow
            conversation={item}
            onOpen={onOpen}
            onDelete={onDelete ? (id) => setDeleteTargetId(id) : undefined}
          />
        )}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={emptyContent}
        ItemSeparatorComponent={ItemSeparator}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      />
      <ConfirmDialog
        visible={Boolean(deleteTarget)}
        title="Sohbet silinsin mi?"
        message="Bu sohbet ve mesajları kaldırılır; onayladığın kombinler geçmişte kalır."
        confirmLabel="Sil"
        busy={busy}
        error={actionError}
        onConfirm={() => {
          if (deleteTarget && onDelete) {
            onDelete(deleteTarget.id);
          }
        }}
        onCancel={() => setDeleteTargetId(null)}
      />
    </>
  );
}
const styles = StyleSheet.create({
  content: { flexGrow: 1, padding: space.lg, paddingBottom: space.xxl },
  headerBlock: { gap: space.md, marginBottom: space.md },
  separator: { height: space.md },
  stateCard: {
    flex: 1,
    minHeight: 220,
    padding: space.xl,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.md,
  },
  errorCard: { borderColor: colors.danger, backgroundColor: colors.dangerSoft },
  errorTitle: { color: colors.danger, textAlign: 'center' },
  centered: { textAlign: 'center' },
});
