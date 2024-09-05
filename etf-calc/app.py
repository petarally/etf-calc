from flask import Flask, request, render_template, jsonify
import yfinance as yf
import requests
import pandas as pd

app = Flask(__name__)

# Helper functions
def get_etf_price_on_nearest_date(symbol, date):
    try:
        etf = yf.Ticker(symbol)
        start_date = pd.to_datetime(date) - pd.DateOffset(days=30)
        end_date = pd.to_datetime(date) + pd.DateOffset(days=30)
        price_data = etf.history(start=start_date, end=end_date)

        if price_data.empty:
            return None
        
        price_data.index = price_data.index.tz_localize(None)
        date = pd.to_datetime(date)
        nearest_date = price_data.index[price_data.index >= date].min()
        if pd.notna(nearest_date):
            return price_data.loc[nearest_date, 'Close']
    except Exception as e:
        print(f"Error retrieving ETF price data: {e}")
    return None

def get_last_available_price(symbol):
    try:
        etf = yf.Ticker(symbol)
        today = pd.to_datetime('today')
        price_data = etf.history(start=today - pd.DateOffset(days=1), end=today)
        
        if not price_data.empty:
            price_data.index = price_data.index.tz_localize(None)
            return price_data.iloc[-1]['Close']
    except Exception as e:
        print(f"Error retrieving last available ETF price data: {e}")
    return None

def get_exchange_rate_on_date():
    try:
        api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(api_url)
        data = response.json()
        return data['rates']['EUR']
    except Exception as e:
        print(f"Error retrieving exchange rate data: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        investments = request.json.get('investments', [])
        etf_symbol = request.json.get('etfSymbol', '')
        
        total_units = 0
        for investment in investments:
            date = investment["date"]
            amount_eur = investment["amount_eur"]

            price_usd = get_etf_price_on_nearest_date(etf_symbol, date)

            if price_usd is None:
                price_usd = get_last_available_price(etf_symbol)
                if price_usd is None:
                    continue

            exchange_rate = get_exchange_rate_on_date()
            if exchange_rate is None:
                continue

            price_eur = price_usd * exchange_rate
            units = amount_eur / price_eur
            total_units += units

        current_price_usd = get_etf_price_on_nearest_date(etf_symbol, pd.to_datetime('today').strftime('%Y-%m-%d'))
        if current_price_usd is None:
            current_price_usd = get_last_available_price(etf_symbol)

        if current_price_usd is not None:
            current_exchange_rate = get_exchange_rate_on_date()
            if current_exchange_rate is not None:
                current_price_eur = current_price_usd * current_exchange_rate
                portfolio_value = total_units * current_price_eur
                total_investment = sum([investment["amount_eur"] for investment in investments])
                profit = portfolio_value - total_investment

                return jsonify({
                    'totalUnits': total_units,
                    'currentPriceEur': current_price_eur,
                    'portfolioValue': portfolio_value,
                    'totalInvestment': total_investment,
                    'profit': profit
                })
            else:
                return jsonify({'error': 'Could not retrieve the current exchange rate.'}), 500
        else:
            return jsonify({'error': 'Could not retrieve the current price for ETF.'}), 500
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
