# ============================================================
# GANDA TELEGRAM BUFFETT DASHBOARD – FULL VERSION
# Trigger : /dashboard
# Railway Ready
# ============================================================

import os
import pandas as pd
import yfinance as yf
import requests
from flask import Flask, request
from datetime import datetime

# ============================================================
# ENV VARIABLES (RAILWAY)
# ============================================================

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("TOKEN atau CHAT_ID belum diset di Railway")

app = Flask(__name__)

# ============================================================
# TELEGRAM SEND (AUTO SPLIT 4096 CHAR)
# ============================================================

def kirim_telegram(teks):
    MAX_LEN = 4000

    for i in range(0, len(teks), MAX_LEN):
        chunk = teks[i:i+MAX_LEN]

        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": f"<pre>{chunk}</pre>",
            "parse_mode": "HTML"
        }
        requests.post(url, data=data)

# ============================================================
# HELPERS
# ============================================================

def to_float(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, str):
        val = val.replace(",", ".")
    return float(val)

def rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")

def get_price(ticker, fallback=0):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        return float(data["Close"].iloc[-1])
    except:
        return fallback

def get_ihsg():
    try:
        data = yf.Ticker("^JKSE").history(period="5d")
        return float(data["Close"].dropna().iloc[-1])
    except:
        return 0.0

# ============================================================
# DASHBOARD ENGINE
# ============================================================

def generate_dashboard():

    EXCEL_FILE = "portfolio.xlsx"

    config_df = pd.read_excel(EXCEL_FILE, sheet_name="Config")
    config = dict(zip(config_df["Parameter"], config_df["Value"]))

    saham_df = pd.read_excel(EXCEL_FILE, sheet_name="Saham")
    cash_df = pd.read_excel(EXCEL_FILE, sheet_name="Cash")

    cash = float(pd.to_numeric(cash_df.iloc[:,1], errors="coerce").dropna().iloc[-1])

    GDP_INDONESIA = to_float(config.get("GDP_INDONESIA_USD", 1.39e12))
    MARKET_CAP_IDX = to_float(config.get("MARKET_CAP_IDX_USD", 8e11))
    MAX_BOBOT_SAHAM = to_float(config.get("MAX_BOBOT_SAHAM", 20))

    rows = []
    total_beli = 0
    total_now = 0

    for _, r in saham_df.iterrows():

        kode = r["Kode"]
        lot = int(r["Lot"])
        harga_beli = to_float(r["Harga Beli"])
        harga_now = get_price(f"{kode}.JK", fallback=harga_beli)

        nilai_beli = harga_beli * lot * 100
        nilai_now = harga_now * lot * 100
        gain = nilai_now - nilai_beli
        gain_pct = (gain / nilai_beli * 100) if nilai_beli else 0

        rows.append({
            "Kode": kode,
            "Lot": lot,
            "Harga Beli": harga_beli,
            "Nilai Beli": nilai_beli,
            "Harga Now": harga_now,
            "Nilai Now": nilai_now,
            "Gain": gain,
            "Gain %": gain_pct
        })

        total_beli += nilai_beli
        total_now += nilai_now

    df = pd.DataFrame(rows)
    df["Bobot"] = df["Nilai Now"] / total_now * 100 if total_now else 0

    total_porto = total_now + cash
    porsi_saham = total_now / total_porto * 100 if total_porto else 0
    buffett = MARKET_CAP_IDX / GDP_INDONESIA * 100

    if buffett < 60:
        kondisi_pasar = "MURAH"
        target_buffett = 85
    elif buffett < 80:
        kondisi_pasar = "WAJAR"
        target_buffett = 75
    else:
        kondisi_pasar = "MAHAL"
        target_buffett = 65

    aksi = "TAMBAH SAHAM" if porsi_saham < target_buffett - 2 else "TAHAN / REBALANCE"
    ihsg_last = get_ihsg()
    now_str = datetime.now().strftime("%d %b %Y %H:%M")

    output = ""

    # ============================================================
    # HEADER
    # ============================================================

    output += "="*60 + "\n"
    output += "GANDA DASHBOARD INVESTASI".center(60) + "\n"
    output += "="*60 + "\n\n"

    output += f"Analisa dijalankan : {now_str}\n"
    output += "-"*60 + "\n"
    output += f"IHSG Terakhir      : {ihsg_last:,.2f}\n"
    output += f"Kondisi Pasar      : {kondisi_pasar}\n"
    output += f"Buffett Indicator  : {buffett:.2f} %\n"
    output += "-"*60 + "\n"
    output += f"Total Saham        : {rupiah(total_now)}\n"
    output += f"Cash               : {rupiah(cash)}\n"
    output += f"Total Portofolio   : {rupiah(total_porto)}\n"
    output += "-"*60 + "\n"
    output += f"Porsi Saham        : {porsi_saham:.2f} %\n"
    output += f"Target Saham       : {target_buffett} %\n"
    output += "-"*60 + "\n"
    output += f"REKOMENDASI AKSI   : {aksi}\n"

    # ============================================================
    # DETAIL TABLE (90 CHAR STYLE)
    # ============================================================

    output += "\n" + "="*90 + "\n"

    header = f"{'Kode':<6}{'Lot':>6}{'Harga Beli':>12}{'Nilai Beli':>15}" \
             f"{'Harga Now':>12}{'Nilai Now':>15}{'G/L Rp':>15}{'G/L %':>8}"

    output += header + "\n"
    output += "="*90 + "\n"

    for _, r in df.iterrows():

        simbol = "🟢" if r["Gain"] >= 0 else "🔴"

        output += (
            f"{r['Kode']:<6}{r['Lot']:>6}"
            f"{r['Harga Beli']:>12,.0f}{r['Nilai Beli']:>15,.0f}"
            f"{r['Harga Now']:>12,.0f}{r['Nilai Now']:>15,.0f}"
            f"{r['Gain']:>15,.0f}"
            f"{r['Gain %']:>8.2f}% {simbol}\n"
        )

    output += "-"*90 + "\n"

    total_gain = total_now - total_beli
    total_gain_pct = total_gain / total_beli * 100 if total_beli else 0

    output += (
        f"{'TOTAL':<6}"
        f"{'':>6}"
        f"{'':>12}"
        f"{total_beli:>15,.0f}"
        f"{'':>12}"
        f"{total_now:>15,.0f}"
        f"{total_gain:>15,.0f}"
        f"{total_gain_pct:>8.2f}%\n"
    )

    # ============================================================
    # BAR BOBOT
    # ============================================================

    output += "\n" + "="*90 + "\n"
    output += "PORTOFOLIO BOBOT (%)\n"
    output += "="*90 + "\n"

    BAR_MAX = 40
    batas_pos = round(MAX_BOBOT_SAHAM / 100 * BAR_MAX)

    for _, r in df.sort_values("Bobot", ascending=False).iterrows():

        panjang = round(r["Bobot"] / 100 * BAR_MAX)
        panjang = max(panjang, 1) if r["Bobot"] > 0 else 0

        bar = ""
        for i in range(BAR_MAX):
            if i == batas_pos:
                bar += "|"
            elif i < panjang:
                bar += "="
            else:
                bar += " "

        if r["Bobot"] <= MAX_BOBOT_SAHAM:
            status = "Normal 🟢"
        elif r["Bobot"] <= 30:
            status = "Konsentrasi Tinggi 🟡"
        else:
            status = "Sangat Terkonsentrasi 🔴"

        output += f"{r['Kode']:<6} |{bar}| {r['Bobot']:>6.2f}%  {status}\n"

    output += "\n"
    output += f"Batas normal per saham : {MAX_BOBOT_SAHAM:.1f}%\n"
    output += "Zona >30% : Konsentrasi sangat tinggi (high conviction)\n"

    return output

# ============================================================
# WEBHOOK
# ============================================================

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        text = data["message"].get("text", "")

        if text == "/dashboard":
            hasil = generate_dashboard()
            kirim_telegram(hasil)

    return "OK"

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
