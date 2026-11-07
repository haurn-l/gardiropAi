# Görev 02 — Ortak alt bar

Başlangıç dalı: `feat/harun-bottom-navigation`.
Kendi çözüm dalın: `feat/harun-bottom-navigation-solution`.
Görev dalı, ilk görevde gönderdiğin Header'ı içerir. Alt barın tamamlanmış
referans çözümü bu dalda veya geçmişinde bulunmaz.

## Hazırlık

Depo klasöründe, önceki çalışmanı commit ettikten sonra:

```sh
git fetch origin
git switch -c feat/harun-bottom-navigation-solution origin/feat/harun-bottom-navigation
cd mobile
npm ci
npm run android
```

Node 24, JDK 21, Android SDK ve çalışan emülatör gerekir.
Mac ve Xcode kullanıyorsan `npm run ios` ile de kontrol et.
Bu çalışma React Native içindir; tarayıcı görüntüsü cihaz kontrolünün yerine geçmez.

## Yapacağın parça

`src/shared/navigation/BottomBar.tsx` içindeki açıklamalı yer tutucuyu tamamla.
Gerekirse `BottomBarItem.tsx` ve küçük bir stil dosyası ekleyebilirsin.
Her kaynak dosyası en fazla 150 satır olsun. Mevcut Header'ı yeniden yazma.

Soldan sağa **Gardırobum / Kombinlerim / Sohbetler / +** görünmeli.
Üç sekme aynı genişliği paylaşır; + ayrı bir aksiyondur.
Seçili sekmenin ikon arkasında açık turuncu alan, koyu ikon ve yazı olsun.
Diğer sekmelerde `colors.muted`, + zemininde `colors.primary`, ikonunda
`colors.onPrimary` kullan. Dış yüzey `colors.surface`, üst çizgi `colors.line`.
Yeni kütüphane, font veya ikon paketi ekleme.

## Hazır sözleşmeler

| Kaynak | Kullanım |
| --- | --- |
| `shared/navigation/bottomBar.types.ts` | `BottomBarProps`, `BottomTabId`, `BottomTab` |
| `shared/navigation/bottomBar.items.ts` | `bottomTabs`: üç sekmenin kimliği, etiketi ve ikonu |
| `shared/ui/Icon.tsx` | `name`, `size`, `color` alanlarıyla ikon |
| `shared/ui/Text.tsx` | Ortak tipografi; `caption` sekme etiketi için uygun |
| `shared/theme/tokens.ts` | `colors`, `space`, `radius` |

Props ve olaylar:

- `activeTab`: üst ekranın seçtiği `wardrobe`, `outfits` veya `conversations`.
  `null` geldiğinde hiçbir sekme seçili görünmez; bu durum profil gibi ek ekranlar içindir.
- `onSelectTab(tabId)`: ilgili sekmeye basınca bir kez çağır. Render sırasında çağırma.
- `onAddPress()`: + basışında bir kez çağır. Bu aksiyon sekme seçimi değildir.
- `bottomInset`: telefonun alt güvenli alanı. Alt boşluk en az
  `Math.max(bottomInset, space.sm)` olmalı. Aynı boşluğu iki kez uygulama.

Bar kendi seçili sekmesini `useState` ile tutmaz. Veriyi üst ekrandan alır.
Barın içine `router`, API çağrısı veya ekran açma kodu ekleme.
Sekmeler `accessibilityRole="tab"`, `accessibilityLabel={item.label}` ve
`accessibilityState={{ selected: ... }}` taşımalı. + butonu `button` rolü
ve “Kıyafet ekle” etiketi taşımalı. Her dokunma alanı en az 48×48 olmalı.

## Çizimlerdeki gezinme kuralı

| Ekran | Alt bar |
| --- | --- |
| Gardırobum, Kombinlerim, sohbet geçmişi | Var |
| Aktif sohbet, kıyafet detayı, kombin detayı, kıyafet ekleme | Yok |

Atölyenin gezinme bağlantıları hazır. `src/features/workshops/BottomBarWorkshop.tsx`
seçimi ve sayaçları yönetir; barı ScrollView'ın dışında tutar.
`src/app/navigation-preview.tsx` kök Stack ekranıdır ve alt bar içermez.
Barın görünürlüğünü düzeltmek için bu ekranlara bar ekleme veya `display: none`
uygulama. Çizimlerdeki sohbet sekmesi sohbet geçmişini temsil eder;
**Sohbetler → Yeni sohbet** ile açılan iç ekranda bar görünmez.

## Elle kontrol listesi

- Açılışta Gardırobum seçili; üç etiket ve + görünür.
- Her sekmeye basınca başlık ve seçili görünüm güncellenir; sekme sayacı bir artar.
- Aktif sekmeye tekrar basınca sayaç yine yalnızca bir artar.
- “Sekmeyi dışarıdan değiştir” seçimi değiştirir, sayaç artırmaz; bar bunu takip eder.
- + yalnızca ekle sayacını artırır ve ekleme ekranını açar; burada bar yoktur.
- Geri dönünce önceki sekme ve sayaçlar korunur; bar yeniden görünür.
- Sohbetler → Yeni sohbet ve diğer iki detay geçişinde de bar yoktur.
- Android sistem geri tuşu veya iOS geri hareketi doğru ana ekrana döner.
- Uzun içeriği kaydırınca alt bar aşağı kaybolmaz.
- 320 px genişlikte etiketler üst üste binmez. Büyük sistem yazısında metin
  kesilmez; gerekli olduğunda satıra geçer. Sabit bar yüksekliği kullanma.
- iOS home göstergesi ve Android gezinme alanı butonların üzerine gelmez.
- Ekran okuyucu etiketleri ve seçili sekmeyi doğru bildirir.

`npm run check` çalıştır. Başlangıç şablonu da derlenir; bu komutun geçmesi,
eksik alt barın tamamlandığı anlamına gelmez. Yukarıdaki akışları ayrıca dene.
Önceki Header örnekleri atölyedeki “Üst bar atölyesini aç” butonundan erişilebilir.

## PR teslimi

Kendi çözüm dalını GitHub'a gönder; hedef `main`, kaynak
`feat/harun-bottom-navigation-solution` olacak şekilde PR aç.
Başlık: `feat(mobile): implement accessible bottom bar`.
Bu başlangıç dalı için ayrıca boş bir PR açma.

İş sırası: temel kurulum **#2**, Header **#3**, ardından bu görev.
Önceki PR'lar henüz birleşmediyse yeni PR açıklamasına bağımlılığı yaz.
Çalışmaya başlamak için birleşmelerini beklemene gerek yok.
Hangi cihazda denediğini, `npm run check` sonucunu, 320 px / büyük yazı
görüntüsünü ve sayaçları gösteren kısa videoyu ekle.
Kapsam dışı `package-lock.json` değişikliği göndermeden önce nedenini kontrol et.
