# GardıropAI

React Native mobil istemci ve Spring Boot backend. Android ve iOS ana hedeflerdir;
web çıktısı tasarım incelemesi ve hızlı geliştirme için de kullanılabilir.

## Mobil geliştirme

Node 24 ile `cd mobile`, `npm ci`, `npm start` çalıştırın.
`npm run web` tarayıcı önizlemesini, `npm run check` kalite kontrollerini açar.
Native çalıştırma için uyumlu Expo Go veya geliştirme derlemesi gerekir.

## Ekip düzeni

`main` dalına doğrudan gönderim yapmayın. `feat/mobile-...`, `fix/mobile-...`
ve `feat/harun-...` gibi açıklayıcı dallardan PR açın. İnceleme ve testten sonra
yetkili ekip üyeleri birleştirir. Mevcut CODEOWNERS kuralı korunur.

API anahtarları mobil uygulamada tutulmaz. `EXPO_PUBLIC_` değişkenleri uygulamayı
kullanan herkes tarafından okunabilir. `.env.example` yalnızca örnek yapılandırma
içerir; yerel `.env`, IDE ve imza dosyaları Git'e eklenmez.

Mimari ve görev sözleşmeleri için `mobile/docs` klasörünü inceleyin.
