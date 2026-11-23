# Android ve iOS geliştirme

Hedef React Native uygulamasıdır. Tarayıcı çıktısı native kabul kontrolünün yerini tutmaz.

## Telefonu yerel backend'e bağlama

PostgreSQL'i ve Spring Boot uygulamasını bilgisayarda başlatın. Bilgisayar ve telefon
aynı Wi-Fi veya hotspot'a bağlanır. `.env.example` dosyasını `.env.local` olarak
kopyalayın ve fiziksel telefon için `EXPO_PUBLIC_API_URL` değerini örneğin
`http://192.168.1.109:8080` biçiminde bilgisayarın güncel adresine ayarlayın.
Telefon tarayıcısında bu adrese `/api/clothes/all` ekleyerek bağlantıyı sınayın.
Ardından `npm start -- --lan` ile Expo'yu açın. API adresini değiştirirseniz
Expo'yu yeniden başlatın. Adres ayarlanmazsa atölye ekranı açılır.

Kamera veya galeriden gelen fotoğraf Expo tarafından JPEG olarak hazırlanır ve
`POST /api/clothes/photo-drafts` yoluna `photo` alanıyla yüklenir. Onayda
`POST /api/clothes/photo-drafts/{uploadId}/confirm` çağrısı kıyafeti kaydeder.
Spring Boot, fotoğrafı varsayılan olarak kullanıcı dizinindeki
`.gardiropai/photos/originals` altında tutar. `GARDIROP_PHOTO_DIR` ile kök dizin
değiştirilebilir. PostgreSQL fotoğrafın HTTP adresini ve kıyafet bilgilerini tutar.
Model bağlandığında işlenmiş kopyalar aynı kökün `processed` dizinine eklenebilir.

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
