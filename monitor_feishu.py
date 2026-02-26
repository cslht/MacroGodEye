import os
import sys
import datetime
import requests

# 确保能导入当前目录的已有模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import monitor_ashare as fa
import monitor_global as fg

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_FEISHU_WEBHOOK_URL" # <-- 替换为你自己的机器人Webhook

def push_to_feishu(md_content):
    """
    发送富文本卡片到飞书机器人
    参考自每天推送论文的逻辑
    """
    header = {"Content-Type": "application/json"}
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 宏观金融监控日报 | {now_str}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": md_content
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "上帝视角：A股与全球宏观风控自动生成"}
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=header, json=payload, timeout=10)
        res_json = response.json()
        if res_json.get("code") == 0:
            print("💡 推送飞书成功!")
        else:
            print("❌ 推送飞书失败，错误信息:", res_json)
    except Exception as e:
        print("❌ 推送飞书发生网络错误:", str(e))

def generate_report():
    """
    调用原有的采集引擎，生成 Markdown 格式的综合报告
    """
    print(">>> 正在抓取 A股 数据 (Tushare)...")
    # --- A股全面获取 ---
    ts_engine = fa.TushareEngine(fa.TS_TOKEN)
    margin_val, _ = ts_engine.get_latest_margin()
    mkt_metrics = ts_engine.get_market_metrics()
    macro = ts_engine.get_macro_data()

    a_share_md = "**🇨🇳 【A股风控雷达】**\n\n"
    
    # 1. 资金杠杆
    a_share_md += "*🏛️ 资金杠杆与情绪*\n"
    if margin_val and mkt_metrics:
        margin_ratio = (margin_val / mkt_metrics['float_mv']) * 100
        status_mb = "🔴 极度疯狂" if margin_val > 2.0 else ("🟡 情绪过热" if margin_val > 1.8 else "🟢 情绪温和")
        status_mr = "🔴 杠杆爆表" if margin_ratio > 4.0 else ("🟡 杠杆偏高" if margin_ratio > 3.0 else "🟢 结构健康")
        a_share_md += f"- **两融余额**: {margin_val:.2f}万亿 ({status_mb})\n"
        a_share_md += f"- **杠杆占比**: {margin_ratio:.2f}% ({status_mr})\n"
    else:
        a_share_md += "- **两融数据**: 获取失败\n"

    # 2. 经济景气度
    pmi = macro.get('pmi')
    pmi_month = macro.get('pmi_month', '')[4:]
    gdp_yoy = macro.get('gdp_yoy')
    a_share_md += "\n*🏭 经济景气度 (Growth)*\n"
    if pmi is not None:
        _, s_pmi = fa.analyze_pmi(pmi)
        a_share_md += f"- **制造业PMI({pmi_month})**: {pmi:.1f} ({s_pmi})\n"
    if gdp_yoy is not None:
        gdp_quarter = macro.get('gdp_quarter', '')
        a_share_md += f"- **GDP同比({gdp_quarter})**: {gdp_yoy:.1f}% \n"

    # 3. 估值锚
    total_mv = mkt_metrics['total_mv'] if mkt_metrics else None
    gdp = macro.get('annual_gdp', fa.MANUAL_GDP_ESTIMATE)
    a_share_md += "\n*🌏 整体估值锚 (Valuation)*\n"
    if total_mv:
        buffett = (total_mv / gdp) * 100
        if buffett > 120: s_bf = "🔴 07年泡沫"
        elif buffett > 100: s_bf = "🔴 15年泡沫"
        elif buffett > 80: s_bf = "🟡 估值偏高"
        else: s_bf = "🟢 估值安全"
        a_share_md += f"- **A股总市值**: {total_mv:.2f} 万亿\n"
        a_share_md += f"- **2025年GDP总量**: {gdp:.2f} 万亿\n"
        a_share_md += f"- **巴菲特指标**: {buffett:.1f}% ({s_bf})\n"

    # 4. 通胀与货币
    cpi = macro.get('cpi')
    ppi = macro.get('ppi')
    sci = macro.get('scissors')
    m2 = macro.get('m2')
    sf_inc = macro.get('sf_inc')
    
    a_share_md += "\n*💸 通胀与货币 (Inflation & Money)*\n"
    if cpi is not None:
        _, s_cpi = fa.analyze_cpi(cpi)
        a_share_md += f"- **CPI同比**: {cpi:.1f}% ({s_cpi})\n"
    if ppi is not None:
        _, s_ppi = fa.analyze_ppi(ppi)
        a_share_md += f"- **PPI同比**: {ppi:.1f}% ({s_ppi})\n"
    if sci is not None:
        _, s_sci = fa.analyze_scissors(sci)
        a_share_md += f"- **M1-M2剪刀差**: {sci:.1f}% ({s_sci})\n"
    if m2 is not None:
        a_share_md += f"- **M2增速**: {m2:.1f}% \n"
    if sf_inc is not None:
        a_share_md += f"- **社融当月增量**: {sf_inc:.0f} 亿\n"

    print(">>> 正在抓取 全球宏观 数据 (CNBC & FRED)...")
    # --- 全球全面获取 ---
    btc, btc_chg = fg.fetch_cnbc("BTC.CB=")
    gold, gold_chg = fg.fetch_cnbc("@GC.1")
    silver, silver_chg = fg.fetch_cnbc("@SI.1")
    copper, copper_chg = fg.fetch_cnbc("@HG.1")
    oil, oil_chg = fg.fetch_cnbc("@CL.1")
    
    us10y, us10y_chg = fg.fetch_cnbc("US10Y")
    us2y, us2y_chg = fg.fetch_cnbc("US2Y")
    jp10y, jp10y_chg = fg.fetch_cnbc("JP10Y")
    dxy, dxy_chg = fg.fetch_cnbc(".DXY")
    usdcnh, usdcnh_chg = fg.fetch_cnbc("CNH=")
    vix, vix_chg = fg.fetch_cnbc(".VIX")
    
    hy_spread, _ = fg.fetch_fred("BAMLH0A0HYM2")
    real_yield_10y, _ = fg.fetch_fred("DFII10")
    rrp_liq, _ = fg.fetch_fred("RRPONTSYD")

    global_md = "\n---\n**🌍 【全球周期罗盘】**\n\n"
    
    # 1. 周期罗盘
    global_md += "*🧭 周期罗盘*\n"
    cg_ratio = (copper * 100) / gold if (copper and gold) else None
    curve_10y2y = (us10y - us2y) * 100 if (us10y and us2y) else None
    
    if gold and cg_ratio:
        _, kw_txt = fg.analyze_kwave(gold, cg_ratio)
        global_md += f"- **康波周期**: {kw_txt} (铜金比: {cg_ratio:.2f})\n"
    if curve_10y2y is not None and hy_spread is not None:
        _, kz_txt = fg.analyze_kuznets(curve_10y2y, hy_spread)
        global_md += f"- **库兹涅茨(地产信用)**: {kz_txt} (利差: {curve_10y2y:.0f}bp)\n"
    if gold and dxy:
        _, dc_txt = fg.analyze_debt_cycle(gold, dxy)
        global_md += f"- **长期债务周期**: {dc_txt}\n"
    if vix and gold:
        _, ft_txt = fg.analyze_4th_turning(vix, gold)
        global_md += f"- **第四次转折(地缘)**: {ft_txt}\n"

    # 2. 宏观比价
    global_md += "\n*⚖️ 宏观比价*\n"
    if gold and silver:
        gs = gold / silver
        s_gs = "🔴 通缩/避险" if gs > 85 else ("🟡 需关注" if gs > 70 else "🟢 复苏/通胀")
        global_md += f"- **金银比 (G/S)**: {gs:.1f} ({s_gs})\n"
    if gold and oil:
        go = gold / oil
        s_go = "🔴 极度衰退/战争" if go > 50 else ("🟡 避险主导" if go > 30 else "🟢 需求正常")
        global_md += f"- **金油比 (Au/Oil)**: {go:.1f} ({s_go})\n"

    # 3. 流动性与债市
    global_md += "\n*💧 流动性与债市*\n"
    if real_yield_10y is not None:
        s_ry = "🟢 宽松/金牛" if real_yield_10y < 1.0 else "🔴 紧缩/杀估值"
        global_md += f"- **10Y真实利率**: {real_yield_10y:.2f}% ({s_ry})\n"
    if rrp_liq is not None:
        s_rrp = "🔴 流动性枯竭" if rrp_liq < 300 else "🟢 资金充裕"
        global_md += f"- **逆回购规模(RRP)**: {rrp_liq:,.0f} B ({s_rrp})\n"
    if us10y and jp10y:
        global_md += f"- **美日利差**: {(us10y - jp10y) * 100:.0f} bp\n"

    # 4. 风险与核心资产
    global_md += "\n*🅰️ 风险与核心资产*\n"
    s_dxy = "🔴 极度紧缩" if dxy and dxy > 106 else ("🟡 流动性紧" if dxy and dxy > 103 else "🟢 宽裕")
    global_md += f"- **美元指数(DXY)**: {dxy} ({s_dxy})\n"
    s_vix = "🔴 极度恐慌" if vix and vix > 30 else ("🟡 波动加剧" if vix and vix > 20 else "🟢 市场平稳")
    global_md += f"- **VIX恐慌指数**: {vix} ({s_vix})\n"
    
    global_md += f"- 🪙 **BTC**: ${btc:,.2f} | 🌕 **黄金**: ${gold:,.2f} | 🛢️ **原油**: ${oil:,.2f}\n"

    return a_share_md + global_md


if __name__ == '__main__':
    print("🚀 启动自动化数据汇总引擎...")
    md_text = generate_report()
    print("\n📦 成功组装汇报内容，准备推送到飞书终端...")
    push_to_feishu(md_text)
