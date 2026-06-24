# -*- coding: utf-8 -*-
"""
波段诊股 - 数据获取模块
负责：股票列表同步、K线数据获取、实时行情
"""

import json
import os
import time
import threading

import pandas as pd
import requests

# 绕过公司代理（直连更快）
NO_PROXY = {"http": None, "https": None}

STOCK_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stock_cache.json")
STOCK_CACHE_TTL = 3600  # 1小时
stock_list_cache = None
stock_list_lock = threading.Lock()


def get_stock_list():
    """获取A股全量股票列表（含缓存）"""
    global stock_list_cache

    if stock_list_cache and (time.time() - stock_list_cache["ts"] < STOCK_CACHE_TTL):
        return stock_list_cache["data"]

    if os.path.exists(STOCK_CACHE_FILE):
        try:
            with open(STOCK_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if time.time() - cached["ts"] < STOCK_CACHE_TTL:
                    stock_list_cache = cached
                    return cached["data"]
        except Exception:
            pass

    try:
        with stock_list_lock:
            if stock_list_cache and (time.time() - stock_list_cache["ts"] < STOCK_CACHE_TTL):
                return stock_list_cache["data"]

            from mootdx.quotes import Quotes
            client = Quotes.factory(market="std", timeout=10)
            sz = client.stocks(market=0)  # 深圳
            sh = client.stocks(market=1)  # 上海

            stocks = []
            for item in sz + sh:
                code = item.get("code", "")
                name = item.get("name", "")
                market_val = item.get("market", 0)

                if not code or not name or len(code) < 5:
                    continue
                if code.startswith("8"):  # 过滤北交所
                    continue

                prefix = "SZ" if market_val == 0 else "SH"
                stocks.append({
                    "code": code,
                    "full_code": f"{prefix}.{code}",
                    "name": name.strip(),
                    "market": "上海" if market_val == 1 else "深圳",
                    "type": "ETF" if code.startswith("15") or code.startswith("51") else "股票",
                })

            stocks.sort(key=lambda x: (x["code"], x["name"]))
            stock_list_cache = {"ts": time.time(), "data": stocks}

            with open(STOCK_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(stock_list_cache, f, ensure_ascii=False)

            return stocks

    except Exception as e:
        print(f"[stock_list] mootdx失败: {e}")
        if os.path.exists(STOCK_CACHE_FILE):
            try:
                with open(STOCK_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)["data"]
            except Exception:
                pass
        return []


def fetch_kline(code, days=150):
    """
    获取K线日线数据（新浪财经HTTP接口）
    返回 pandas DataFrame，列: date/open/close/high/low/volume
    """
    if "." in code:
        prefix, code_num = code.split(".")
        market = "sh" if prefix.upper() == "SH" else "sz"
    else:
        market = "sh" if code.startswith(("5", "6", "9")) else "sz"
        code_num = code

    symbol = f"{market}{code_num}"

    try:
        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": str(days + 30)}
        resp = requests.get(url, params=params, timeout=10, proxies=NO_PROXY)
        data = resp.json()

        if not data or not isinstance(data, list):
            return pd.DataFrame()

        df_data = []
        for k in data[-days:]:
            df_data.append({
                "date": k["day"],
                "open": float(k["open"]),
                "close": float(k["close"]),
                "high": float(k["high"]),
                "low": float(k["low"]),
                "volume": float(k["volume"]),
            })
        return pd.DataFrame(df_data)

    except Exception as e:
        print(f"[fetch] K线获取失败: {e}")

    return pd.DataFrame()


def fetch_realtime(code):
    """获取实时行情快照，新浪HTTP优先，东财HTTPS备用"""
    if "." in code:
        prefix, code_num = code.split(".")
        market = "sh" if prefix.upper() == "SH" else "sz"
    else:
        market = "sh" if code.startswith(("5", "6", "9")) else "sz"
        code_num = code

    symbol = f"{market}{code_num}"

    # ── 方案1：新浪HTTP ──
    try:
        url = f"http://hq.sinajs.cn/list={symbol}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        resp = requests.get(url, timeout=5, headers=headers, proxies=NO_PROXY)
        text = resp.text

        if '"' in text:
            parts = text.split('"')[1].split(",")
            if len(parts) > 30:
                return {
                    "code": code_num,
                    "name": parts[0],
                    "open": float(parts[1]) if parts[1] else 0,
                    "prev_close": float(parts[2]) if parts[2] else 0,
                    "price": float(parts[3]) if parts[3] else 0,
                    "high": float(parts[4]) if parts[4] else 0,
                    "low": float(parts[5]) if parts[5] else 0,
                    "volume": float(parts[8]) if parts[8] else 0,
                    "amount": float(parts[9]) if parts[9] else 0,
                    "change": round(float(parts[3]) - float(parts[2]), 3) if parts[3] and parts[2] else 0,
                    "change_pct": round((float(parts[3]) - float(parts[2])) / float(parts[2]) * 100, 2)
                    if parts[3] and parts[2] and float(parts[2]) != 0 else 0,
                    "turnover": 0,
                }
    except Exception as e:
        print(f"[realtime] 新浪失败: {e}")

    # ── 方案2：东财HTTPS ──
    try:
        is_etf = code_num.startswith(("15", "16", "18", "20", "51", "56", "58"))
        divisor = 1000.0 if is_etf else 100.0
        secid = f"{0 if market == 'sz' else 1}.{code_num}"
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {"secid": secid, "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f168,f169,f170"}
        resp = requests.get(url, params=params, timeout=5, proxies=NO_PROXY)
        data = resp.json().get("data", {})
        if data:
            return {
                "code": code_num,
                "name": data.get("f58", ""),
                "price": round(data.get("f43", 0) / divisor, 3),
                "prev_close": round(data.get("f60", 0) / divisor, 3),
                "open": round(data.get("f46", 0) / divisor, 3),
                "high": round(data.get("f44", 0) / divisor, 3),
                "low": round(data.get("f45", 0) / divisor, 3),
                "volume": data.get("f47", 0),
                "amount": data.get("f48", 0),
                "turnover": round(data.get("f168", 0) / 100, 2),
                "change": round(data.get("f169", 0) / divisor, 3),
                "change_pct": round(data.get("f170", 0) / 100, 2),
            }
    except Exception as e:
        print(f"[realtime] 东财失败: {e}")

    return None
