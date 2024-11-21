import time
import numpy as np
import pandas as pd
from binance.client import Client
from binance.enums import *
from decimal import Decimal

percentuale_stop_loss = 0.02
percentuale_trailing_stop = 0.02
simbolo = "BTCUSDC"  #Scegliere la valuta per la quale investire, per esempio io ho scelto di investire in bitcoin(BTC) con il dollaro americano in stable coin(USDC)
api_key = '' #Inserire la propria chiave api di binance
api_secret = '' #Inserire la propria chiave api segreta di binance visualizzabile solo al momento della creazione delle chiavi

class BotDiTrading:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.simbolo = simbolo
        self.saldo_btc = Decimal(0.0)
        self.saldo_usdc = Decimal(0.0)
        self.prezzo_iniziale = None
        self.storia_prezzi = []
        self.info_simbolo = self.client.get_symbol_info(self.simbolo)
        self.quantita_minima = None
        self.step_size = None
        for filtro in self.info_simbolo['filters']:
            if filtro['filterType'] == 'LOT_SIZE':
                self.quantita_minima = Decimal(filtro['minQty'])
                self.step_size = Decimal(filtro['stepSize'])
                break
        self.aggiorna_saldi()

    def aggiorna_saldi(self):
        try:
            account_info = self.client.get_account()
            for asset in account_info['balances']:
                if asset['asset'] == 'BTC':
                    self.saldo_btc = Decimal(asset['free'])
                elif asset['asset'] == 'USDC':
                    self.saldo_usdc = Decimal(asset['free'])
            print(f"Saldi aggiornati - BTC: {self.saldo_btc}, USDC: {self.saldo_usdc}")
        except Exception as e:
            print(f"Errore durante l'aggiornamento dei saldi: {e}")

    def recupera_prezzo_corrente(self):
        ticker = self.client.get_symbol_ticker(symbol=self.simbolo)
        return float(ticker['price'])

    def calcola_atr(self, prezzi, periodo=14):
        if len(prezzi) < periodo + 1:
            return None
        high_low = np.abs(np.diff(prezzi))
        high_close = np.abs(np.array(prezzi[1:]) - np.array(prezzi[:-1]))
        true_ranges = np.maximum(high_low, high_close)
        atr = np.mean(true_ranges[-periodo:])
        return atr

    def calcola_rsi(self, prezzi, periodo=14):
        if len(prezzi) < periodo:
            return None
        delta = np.diff(prezzi)
        guadagno = np.where(delta > 0, delta, 0)
        perdita = np.where(delta < 0, -delta, 0)
        guadagno_medio = np.mean(guadagno[-periodo:])
        perdita_media = np.mean(perdita[-periodo:])
        rs = guadagno_medio / perdita_media if perdita_media != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calcola_sma(self, prezzi, periodo):
        if len(prezzi) < periodo:
            return None
        return np.mean(prezzi[-periodo:])

    def calcola_ema(self, prezzi, periodo):
        if len(prezzi) < periodo:
            return None
        return pd.Series(prezzi).ewm(span=periodo, adjust=False).mean().iloc[-1]

    def arrotonda_quantita(self, quantita):
        quantita_arrotondata = (quantita // self.step_size) * self.step_size
        if quantita_arrotondata < self.quantita_minima:
            return Decimal(0)
        return quantita_arrotondata

    def vendi(self):
        prezzo_corrente = Decimal(self.recupera_prezzo_corrente())
        quantita_vendita = self.saldo_btc
        quantita_vendita = self.arrotonda_quantita(quantita_vendita)
        if quantita_vendita == 0:
            print("Quantità di BTC troppo piccola per essere venduta.")
            return
        if self.saldo_btc >= quantita_vendita:
            try:
                ordine = self.client.order_market_sell(
                    symbol=self.simbolo,
                    quantity=float(quantita_vendita)
                )
                print(f"Ordine di vendita eseguito: {ordine}")
                self.aggiorna_saldi()
            except Exception as e:
                print(f"Errore durante la vendita: {e}")
        else:
            print("Saldo BTC insufficiente per vendere.")

    def compra(self):
        prezzo_corrente = Decimal(self.recupera_prezzo_corrente())
        quantita_acquisto = self.saldo_usdc / prezzo_corrente
        quantita_acquisto = self.arrotonda_quantita(quantita_acquisto)
        if self.saldo_usdc >= quantita_acquisto * prezzo_corrente:
            try:
                ordine = self.client.order_market_buy(
                    symbol=self.simbolo,
                    quantity=float(quantita_acquisto)
                )
                print(f"Ordine di acquisto eseguito: {ordine}")
                self.aggiorna_saldi()
            except Exception as e:
                print(f"Errore durante l'acquisto: {e}")
        else:
            print("Saldo USDC insufficiente per acquistare BTC.")

    def trade(self):
        while True:
            try:
                prezzo_corrente = self.recupera_prezzo_corrente()
                self.storia_prezzi.append(prezzo_corrente)
                print(f"Prezzo attuale: {prezzo_corrente:.2f}")
                rsi = self.calcola_rsi(self.storia_prezzi, 14)
                sma = self.calcola_sma(self.storia_prezzi, 14)
                ema = self.calcola_ema(self.storia_prezzi, 14)
                if rsi is None or sma is None or ema is None:
                    print("Indicatori tecnici insufficienti.")
                    time.sleep(10)
                    continue
                mercato_in_rialzo = prezzo_corrente > self.storia_prezzi[-2]
                mercato_in_ribasso = prezzo_corrente < self.storia_prezzi[-2]
                print(f"RSI: {rsi:.2f}, SMA: {sma:.2f}, EMA: {ema:.2f}")
                if mercato_in_rialzo and self.saldo_btc > 0:
                    if rsi > 70 and prezzo_corrente > sma and prezzo_corrente > ema:
                        print("Mercato in rialzo. Vendita BTC.")
                        self.vendi()
                    else:
                        print("Mercato in rialzo, ma gli indicatori non sono favorevoli per la vendita.")
                elif mercato_in_ribasso and self.saldo_usdc > 5:
                    if rsi < 30 and prezzo_corrente < sma and prezzo_corrente < ema:
                        print("Mercato in ribasso. Acquisto BTC.")
                        self.compra()
                    else:
                        print("Mercato in ribasso, ma gli indicatori non sono favorevoli per l'acquisto.")
                else:
                    print("Nessuna azione di trading.")
                time.sleep(15)
            except Exception as e:
                print(f"Errore nel ciclo di trading: {e}")
                time.sleep(10)

bot = BotDiTrading(api_key, api_secret)
bot.trade()
