                 
  import os
  import requests
  import yfinance as yf
  from datetime import datetime

  TICKERS = [
      "NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA",
      "AVGO", "TXN", "COHR", "INTC", "ASML", "SNDK"
  ]

  GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
  WA_URL   = "https://api.callmebot.com/whatsapp.php"

  GROQ_API_KEY    = os.environ["GROQ_API_KEY"]
  WHATSAPP_PHONE  = os.environ["WHATSAPP_PHONE"]
  WHATSAPP_APIKEY = os.environ["WHATSAPP_APIKEY"]


  def get_price_data():
      results = []
      for ticker in TICKERS:
          try:
              stock = yf.Ticker(ticker)
              hist  = stock.history(period="10d", interval="1d")
              info  = stock.info
              if hist.empty:
                  results.append({"ticker": ticker, "error": "no data"})
                  continue
              closes    = hist["Close"].tolist()
              price     = round(closes[-1], 2)
              change_7d = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if len(closes) >= 2 else None
              trend     = "↑" if closes[-1] > closes[0] else ("↓" if closes[-1] < closes[0] else "→")
              results.append({
                  "ticker": ticker,
                  "company": info.get("longName") or info.get("shortName", ticker),
                  "price": price,
                  "change_7d": change_7d,
                  "trend": trend,
              })
          except Exception as e:
              results.append({"ticker": ticker, "error": str(e)})
      return results


  def get_ai_brief(price_data):
      summary = "\n".join([
          f"- {d['ticker']}: ${d.get('price','N/A')} | 7d: {d.get('change_7d',0):+.1f}% {d.get('trend','')}"
          for d in price_data if "error" not in d
      ])
      prompt = f"""You are a financial analyst. Based on the 7-day price data below, write a concise market brief (max 150
   words). Identify top gainers, biggest losers, and overall trend. Be direct.

  {summary}"""
      try:
          resp = requests.post(
              GROQ_URL,
              headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
              json={
                  "model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 300,
                  "temperature": 0.7,
              },
              timeout=30
          )
          resp.raise_for_status()
          return resp.json()["choices"][0]["message"]["content"]
      except Exception as e:
          return f"AI analysis unavailable: {e}"


  def send_whatsapp(message):
      try:
          resp = requests.get(
              WA_URL,
              params={"phone": WHATSAPP_PHONE, "text": message, "apikey": WHATSAPP_APIKEY},
              timeout=15
          )
          return resp.status_code == 200
      except Exception as e:
          print(f"WhatsApp error: {e}")
          return False


  def build_message(price_data, ai_brief):
      today = datetime.now().strftime("%b %d, %Y")
      lines = [f"📊 *Daily Market Digest — {today}*", ""]
      lines.append("*🤖 AI Brief:*")
      lines.append(ai_brief)
      lines.append("")

      valid = [d for d in price_data if "error" not in d and d.get("change_7d") is not None]
      valid.sort(key=lambda x: x["change_7d"], reverse=True)

      gainers = [d for d in valid if d["change_7d"] > 0][:3]
      if gainers:
          lines.append("*🟢 Top Gainers (7d):*")
          for d in gainers:
              lines.append(f"  {d['ticker']} ${d['price']} {d['trend']} {d['change_7d']:+.1f}%")
          lines.append("")

      losers = [d for d in valid if d["change_7d"] < 0][-3:][::-1]
      if losers:
          lines.append("*🔴 Top Losers (7d):*")
          for d in losers:
              lines.append(f"  {d['ticker']} ${d['price']} {d['trend']} {d['change_7d']:+.1f}%")
          lines.append("")

      lines.append("*📋 All Tickers:*")
      for d in valid:
          emoji = "🟢" if d["change_7d"] > 0 else ("🔴" if d["change_7d"] < 0 else "⚪")
          lines.append(f"  {emoji} {d['ticker']} ${d['price']} ({d['change_7d']:+.1f}%)")

      lines.append("")
      lines.append("_Your Sentiment Dashboard_")
      return "\n".join(lines)


  if __name__ == "__main__":
      print("Fetching price data...")
      price_data = get_price_data()
      print("Generating AI brief...")
      ai_brief = get_ai_brief(price_data)
      print("Building message...")
      message = build_message(price_data, ai_brief)
      print(message)
      print("Sending WhatsApp...")
      ok = send_whatsapp(message)
      print("Sent!" if ok else "Failed.")
