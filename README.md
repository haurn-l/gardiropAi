# GardıropAI

React Native mobil istemci ve Spring Boot backend. Uygulamanın hedefleri Android ve iOS
telefonlar ve tabletlerdir. Ekran kabulü native uygulamada yapılır.

## Mobil geliştirme

Node 24 ile `cd mobile` ve `npm ci` çalıştırın.

- iOS: Xcode ve bir iPhone simülatörü hazırken `npm run ios`.
- Android: Android SDK, JDK 21 ve bir emülatör hazırken `npm run android`.
- Kalite kontrolü: `npm run check`.

Bu komutlar native uygulamayı derler, cihaza kurar ve geliştirme sunucusunu açar.
Kamera gibi native bağımlılıklar değiştiğinde uygulamayı yeniden derleyin.
Release derlemesi ve cihaz kontrolleri: [Native geliştirme](mobile/docs/native-development.md).

## Ekip düzeni

Her geliştirici güncel `main` üzerinden kendi çalışma dalını açar.
Dal adları yapılan işi anlatır: `feat/mobile-...`, `fix/mobile-...` veya `chore/...`.
`main` dalına doğrudan gönderim yapılmaz; inceleme ve kontrollerden sonra PR
birleştirilir. Adımlar: [Katkı rehberi](CONTRIBUTING.md).

API anahtarları mobil uygulamada tutulmaz. `EXPO_PUBLIC_` değişkenleri uygulamayı
kullanan herkes tarafından okunabilir. `.env.example` yalnızca örnek yapılandırma
içerir; yerel `.env`, IDE ve imza dosyaları Git'e eklenmez.

Mimari ve native geliştirme dokümanları `mobile/docs` klasöründedir.
Kişiye özel görev ve mentorluk notları ekip içinde özelden paylaşılır;
kaynak kodda bileşen sözleşmeleri ve teknik karar açıklamaları bulunur.
