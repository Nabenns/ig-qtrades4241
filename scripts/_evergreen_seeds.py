"""Curated evergreen post seeds. Used by scripts/seed_evergreen.py.

Each entry must validate against ig_qt.analyst.schemas.AngleDraft:
- post_type: "feed"
- topic_tag: lowercase_snake_case
- caption_draft: 80-2200 chars
- visual_spec.type: "headline"
- visual_spec.headline: required
- disclaimer_required: True
- confidence: 0.7
"""
from __future__ import annotations

from typing import Any

EVERGREEN_SEEDS: list[dict[str, Any]] = []


# 1. Risk management — 2% rule
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "risk_2_percent_rule",
    "angle": "Aturan 2% per trade: kunci akun forex tahan losing streak panjang.",
    "key_points": [
        "Risk per trade max 2% dari equity",
        "Stop loss wajib di-set sebelum entry, bukan setelah floating loss",
        "Position sizing dihitung dari jarak SL ke entry, bukan feeling",
        "10 loss berturut hanya kurangin akun sekitar 18%, bukan 100%",
    ],
    "caption_draft": (
        "Risk management itu bukan sekadar 'pake stop loss'. "
        "Ini soal seberapa besar kamu siap rugi DI SETIAP TRADE.\n\n"
        "Aturan 2% sederhananya: dalam satu trade, kamu cuma boleh rugi maksimal "
        "2% dari total equity akun. Akun $1000? Risk per trade max $20. Akun $10K? "
        "Max $200. Titik.\n\n"
        "Kenapa 2%? Karena math-nya bersahabat sama psikologi:\n"
        "- 5 loss berturut → akun turun 9.6%, masih recoverable\n"
        "- 10 loss berturut → akun turun 18.3%, masih bisa balik\n"
        "- 20 loss berturut → akun turun 33%, butuh effort tapi masih hidup\n\n"
        "Bandingkan kalo risk 10% per trade:\n"
        "- 10 loss berturut → akun habis 65%. Butuh untung 186% buat balik modal. "
        "Mustahil tanpa luck.\n\n"
        "Cara hitung position size:\n"
        "1. Tentuin entry price\n"
        "2. Tentuin stop loss berdasarkan struktur (bukan jumlah dollar)\n"
        "3. Hitung jarak entry ke SL dalam pips\n"
        "4. Position size = (2% equity) / (jarak SL × value per pip)\n\n"
        "Trader pemula sering salah: mereka tentuin lot dulu, baru cari SL yang 'pas'. "
        "Itu kebalik. Yang bener: SL ditentuin struktur market, lot menyesuaikan risk.\n\n"
        "Konsisten 2% bikin loss feel manageable. Kamu gak akan tilt. Gak akan revenge trade. "
        "Akun bertahan cukup lama buat edge kamu kerja.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Aturan 2% per Trade",
        "subheadline": "Kunci akun forex tahan banting",
        "highlight_phrase": "2%",
        "highlight_color": "teal",
        "hero_image_prompt": (
            "minimalist financial dashboard with glowing teal percentage gauge in foreground, "
            "dark navy background, cinematic depth of field, professional finance aesthetic, "
            "soft volumetric lighting"
        ),
    },
    "dynamic_hashtags": ["#riskmanagement", "#forexedukasi", "#tradingdisiplin"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 2. Trading psychology — FOMO
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "psychology_fomo_trap",
    "angle": "FOMO bikin entry telat di top atau bottom: ini cara breaknya.",
    "key_points": [
        "FOMO = takut ketinggalan move yang udah jalan",
        "Entry FOMO biasanya di puncak gerakan, R:R buruk",
        "Solusi: tunggu pullback, jangan kejar candle",
        "Missed trade lebih murah daripada bad trade",
    ],
    "caption_draft": (
        "Pernah liat EUR/USD lari 80 pips, terus kamu jump in karena takut "
        "ketinggalan? Selamat datang di FOMO trade.\n\n"
        "FOMO (Fear Of Missing Out) itu emosi paling mahal di trading. Bukan greed, "
        "bukan fear of loss. FOMO yang bener-bener menggerogoti akun.\n\n"
        "Ciri FOMO trade:\n"
        "- Entry setelah candle besar udah jadi\n"
        "- Stop loss dipaksa lebar karena 'biar aman'\n"
        "- Risk:reward jadi 1:1 atau lebih buruk\n"
        "- Begitu posisi minus 10 pips, kamu udah panik\n\n"
        "Logikanya simpel: kalau move udah jalan 80 pips, peluang lanjut 80 pips lagi "
        "lebih kecil daripada peluang pullback 30 pips. Kamu masuk di area paling buruk.\n\n"
        "Cara break FOMO:\n"
        "1. Trading plan di-set SEBELUM market buka. Level entry, SL, TP udah ditulis.\n"
        "2. Kalau price udah lewat level entry kamu jauh, trade itu invalid. Skip.\n"
        "3. Tunggu pullback ke area entry yang valid. Kalau gak balik, ya gak masuk.\n"
        "4. Reframe: missed trade itu GRATIS. Bad trade itu mahal.\n\n"
        "Inget: market akan kasih setup baru besok, lusa, minggu depan. Forex 24/5. "
        "Gak ada urgency. Yang ada cuma disiplin.\n\n"
        "Trader pro skip 80% setup yang mereka liat. Mereka cuma masuk di setup A+. "
        "Pemula masuk di semua yang 'kayaknya bisa'.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "FOMO Itu Mahal",
        "subheadline": "Skip setup buruk lebih murah daripada bad trade",
        "highlight_phrase": "FOMO",
        "highlight_color": "red",
        "hero_image_prompt": (
            "lone figure standing at edge of cliff watching a fast-moving train pass below, "
            "dramatic golden hour lighting, cinematic composition, sense of missed opportunity "
            "and patience, photorealistic, shallow depth of field"
        ),
    },
    "dynamic_hashtags": ["#tradingpsychology", "#forexpsychology", "#disiplintrading"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 3. Macro — CPI explainer
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "macro_cpi_explainer",
    "angle": "CPI bukan cuma angka inflasi: ini cara baca dampaknya ke USD.",
    "key_points": [
        "CPI = Consumer Price Index, ukur perubahan harga barang+jasa",
        "Headline CPI all items, Core CPI exclude food+energy",
        "Surprise CPI (actual vs forecast) lebih penting dari nilai absolut",
        "Higher CPI → ekspektasi rate hike → USD biasa menguat",
    ],
    "caption_draft": (
        "Setiap bulan trader nungguin satu data ini: CPI. Tapi banyak yang cuma liat "
        "angka, gak tau cara baca dampaknya ke pair forex.\n\n"
        "CPI (Consumer Price Index) ngukur perubahan harga sekeranjang barang dan jasa "
        "yang dibeli rumah tangga. Sederhananya: ini gauge inflasi.\n\n"
        "Ada dua versi yang penting:\n"
        "- Headline CPI: all items, termasuk makanan + energi\n"
        "- Core CPI: exclude makanan + energi (lebih stabil, sering jadi acuan Fed)\n\n"
        "Tiga angka yang dirilis setiap data:\n"
        "1. Actual: angka sebenarnya\n"
        "2. Forecast: ekspektasi konsensus analis\n"
        "3. Previous: data bulan sebelumnya\n\n"
        "Yang gerakin pasar bukan angka absolut, tapi SURPRISE — selisih actual vs "
        "forecast. Forecast 3.2%, actual 3.5% = bullish USD (hawkish surprise). "
        "Forecast 3.2%, actual 2.9% = bearish USD (dovish surprise).\n\n"
        "Logikanya:\n"
        "- CPI tinggi → inflasi panas → Fed kemungkinan naikin suku bunga\n"
        "- Suku bunga naik → yield US naik → USD lebih menarik → USD strengthens\n"
        "- Kebalikannya buat CPI rendah\n\n"
        "Tapi ingat: market sering pricing in expectation. Kalau forecast udah hawkish "
        "dan actual sesuai, gerakan bisa kecil bahkan kebalik (sell the news).\n\n"
        "Pair yang paling sensitif: EUR/USD, USD/JPY, GBP/USD, XAU/USD. Spread bisa "
        "melebar 10-20x normal di detik-detik release.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Cara Baca CPI",
        "subheadline": "Surprise lebih penting dari angka absolut",
        "highlight_phrase": "CPI",
        "highlight_color": "amber",
        "hero_image_prompt": (
            "abstract financial data visualization with amber gauge meter and "
            "rising bar charts, dark blue gradient background, cinematic lighting, "
            "professional macro economics theme, "
            "subtle paper texture, depth of field"
        ),
    },
    "dynamic_hashtags": ["#cpi", "#forexmacro", "#inflasi"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 4. Macro — NFP explainer
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "macro_nfp_explainer",
    "angle": "NFP first Friday: kenapa data ini gerakin USD lebih dari yang lain.",
    "key_points": [
        "NFP = Non-Farm Payrolls, jumlah lapangan kerja baru di AS (exclude pertanian)",
        "Rilis Jumat pertama setiap bulan, jam 19:30 WIB",
        "3 komponen: NFP, Unemployment Rate, Average Hourly Earnings",
        "AHE sering lebih moving daripada NFP itu sendiri (proxy inflation)",
    ],
    "caption_draft": (
        "Kalau kamu trader USD, satu hari dalam sebulan harus dilingkarin: "
        "Jumat pertama. Itu hari NFP.\n\n"
        "NFP (Non-Farm Payrolls) ngukur perubahan jumlah orang yang kerja di AS, "
        "exclude sektor pertanian (karena seasonal). Angka ini gauge utama kesehatan "
        "ekonomi AS, dan Fed pakai ini buat keputusan moneter.\n\n"
        "Yang dirilis sekaligus 3 angka:\n"
        "1. NFP change: berapa job baru bulan itu (forecast biasa 150-300K)\n"
        "2. Unemployment Rate: % angkatan kerja yang nganggur\n"
        "3. Average Hourly Earnings (AHE): perubahan upah per jam\n\n"
        "Banyak trader fokus di NFP angka, padahal AHE seringkali lebih bergerak. "
        "Kenapa? Karena AHE = wage inflation = inflation pressure. Fed sangat "
        "memperhatikan ini.\n\n"
        "Cara baca dampak ke USD (umumnya):\n"
        "- NFP > forecast + AHE > forecast → strong USD (hawkish)\n"
        "- NFP < forecast + AHE < forecast → weak USD (dovish)\n"
        "- Mixed (NFP beat tapi AHE miss) → reaksi tidak konsisten, sering whipsaw\n\n"
        "Volatilitas saat rilis BRUTAL. Spread bisa melebar 50-100x normal di detik "
        "pertama. Stop loss bisa kena slippage parah. Banyak trader profesional "
        "TIDAK trading 5 menit sebelum sampai 30 menit setelah rilis.\n\n"
        "Setelah dust settle (1-2 jam), baru muncul trend yang lebih clean. Disitu "
        "biasanya peluang lebih bagus daripada gambling di detik release.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Memahami NFP",
        "subheadline": "Jumat pertama, hari paling volatile bagi USD",
        "highlight_phrase": "NFP",
        "highlight_color": "teal",
        "hero_image_prompt": (
            "stylized US Capitol building silhouette with floating data points and labor charts, "
            "deep blue and teal gradient sky, cinematic atmospheric lighting, "
            "professional macro finance theme, subtle volumetric fog"
        ),
    },
    "dynamic_hashtags": ["#nfp", "#forexnews", "#usdtrading"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 5. Risk:Reward ratio
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "rrr_risk_reward_ratio",
    "angle": "Win rate 40% bisa profitable kalau RRR-nya bener. Ini math-nya.",
    "key_points": [
        "RRR = Risk:Reward, perbandingan jarak SL ke jarak TP",
        "Min RRR 1:2 bikin kamu profitable di win rate 40%",
        "Tinggi RRR sering = win rate rendah, dan sebaliknya",
        "Yang dihitung: expectancy, bukan win rate doang",
    ],
    "caption_draft": (
        "Banyak trader pemula obsesi sama win rate. 'Strategy gua 80% akurat!' "
        "Tapi akun tetep minus. Kenapa? Karena RRR-nya 1:0.3.\n\n"
        "RRR (Risk:Reward Ratio) itu perbandingan antara berapa banyak kamu rugi kalau "
        "kena SL vs berapa banyak untung kalau kena TP. RRR 1:2 artinya: risk $100 "
        "untuk potensi profit $200.\n\n"
        "Math-nya:\n"
        "Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)\n\n"
        "Skenario A — Win rate 70%, RRR 1:0.5:\n"
        "(0.7 × 50) - (0.3 × 100) = 35 - 30 = +5 per trade. Tipis.\n\n"
        "Skenario B — Win rate 40%, RRR 1:2:\n"
        "(0.4 × 200) - (0.6 × 100) = 80 - 60 = +20 per trade. 4x lebih baik.\n\n"
        "Skenario C — Win rate 30%, RRR 1:3:\n"
        "(0.3 × 300) - (0.7 × 100) = 90 - 70 = +20 per trade. Sama dengan B, "
        "tapi mental harus lebih kuat (banyak loss berturut).\n\n"
        "Lesson: kombinasi win rate + RRR yang menentukan, bukan salah satunya.\n\n"
        "Cara naikin RRR:\n"
        "1. SL lebih ketat (di luar struktur, bukan asal kecil)\n"
        "2. TP lebih jauh (next major resistance/support)\n"
        "3. Skip trade yang RRR-nya < 1:1.5\n"
        "4. Trail stop saat profit, biar reward bisa stretching\n\n"
        "Trader pro biasanya operate di RRR 1:2 sampai 1:3 dengan win rate 40-50%. "
        "Itu sweet spot. Bukan 80% accuracy yang dijual signal-signal di telegram.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "RRR Mengalahkan Win Rate",
        "subheadline": "Math sederhana yang dilewatkan trader pemula",
        "highlight_phrase": "RRR",
        "highlight_color": "teal",
        "hero_image_prompt": (
            "minimalist scale balance with golden coins on one side and a small dial on the other, "
            "dark studio background, cinematic rim lighting, professional finance aesthetic, "
            "shallow depth of field, subtle dust particles in light"
        ),
    },
    "dynamic_hashtags": ["#riskreward", "#forexstrategy", "#tradingmath"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 6. Macro — central bank role
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "macro_central_bank_role",
    "angle": "Fed, ECB, BoJ: kenapa keputusan mereka gerakin pair forex secara permanen.",
    "key_points": [
        "Central bank kontrol suku bunga + money supply negara mereka",
        "Hawkish = arah pengetatan (rate naik), Dovish = pelonggaran (rate turun)",
        "Interest rate differential drive long-term forex trends",
        "Forward guidance lebih moving daripada keputusan rate itu sendiri",
    ],
    "caption_draft": (
        "Kalau kamu trading forex tanpa ngerti central bank, kamu trading buta. "
        "Bank sentral itu yang nentuin arah jangka panjang setiap mata uang.\n\n"
        "Tugas utama central bank:\n"
        "1. Stabilitas harga (target inflasi, biasa 2%)\n"
        "2. Maximum employment (untuk Fed)\n"
        "3. Kestabilan sistem keuangan\n\n"
        "Tools mereka:\n"
        "- Interest rate (paling utama)\n"
        "- Quantitative Easing/Tightening\n"
        "- Forward guidance (komunikasi ke pasar)\n"
        "- Reserve requirement\n\n"
        "Big six central banks dan currency mereka:\n"
        "- Fed (Federal Reserve) → USD\n"
        "- ECB (European Central Bank) → EUR\n"
        "- BoE (Bank of England) → GBP\n"
        "- BoJ (Bank of Japan) → JPY\n"
        "- SNB (Swiss National Bank) → CHF\n"
        "- RBA, RBNZ, BoC → AUD, NZD, CAD\n\n"
        "Stance bank sentral:\n"
        "- HAWKISH: arah ke pengetatan, rate kemungkinan naik. Currency cenderung kuat.\n"
        "- DOVISH: arah ke pelonggaran, rate kemungkinan turun. Currency cenderung lemah.\n"
        "- NEUTRAL: tidak ada bias ke arah manapun. Currency bergerak di range.\n\n"
        "Konsep penting: INTEREST RATE DIFFERENTIAL. Kalau Fed naikin rate ke 5% sementara "
        "ECB tetap di 2%, ada incentive 3% buat hold USD. Modal mengalir ke USD. "
        "EUR/USD jatuh dalam jangka menengah.\n\n"
        "Yang lebih moving daripada rate decision sendiri? FORWARD GUIDANCE — "
        "panduan untuk meeting selanjutnya. Pasar pricing in expectation 6-12 bulan ke "
        "depan. Ketika forward guidance berubah, repricing bisa massive.\n\n"
        "Kalender wajib dicatat: FOMC (Fed) 8x/tahun, ECB 8x/tahun, BoJ 8x/tahun.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Kenapa Bank Sentral Penting",
        "subheadline": "Yang nentuin arah jangka panjang setiap mata uang",
        "highlight_phrase": "Bank Sentral",
        "highlight_color": "amber",
        "hero_image_prompt": (
            "neoclassical central bank building facade with dramatic side lighting, "
            "golden hour ambiance, marble columns, cinematic depth of field, "
            "professional architectural photography, subtle atmospheric haze"
        ),
    },
    "dynamic_hashtags": ["#centralbank", "#fedinterestrate", "#forexmacro"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 7. Chart pattern — support & resistance
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "chart_support_resistance",
    "angle": "Support resistance bukan garis sakti: ini cara pakainya yang bener.",
    "key_points": [
        "Support = area di mana buyer dominan, resistance = seller dominan",
        "Bukan garis tipis, tapi ZONA (range 5-15 pips)",
        "Old resistance jadi new support saat broken (role reversal)",
        "Lebih reliable di higher timeframe (H4, Daily)",
    ],
    "caption_draft": (
        "Support resistance itu konsep paling tua di trading, dan paling sering "
        "disalahgunakan. Banyak trader gambar 50 garis di chart, kemudian bingung "
        "kenapa price gak respect satu pun.\n\n"
        "Definisi sederhana:\n"
        "- SUPPORT: level/zona di mana buyer historically muncul, harga cenderung "
        "berhenti turun.\n"
        "- RESISTANCE: level/zona di mana seller historically muncul, harga cenderung "
        "berhenti naik.\n\n"
        "Kunci yang sering miss: bukan garis tipis, tapi ZONA. Karena institutional "
        "order gak masuk di harga persis 1.0850. Mereka split di 1.0845-1.0855. "
        "Gambar zona, bukan line.\n\n"
        "Cara identifikasi yang valid:\n"
        "1. Cari swing high/low yang TESTED MINIMAL 2X di higher timeframe\n"
        "2. Lebih bagus kalau ada confluence (round number, fibonacci, MA)\n"
        "3. Lebih reliable di Daily > H4 > H1 > M15 > M5\n"
        "4. Recent levels lebih relevan daripada level dari setahun lalu\n\n"
        "Konsep penting — ROLE REVERSAL:\n"
        "Saat resistance ditembus dengan strong momentum (closing candle di atasnya, "
        "bukan wick doang), level itu sering BERUBAH JADI SUPPORT. Pullback ke level "
        "tersebut sering jadi entry yang nice.\n\n"
        "Hal yang sering bikin pemula salah baca:\n"
        "- Liat chart H1 doang, gambar S/R di setiap touch. Hasilnya 20 garis, semua "
        "weak.\n"
        "- Anggap S/R sebagai 'pasti bounce'. Padahal level cuma area probability tinggi, "
        "bukan jaminan.\n"
        "- Lupa stop loss. S/R bisa false break, kamu butuh exit plan kalau salah.\n\n"
        "Pro tip: gambar S/R dari Daily timeframe DULU. Baru zoom in ke H4/H1 untuk "
        "execution. Top-down approach selalu lebih reliable.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Support & Resistance",
        "subheadline": "Zona, bukan garis tipis",
        "highlight_phrase": "Zona",
        "highlight_color": "teal",
        "hero_image_prompt": (
            "abstract minimalist horizontal line composition with glowing teal bands, "
            "dark gradient background, soft light leaks, cinematic financial aesthetic, "
            "subtle grid texture, professional trading visualization"
        ),
    },
    "dynamic_hashtags": ["#supportresistance", "#technicalanalysis", "#chartpattern"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 8. Leverage demystified
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "leverage_demystified",
    "angle": "Leverage 1:500 bukan kekuatan, itu pisau bermata dua. Ini cara amannya.",
    "key_points": [
        "Leverage cuma menentukan margin requirement, bukan risk",
        "Risk ditentukan oleh position size + stop loss",
        "Akun kecil + leverage tinggi = blow up cepat kalau gak disiplin",
        "Effective leverage yang aman: < 5:1 dari equity, bukan dari max broker",
    ],
    "caption_draft": (
        "Banyak broker promosi 1:500, 1:1000, bahkan 1:2000 leverage. Kayaknya "
        "wow ya, modal $100 bisa kontrol $200K position. Padahal itu tali gantungan.\n\n"
        "Leverage SEBENARNYA bukan multiplier untung. Itu cuma menentukan berapa "
        "MARGIN yang dikunci buat buka posisi. Risk sebenarnya ditentukan oleh "
        "position size dan stop loss, bukan leverage broker.\n\n"
        "Contoh:\n"
        "- Akun $1000, leverage 1:500\n"
        "- Buka 1 lot EUR/USD (100K units)\n"
        "- Margin yang dikunci: $200 (cuma 20% akun)\n"
        "- Tapi setiap pip = $10\n"
        "- SL 50 pips = risk $500 = 50% akun!\n\n"
        "Itu bukan leverage yang bahaya, tapi POSITION SIZE yang gak masuk akal "
        "buat ukuran akun kamu.\n\n"
        "Konsep yang lebih penting: EFFECTIVE LEVERAGE.\n"
        "Effective Leverage = Total Position Value / Account Equity\n\n"
        "Akun $10K, posisi total $50K → effective 5:1\n"
        "Akun $10K, posisi total $200K → effective 20:1 (bahaya)\n"
        "Akun $10K, posisi total $500K → effective 50:1 (suicide)\n\n"
        "Trader profesional biasanya operate di effective leverage 1:1 sampai 5:1, "
        "BUKAN max leverage broker.\n\n"
        "Kapan leverage tinggi berguna? Cuma satu skenario: ketika kamu punya akun "
        "besar tapi mau alokasikan modal kecil per pair (multi-pair strategy). "
        "Untuk pemula, leverage 1:30 - 1:100 udah lebih dari cukup.\n\n"
        "Inget: regulator di EU, US, Australia batasin retail leverage ke 1:30 untuk "
        "alasan. Mereka tau angka yang lebih besar bukan bantuan, itu jebakan.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Leverage Itu Pisau",
        "subheadline": "Bermata dua, bukan multiplier untung",
        "highlight_phrase": "Pisau",
        "highlight_color": "red",
        "hero_image_prompt": (
            "stylized double-edged blade reflecting neon red and teal light, "
            "dark velvet background, dramatic chiaroscuro lighting, cinematic close-up, "
            "professional product photography style, shallow depth of field"
        ),
    },
    "dynamic_hashtags": ["#leverage", "#forexedukasi", "#riskmanagement"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 9. Trading journal
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "trading_journal_habit",
    "angle": "Trader profitable selalu nge-journal. Ini template minimal yang efektif.",
    "key_points": [
        "Journal bikin pattern visible: yang bekerja vs yang gak",
        "Catat: setup, entry reason, emotion, hasil, lesson",
        "Review mingguan lebih penting daripada catatan harian doang",
        "Track metric: win rate, avg RRR, expectancy per setup",
    ],
    "caption_draft": (
        "Pertanyaan jujur: kalau gua tanya kamu, dari 50 trade terakhir, mana yang "
        "paling profitable secara setup? Bisa jawab? Kalau enggak, kamu butuh journal.\n\n"
        "Trading journal itu yang membedakan trader random dengan trader sistematis. "
        "Tanpa journal, kamu gak bisa ningkatin sesuatu yang gak diukur.\n\n"
        "Template minimal (bisa di Excel/Notion/aplikasi khusus):\n"
        "1. Tanggal + waktu entry\n"
        "2. Pair + arah (BUY/SELL)\n"
        "3. Setup type (breakout, pullback, reversal, dll)\n"
        "4. Entry, SL, TP price\n"
        "5. Position size + risk amount\n"
        "6. Reason in 1-2 sentences (kenapa entry)\n"
        "7. Emotion saat entry (fear, FOMO, confident, neutral)\n"
        "8. Screenshot chart\n"
        "9. Hasil (pips + dollar)\n"
        "10. Lesson learned\n\n"
        "Yang banyak miss: ITEM 7 (emotion) dan ITEM 10 (lesson). Itu yang paling "
        "valuable jangka panjang.\n\n"
        "Review mingguan (LEBIH penting daripada nyatat doang):\n"
        "- Setup mana yang win rate-nya tinggi?\n"
        "- Setup mana yang sering loss tapi tetap diambil?\n"
        "- Jam berapa trading kamu paling profitable?\n"
        "- Pair mana yang kamu master, mana yang sebaiknya skip?\n"
        "- Emotional state apa yang correlate dengan loss?\n\n"
        "Metric yang harus tracking:\n"
        "- Win rate per setup type\n"
        "- Average R:R per setup type\n"
        "- Expectancy per setup type (formula di post sebelumnya)\n"
        "- Best vs worst trade per minggu\n\n"
        "Setelah 50-100 trade, pattern akan keliatan. Kamu bisa cut setup yang weak, "
        "double down di yang strong. Itu evolusi dari gambling ke business.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Kenapa Journal Wajib",
        "subheadline": "Yang membedakan trader sistematis dari random",
        "highlight_phrase": "Journal",
        "highlight_color": "teal",
        "hero_image_prompt": (
            "elegant leather journal open on a dark wooden desk, vintage fountain pen beside it, "
            "soft warm desk lamp lighting, cinematic atmosphere, financial charts subtly visible "
            "in background bokeh, professional editorial photography"
        ),
    },
    "dynamic_hashtags": ["#tradingjournal", "#tradingdisiplin", "#forexpro"],
    "disclaimer_required": True,
    "confidence": 0.7,
})


# 10. Multi-timeframe analysis
EVERGREEN_SEEDS.append({
    "post_type": "feed",
    "topic_tag": "multi_timeframe_analysis",
    "angle": "Top-down analysis: kenapa trader pro selalu mulai dari Daily, bukan M5.",
    "key_points": [
        "Daily/H4 = trend direction, H1/M15 = entry timing",
        "Trade dengan trend higher TF, against trend = countertrend (lebih risky)",
        "M5/M1 cuma buat fine-tuning entry, bukan basis decision",
        "Konfluensi multi-TF level = setup A+",
    ],
    "caption_draft": (
        "Trader pemula buka chart dan langsung zoom ke M5 atau M1. Liat candle naik "
        "2 candle, langsung BUY. Itu bukan trading, itu reaksi.\n\n"
        "Trader pro selalu pakai TOP-DOWN ANALYSIS — analyze dari timeframe besar dulu, "
        "baru turun ke timeframe execution.\n\n"
        "Hierarki yang biasa dipakai:\n"
        "- DAILY (D1): Major trend direction. Bullish, bearish, atau ranging?\n"
        "- H4: Confirmation. Apakah aligned dengan Daily? S/R level utama.\n"
        "- H1: Entry context. Cari area entry yang valid (pullback, breakout retest).\n"
        "- M15/M5: Fine-tuning. Trigger entry (candlestick pattern, momentum shift).\n\n"
        "Kunci utama: TRADE SEARAH HIGHER TIMEFRAME.\n\n"
        "Kalau Daily bullish, prioritaskan BUY setup di H1/M15. Sell setup di lower "
        "TF saat Daily bullish itu countertrend — bisa profit, tapi probability lebih "
        "rendah dan butuh skill yang lebih tinggi.\n\n"
        "Konsep KONFLUENSI:\n"
        "Setup terbaik adalah ketika multiple timeframe SETUJU di area yang sama.\n"
        "- Daily: bullish trend, harga di support major\n"
        "- H4: pullback ke 50% fibonacci\n"
        "- H1: bullish engulfing di support\n"
        "- M15: momentum shift, RSI bouncing dari oversold\n"
        "Itu setup A+ yang patut diambil.\n\n"
        "Common mistakes:\n"
        "1. Cuma liat M5 doang. Kamu trading dalam noise tanpa konteks.\n"
        "2. Higher TF sell, tapi BUY di M5 cuma karena 'kelihatan kuat'. Countertrend "
        "tanpa sadar.\n"
        "3. Force konfluensi yang gak ada. Kalau Daily ranging, jangan paksa narrative "
        "trending.\n\n"
        "Pro routine harian:\n"
        "1. Pagi: cek Daily semua pair watchlist (5 menit)\n"
        "2. Tentuin bias hari ini: bullish/bearish/skip per pair\n"
        "3. Tunggu price reach area entry valid di H1\n"
        "4. Trigger di M15/M5 sesuai bias\n\n"
        "Disiplin top-down kamu akan filter 70% trade buruk yang tadinya kamu ambil.\n\n"
        "Edukasi semata, bukan saran trading."
    ),
    "visual_spec": {
        "type": "headline",
        "headline": "Top-Down Analysis",
        "subheadline": "Mulai dari Daily, bukan M5",
        "highlight_phrase": "Top-Down",
        "highlight_color": "teal",
        "hero_image_prompt": (
            "stacked layers of glass panels each showing different scale of city map from above, "
            "cinematic side lighting with teal accents, dark environment, "
            "professional architectural visualization, depth and hierarchy"
        ),
    },
    "dynamic_hashtags": ["#multitimeframe", "#technicalanalysis", "#forexstrategy"],
    "disclaimer_required": True,
    "confidence": 0.7,
})
