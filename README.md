# Piring Indonesia: Pola Konsumsi Pangan 514 Kabupaten/Kota

UAS Visualisasi Data dan Informasi 2025/2026, Politeknik Statistika STIS.

- **Situs:** https://USERNAME.github.io/NAMA-REPO/   <!-- ISI -->
- **Repositori:** https://github.com/USERNAME/NAMA-REPO   <!-- ISI -->

## Topik visualisasi
| Topik | Teknik | Halaman |
|---|---|---|
| (a) Multivariat | PCA, k-means, parallel coordinates, heatmap profil klaster, brushing-linking | `multivariat.qmd` |
| (e) Geospasial | Choropleth kuantil 5 kelas + simbol proporsional, tooltip, zoom/pan, layer batas provinsi | `peta.qmd` |
| (c) Hierarki | Treemap (breadcrumb) + sunburst, Indonesia > Pulau > Provinsi > Kab/kota | `hierarki.qmd` |

## Data
Sumber utama: 8 tabel BPS *Rata-rata Konsumsi Perkapita Seminggu menurut Kelompok … per Kabupaten/kota 2024* (514 kab/kota, 142 komoditas). Rincian di [`data/SUMBER_DATA.csv`](data/SUMBER_DATA.csv); kamus komoditas di [`docs/kamus_data.csv`](docs/kamus_data.csv).
Data tambahan: batas wilayah kab/kota (shapefile, non-BPS; periode 2019, lihat `data/geo/README_GEO.md`) serta tabel BPS *Jumlah Penduduk menurut Kabupaten/Kota dan Kelompok Umur 2024* (untuk ukuran blok hierarki).

## Struktur
```
config.yaml            pengaturan: variabel multivariat, jumlah klaster, jalur file
data/raw/              9 xlsx BPS (8 konsumsi + 1 penduduk) + penduduk_kabkota_2024.csv (hasil olahan)
data/geo/              Administrasi_Kabupaten.shp (+dbf, prj, cpg) + alias_nama.csv + README_GEO.md
data/processed/        hasil olahan (di-commit; dipakai saat deploy)
scripts/01_parse_konsumsi.py   xlsx -> csv rapi (long, wide, multivariat)
scripts/02_prepare_geo.py      cocokkan GeoJSON dengan nama BPS, sederhanakan geometri
src/viz.py             semua fungsi visualisasi
*.qmd                  halaman situs (Quarto)
```

## Cara menjalankan
```bash
pip install -r requirements.txt
python scripts/01_parse_konsumsi.py     # sudah dijalankan; hasil ada di data/processed/
python scripts/02_prepare_geo.py        # shapefile di data/geo/ -> GeoJSON; harus melapor "Cocok: 514/514"
python scripts/03_prepare_penduduk.py   # xlsx penduduk -> data/raw/penduduk_kabkota_2024.csv (validasi total nasional)
quarto preview                          # lihat lokal
git add . && git commit && git push     # deploy otomatis ke GitHub Pages (Settings > Pages > gh-pages)
```

## Catatan metodologis
- Sel "-" pada tabel BPS dianggap 0 dan ditandai (`strip`); 8,7% dari seluruh sel.
- Satuan tiap komoditas berbeda (satuan komoditas BPS), sehingga analisis memakai z-score dan tidak menjumlahkan komoditas.
- Tabel penduduk memuat 26 kab/kota Papua dua kali (provinsi lama dan baru, nilai identik); duplikat dibuang dan jumlah akhir sama dengan total nasional (281.603.799).
- 38 provinsi (struktur 2024) dipakai; pemetaan kab/kota ke provinsi berdasarkan urutan baris sumber dan sudah diverifikasi.

## Deklarasi alat bantu AI
ISI (tulis juga di bagian Metodologi makalah).

## Lisensi dan atribusi
Data konsumsi: BPS. Batas wilayah: shapefile administrasi kabupaten/kota (atribut sumber: BPS, periode 2019); ISI sumber asli.
