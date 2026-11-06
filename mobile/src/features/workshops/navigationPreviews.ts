export const navigationPreviews = {
  chat: { title: 'Aktif sohbet', description: 'Sohbet geçmişinden açılan konuşmada alt bar bulunmaz.' },
  item: { title: 'Kıyafet detayı', description: 'Kıyafet kartından açılan detayda alt bar bulunmaz.' },
  outfit: { title: 'Kombin detayı', description: 'Kombin listesinden açılan detayda alt bar bulunmaz.' },
  capture: { title: 'Kıyafet ekleme', description: '+ aksiyonuyla açılan ekleme akışında alt bar bulunmaz.' },
} as const;

export type PreviewId = keyof typeof navigationPreviews;
