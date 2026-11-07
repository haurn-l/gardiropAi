# 🧥 Gardirop AI

**Gardirop AI**, kullanıcıların gardıroplarındaki kıyafetleri dijitalleştirmesini sağlayan, kıyafetlerin temiz/kirli durumlarını takip eden ve yapay zeka destekli stil asistanı ile kişiselleştirilmiş kombin önerileri sunan tam kapsamlı (Full-Stack) bir akıllı gardırop yönetim uygulamasıdır.

## 🚀 Proje Hakkında

Günlük hayatta *"Bugün ne giysem?"* sorusunu ortadan kaldırmayı amaçlayan **Gardirop AI**, kullanıcıların sahip olduğu kıyafetleri kategorize eder, mevsim ve renk uyumlarını analiz eder ve kullanıcının stil tercihlerine göre en uygun kombinleri oluşturur.

Kullanıcıların stil tercihleri, PostgreSQL'in `JSONB` veri tipi kullanılarak dinamik bir şekilde saklanır ve zaman içerisinde güncellenebilir. Ayrıca entegre sohbet asistanı (AI Chatbot) sayesinde kullanıcılar kişiselleştirilmiş stil danışmanlığı alabilir.

## ✨ Temel Özellikler

- **📸 Dijital Gardırop Yönetimi:** Kıyafetleri fotoğraf, kategori (`UST_GIYIM`, `ALT_GIYIM`, `DIS_GIYIM`, `AYAKKABI` vb.), alt kategori, renk, mevsim ve baskı durumuna göre kaydetme ve yönetme.
- **🧺 Kıyafet Durum Takibi:** Kıyafetlerin `TEMIZ`, `KIRLI` veya `KULLANIM_DISI` durumlarını güncelleyebilme ve yalnızca temiz kıyafetler üzerinden kombin oluşturabilme.
- **✨ Akıllı Kombin Oluşturucu:** Gardıroptaki parçalarla kombinler (`Combine`) oluşturma, geçmiş kombinleri görüntüleme ve kombinleri 1-5 arasında puanlama (`ratingScore`).
- **🤖 AI Stil Asistanı & Sohbet:** Kullanıcıya özel sohbet oturumları (`ChatSession`) ve mesaj geçmişi (`ChatMessage`) üzerinden interaktif moda danışmanlığı.
- **🧬 Dinamik Stil Profili:** Kullanıcının zaman içerisinde değişen stil tercihlerini PostgreSQL `JSONB` formatında esnek bir şekilde saklama, güncelleme ve sıfırlama (Cold Start) desteği.
- **📱 Modern Mobil Arayüz:** React Native ve TypeScript kullanılarak geliştirilen kullanıcı dostu mobil ekranlar ve akıcı alt navigasyon (`BottomBar`) yapısı.

## 🛠️ Teknoloji Yığını (Tech Stack)

### Backend

| Teknoloji | Kullanım Amacı |
|---|---|
| **Java 23** | Backend programlama dili |
| **Spring Boot 4.1.1** | Backend framework |
| **Spring Data JPA** | Veri erişim katmanı |
| **Hibernate** | ORM (Object-Relational Mapping) |
| **PostgreSQL** | İlişkisel veritabanı |
| **JSONB** | Dinamik stil profili verilerinin saklanması |
| **Jakarta Bean Validation** | Veri doğrulama işlemleri |
| **Lombok** | Tekrarlayan kodların azaltılması |
| **Maven Wrapper** | Proje bağımlılıklarının ve build süreçlerinin yönetimi |

**Backend Mimari ve Hata Yönetimi:**
- Merkezi hata yönetimi için `@RestControllerAdvice`.
- Özel ve hiyerarşik Exception mimarisi.
- Katmanlı mimari yaklaşımı.
- Spring Data JPA ile veritabanı işlemlerinin yönetimi.

### Mobile / Frontend

| Teknoloji | Kullanım Amacı |
|---|---|
| **TypeScript** | Tip güvenli programlama |
| **React Native** | Cross-platform mobil uygulama geliştirme |
| **Expo** | Mobil uygulama geliştirme ve çalıştırma ortamı |

**Frontend Mimari:**
- Component-Driven (Bileşen Tabanlı) mimari.
- Modüler ve yeniden kullanılabilir bileşen yapısı.
- TypeScript tabanlı `.tsx` ve `.ts` dosya organizasyonu.
- Kullanıcı dostu ve akıcı `BottomBar` navigasyon yapısı.

---

## 🎯 Projenin Amacı

Gardirop AI'ın temel amacı, geleneksel gardırop kullanımını dijitalleştirerek kullanıcıların kıyafet yönetimini kolaylaştırmak ve yapay zeka destekli kişiselleştirilmiş kombin önerileri sunmaktır.

Kullanıcının gardırop içeriğini, kıyafetlerin mevcut durumlarını, mevsimsel koşulları ve kişisel stil tercihlerini bir araya getirerek daha akıllı bir giyim deneyimi sunmayı hedefler.
