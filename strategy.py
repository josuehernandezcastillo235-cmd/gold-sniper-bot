import requests
import pandas as pd
import os
from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

API_KEY=os.getenv("API_KEY")

def obtener_df(intervalo):
    url=("https://api.twelvedata.com/time_series"
         f"?symbol=XAU/USD&interval={intervalo}&outputsize=250&apikey={API_KEY}")
    data=requests.get(url,timeout=15).json()
    if "values" not in data:
        raise Exception(data.get("message","Error"))
    df=pd.DataFrame(data["values"]).iloc[::-1].reset_index(drop=True)
    for c in ["open","high","low","close"]:
        df[c]=df[c].astype(float)
    df["EMA20"]=EMAIndicator(df["close"],20).ema_indicator()
    df["EMA50"]=EMAIndicator(df["close"],50).ema_indicator()
    df["EMA200"]=EMAIndicator(df["close"],200).ema_indicator()
    df["RSI"]=RSIIndicator(df["close"],14).rsi()
    df["ATR"]=AverageTrueRange(df["high"],df["low"],df["close"],14).average_true_range()
    df["ADX"]=ADXIndicator(df["high"],df["low"],df["close"],14).adx()
    return df

def analizar():
    try:
        df5=obtener_df("5min")
        df15=obtener_df("15min")
    except Exception as e:
        return f"❌ Error datos: {e}"
    u5=df5.iloc[-1];u15=df15.iloc[-1]
    p=float(u5["close"]);e20=float(u5["EMA20"]);e50=float(u5["EMA50"]);e200=float(u5["EMA200"])
    atr=float(u5["ATR"]);rsi=float(u5["RSI"]);adx=float(u5["ADX"])
    alc15=u15["EMA20"]>u15["EMA50"]>u15["EMA200"]
    baj15=u15["EMA20"]<u15["EMA50"]<u15["EMA200"]
    cerca=abs(p-e20)<=atr*0.5
    conf=min(95,50+(15 if adx>30 else 0)+(15 if (rsi>60 or rsi<40) else 0)+(10 if cerca else 0))
    if e20>e50>e200 and alc15 and rsi>58 and adx>25 and cerca:
        sl=p-atr*1.2;tp=p+atr*2.5
        return f'''🥇 XAU SNIPER AI V3.0\n\n🟢 COMPRA\n\n⭐ Confianza: {conf}%\n\n📋 COPIAR\n\nEntrada: {p:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}\n\nRSI: {rsi:.1f}\nADX: {adx:.1f}'''
    if e20<e50<e200 and baj15 and rsi<42 and adx>25 and cerca:
        sl=p+atr*1.2;tp=p-atr*2.5
        return f'''🥇 XAU SNIPER AI V3.0\n\n🔴 VENTA\n\n⭐ Confianza: {conf}%\n\n📋 COPIAR\n\nEntrada: {p:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}\n\nRSI: {rsi:.1f}\nADX: {adx:.1f}'''
    return "😴 Sin señal"
    
