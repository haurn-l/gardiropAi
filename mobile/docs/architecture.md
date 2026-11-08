# Mobil mimari

`src/app` yalnızca ekran bağlantılarını ve navigasyonu taşır. Kullanıcı akışları
`src/features` altında kendi bileşenleri, verileri ve işlemleriyle yaşar.
`src/shared` tema, tekrar kullanılan arayüz ve altyapı parçalarını içerir.
Bir özelliğe özgü bileşeni sırf kısa olsun diye shared içine taşımayın.

TypeScript strict kullanılır. Bileşen başına tek sorumluluk, açıklayıcı isimler ve
kararın nedenini anlatan Türkçe yorumlar beklenir. Kaynak dosyalarda 150 satır
üst sınırı vardır; boş satır ve yorumlar bu sınırın içindedir.

Görsel bileşenler HTTP çağırmaz. İş mantığı saf fonksiyonlarla, cihaz erişimi ayrı
servislerle yürür. Durum verileri sürümlü saklanır. Kamera izni yalnızca kullanıcı
kamera seçtiğinde istenir. Kullanıcı fotoğrafları demo modunda cihazda kalır.

Performans değerlendirmesi release derlemesinde yapılır. Uzun listeler sanallaştırılır;
görseller sınırlı çözünürlükte saklanır. Bağımlılık kaldırma kararı ölçümden sonra verilir.
Native modüller ve navigasyon için platformla uyumlu, bakımlı paketler kullanılır.

Her geliştirici kendi dalını güncel `main` üzerinden açar. İnceleme bileşenin
sözleşmesine, kullanıcı davranışına ve test kanıtına göre yapılır.
Kişisel çalışma notları depoya eklenmez; ekip akışı kökteki `CONTRIBUTING.md`
dosyasında anlatılır.
