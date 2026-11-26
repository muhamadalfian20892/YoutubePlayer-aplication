T U N E V I A
=============

Versi: 1.7.0
Penulis: Muhammad Alfian (Technokers Lab)


HALO DAN SELAMAT DATANG
-----------------------
Hai semuanya. Aku Muhammad Alfian, orang yang ngabisin terlalu banyak waktu luang buat ngoding proyek ini. Makasih banget udah download Tunevia. Aku pengen luangin waktu buat bener-bener ngejelasin program ini tuh apa, kenapa aku repot-repot bikin, dan gimana cara kerja semua hal di dalemnya.

Aku ini tunanetra, dan aku bergantung banget sama pembaca layar (screen reader) yang namanya NVDA buat pake komputer tiap hari. Awalnya aku bikin Tunevia karena aku mulai ngerasa sebel banget pake web browser biasa cuma buat dengerin YouTube. Browser tuh makan RAM gede banget, tab-nya suka ilang kalau kita buka banyak halaman sekaligus, dan jujur aja, tampilan web itu ibarat mimpi buruk buat pengguna pembaca layar kalau kita cuma pengen dengerin musik di latar belakang sambil kerja.

Jadi, aku mutusin buat bikin program desktop khusus sendiri. Tujuannya simpel: bikin sesuatu yang nyambung langsung ke YouTube dan YouTube Music, loadingnya secepat kilat, muter audio tanpa perlu muat file video yang berat kecuali kalau emang diminta, dan 100 persen bisa diakses cuma modal keyboard doang.

File readme ini bakal panjang banget karena aku mau ngejelasin setiap jengkal dari program ini ke kalian. Nggak ada ringkasan singkat di sini. Aku pengen kalian tau persis tiap tombol fungsinya buat apa dan gimana sistemnya kerja di balik layar.


SEBELUM MULAI: PERSIAPAN (SETUP)
--------------------------------
Sebelum kita masuk ke bagian yang seru-seru, kalian harus mastiin programnya beneran bisa jalan. Tunevia ini dibangun pake bahasa Python, tapi dia butuh beberapa bantuan dari luar buat ngelakuin tugas-tugas beratnya.

Pertama, Tunevia pake VLC Media Player buat muter suaranya. VLC itu kokoh banget dan bisa nanganin hampir semua format audio yang ada. Kabar baiknya, kalian nggak perlu repot-repot nginstal VLC di komputer kalian! Aku udah nyediain file VLC yang dibutuhin langsung di dalem folder 'libs' di program ini. Jadi program ini bener-bener portabel dan siap jalan.

Kedua, kalau kalian ngejalanin ini dari source code mentahnya (bukan dari file executable yang udah jadi), kalian harus nginstal library Python-nya dulu. Buka command prompt atau terminal di dalem folder Tunevia terus ketik perintah: pip install -r requirements.txt. Ini bakal nginstal hal-hal kayak wxPython buat tampilannya dan python-vlc.

Terakhir, ada alat yang namanya yt-dlp. Ini adalah mesin ajaib yang dipake Tunevia buat ngobrol sama YouTube, nyari video, dan nge-download file. Masalahnya, YouTube itu terus-terusan ngubah kode website mereka, yang bikin alat semacam ini sering rusak. Gara-gara itu, kalian nggak perlu pusing nginstal yt-dlp sendiri. Tiap kali kalian buka Tunevia, dia bakal diem-diem ngecek internet buat nyari tau apa ada versi yt-dlp yang lebih baru, dan otomatis nge-downloadin buat kalian. Jadi kalau kalian ngerasa ada jeda dikit pas pertama kali buka aplikasi, nah itu dia lagi sibuk update.


TAMPILAN UTAMA
--------------
Pas kalian buka Tunevia, kalian bakal liat tampilan Windows klasik. Aku nggak mau bikin sesuatu yang terlalu mencolok atau bikin bingung. Di bagian paling atas, ada deretan tab. Kalian bisa klik tab ini pake mouse, atau kalau kalian lebih suka pake keyboard, kalian bisa tahan tombol Control terus tekan angka 1 sampe 9 buat lompat antar tab secara instan.

Yuk kita bahas satu-satu setiap tab dan apa aja yang bisa kalian lakuin di dalemnya.


TAB 1: PENCARIAN YOUTUBE (Ctrl + 1)
-----------------------------------
Ini adalah titik awal kalian. Di bagian atas tab ini ada kotak teks yang gede. Ini adalah kolom pencarian kalian. Kalian bisa ngetik judul lagu, podcast, atau nama artis di sini. Tapi kalian juga bisa langsung paste link YouTube kalau kebetulan dikirimin temen. Kalian bahkan bisa paste link keseluruhan YouTube Playlist, dan aplikasinya bakal ngerti.

Pas kalian tekan Enter, program bakal ngehubungin YouTube dan narik daftar hasilnya. Area di bawah kolom pencarian bakal penuh sama hasil ini. Aku udah ngedesain daftarnya biar gampang dibaca. Tiap baris bakal ngasih tau judul lengkap videonya, durasinya secara pasti, dan nama channel yang nge-upload.

Kalau kalian klik kanan di item mana aja di daftar ini, bakal muncul menu dengan banyak pilihan:
- Play Audio: Ini bakal langsung muat audio dari video itu ke player dan mulai muterin lagunya.
- Add to Queue: Kalau kalian lagi dengerin lagu lain, opsi ini bakal masukin lagunya ke antrean buat diputer selanjutnya.
- Download: Ini bakal ngirim videonya ke alat Downloader, yang bakal aku jelasin nanti.
- Add to Favorites: Ini bakal nyimpen lagunya ke tab Favorit kalian biar nggak ilang.
- View videos by this uploader: Ini shortcut yang asik banget. Kalau kalian nemu channel yang kalian suka, klik ini, dan Tunevia bakal otomatis nyari ulang khusus buat nampilin video dari channel itu aja.
- Start Radio: Kalau kalian klik ini, Tunevia bakal muter lagunya, terus dia bakal otomatis nyari lagu-lagu yang mirip dan muterin terus tanpa henti. Berasa kayak punya stasiun radio pribadi.
- Copy Link: Cuma buat nge-copy URL YouTube-nya ke clipboard kalian.

Oh ya, aku juga bikin sistem cache di pencariannya. Kalau kalian nyari "Linkin Park", terus NYARI hal lain, terus nyari "Linkin Park" lagi di sesi yang sama, hasilnya bakal muncul seketika karena aplikasinya inget hasil pencarian sebelumnya.


TAB 2: DISCOVERY (Ctrl + 2)
---------------------------
Kadang kalian cuma pengen tau apa yang lagi populer sekarang tanpa harus mikir mau nyari apa. Di tab ini, kalian bakal nemuin dua tombol gede di atas. Satu tulisannya "Top 100 Global" dan satunya lagi "New Releases".

Pas kalian klik salah satu tombol ini, Tunevia bakal pergi ke tangga lagu musik resmi YouTube dan narik data terbarunya. Daftar gede di bawah tombol bakal dipenuhi sama lagu-lagu yang lagi trending. Cara kerjanya persis kayak daftar hasil pencarian. Kalian bisa klik ganda lagunya buat muter, atau klik kanan buat masukin antrean atau favorit.


TAB 3: RADAR (Ctrl + 3)
-----------------------
Ini fitur yang aku banggain banget. Fitur ini dibikin buat ngebantu kalian nemuin musik baru murni berdasarkan apa yang sebenernya kalian suka, tanpa pake algoritma pelacakan yang ngeselin.

Di tab ini, ada satu tombol gede tulisannya "Scan". Pas kalian klik, program bakal ngeliat riwayat lagu yang baru-baru ini kalian puter di dalem Tunevia. Dia bakal ngambil beberapa lagu itu, nanya ke YouTube video apa aja yang berkaitan sama lagu-lagu itu, terus nyusun daftar yang panjang. Bagian paling pinternya adalah dia otomatis nyaring dan ngebuang lagu-lagu yang udah pernah kalian dengerin.

Jadi, kalian bakal dapet daftar rekomendasi baru yang bener-bener disesuaikan sama mood kalian belakangan ini. Butuh waktu beberapa detik emang buat proses scan-nya karena dia harus nyilangin banyak data, tapi hasilnya bener-bener sepadan.


TAB 4: AUDIO PLAYER (Ctrl + 4)
------------------------------
Ini adalah pusat buat pengalaman dengerin musik kalian.
Di bagian paling atas tab ini, ada area teks status. Ini ngasih tau judul pasti dari apa yang lagi diputer, nama channelnya, dan jumlah view-nya.

Di bawahnya, kalian punya dua slider horizontal. Yang panjang itu Seek Bar. Kalian bisa klik di mana aja di garis itu buat lompat ke tengah lagu. Yang lebih pendek itu kontrol Volume kalian. Kalau kalian pake keyboard, kalian bisa pake panah kiri dan kanan buat skip maju mundur di lagunya, dan panah atas bawah buat ngubah volume. Kalau kalian pengen tau sisa waktu lagunya, tekan aja huruf 'T' di keyboard, dan program bakal ngomongin waktunya keras-keras.

Di bawah slider ada tombol-tombol utama: Play/Pause, Stop, Previous Track (Lagu Sebelumnya), dan Next Track (Lagu Berikutnya).

Tapi di bawah tombol-tombol itu ada grid yang isinya alat-alat canggih:
- Playback Speed: Slider yang bisa ngelambatin audio sampe kecepatan 0.25x atau dicepetin sampe dua kali lipat. Cocok banget buat dengerin podcast yang panjang.
- Equalizer: Kalau kalian tekan Ctrl+E atau klik tombol ini, jendela baru bakal kebuka isinya audio equalizer 10-band. Kalian bisa ngatur bass dan treble persis kayak yang kalian mau. Kalian juga bisa nyimpen preset buatan sendiri. Ada slider Pre-amp di situ yang bisa naikin volume sampe 200 persen, tapi hati-hati banget ya karena ini bisa bikin suara audionya pecah (distorsi) kalau terlalu dipaksa.
- Audio Track: Kadang video YouTube punya beberapa trek bahasa. Kalau ada, tombol ini bisa diklik biar kalian bisa milih mau dengerin bahasa yang mana.
- Toggle Shuffle dan Repeat: Tombol buat ngacak playlist kalian atau ngulang satu lagu terus-terusan.
- Mono Audio: Tombol buat maksa audio jadi satu saluran (mono). Ini berguna banget kalau kalian cuma pake earphone sebelah atau kalau videonya punya mixing stereo yang berantakan.
- Spatial Audio: Tekan Ctrl+Shift+S buat menyalakan atau mematikan Spatial Audio secara cepat, atau tekan Ctrl+Shift+E buat membuka jendela pengaturannya. Kalian bisa memperlebar panggung suara dan memberi kesan ruang lewat lima preset (Off, Subtle Wide, Concert Hall, Studio Room, Wide Stage) atau mengatur slider Soundstage Width, Room Size, dan 3D Depth dengan pemakaian RAM yang tetap ringan.
- Bookmarks: Kalau kalian tekan Ctrl+B pas lagi dengerin lagu, bakal muncul jendela buat kalian ngetik catatan kecil. Ini nyimpen cap waktu (timestamp) persis di detik itu. Nanti, kalian bisa buka bookmark kalian dan langsung lompat ke momen lucu di podcast atau solo gitar favorit kalian.

Ada juga tombol yang namanya "Show Video". Secara default, Tunevia cuma muter audionya aja buat nghemat kuota internet dan memori komputer kalian. Tapi kalau kalian emang pengen nonton video musiknya, klik ini, dan jendela kecil yang simpel bakal muncul nampilin videonya.


TAB 5: HISTORY (Ctrl + 5)
-------------------------
Tiap hal yang kalian puter di Tunevia bakal terekam di sini jadi kalian nggak bakal pernah kehilangan jejak lagu yang enak.
Karena daftar ini bisa jadi panjang banget, aku naruh kolom pencarian tepat di bagian atas tab History. Kalian tinggal ketik satu kata, dan daftarnya langsung tersaring nyocokin apa yang kalian ketik. Kalian bisa klik kanan item di sini buat muter lagunya lagi. Ada juga tombol buat nge-export seluruh riwayat kalian jadi file playlist (kayak file .m3u) buat di-backup.


TAB 6: FAVORIT (Ctrl + 6)
-------------------------
Ini koleksi pribadi kalian. Tiap kali kalian klik kanan lagu di tab Search, Discovery, atau Radar terus milih "Add to Favorites", lagunya bakal masuk ke sini. Fungsinya sama persis kayak daftar-daftar yang lain.


TAB 7: LIRIK (Ctrl + 7) - TOLONG BACA BAGIAN INI
------------------------------------------------
Oke, aku harus ngebahas tab Lirik ini secara mendetail, karena aku harus jujur banget soal kelemahan sistem otomatisasinya saat ini.

Tab ini sebagian besar isinya kotak teks GEDE tempat kalian bisa baca lirik. Di bagian bawah, ada tempat kalian bisa ngetik judul lagu dan artis secara manual, klik Search, dan aplikasinya bakal nyari liriknya dari Genius.com. Kalian juga bisa nge-save liriknya ke file teks di komputer kalian.

Nah, di tab Settings, ada opsi yang namanya "Auto-fetch lyrics". Idenya adalah pas lagu mulai diputer, kalian nggak usah ngapa-ngapain. Tunevia bakal otomatis nyari liriknya dan masukin ke dalem kotak teks itu.

Tapi ini letak masalahnya: sistem otomatisasinya itu buta dan jujur aja lumayan ngawur. Tunevia tuh sebenernya nggak tau apakah video YouTube yang lagi kalian puter itu beneran video musik atau cuma orang ngomong doang. Pas video mulai, aplikasinya cuma ngambil judul videonya, nyoba ngehapus kata-kata umum kayak "(Official Music Video)", dan ngelempar sisa teksnya ke API Genius buat dicari.

Kalau kalian lagi dengerin "Coldplay - Numb", fitur ini jalan sempurna. Tapi coba bayangin kalian lagi dengerin video esai 45 menit soal sejarah Romawi, atau tutorial cara benerin wastafel bocor. Tunevia nggak peduli. Dia bakal ngambil judul "Cara benerin wastafel bocor", ngirim itu ke Genius, dan nyari liriknya secara buta. Karena database Genius itu gede banget, kadang dia nemuin kecocokan sama lagu rap indie antah berantah yang kebetulan punya kata "wastafel" di judulnya. Tiba-tiba, kalian lagi nyoba dengerin tutorial ledeng, tapi tab liriknya malah penuh sama lirik lagu aneh yang sama sekali nggak nyambung.

Dan yang bikin sebel, dia bakal terus-terusan nyari. Tiap kali video baru diputer, dia nyari lagi. Dia nggak peduli itu lagu, vlog, atau berita. Kalau kalian pake Tunevia buat dengerin campuran antara musik dan video orang ngomong, fitur ini bakal bikin kesel banget dengan cepet. Udah buang-buang kuota internet, nampilin teks ngawur pula.

Saran jujur dari aku? Kalau kalian lebih sering dengerin podcast atau video YouTube acak, mending MATIIN aja pengaturan Auto-fetch ini. Biarin aja mati. Pas kalian bener-bener lagi muter lagu dan pengen nyanyi, tinggal buka tab Lirik dan pake kotak pencarian manual di bawah. Caranya jauh lebih nggak bikin emosi. Mungkin ke depannya aku bakal coba bikin sistemnya lebih pinter buat deteksi ini beneran musik atau bukan, tapi buat sekarang, ya begitulah adanya.


TAB 8: STATS (STATISTIK)
------------------------
Ini panel kecil yang asik. Dia nyatet kebiasaan dengerin musik kalian seiring waktu. Dia bakal nampilin daftar artis teratas kalian dan lagu yang paling sering kalian putar. Dia juga nyoba ngitung seberapa banyak waktu yang kalian abisin buat dengerin musik beneran dibandingin sama konten video lainnya. Pokoknya ini ngasih rincian visual tentang kehidupan Tunevia kalian.


TAB 9: PENGATURAN (Ctrl + 8)
----------------------------
Ini PENGATURAN. Aku udah nyoba ngelompokin semuanya senormal mungkin biar gampang dicari.

- Grup Umum (General): Di sini kalian bisa ganti bahasa seluruh aplikasi. Bahasanya langsung ganti saat itu juga. Kalian juga bisa centang kotak buat bikin jendela Tunevia selalu ada di atas (Always on Top) program lain, atau bikin dia minimize ke system tray (di deket jam kalian) alih-alih menuh-menuhin taskbar. Kalian juga bisa nyalain Clipboard Monitoring di sini. Kalau dinyalain, tiap kali kalian nge-copy link YouTube di mana aja di komputer kalian, Tunevia bakal munculin kotak nanya apa kalian mau muter atau nge-download videonya.
- Grup Playback: Kalian bisa ngatur kualitas audio bawaan kalian. Kalian bisa ngubah interval seek bawaan (pas kalian tekan tombol panah, kalian mau dia lompat 5 detik, 10 detik, atau semenit penuh?). Kalian juga bisa nyalain Audio Normalization di sini, yang fungsinya nyoba nyegah lagu yang pelan biar nggak terlalu pelan dan lagu yang kenceng biar nggak bikin budek kuping kalian.
- Grup Pencarian & Downloader: Kalian bisa ngatur folder tempat file download-an kalian disimpen. Ada juga pengaturan yang namanya "Comment Fetch Limit". Kalian bisa setel ini ke 10, 20, 50, atau bahkan "All" (Semua). Ini ngatur seberapa banyak komentar yang bakal dimuat pas kalian buka jendela Video Comments. (Ngomong-ngomong, kemaren-kemaren sempet ada bug yang bikin aplikasinya crash pas kalian nyoba ngubah pengaturan ini, tapi akhirnya udah aku beresin di versi ini, jadi kalian udah bisa ngubahnya dengan aman sekarang).
- Grup Suara (Sound): Tunevia suka ngeluarin suara klik dan pop kecil pas kalian nekan tombol atau pas download selesai. Kalau kalian benci suara itu, kalian bisa matiin semua suara antarmuka (UI) di sini.
- Manajemen Tab: Kalau kalian nggak pernah pake tab Radar atau tab Stats, kalian beneran bisa ngilangin centangnya di sini biar tab-nya sembunyi sepenuhnya. Kalian juga bisa ngubah urutan tab-nya muncul di bagian atas layar.


TAB 10: BANTUAN (Ctrl + 9)
--------------------------
Ini cuma penampil teks bawaan yang ngedata semua pintasan keyboard (shortcut) dan ngasih pengingat singkat soal cara kerja fitur-fiturnya.


JENDELA DOWNLOADER (Ctrl + D)
-----------------------------
Tunevia itu bukan cuma player; dia punya mesin download yang sangat kuat di dalemnya. Kalian nggak butuh tab khusus buat ini. Cukup tekan Ctrl+D dari mana aja di dalem aplikasi, dan jendela Downloader terpisah bakal kebuka.

Bagian paling mantap dari downloader ini adalah dia nanganin antrean (queue) dan batch. Ada kotak teks raksasa di bagian atas. Kalian nggak perlu paste link satu per satu. Kalian bisa nge-copy daftar berisi dua puluh link YouTube dari file teks, paste semuanya ke dalem kotak itu sekaligus, dan klik Add.

Pas kalian nambahin link, bakal muncul jendela yang nanya kalian mau kualitas kayak gimana. Kalian bisa milih berbagai resolusi video, atau kalian bisa pilih "Audio Only" (Hanya Audio). Kalau kalian pilih Audio Only, Tunevia bakal nge-download audio mentahnya terus otomatis pake alat yang namanya FFmpeg buat ngubahnya jadi file MP3 yang bersih buat kalian.

Download-an kalian bakal berbaris di daftar antrean. Kalian bisa liat persentase progres dan statusnya (kayak "Downloading..." atau "Converting..."). Kalian punya tombol buat nge-pause seluruh antrean, ngelanjutin lagi, atau ngebatalin item. Oh ya, kalau kalian nutup Tunevia pas masih ada sisa antrean, dia bakal inget. Pas kalian buka downloader lagi nanti, antrean kalian masih ada di situ nungguin kalian.


COMMAND PALETTE (Ctrl + K)
--------------------------
Kalau kalian suka kerja cepet dan males ngelepas tangan dari keyboard buat megang mouse, kalian bakal suka banget sama fitur ini. Tekan Ctrl+K di mana aja di dalem program. Kotak pencarian kecil bakal muncul di tengah layar.

Ini adalah kolom pencarian buat ngetik perintah (aksi). Alih-alih ngobrak-ngabrik pengaturan buat nyari tombol dark mode, kalian tinggal tekan Ctrl+K, ketik kata "dark", dan tekan enter. Aplikasinya langsung berubah jadi dark mode. Kalian bisa ngetik "shuffle" buat nyalain mode acak, "down" buat buka downloader, atau "clear" buat ngehapus cache pencarian kalian. Fitur ini bener-bener ngebut banget kalau kalian udah terbiasa.


GLOBAL HOTKEYS (PINTASAN GLOBAL)
--------------------------------
Kadang kalian lagi ngetik dokumen atau main game, terus ada lagu yang kelewat kenceng, atau kalian cuma pengen nge-skip lagunya. Kalian harusnya nggak perlu alt-tab keluar dari game kalian cuma buat ganti lagu.

Gara-gara itu, Tunevia mendaftarkan Global Hotkeys ke sistem Windows. Artinya, kalian bisa ngontrol musiknya dari mana aja di komputer kalian, asalkan Tunevia lagi jalan di latar belakang.
- Alt + Shift + P: Buat Play atau Pause musiknya.
- Alt + Shift + N: Skip ke lagu Berikutnya (Next).
- Alt + Shift + B: Balik ke lagu Sebelumnya (Previous).
- Alt + Shift + Panah Atas: Naikin volume.
- Alt + Shift + Panah Bawah: Nurunin volume.
- Alt + Shift + Panah Kiri/Kanan: Mundurin atau majuin lagu yang lagi diputer.


PENAMPIL KOMENTAR VIDEO
-----------------------
Kadang bagian paling seru dari video YouTube itu ya baca komentarnya sambil dengerin audionya. Aku nambahin fitur buat ini. Pas lagu lagi diputer di tab Audio Player, kalian bisa buka jendela khusus buat liat komentar. Fitur ini ngebuang semua grafis website yang berat dan cuma ngasih kalian daftar teks bersih isinya omongan orang-orang, jumlahnya disesuaikan sama limit yang kalian atur di settings tadi.


CATATAN SOAL BUG DAN KELAKUAN ANEH
----------------------------------
Aku ngebangun aplikasi ini di waktu luangku, jadi ya nggak sempurna-sempurna amat. Ada beberapa hal yang harus kalian tau.

Kadang kalian nyoba muter video terus videonya nge-skip atau ada tulisan gagal (failed). 90 persen kasus kayak gini kejadian karena videonya dibatasi usia (Age-Restricted) sama YouTube. YouTube ngeharusin kalian login ke akun buat buktiin umur kalian buat nonton video semacam itu. Karena Tunevia nggak punya layar login, YouTube ngeblokir aplikasinya buat baca file videonya. Sebenernya ada jalan pintas buat ngakalin ini pake file "cookies.txt" dari browser kalian, yang bisa dimasukin lewat tab Settings, tapi prosesnya agak teknis.

Terus, inget kan sama omonganku soal tab Lirik tadi. Kalau dia mulai ngasih hasil yang gila dan nggak nyambung, langsung aja matiin fitur auto-fetch-nya.


KONTAK DAN OPEN SOURCE
----------------------
Tunevia ini sepenuhnya open source (sumber terbuka). Aku nggak nyari duit dari sini; aku cuma pengen bikin alat yang bikin dengerin musik jadi lebih gampang buat semua orang, terutama buat temen-temen kayak aku yang butuh screen reader buat navigasi PC mereka. Kalau kalian ngerti cara ngoding pake Python dan pengen liat gimana aku bikin integrasi VLC atau nyambungin mesin suara NVDA-nya, silakan aja liat kodenya. Kalian bebas ngemodifikasi, ngeberesin kesalahan-kesalahanku, atau nambahin fitur buatan kalian sendiri.

Kalau kalian nemu bug yang bikin programnya rusak, atau kalau kalian punya ide fitur yang keren banget yang belum kepikiran sama aku, tolong banget hubungi aku. Aku selalu berusaha bikin aplikasi ini jadi lebih baik.

Kalian bisa email aku di: hafiyanajah@gmail.com
Atau kalian bisa nemuin aku di GitHub di: muhamadalfian20892

Makasih banyak udah mau nyobain Tunevia. Aku harap kalian bisa nikmatin dengerin musik pake aplikasi ini sama kayak aku nikmatin proses bikinnya.

- Muhammad Alfian (Technokers Lab)