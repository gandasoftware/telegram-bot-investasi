import os
import requests
import pandas as pd
import yfinance as yf
from flask import Flask, request
from datetime import datetime

# ============================================================
# ENV VARIABLE
# ============================================================

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("TOKEN atau CHAT_ID belum diset di Railway Variables")

# ============================================================
# FLASK APP
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
    requests.post(url, data=data, timeout=15)

# ============================================================
# MARKET DATA
# ============================================================

def get_price(symbol, fallback=0):
    try:
        data = yf.Ticker(symbol)
        hist = data.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return fallback
    except:
        return fallback

def get_ihsg():
    try:
        data = yf.Ticker("^JKSE")
        hist = data.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return 0
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

    try:
        saham_df = pd.read_excel(EXCEL_FILE, sheet_name="Saham")
        cash_df = pd.read_excel(EXCEL_FILE, sheet_name="Cash")
        config_df = pd.read_excel(EXCEL_FILE, sheet_name="Config")
    except Exception as e:
        return f"ERROR baca Excel: {e}"

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

    if total_now == 0:
        return "Portofolio kosong."

    df = pd.DataFrame(rows)
    df["Bobot"] = df["Nilai Now"] / total_now * 100

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
    output += "📊 GANDA DASHBOARD INVESTASI\n\n"
    output += f"Update : {now_str}\n"
    output += f"IHSG   : {ihsg:,.2f}\n"
    output += f"Kondisi: {kondisi}\n"
    output += f"Buffett: {buffett:.2f}%\n\n"
    output += f"Saham  : {rupiah(total_now)}\n"
    output += f"Cash   : {rupiah(cash)}\n"
    output += f"Total  : {rupiah(total_porto)}\n\n"
    output += f"Porsi Saham : {porsi_saham:.2f}%\n"
    output += f"Target      : {target}%\n"
    output += f"REKOMENDASI  : {aksi}\n"

    return output

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Bot aktif 🚀"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data and "message" in data:
        message = data["message"]
        text = message.get("text", "")

        if text == "/dashboard":
            hasil = generate_dashboard()
            kirim_telegram(hasil)

    return "OK"

# ============================================================
# RUN LOCAL (Railway pakai gunicorn)
# ============================================================

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=PORT)
