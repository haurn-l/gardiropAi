import type { ConversationRecord } from '../../assistant/model/chat.types';
import { selectEligibleWardrobe } from '../../assistant/model/chatHelpers';
import { createOutfitItemSnapshot } from '../../outfits/model/outfitSnapshot';
import { initialClothingRecords } from '../clothing-management/clothingDemoData';

const cleanItems = selectEligibleWardrobe(initialClothingRecords);
const firstPack = cleanItems.slice(0, 3).map(createOutfitItemSnapshot);
const secondPack = cleanItems.slice(1, 4).map(createOutfitItemSnapshot);

/**
 * Sohbet akışı örnek oturumu için başlangıç konuşmalarıdır.
 */
export const initialConversations: readonly ConversationRecord[] = [
  {
    id: 'conv-01',
    title: 'Serin Sonbahar Ofis Kombini',
    updatedAt: '2026-11-23T09:15:00.000Z',
    messages: [
      {
        id: 'msg-01',
        sender: 'user',
        text: 'Bugün hava serin, ofis için sade ve rahat bir kombin önerir misin?',
        createdAt: '2026-11-23T09:14:00.000Z',
        status: 'sent',
      },
      {
        id: 'msg-02',
        sender: 'assistant',
        text: 'Temiz parçalarından katmanlı bir ofis kombini hazırladım. Beğenmediğin parçaları sabitlemeden yenileyebilirsin:',
        createdAt: '2026-11-23T09:15:00.000Z',
        status: 'sent',
        suggestion: {
          id: 'sug-01',
          title: 'Serin Sonbahar Ofis Kombini',
          reason: 'Temiz parçalarından mevsime ve ofis kullanımına uygun seçildi.',
          items: firstPack,
          pinnedItemIds: [],
          approvedOutfitId: null,
          feedback: null,
        },
      },
    ],
  },
  {
    id: 'conv-02',
    title: 'Hafta Sonu Kahve Buluşması',
    updatedAt: '2026-11-22T18:05:00.000Z',
    messages: [
      {
        id: 'msg-03',
        sender: 'user',
        text: 'Hafta sonu kahve ve yürüyüş için rahat bir kombin oluştur.',
        createdAt: '2026-11-22T18:04:00.000Z',
        status: 'sent',
      },
      {
        id: 'msg-04',
        sender: 'assistant',
        text: 'Rahat ve uyumlu bir hafta sonu kombini seçtim:',
        createdAt: '2026-11-22T18:05:00.000Z',
        status: 'sent',
        suggestion: {
          id: 'sug-02',
          title: 'Hafta Sonu Kahve ve Yürüyüş Kombini',
          reason: 'Günlük rahat parçalarından oluşturuldu.',
          items: secondPack,
          pinnedItemIds: secondPack[0] ? [secondPack[0].id] : [],
          approvedOutfitId: 'out-01',
          feedback: 'like',
        },
      },
    ],
  },
  {
    id: 'conv-03',
    title: 'Akşam Yemeği Renk Uyumu',
    updatedAt: '2026-11-21T16:40:00.000Z',
    messages: [
      {
        id: 'msg-05',
        sender: 'user',
        text: 'Ekru gömlekle hangi ton dış giyim daha dengeli durur?',
        createdAt: '2026-11-21T16:39:00.000Z',
        status: 'sent',
      },
      {
        id: 'msg-06',
        sender: 'assistant',
        text: 'Ekru gömleği siyah, lacivert veya koyu kahve dış giyimle eşleştirerek temiz bir kontrast yakalayabilirsin.',
        createdAt: '2026-11-21T16:40:00.000Z',
        status: 'sent',
      },
    ],
  },
];
