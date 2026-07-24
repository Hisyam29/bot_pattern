import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import os

# =========================
# CONFIG
# =========================
TOKEN = "8265694791:AAHElCfxfPoB40pZe5yv9tvVcQEIFIAQUAw"
CHAT_IDS = [
    "1280847575",  # kamu
]

INTERVAL = "4h"
PERIOD = "60d"

ATR_PERIOD = 2
MULTIPLIER = 1


MIN_VALUE = 2_000_000_000  # 2 Miliar (sesuai template terakhirmu)

# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    for chat_id in CHAT_IDS:
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"  # Ditambahkan agar teks format tebal/emoji rapi
        }
        try:
            res = requests.post(url, data=data)
            print(f"Telegram ke {chat_id}:", res.text)
        except:
            print(f"Gagal kirim ke {chat_id}")

# =========================
# LOAD SAHAM DARI EXCEL
# =========================
def load_symbols():
    df = pd.read_excel(r"C:\Users\Hisyam\OneDrive\Documents\Coding\saham.xlsx")

    print("KOLOM TERDETEKSI:", df.columns)

    # ambil kolom "Kode"
    symbols = df["Kode"].tolist()

    # bersihkan
    symbols = [str(s).strip().upper() for s in symbols if str(s) != 'nan']

    # tambah .JK
    symbols = [s + ".JK" for s in symbols]

    print("TOTAL SAHAM:", len(symbols))
    print(symbols[:10])

    return symbols

# =========================
# GET DATA
# =========================
def get_data(symbol):
    df = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)
    return df

# =========================
# SUPER TREND (2,1)
# =========================
def compute_supertrend(df):
    df = df.copy()

    df['H-L'] = df['High'] - df['Low']
    df['H-C'] = (df['High'] - df['Close'].shift()).abs()
    df['L-C'] = (df['Low'] - df['Close'].shift()).abs()

    df['TR'] = df[['H-L','H-C','L-C']].max(axis=1)
    df['ATR'] = df['TR'].rolling(ATR_PERIOD).mean()

    hl2 = (df['High'] + df['Low']) / 2

    df['upperband'] = hl2 + MULTIPLIER * df['ATR']
    df['lowerband'] = hl2 - MULTIPLIER * df['ATR']

    df['in_uptrend'] = True

    for i in range(1, len(df)):
        if df['Close'].iloc[i] > df['upperband'].iloc[i-1]:
            df.loc[df.index[i], 'in_uptrend'] = True
        elif df['Close'].iloc[i] < df['lowerband'].iloc[i-1]:
            df.loc[df.index[i], 'in_uptrend'] = False
        else:
            df.loc[df.index[i], 'in_uptrend'] = df['in_uptrend'].iloc[i-1]

    return df

# ==============================================================================
# PATTERN RECOGNITION ENGINE (3 CANDLESTICK + 3 CONTINUATION PATTERNS)
# ==============================================================================
def detect_patterns(df):
    if len(df) < 20:
        return False, "None"

    # Koordinat Candlestick
    open_0 = df['Open'].iloc[-1]   # Hari ini
    high_0 = df['High'].iloc[-1]
    low_0 = df['Low'].iloc[-1]
    close_0 = df['Close'].iloc[-1]
    
    open_1 = df['Open'].iloc[-2]   # Kemarin
    close_1 = df['Close'].iloc[-2]
    
    open_2 = df['Open'].iloc[-3]   # Kemarin Lusa
    close_2 = df['Close'].iloc[-3]
    
    body_0 = abs(close_0 - open_0) 
    body_1 = abs(close_1 - open_1) 
    body_2 = abs(close_2 - open_2) 
    
    lower_shadow_0 = min(open_0, close_0) - low_0
    upper_shadow_0 = high_0 - max(open_0, close_0)

    # --------------------------------------------------------------------------
    # A. 3 POLA CANDLESTICK BULLISH
    # --------------------------------------------------------------------------
    # 1. Morning Star (Pola 3-Candle)
    is_candle2_merah = close_2 < open_2
    is_candle0_hijau = close_0 > open_0
    titik_tengah_candle2 = open_2 - (body_2 / 2)
    
    is_morning_star = (
        is_candle2_merah and  
        (body_1 < (body_2 * 0.35)) and  # Candle tengah berbadan kecil
        is_candle0_hijau and  
        (close_0 > titik_tengah_candle2) # Close melewati 50% body candle lusa
    )
    if is_morning_star:
        return True, "⭐ Morning Star Pattern (Reversal Naik)"

    # 2. Bullish Engulfing (Pola 2-Candle)
    is_engulfing = (close_1 < open_1) and (close_0 > open_0) and (close_0 >= open_1) and (open_0 <= close_1)
    if is_engulfing:
        return True, "🔥 Bullish Engulfing (Reversal Naik)"

    # 3. Hammer (Pola 1-Candle)
    is_hammer = (lower_shadow_0 >= (2 * body_0)) and (upper_shadow_0 <= (0.2 * body_0)) and (body_0 > 0)
    if is_hammer:
        return True, "🔨 Hammer Signal (Buyer Rejection)"

    # --------------------------------------------------------------------------
    # B. 3 POLA CHART KONTINUASI (CONTINUATION PATTERNS)
    # --------------------------------------------------------------------------
    window = 15
    highs = df['High'].iloc[-window:].values
    lows = df['Low'].iloc[-window:].values
    x = np.arange(window)
    
    slope_high, _ = np.polyfit(x, highs, 1)
    slope_low, _ = np.polyfit(x, lows, 1)
    
    # Pola Kontinu 1: Ascending Triangle (Atap Datar, Alas Nanjak)
    if (-0.4 < slope_high < 0.4) and (slope_low > 0.4):
        return True, "📐 Ascending Triangle (Breakout Continuation)"

    # Pola Kontinu 2: Bullish Rectangle Breakout (Atap Datar, Alas Datar + Breakout)
    if (-0.4 < slope_high < 0.4) and (-0.4 < slope_low < 0.4):
        max_high_sebelumnya = np.max(highs[:-1])
        if close_0 > max_high_sebelumnya:
            return True, "📦 Bullish Rectangle Breakout (Penerusan Tren)"

    # Pola Kontinu 3: Falling Wedge Breakout (Atap Turun, Alas Turun + Menyempit)
    if (slope_high < -0.4) and (slope_low < -0.4):
        lebar_awal = highs[0] - lows[0]
        lebar_akhir = highs[-1] - lows[-1]
        if lebar_akhir < lebar_awal:
            return True, "📉 Falling Wedge Breakout (Penerusan Tren)"

    return False, "None"

# =========================
# MAIN BOT (HYBRID)
# =========================
def run_bot():
    symbols = load_symbols()

    send_telegram("🚀 *BOT TREND FOLLOWING + PATTERNS AKTIF (WITHOUT MACD)*")

    while True:
        print("Scanning market...")

        found = False

        for symbol in symbols:
            try:
                df = get_data(symbol)

                if len(df) < 30:  # Dityesuaikan ke 30 agar aman untuk kalkulasi pola & MA
                    continue

                df = compute_supertrend(df)

                current = df['in_uptrend'].iloc[-1]
                last_price = df['Close'].iloc[-1]
                volume_now = df['Volume'].iloc[-1]
                volume_avg = df['Volume'].rolling(20).mean().iloc[-1]

                value = last_price * volume_now

                # =========================
                # FILTER DASAR
                # =========================
                if last_price < 100:
                    continue

                if volume_avg < 1_000_000:
                    continue

                # ==============================================================
                # HARD LOGIC INTEGRATION (3 RULES WITHOUT MACD + PATTERNS)
                # ==============================================================
                # Rule 1: Wajib sedang berada di zona Uptrend
                rule_uptrend = (current == True)
                
                # Rule 2: Volume Meledak minimal 1.5x rata-rata 20 candle
                rule_volume = (volume_now >= 1.5 * volume_avg)
                vol_ratio = round(volume_now / volume_avg, 2) if volume_avg != 0 else 0
                
                # Rule 3: Konfirmasi Pola Bullish Terdeteksi
                has_pattern, pattern_name = detect_patterns(df)

                # ==============================================================================
                # UPGRADE FILTER LIKUIDITAS (BENTENG PERTAHANAN DARI SAHAM SEPI)
                # ==============================================================================
                # Hitung rata-rata nilai transaksi harian selama 20 hari terakhir
                df['daily_value'] = df['Close'] * df['Volume']
                avg_value_20days = df['daily_value'].rolling(20).mean().iloc[-1]

                # Rumus jarak harga dari MA20
                df['ma20'] = df['Close'].rolling(20).mean()
                jarak_ma20_pct = ((df['Close'].iloc[-1] - df['ma20'].iloc[-1]) / df['ma20'].iloc[-1]) * 100

                # 1. TOLAK jika secara historis rata-rata saham ini sepi (transaksi harian < 2 Miliar)
                if avg_value_20days < 2_000_000_000:
                    print(f"❌ {symbol} Ditolak: Rata-rata transaksi harian terlalu sepi (Bukan Big Money asli).")
                    continue

                # 2. TOLAK jika harga hari ini sudah terbang terlalu jauh/pucuk dibanding MA20-nya (Overbought sesaat)
                if jarak_ma20_pct > 8.0:
                    print(f"❌ {symbol} Ditolak: Harga sudah terlalu menjauh dari MA20 ({round(jarak_ma20_pct,1)}%), rawan longsor.")
                    continue

                # EKSEKUSI FILTER KAKU MUTLAK
                if rule_uptrend and rule_volume and has_pattern:
                    
                    if value >= MIN_VALUE:  # Uang masuk valid
                        
                        found = True
                        clean_symbol = symbol.replace(".JK", "")

                        message = f"""🔥 *VALID BULLISH PATTERN DETECTED*

*Stock* : {clean_symbol}
*Price* : {int(last_price)}
*TF* : {INTERVAL}

*Signal* : UPTREND + VOLUME SPIKE
*Volume* : {int(volume_now)} ({vol_ratio}x lipat harian)
*Value* : Rp {int(value):,}
*Pola* : {pattern_name}
"""
                        send_telegram(message)
                        print("SIGNAL VALID:", clean_symbol, "| Pola:", pattern_name)

            except Exception as e:
                print("Error:", symbol, e)

        if not found:
            print("Tidak ada sinyal kuat")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    run_bot()