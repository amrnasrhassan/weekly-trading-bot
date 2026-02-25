import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime
import os

# ===============================
# إعدادات
# ===============================
TICKERS = ["SPY", "QQQ", "TLT", "GLD"]
INITIAL_CAPITAL = 3000
TOP_N = 2
MOM_WINDOW = 12
MA_WINDOW = 200
VOL_LOOKBACK = 20
VOL_THRESHOLD = 0.25
REDUCED_EXPOSURE = 0.7

EMAIL_ADDRESS = "amr.nasr.hassan@gmail.com"
EMAIL_PASSWORD = os.environ["EMAIL_PASS"]

# ===============================
# تحميل البيانات
# ===============================
data = yf.download(TICKERS, period="15y", interval="1wk", auto_adjust=True)
prices = data["Close"].dropna()

momentum = prices.pct_change(MOM_WINDOW).shift(1)
ma200 = prices.rolling(MA_WINDOW).mean()

# ===============================
# الباك تست
# ===============================
capital = INITIAL_CAPITAL
portfolio_returns = []
equity_curve = []
dates = []

for i in range(MA_WINDOW + MOM_WINDOW, len(prices)):

    current_prices = prices.iloc[i]
    current_mom = momentum.iloc[i]
    current_ma = ma200.iloc[i]

    eligible = current_prices[current_prices > current_ma].index

    if len(eligible) > 0:
        ranked = current_mom[eligible].sort_values(ascending=False)
        selected = ranked.head(TOP_N).index
    else:
        selected = []

    if len(selected) > 0:
        weekly_return = prices[selected].iloc[i] / prices[selected].iloc[i-1] - 1
        portfolio_return = weekly_return.mean()
    else:
        portfolio_return = 0

    if len(portfolio_returns) > VOL_LOOKBACK:
        recent = pd.Series(portfolio_returns[-VOL_LOOKBACK:])
        vol = recent.std() * np.sqrt(52)
        exposure = REDUCED_EXPOSURE if vol > VOL_THRESHOLD else 1.0
    else:
        exposure = 1.0

    adjusted_return = portfolio_return * exposure
    capital *= (1 + adjusted_return)

    portfolio_returns.append(adjusted_return)
    equity_curve.append(capital)
    dates.append(prices.index[i])

equity_series = pd.Series(equity_curve, index=dates)
returns = pd.Series(portfolio_returns)

# ===============================
# حساب الأداء
# ===============================
years = len(equity_series) / 52
total_return = equity_series.iloc[-1] / equity_series.iloc[0] - 1
cagr = (1 + total_return) ** (1 / years) - 1
vol = returns.std() * np.sqrt(52)
sharpe = (returns.mean() * 52) / vol if vol != 0 else 0

rolling_max = equity_series.cummax()
dd = (equity_series - rolling_max) / rolling_max
max_dd = dd.min()

win_rate = (returns > 0).mean()
avg_gain = returns[returns > 0].mean()
avg_loss = returns[returns < 0].mean()
profit_factor = abs(avg_gain / avg_loss) if avg_loss != 0 else np.nan
reduced_weeks = (returns.rolling(VOL_LOOKBACK).std() * np.sqrt(52) > VOL_THRESHOLD).mean()

# ===============================
# إشارة هذا الأسبوع
# ===============================
i = len(prices) - 1
current_prices = prices.iloc[i]
current_mom = momentum.iloc[i]
current_ma = ma200.iloc[i]

eligible = current_prices[current_prices > current_ma].index

if len(eligible) > 0:
    ranked = current_mom[eligible].sort_values(ascending=False)
    selected_now = ranked.head(TOP_N).index.tolist()
else:
    selected_now = []

signal_text = "\n===== إشارة هذا الأسبوع =====\n"

if len(selected_now) == 0:
    signal_text += "لا توجد أصول مؤهلة — ابقَ في كاش.\n"
else:
    allocation = equity_series.iloc[-1] / len(selected_now)
    for ticker in selected_now:
        price = current_prices[ticker]
        shares = allocation // price
        invested = shares * price

        signal_text += f"""
الأصل: {ticker}
السعر الحالي: {price:.2f}$
عدد الأسهم المقترح: {int(shares)}
قيمة الاستثمار: {invested:.2f}$
"""

# ===============================
# إنشاء التقرير
# ===============================
report = f"""
📊 Weekly Trading Report
=========================

Date: {datetime.now().strftime('%Y-%m-%d')}

CAGR: {cagr*100:.2f}%
Sharpe: {sharpe:.2f}
Max Drawdown: {max_dd*100:.2f}%
Total Return: {total_return*100:.2f}%
Current Equity: {equity_series.iloc[-1]:.2f}$

Win Rate: {win_rate*100:.2f}%
Average Gain: {avg_gain*100:.2f}%
Average Loss: {avg_loss*100:.2f}%
Profit Factor: {profit_factor:.2f}
Weeks with Reduced Exposure: {reduced_weeks*100:.2f}%
"""

report += signal_text

# ===============================
# إرسال الإيميل
# ===============================
msg = EmailMessage()
msg["Subject"] = "📊 Weekly Trading Report"
msg["From"] = EMAIL_ADDRESS
msg["To"] = EMAIL_ADDRESS
msg.set_content(report)

context = ssl.create_default_context()

with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)

print("Email Sent Successfully")
