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

`main` dalına doğrudan gönderim yapmayın. `feat/mobile-...`, `fix/mobile-...`
ve `feat/harun-...` gibi açıklayıcı dallardan PR açın. İnceleme ve testten sonra
yetkili ekip üyeleri birleştirir. Mevcut CODEOWNERS kuralı korunur.

API anahtarları mobil uygulamada tutulmaz. `EXPO_PUBLIC_` değişkenleri uygulamayı
kullanan herkes tarafından okunabilir. `.env.example` yalnızca örnek yapılandırma
içerir; yerel `.env`, IDE ve imza dosyaları Git'e eklenmez.

Mimari ve görev sözleşmeleri için `mobile/docs` klasörünü inceleyin.
