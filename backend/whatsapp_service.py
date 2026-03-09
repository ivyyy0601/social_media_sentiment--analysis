"""
WhatsApp notification service via CallMeBot (free, no business account needed).
Setup: Send "I allow callmebot to send me messages" to +34 644 60 92 60 on WhatsApp.
They will reply with your API key.
"""

import requests
from urllib.parse import quote


class WhatsAppService:
    API_URL = "https://api.callmebot.com/whatsapp.php"

    def __init__(self, phone: str, api_key: str):
        """
        phone:   Your WhatsApp number with country code, no + or spaces (e.g. 85212345678)
        api_key: API key received from CallMeBot
        """
        self.phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        self.api_key = api_key

    def send(self, message: str) -> bool:
        """Send a WhatsApp message. Returns True on success."""
        try:
            resp = requests.get(
                self.API_URL,
                params={
                    'phone': self.phone,
                    'text': message,
                    'apikey': self.api_key,
                },
                timeout=15
            )
            success = resp.status_code == 200
            if not success:
                print(f"[WhatsApp] Failed: {resp.status_code} {resp.text[:100]}")
            return success
        except Exception as e:
            print(f"[WhatsApp] Error: {e}")
            return False

    def send_daily_digest(self, board_data: list, market_overview: dict) -> bool:
        """
        Format and send the daily sentiment digest.
        board_data: list of ticker sentiment dicts (from ticker-board endpoint)
        market_overview: overall market sentiment dict
        """
        msg = self._build_digest(board_data, market_overview)
        return self.send(msg)

    def _build_digest(self, board: list, overview: dict) -> str:
        from datetime import datetime
        today = datetime.now().strftime('%b %d, %Y')

        bullish = [t for t in board if t.get('label') == 'bullish' and t.get('total_posts', 0) > 0]
        bearish = [t for t in board if t.get('label') == 'bearish' and t.get('total_posts', 0) > 0]
        no_data = [t for t in board if t.get('total_posts', 0) == 0]

        lines = [
            f"📊 *Daily Sentiment Digest* — {today}",
            "",
        ]

        # Overall market
        overall = overview.get('overall_market_sentiment', {})
        avg_score = overall.get('average_score')
        if avg_score is not None:
            mood = '📈 Bullish' if avg_score > 0.05 else ('📉 Bearish' if avg_score < -0.05 else '➡️ Neutral')
            lines.append(f"*Overall Market:* {mood} (score: {avg_score:+.3f})")
            lines.append("")

        # Top bullish
        if bullish:
            lines.append("*🟢 Most Bullish:*")
            for t in bullish[:3]:
                score = t.get('score', 0)
                lines.append(f"  • {t['ticker']} ({t.get('company', '')[:20]}) {score:+.3f} | {t['total_posts']} posts")
            lines.append("")

        # Top bearish
        if bearish:
            lines.append("*🔴 Most Bearish:*")
            for t in bearish[:3]:
                score = t.get('score', 0)
                lines.append(f"  • {t['ticker']} ({t.get('company', '')[:20]}) {score:+.3f} | {t['total_posts']} posts")
            lines.append("")

        # Tickers with no data
        if no_data:
            tickers_str = ', '.join(t['ticker'] for t in no_data)
            lines.append(f"*⚪ No recent data:* {tickers_str}")
            lines.append("")

        lines.append("_Powered by your Sentiment Dashboard_")
        return '\n'.join(lines)
