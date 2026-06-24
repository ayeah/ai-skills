---
name: bandstock-diagnosis
description: >
  波段诊股 — A股/ETF 波段技术分析工具。适用于 1~3 个月波段操作的全栈分析，
  涵盖 MA/MACD/RSI/布林带/KDJ 五大指标，输出支撑阻力位和操作建议。
  当用户要求分析 A 股或 ETF 技术面、获取波段操作建议、查看 K 线指标
  时使用此技能。启动 Flask 服务后通过浏览器访问 http://localhost:5000，
  输入代码即可获得实时分析。
agent_created: true
---

# 波段诊股 (BandStock Diagnosis)

A 股波段技术分析工具，所有指标参数针对 **1~3 个月波段操作** 优化。

## 何时使用

- 用户要求分析某只 A 股或 ETF 的技术指标
- 用户询问波段操作建议、支撑阻力位
- 用户希望可视化查看 K 线图 + 技术指标
- 用户输入格式如："分析 159851"、"帮我看下 600519"、"贵州茅台怎么样"

## 启动服务

### 1. 安装依赖

```bash
cd ~/./skills/bandstock-diagnosis/scripts
pip install -r requirements.txt
```

如果 `mootdx` 安装失败（仅用于股票列表同步，不影响核心分析），可跳过，
或手动安装：`pip install mootdx>=0.11.0`

### 2. 启动后端

```bash
cd ~/./skills/bandstock-diagnosis/scripts
.venv/bin/python app.py
```

服务默认运行在 `http://localhost:5000`，端口冲突时修改 `app.py` 末尾的 `port=5000`。

### 3. 访问

浏览器打开 `http://localhost:5000`，输入股票/ETF 代码即可分析。

也可以通过 URL 参数直达：
- `http://localhost:5000/?code=159851` — 金融科技ETF
- `http://localhost:5000/?code=600519` — 贵州茅台

## 技术指标参数

所有参数配置见 `references/indicators.md`，汇总如下：

| 指标 | 参数 | 波段逻辑 |
|------|------|----------|
| 均线 | MA10/20/50/120 | MA50≈2.5月趋势，MA120=半年大方向 |
| MACD | (19,39,9) | 延长EMA周期，过滤周内假信号 |
| RSI | (14,21,42) | RSI14经典摆荡，RSI42捕捉两月极端情绪 |
| 布林带 | (30,2) | 30日均线更平滑，带宽冲击更小 |
| KDJ | (34,5,10) | 慢速KDJ，平抑短期噪音 |
| 成交量 | VOL10/30 | 对齐波段时间框架 |

## 评分系统

综合评分 ±10 分制。阈值：≥7 强烈做多 | ≥3 偏多 | ≥-3 中性震荡 | ≥-7 偏空 | < -7 强烈做空。

评分权重最高的信号：
- MA10 金叉/死叉 MA50 (±2.5)
- RSI42 超卖/超买 (±2.0)
- 价格与 MA50 关系 (±2.0)

## 目录结构

```
bandstock-diagnosis/
├── SKILL.md                  # 本文件
├── references/
│   └── indicators.md         # 技术指标参数详细说明
└── scripts/
    ├── app.py                # Flask 服务入口
    ├── requirements.txt      # Python 依赖
    ├── src/
    │   ├── engine.py         # 分析引擎（指标计算、评分、支撑阻力）
    │   └── data.py           # 数据获取（K线、实时行情、股票列表）
    └── templates/
        └── index.html        # 前端界面（Chart.js 渲染）
```

## API 端点（智能体可直接调用）

| 端点 | 说明 |
|------|------|
| `GET /api/search?q=xxx` | 股票代码自动补全 |
| `GET /api/analyze?code=xxx` | 完整分析（JSON） |
| `GET /api/analyze/stream?code=xxx` | SSE 流式分析（含进度） |
| `GET /api/realtime?code=xxx` | 轻量实时行情 |

## 数据源

- K线日线：新浪财经 HTTP（优先）
- 实时行情：新浪 HTTP → 东方财富 HTTPS（备用）
- 股票列表：通达信 mootdx（1小时缓存）

## 注意事项

- 分析结果仅供参考，不构成投资建议
- 需要稳定的网络连接访问外部数据源
- 首次启动时股票列表同步可能需要 3-5 秒
- 非交易时段实时行情可能为空，此时使用 K 线最后价格
