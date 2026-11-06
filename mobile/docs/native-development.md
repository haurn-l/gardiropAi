# Android ve iOS geliştirme

Hedef React Native uygulamasıdır. Tarayıcı çıktısı native kabul kontrolünün yerini tutmaz.

## Yerel derleme

Node 24 ve `npm ci` sonrasında:

```sh
npm run ios -- --device
npm run android -- --device
```

iOS için Xcode, CocoaPods ve kurulu bir iOS simülatör runtime'ı gerekir.
Android için SDK, çalışan emülatör ve JDK 21 kullanın. `JAVA_HOME` ile JDK'yı,
`ANDROID_HOME` ile SDK yolunu kendi makinenize göre ayarlayın; kişisel yolları commit etmeyin.

Performans kontrolü, geliştirme sunucusuna ihtiyaç duymayan release uygulamasıyla yapılır:

```sh
npm run ios -- --device --configuration Release --no-bundler
npm run android -- --device --variant release --no-bundler
```

Bu iOS komutu seçilen simülatöre uygulama üretir; App Store'a yüklenecek imzalı
paket değildir. Android yerel release ayarları da mağaza dağıtımının yerine geçmez.
İmzalama bilgileri ve anahtar dosyaları repoya girmez.

`ios/` ve `android/` Expo tarafından üretilir ve Git'e eklenmez. Kalıcı native
ayarları `app.json` ve config plugin'leri üzerinden yönetin. CocoaPods klasör yolundaki
Türkçe karakterlerde kodlama hatası verirse projeyi ASCII karakterli bir çalışma
klasörüne kopyalayıp orada derleyin. Sadece sembolik bağlantı yeterli olmayabilir.

## Kontroller

`npm run check` tipleri, lint'i, iş mantığını ve 150 satır sınırını denetler.
CI iki platformun JavaScript paketlerini üretir; Xcode/Gradle derlemesi veya
simülatör kabulü yaptığı anlamına gelmez. Ekranlar gerçek native derlemede açılmalı;
Android sistem geri tuşu, iOS geri hareketi, güvenli alanlar, klavye, izin reddi
ve farklı ekran boyları kontrol edilmelidir.
