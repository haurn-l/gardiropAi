# Görev 01 Ortak üst bar

Amaç: farklı ekranlarda tek Header kullanmak. Dal: `feat/harun-header`.
Referans çözüm bu dalın geçmişinde yoktur. Önce `feat/mobile-foundation`
PR'ı main'e alınmalıdır. `feat/harun-header` dalını başlangıç alarak
`feat/harun-header-solution` dalını oluştur; çözümünü main'e PR açarak gönder.
Temel PR henüz birleşmediyse kendi PR açıklamanda #2 bağımlılığını belirt.

## Başlangıç

`cd mobile` ve `npm ci` sonrasında iOS için `npm run ios`, Android için
`npm run android` çalıştır. Kontrolleri simülatörde veya cihazda yap.
`src/app/index.tsx` dört kullanım örneğini ve olay sayaçlarını gösterir.
Asıl dosyan `src/shared/ui/Header.tsx`. Gerekirse Header'a özel stil dosyası
ekleyebilirsin. Paket, API veya navigasyon eklemene gerek yok.

## Kullanacağın sözleşmeler

- `HeaderProps`, `HeaderAction`: `src/shared/ui/header.types.ts`.
- `IconButton`: `src/shared/ui/IconButton.tsx`; icon, label, onPress parametreleri.
- `Text`: `src/shared/ui/Text.tsx`; heading ve caption görünümleri.
- Tema: `src/shared/theme/tokens.ts`; colors, space, radius.

`onBack(): void` ve `action.onPress(): void` üst ekranın verdiği davranışlardır.
Render sırasında çağırma; kullanıcının basmasına bağla.

## Kabul koşulları

- Yalnızca başlıkta iki tarafta boş buton alanı bulunmaz.
- onBack varsa erişilebilir adı “Geri dön” olan buton görünür.
- action varsa doğru ikon, etiket ve tıklama davranışı görünür.
- Tek basış ilgili sayacı tam bir kez artırır; render sayaçları değiştirmez.
- subtitle verilmediyse alt başlık alanı oluşmaz.
- 320 px genişlikte uzun başlık ve iki buton çakışmaz.
- Büyük sistem yazı boyutunda içerik kesilmez; başlık satıra geçebilir.
- 44x44 dokunma alanı ve ortak tema korunur.
- `npm run check` geçer; kaynak dosyaları en fazla 150 satırdır.

## PR teslimi

Başlık: `feat(mobile): implement reusable header`.
Denenen örnekleri, platformları ve ekran görüntüsünü açıklamaya ekle.
Main'e doğrudan gönderme. İsimler açıklayıcı, karar yorumları Türkçe olsun.
Referansla aynı kod beklenmez; sözleşme ve davranış esas alınır.
