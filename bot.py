import os
import requests
import pandas as pd
import yfinance as yf
from flask import Flask, request
from openpyxl import load_workbook
from datetime import datetime

# ============================================================
# ENV VARIABLE
# ============================================================

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ============================================================
# FLASK APP (WEBHOOK RAILWAY)
# ============================================================

app = Flask(__name__)

# ============================================================
# UTIL
# ============================================================

def rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")

def to_float(x):
    try:
        return float(x)
    except:
        return 0

def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": pesan
    }
    requests.post(url, data=data)

# ============================================================
# DATA MARKET
# ============================================================

def get_price(symbol, fallback=0):
    try:
        data = yf.Ticker(symbol)
        return float(data.history(period="1d")["Close"].iloc[-1])
    except:
        return fallback

def get_ihsg():
    try:
        data = yf.Ticker("^JKSE")
        return float(data.history(period="1d")["Close"].iloc[-1])
    except:
        return 0

# ============================================================
# WORLD BANK DATA
# ============================================================

def get_gdp_indonesia_usd():
    url = "https://api.worldbank.org/v2/country/IDN/indicator/NY.GDP.MKTP.CD?format=json"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()[1]
        for item in data:
            if item.get("value") is not None:
                return float(item["value"])
    except:
        return None

def get_marketcap_idx_usd():
    url = "https://api.worldbank.org/v2/country/IDN/indicator/CM.MKT.LCAP.CD?format=json"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()[1]
        for item in data:
            if item.get("value") is not None:
                return float(item["value"])
    except:
        return None

# ============================================================
# DASHBOARD
# ============================================================

def generate_dashboard():

    EXCEL_FILE = "portfolio.xlsx"

    saham_df = pd.read_excel(EXCEL_FILE, sheet_name="Saham")
    cash_df = pd.read_excel(EXCEL_FILE, sheet_name="Cash")
    config_df = pd.read_excel(EXCEL_FILE, sheet_name="Config")

    config = dict(zip(config_df["Parameter"], config_df["Value"]))
    MAX_BOBOT_SAHAM = to_float(config.get("MAX_BOBOT_SAHAM", 20))

    cash = float(pd.to_numeric(cash_df.iloc[:,1], errors="coerce").dropna().iloc[-1])

    GDP = get_gdp_indonesia_usd()
    MARKET_CAP = get_marketcap_idx_usd()

    if not GDP or not MARKET_CAP:
        return "ERROR: Gagal mengambil data makro."

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
    buffett = MARKET_CAP / GDP * 100

    if buffett < 60:
        kondisi = "MURAH"
        target = 85
    elif buffett < 80:
        kondisi = "WAJAR"
        target = 75
    else:
        kondisi = "MAHAL"
        target = 65

    aksi = "TAMBAH SAHAM" if porsi_saham < target - 2 else "TAHAN / REBALANCE"

    ihsg = get_ihsg()
    now_str = datetime.now().strftime("%d %b %Y %H:%M")

    output = ""

    output += "="*60 + "\n"
    output += "GANDA DASHBOARD INVESTASI".center(60) + "\n"
    output += "="*60 + "\n\n"

    output += f"Analisa dijalankan : {now_str}\n"
    output += "-"*60 + "\n"
    output += f"IHSG Terakhir      : {ihsg:,.2f}\n"
    output += f"Kondisi Pasar      : {kondisi}\n"
    output += f"Buffett Indicator  : {buffett:.2f} %\n"
    output += "-"*60 + "\n"
    output += f"Total Saham        : {rupiah(total_now)}\n"
    output += f"Cash               : {rupiah(cash)}\n"
    output += f"Total Portofolio   : {rupiah(total_porto)}\n"
    output += "-"*60 + "\n"
    output += f"Porsi Saham        : {porsi_saham:.2f} %\n"
    output += f"Target Saham       : {target} %\n"
    output += "-"*60 + "\n"
    output += f"REKOMENDASI AKSI   : {aksi}\n\n"

    output += "="*60 + "\n"
    output += "DETAIL PORTOFOLIO\n"
    output += "="*60 + "\n"

    header = f"{'Kode':<6}{'Lot':>6}{'Harga Beli':>12}{'Nilai Beli':>15}" \
             f"{'Harga Now':>12}{'Nilai Now':>15}{'G/L Rp':>15}{'G/L %':>8}"
    output += header + "\n"
    output += "-"*90 + "\n"

    for _, r in df.iterrows():
        output += (
            f"{r['Kode']:<6}{r['Lot']:>6}"
            f"{r['Harga Beli']:>12,.0f}{r['Nilai Beli']:>15,.0f}"
            f"{r['Harga Now']:>12,.0f}{r['Nilai Now']:>15,.0f}"
            f"{r['Gain']:>15,.0f}"
            f"{r['Gain %']:>8.2f}%\n"
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
        f"{total_gain_pct:>8.2f}%\n\n"
    )

    output += "PORTOFOLIO BOBOT (%)\n"

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

        output += f"{r['Kode']:<6} |{bar}| {r['Bobot']:>6.2f}%\n"

    output += f"\nBatas normal per saham : {MAX_BOBOT_SAHAM:.1f}%\n"

    return output

# ============================================================
# WEBHOOK
# ============================================================

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    text = data["message"]["text"]

    if text == "/dashboard":
        hasil = generate_dashboard()
        kirim_telegram(hasil)

    return "ok"

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
