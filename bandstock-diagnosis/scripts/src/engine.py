# -*- coding: utf-8 -*-
"""
波段诊股 - 分析引擎模块
负责：技术指标计算、支撑阻力位、综合评分
所有参数配置适用于 1~3 个月波段操作
"""

import pandas as pd
import numpy as np


# ── 波段参数配置 ──
BAND_PARAMS = {
    "MA": "10/20/50/120",
    "MACD": "(19,39,9)",
    "RSI": "(14,21,42)",
    "Bollinger": "(30,2)",
    "KDJ": "(34,5,10)",
    "VOL": "10/30",
}


def safe_float(val):
    """安全转 float，处理 NaN"""
    try:
        return float(val) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """计算 RSI 指标"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))


def calc_indicators(df: pd.DataFrame):
    """
    计算全部波段技术指标
    返回 (result_dict, error_str)
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]
    n = len(df)

    result = {
        "dates": df["date"].tolist(),
        "closes": [safe_float(v) for v in close],
        "volumes": [safe_float(v) for v in vol],
    }

    if n < 50:
        return result, "数据不足（需要至少50个交易日）"

    # ── 均线 MA10/MA20/MA50/MA120 ──
    result["MA10"] = [safe_float(v) for v in close.rolling(10).mean()]
    result["MA20"] = [safe_float(v) for v in close.rolling(20).mean()]
    result["MA50"] = [safe_float(v) for v in close.rolling(50).mean()]
    result["MA120"] = [safe_float(v) for v in close.rolling(120).mean()]

    # ── MACD (19, 39, 9) ──
    ema19 = close.ewm(span=19, adjust=False).mean()
    ema39 = close.ewm(span=39, adjust=False).mean()
    dif = ema19 - ema39
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = (dif - dea) * 2
    result["DIF"] = [safe_float(v) for v in dif]
    result["DEA"] = [safe_float(v) for v in dea]
    result["HIST"] = [safe_float(v) for v in hist]

    # ── RSI (14, 21, 42) ──
    result["RSI14"] = [safe_float(v) for v in _rsi(close, 14)]
    result["RSI21"] = [safe_float(v) for v in _rsi(close, 21)]
    result["RSI42"] = [safe_float(v) for v in _rsi(close, 42)]

    # ── 布林带 (30, 2) ──
    boll_mid = close.rolling(30).mean()
    boll_std = close.rolling(30).std()
    result["BOLL_UP"] = [safe_float(v) for v in (boll_mid + 2 * boll_std)]
    result["BOLL_MID"] = [safe_float(v) for v in boll_mid]
    result["BOLL_LOW"] = [safe_float(v) for v in (boll_mid - 2 * boll_std)]

    # ── KDJ (34, 5, 10) ──
    low_min = low.rolling(34, min_periods=1).min()
    high_max = high.rolling(34, min_periods=1).max()
    rsv = (close - low_min) / (high_max - low_min + 1e-9) * 100
    k = rsv.ewm(alpha=1 / 5, adjust=False).mean()
    d = k.ewm(alpha=1 / 10, adjust=False).mean()
    j = 3 * k - 2 * d
    result["KDJ_K"] = [safe_float(v) for v in k]
    result["KDJ_D"] = [safe_float(v) for v in d]
    result["KDJ_J"] = [safe_float(v) for v in j]

    # ── 成交量均线 VOL10/30 ──
    result["VOL10"] = [safe_float(v) for v in vol.rolling(10).mean()]
    result["VOL30"] = [safe_float(v) for v in vol.rolling(30).mean()]

    return result, None


def calc_support_resistance(df: pd.DataFrame, indicators: dict) -> dict:
    """
    计算支撑位与阻力位
    方法：斐波那契回撤 + 枢轴点 + 均线 + 布林带
    """
    closes = pd.Series(indicators["closes"])
    recent_price = closes.iloc[-1]
    recent_high = df["high"].max()
    recent_low = df["low"].min()

    # ── 斐波那契 ──
    diff = recent_high - recent_low
    fib_levels = {
        "0%": round(recent_high, 3),
        "23.6%": round(recent_high - diff * 0.236, 3),
        "38.2%": round(recent_high - diff * 0.382, 3),
        "50.0%": round(recent_high - diff * 0.5, 3),
        "61.8%": round(recent_high - diff * 0.618, 3),
        "78.6%": round(recent_high - diff * 0.786, 3),
        "100%": round(recent_low, 3),
    }

    # ── 枢轴点 ──
    last = df.iloc[-1]
    pp = (last["high"] + last["low"] + last["close"]) / 3
    r1 = 2 * pp - last["low"]
    s1 = 2 * pp - last["high"]
    r2 = pp + (last["high"] - last["low"])
    s2 = pp - (last["high"] - last["low"])
    r3 = last["high"] + 2 * (pp - last["low"])
    s3 = last["low"] - 2 * (last["high"] - pp)

    # ── 收集全部价位 ──
    all_levels = []

    for label, val in fib_levels.items():
        all_levels.append({"label": f"斐波那契 {label}", "price": val, "type": "fib"})

    for label, val in [
        ("枢轴 R3", r3), ("枢轴 R2", r2), ("枢轴 R1", r1),
        ("枢轴 PP", pp),
        ("枢轴 S1", s1), ("枢轴 S2", s2), ("枢轴 S3", s3),
    ]:
        all_levels.append({"label": label, "price": round(val, 3), "type": "pivot"})

    for label, key in [("MA10", "MA10"), ("MA20", "MA20"), ("MA50", "MA50"), ("MA120", "MA120")]:
        arr = indicators.get(key, [])
        if arr and len(arr) > 0:
            val = safe_float(arr[-1])
            if val:
                all_levels.append({"label": label, "price": round(val, 3), "type": "ma"})

    for label, key in [("布林上轨", "BOLL_UP"), ("布林中轨", "BOLL_MID"), ("布林下轨", "BOLL_LOW")]:
        arr = indicators.get(key, [])
        if arr and len(arr) > 0:
            val = safe_float(arr[-1])
            if val:
                all_levels.append({"label": label, "price": round(val, 3), "type": "boll"})

    # ── 分离支撑/阻力 ──
    resistances = [l for l in all_levels if l["price"] > recent_price * 1.002]
    supports = [l for l in all_levels if l["price"] < recent_price * 0.998]
    resistances.sort(key=lambda x: x["price"])
    supports.sort(key=lambda x: x["price"], reverse=True)

    def _dedup(levels, eps=0.003):
        if not levels:
            return []
        result = [levels[0]]
        for l in levels[1:]:
            if l["price"] - result[-1]["price"] > eps:
                result.append(l)
        return result

    return {
        "price": round(recent_price, 3),
        "recent_high": round(recent_high, 3),
        "recent_low": round(recent_low, 3),
        "fib_levels": fib_levels,
        "resistances": _dedup(resistances)[:6],
        "supports": _dedup(supports)[:6],
    }


def calc_score(indicators: dict, df: pd.DataFrame = None) -> dict:
    """波段综合评分系统（±10 分制）"""
    closes = pd.Series(indicators["closes"])
    price = closes.iloc[-1]
    score = 0.0
    reasons = []

    # ── 均线 ──
    ma10 = safe_float(indicators["MA10"][-1])
    ma20 = safe_float(indicators["MA20"][-1])
    ma50 = safe_float(indicators["MA50"][-1])

    if ma10 and price > ma10:
        score += 1; reasons.append(("多", "价格站上MA10"))
    elif ma10:
        score -= 1; reasons.append(("空", "价格跌破MA10"))

    if ma20 and price > ma20:
        score += 1.5; reasons.append(("多", "价格站上MA20"))
    elif ma20:
        score -= 1.5; reasons.append(("空", "价格跌破MA20"))

    if ma50 and price > ma50:
        score += 2; reasons.append(("多", "价格站上MA50（中期偏多）"))
    elif ma50:
        score -= 2; reasons.append(("空", "价格跌破MA50（中期偏空）"))

    # MA10 金叉/死叉 MA50
    if len(indicators["MA10"]) >= 2:
        prev_ma10 = safe_float(indicators["MA10"][-2])
        prev_ma50 = safe_float(indicators["MA50"][-2])
        if prev_ma10 and prev_ma50 and ma10 and ma50:
            if prev_ma10 <= prev_ma50 and ma10 > ma50:
                score += 2.5; reasons.append(("强多", "MA10金叉MA50"))
            elif prev_ma10 >= prev_ma50 and ma10 < ma50:
                score -= 2.5; reasons.append(("强空", "MA10死叉MA50"))

    # ── MACD ──
    dif = safe_float(indicators["DIF"][-1])
    dea = safe_float(indicators["DEA"][-1])
    if dif is not None and dea is not None:
        score += 0.5 if dif > 0 else -0.5
        reasons.append(("弱多", "DIF>0") if dif > 0 else ("弱空", "DIF<0"))
        if dif > dea:
            score += 1; reasons.append(("多", "DIF在DEA上方（金叉状态）"))
        else:
            score -= 1; reasons.append(("空", "DIF在DEA下方（死叉状态）"))

    # ── RSI42 ──
    rsi42 = safe_float(indicators["RSI42"][-1])
    if rsi42 is not None:
        if rsi42 >= 65:
            score -= 1.5; reasons.append(("空", f"RSI42={rsi42:.1f} 偏高，注意回调"))
        elif rsi42 <= 30:
            score += 2; reasons.append(("强多", f"RSI42={rsi42:.1f} 超卖，波段底部可能"))
        else:
            reasons.append(("中性", f"RSI42={rsi42:.1f} 正常区间"))

    # ── 布林带 ──
    boll_up = safe_float(indicators["BOLL_UP"][-1])
    boll_mid = safe_float(indicators["BOLL_MID"][-1])
    boll_low = safe_float(indicators["BOLL_LOW"][-1])
    if boll_mid and price > boll_mid:
        score += 1; reasons.append(("多", "价格在布林中轨上方"))
    elif boll_mid:
        score -= 1; reasons.append(("空", "价格在布林中轨下方"))
    if boll_low and price < boll_low * 1.03:
        score += 1.5; reasons.append(("多", "价格接近布林下轨（超跌区域）"))
    if boll_up and price > boll_up * 0.97:
        score -= 1.5; reasons.append(("空", "价格接近布林上轨（超涨区域）"))

    # ── KDJ ──
    k_val = safe_float(indicators["KDJ_K"][-1])
    d_val = safe_float(indicators["KDJ_D"][-1])
    j_val = safe_float(indicators["KDJ_J"][-1])
    if j_val is not None:
        if j_val >= 80:
            score -= 1; reasons.append(("空", f"KDJ J值={j_val:.1f} 超买"))
        elif j_val <= 20:
            score += 1.5; reasons.append(("多", f"KDJ J值={j_val:.1f} 超卖"))
        else:
            reasons.append(("中性", f"KDJ J值={j_val:.1f} 中性"))
    if k_val is not None and d_val is not None:
        if k_val > d_val:
            score += 0.5; reasons.append(("弱多", "K线在D线上方"))
        else:
            score -= 0.5; reasons.append(("弱空", "K线在D线下方"))

    # ── 结论 ──
    if score >= 7:
        conclusion = "强烈做多"; suggestion = "可积极做多/持股待涨"; color = "#e84040"
    elif score >= 3:
        conclusion = "偏多"; suggestion = "可轻仓布局，设好止损"; color = "#e84040"
    elif score >= -3:
        conclusion = "中性震荡"; suggestion = "观望等待方向确认"; color = "#f5a623"
    elif score >= -7:
        conclusion = "偏空"; suggestion = "建议减仓或空仓规避"; color = "#21a366"
    else:
        conclusion = "强烈做空"; suggestion = "空仓观望，不参与"; color = "#21a366"

    return {
        "score": round(score, 1),
        "conclusion": conclusion,
        "suggestion": suggestion,
        "color": color,
        "reasons": reasons,
    }
