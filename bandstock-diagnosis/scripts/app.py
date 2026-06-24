# -*- coding: utf-8 -*-
"""
波段诊股 - Flask 后端服务
路由层：搜索、分析（SSE流式）、实时行情
核心引擎 → src/engine.py  |  数据获取 → src/data.py
"""

import json
import time

from flask import Flask, jsonify, request, render_template, Response, stream_with_context
from flask_cors import CORS

from src.data import get_stock_list, fetch_kline, fetch_realtime
from src.engine import calc_indicators, calc_score, calc_support_resistance, BAND_PARAMS, safe_float

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)


# ═══════════════════════════════════════════════════════════
# SSE 工具函数
# ═══════════════════════════════════════════════════════════

def sse(event: str, data: dict) -> str:
    """构造 SSE 事件帧"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ═══════════════════════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    """股票/ETF 代码自动补全"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    stocks = get_stock_list()
    if not stocks:
        return jsonify({"results": []})

    q_lower = q.lower()
    results = []
    for s in stocks:
        if q_lower in s["code"].lower() or q_lower in s["name"].lower():
            results.append(s)
        if len(results) >= 20:
            break

    return jsonify({"results": results})


@app.route("/api/analyze")
def api_analyze():
    """完整分析（一次性返回）"""
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"error": "请输入股票/ETF代码"}), 400

    code = _normalize_code(code)
    try:
        rt = fetch_realtime(code)
        df = fetch_kline(code)
        if df.empty:
            return jsonify({"error": "无法获取行情数据，请检查代码是否正确"}), 500

        indicators, err = calc_indicators(df)
        if err:
            return jsonify({"error": err}), 500

        sr = calc_support_resistance(df, indicators)
        scoring = calc_score(indicators)

        last_price = indicators["closes"][-1] if indicators["closes"] else 0
        if rt is None:
            prev_close = indicators["closes"][-2] if len(indicators["closes"]) > 1 else last_price
            rt = {
                "code": code.split(".")[-1], "name": "",
                "price": last_price, "prev_close": prev_close,
                "open": last_price, "high": last_price, "low": last_price,
                "volume": 0, "amount": 0, "turnover": 0,
                "change": round(last_price - prev_close, 3),
                "change_pct": round((last_price - prev_close) / prev_close * 100, 2) if prev_close else 0,
            }

        return jsonify({
            "code": code, "name": rt.get("name", ""), "realtime": rt,
            "snapshot": _build_snapshot(indicators),
            "chart": _build_chart(indicators),
            "support_resistance": sr,
            "scoring": scoring,
            "params": BAND_PARAMS,
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"分析出错: {str(e)}"}), 500


@app.route("/api/analyze/stream")
def api_analyze_stream():
    """SSE 流式分析 — 实时推送进度"""
    code = request.args.get("code", "").strip()
    if not code:
        def err_gen():
            yield sse("error", {"msg": "请输入股票/ETF代码", "action": "请在上方搜索框中输入代码后重试"})
        return Response(err_gen(), mimetype="text/event-stream")

    code = _normalize_code(code)

    def generate():
        t0 = time.time()

        # ── 阶段 1: 实时行情 ──
        yield sse("progress", {"step": "realtime", "msg": f"⏳ 开始分析 {code}，正在获取实时行情...", "phase": "fetch"})
        try:
            rt = fetch_realtime(code)
            if rt and rt.get("name"):
                yield sse("progress", {
                    "step": "realtime_done",
                    "msg": f'✔ 实时行情获取成功：{rt["name"]} 当前价 ¥{rt["price"]}（{rt["change_pct"]:+.2f}%）',
                    "phase": "fetch",
                })
            else:
                yield sse("progress", {"step": "realtime_done", "msg": "⚠ 实时行情获取失败，将使用K线最后价格作为替代", "phase": "fetch", "level": "warn"})
        except Exception as e:
            yield sse("progress", {"step": "realtime_done", "msg": f"⚠ 实时行情接口异常：{str(e)[:80]}", "phase": "fetch", "level": "warn"})

        # ── 阶段 2: K线 ──
        yield sse("progress", {"step": "kline", "msg": "⏳ 正在下载K线日线数据（约150根日K）...", "phase": "fetch"})
        try:
            df = fetch_kline(code)
        except Exception as e:
            yield sse("error", {"msg": f"K线数据下载失败：{str(e)[:100]}", "action": "请检查网络连接后重试"})
            return

        if df.empty:
            yield sse("error", {"msg": "无法获取K线数据，该代码可能不存在或数据源暂时不可用", "action": "请确认代码正确，或稍后重试"})
            return

        yield sse("progress", {
            "step": "kline_done",
            "msg": f'✔ K线数据获取完成：{len(df)} 条日线记录，范围 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}',
            "phase": "fetch",
        })

        # ── 阶段 3: 指标计算 ──
        for step_msg in [
            ("calc_ma",   "  计算均线系统 MA10 / MA20 / MA50 / MA120 ..."),
            ("calc_macd", "  计算 MACD 指标 (19, 39, 9) ..."),
            ("calc_rsi",  "  计算 RSI 指标 (14 / 21 / 42) ..."),
            ("calc_boll", "  计算布林带 (30, 2) ..."),
            ("calc_kdj",  "  计算慢速 KDJ (34, 5, 10) ..."),
            ("calc_vol",  "  计算成交量均线 VOL10 / VOL30 ..."),
        ]:
            yield sse("progress", {"step": step_msg[0], "msg": step_msg[1], "phase": "calc"})

        indicators, err = calc_indicators(df)
        if err:
            yield sse("error", {"msg": err, "action": "数据量不足，请尝试其他股票代码"})
            return

        yield sse("progress", {"step": "calc_done", "msg": "✔ 全部技术指标计算完毕", "phase": "calc"})

        # ── 阶段 4: 支撑/阻力 ──
        yield sse("progress", {"step": "sr", "msg": "⏳ 正在计算支撑位与阻力位（斐波那契 + 枢轴点 + 均线 + 布林带）...", "phase": "calc"})
        sr = calc_support_resistance(df, indicators)
        yield sse("progress", {
            "step": "sr_done",
            "msg": f'✔ 支撑/阻力位计算完成：{len(sr.get("supports",[]))} 个支撑位，{len(sr.get("resistances",[]))} 个阻力位',
            "phase": "calc",
        })

        # ── 阶段 5: 评分 ──
        yield sse("progress", {"step": "score", "msg": "⏳ 正在生成综合评分与操作建议...", "phase": "score"})
        scoring = calc_score(indicators)
        s_val = scoring["score"]
        icon = "🟢" if s_val >= 3 else ("🟡" if s_val >= -3 else "🔴")
        yield sse("progress", {
            "step": "score_done",
            "msg": f'✔ 综合评分完成：{icon} {scoring["conclusion"]}（评分 {s_val:+.1f}）',
            "phase": "score",
        })

        # ── 组装 ──
        yield sse("progress", {"step": "assemble", "msg": "⏳ 正在组装结果数据...", "phase": "done"})

        last_price = indicators["closes"][-1] if indicators["closes"] else 0
        if rt is None:
            prev_close = indicators["closes"][-2] if len(indicators["closes"]) > 1 else last_price
            rt = {
                "code": code.split(".")[-1], "name": "",
                "price": last_price, "prev_close": prev_close,
                "open": last_price, "high": last_price, "low": last_price,
                "volume": 0, "amount": 0, "turnover": 0,
                "change": round(last_price - prev_close, 3),
                "change_pct": round((last_price - prev_close) / prev_close * 100, 2) if prev_close else 0,
            }

        total_elapsed = round(time.time() - t0, 2)
        yield sse("progress", {"step": "all_done", "msg": f"✨ 全部分析完成！总耗时 {total_elapsed}s", "phase": "done"})

        yield sse("result", {
            "code": code, "name": rt.get("name", ""), "realtime": rt,
            "snapshot": _build_snapshot(indicators),
            "chart": _build_chart(indicators),
            "support_resistance": sr,
            "scoring": scoring,
            "params": BAND_PARAMS,
            "elapsed": total_elapsed,
        })

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.route("/api/realtime")
def api_realtime():
    """轻量实时行情"""
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"error": "请输入代码"}), 400
    code = _normalize_code(code)
    rt = fetch_realtime(code)
    if rt:
        return jsonify({"success": True, "data": rt})
    return jsonify({"success": False, "error": "获取失败"}), 500


# ═══════════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════════

def _normalize_code(code: str) -> str:
    """标准化代码格式 → SH.xxxxxx / SZ.xxxxxx"""
    if "." in code:
        return code
    if code.startswith(("0", "3", "15", "16", "18", "20")):
        return f"SZ.{code}"
    return f"SH.{code}"


def _build_snapshot(indicators: dict) -> dict:
    """从指标序列提取最新快照"""
    keys = ["MA10", "MA20", "MA50", "MA120", "DIF", "DEA", "HIST",
            "RSI14", "RSI21", "RSI42",
            "BOLL_UP", "BOLL_MID", "BOLL_LOW",
            "KDJ_K", "KDJ_D", "KDJ_J"]
    snap = {}
    for k in keys:
        arr = indicators.get(k, [])
        val = safe_float(arr[-1]) if arr else None
        snap[k] = round(val, 4) if val is not None else None
    return snap


def _build_chart(indicators: dict) -> dict:
    """裁剪最近90天数据供前端绘图"""
    chart_keys = ["dates", "closes", "volumes",
                  "MA10", "MA20", "MA50", "MA120",
                  "DIF", "DEA", "HIST",
                  "RSI14", "RSI42",
                  "BOLL_UP", "BOLL_MID", "BOLL_LOW",
                  "KDJ_K", "KDJ_D", "KDJ_J"]
    return {k: indicators.get(k, [])[-90:] for k in chart_keys}


# ═══════════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("  波段诊股 v1.2 — 模块化架构")
    print("  访问 http://localhost:5000 开始使用")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
