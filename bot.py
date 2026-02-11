# ============================================================
# GANDA DASHBOARD INVESTASI - TELEGRAM BOT
# COMMAND: /dashboard
# ============================================================

import os
import pandas as pd
import yfinance as yf
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("TOKEN")  # Ambil dari Railway Variables
EXCEL_FILE = "portfolio.xlsx"

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
# COMMAND /dashboard
# ============================================================

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        config_df = pd.read_excel(EXCEL_FILE, sheet_name="Config")
        config = dict(zip(config_df["Parameter"], config_df["Value"]))

        GDP_INDONESIA = to_float(config.get("GDP_INDONESIA_USD", 1.39e12))
        MARKET_CAP_IDX = to_float(config.get("MARKET_CAP_IDX_USD", 8e11))
        MAX_BOBOT_SAHAM = to_float(config.get("MAX_BOBOT_SAHAM", 20))

        saham_df = pd.read_excel(EXCEL_FILE, sheet_name="Saham")
        cash_df = pd.read_excel(EXCEL_FILE, sheet_name="Cash")
        cash = float(pd.to_numeric(cash_df.iloc[:,1], errors="coerce").dropna().iloc[-1])

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
        ihsg_last = get_ihsg()

        if buffett < 60:
            kondisi_pasar = "MURAH"
            target_buffett = 85
        elif buffett < 80:
            kondisi_pasar = "WAJAR"
            target_buffett = 75
        else:
            kondisi_pasar = "MAHAL"
            target_buffett = 65

        aksi = "TAMBAH SAHAM" if porsi_saham < target_buffett else "TAHAN / REBALANCE"

        WIDTH = 60
        now_str = datetime.now().strftime("%d %b %Y %H:%M")

        output = ""
        output += "="*WIDTH + "\n"
        output += "GANDA DASHBOARD INVESTASI".center(WIDTH) + "\n"
        output += "="*WIDTH + "\n\n"

        output += f"Analisa dijalankan : {now_str}\n"
        output += "-"*WIDTH + "\n"
        output += f"IHSG Terakhir      : {ihsg_last:,.2f}\n"
        output += f"Kondisi Pasar      : {kondisi_pasar}\n"
        output += f"Buffett Indicator  : {buffett:.2f} %\n"

        output += "-"*WIDTH + "\n"
        output += f"Total Saham        : {rupiah(total_now)}\n"
        output += f"Cash               : {rupiah(cash)}\n"
        output += f"Total Portofolio   : {rupiah(total_porto)}\n"

        output += "-"*WIDTH + "\n"
        output += f"Porsi Saham        : {porsi_saham:.2f} %\n"
        output += f"Target Saham       : {target_buffett} %\n"
        output += "-"*WIDTH + "\n"
        output += f"REKOMENDASI AKSI   : {aksi}\n\n"

        await update.message.reply_text(f"<pre>{output}</pre>", parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"Terjadi error:\n{e}")

# ============================================================
# MAIN
# ============================================================

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("dashboard", dashboard))

print("Bot running...")
app.run_polling()
