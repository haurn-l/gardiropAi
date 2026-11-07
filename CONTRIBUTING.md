# Katkı rehberi

Her geliştirici kendi dalını güncel `main` üzerinden açar. Dal adı kişinin
adını değil değişikliği anlatır: `feat/mobile-clothing-card`,
`fix/mobile-navigation` veya `chore/mobile-docs`.

## Çalışmaya başlama

Depo kökünde `git status --short` ile yerel değişiklikleri kontrol edin.
Tamamlanmamış iş varsa mevcut dalda kaydedin; değişiklikleri silerek devam etmeyin.
Temiz çalışma alanında:

```sh
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feat/mobile-clothing-card
```

Örnekteki dal adını yapacağınız işe göre değiştirin. Yerel `main` henüz yoksa
`git switch main` yerine `git switch --track origin/main` kullanın.
`pull --ff-only` hata verirse durun; force push veya reset ile geçmişi değiştirmeyin.

## Değişikliği gönderme

- Mobil değişikliklerde `mobile` içinde `npm run check` çalıştırın.
- Arayüzü Android veya iOS cihazda deneyin; denemediğiniz platformu belirtin.
- `git diff --check` ve `git diff` ile göndereceğiniz farkı okuyun.
- Yalnızca ilgili dosyaları `git add <dosya-yolu>` ile hazırlayın.
- `git diff --cached` ile commit kapsamını kontrol edin ve açıklayıcı commit yazın.
- `git push -u origin <dal-adı>` ile kendi dalınızı gönderin.
- GitHub'da hedef (`base`) `main`, kaynak (`compare`) kendi dalınız olacak şekilde PR açın.

Aynı işte düzeltme gerektiğinde aynı dala commit gönderin; açık PR otomatik
güncellenir. Her düzeltmede PR'ı kapatıp yenisini açmayın. PR numarası görev
numarası değildir. Onay ve gerekli kontroller tamamlanınca yetkili kişi birleştirir.

## Kaynak kod ve ekip notları

README, kurulum, mimari, API sözleşmeleri ve test talimatları depoda bulunur.
Kişiye özel eğitim, görev dağılımı ve mentorluk notları özel ekip kanalında paylaşılır.
Kod yorumları kararların nedenini açıklar; kişiye hitap eden ödev talimatları içermez.
Gerekiyorsa yerel notlar için Git'in yok saydığı `private-notes/` kullanılır.

PR açıklaması problemi, değişen davranışı, yapılan kontrolleri ve bilinen
sınırları anlatır. Özel görev metnini PR'a kopyalamayın. API anahtarı, `.env`,
IDE ayarı ve imza dosyaları gönderilmez. Mevcut CODEOWNERS kuralları geçerlidir.
