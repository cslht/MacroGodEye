import requests
import urllib3
import time
import re
import datetime
import os
import sys
import unicodedata
import threading
import itertools

# 禁用SSL安全警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# 0. 终端配置与排版常量
# ==============================================================================
os.system('') # 激活Windows终端颜色

# --- 布局常量 ---
COL_W_LABEL = 24   # 标签列
COL_W_VAL = 22     # 数值列
COL_W_CHG = 10     # 涨跌幅列

class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'    # 涨/危险/衰退
    GREEN = '\033[92m'  # 跌/安全/增长
    YELLOW = '\033[93m' # 平/警告
    BLUE = '\033[94m'   # 【修复】新增蓝色 (用于康波冬)
    MAGENTA = '\033[95m'# 比特币/特殊
    CYAN = '\033[96m'   # 标题
    WHITE = '\033[97m'
    GREY = '\033[90m'

def get_str_width(s):
    """精确计算字符串显示宽度"""
    width = 0
    for char in s:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width

def pad_label(s, target_width):
    """智能填充标签列"""
    current_width = get_str_width(s)
    spaces = target_width - current_width
    return s + " " * max(0, spaces)

# ==============================================================================
# 1. 动态加载动画
# ==============================================================================
done = False
def animate_loading():
    chars = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    while not done:
        sys.stdout.write(f'\r{Colors.GREY} {next(chars)} 正在连接全球金融市场...{Colors.RESET}')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * 40 + '\r')

# ==============================================================================
# 2. 网络设置 (直连 + 重试)
# ==============================================================================
_original_request = requests.Session.request
def _patched_request(self, method, url, *args, **kwargs):
    kwargs['verify'] = False
    kwargs['proxies'] = {"http": None, "https": None}
    if 'timeout' not in kwargs: kwargs['timeout'] = 10
    return _original_request(self, method, url, *args, **kwargs)
requests.Session.request = _patched_request

def fetch_with_retry(url, parser_func, retries=3):
    for i in range(retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers)
            result = parser_func(res.text)
            if result[0] is not None: return result
        except: pass
        if i < retries - 1: time.sleep(0.5)
    return None, None

# ==============================================================================
# 3. 数据解析逻辑
# ==============================================================================
def parse_cnbc(text):
    price, pct = None, None
    match_price = re.search(r'"last":"(\d+\.?\d*)"', text)
    if match_price: price = float(match_price.group(1))
    
    match_pct = re.search(r'"change_pct":"(.*?)"', text)
    if match_pct:
        try: pct = float(match_pct.group(1).replace('%', ''))
        except: pct = 0.0
            
    if price is None:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, 'html.parser')
        tag = soup.find("span", class_="QuoteStrip-lastPrice")
        if tag: price = float(tag.text.strip().replace('%', '').replace(',', ''))
            
    return price, pct

def parse_fred(text):
    match = re.search(r'series-meta-observation-value">\s*([\d\.,]+)', text)
    if match: 
        raw_str = match.group(1).replace(',', '')
        return float(raw_str), None
    return None, None

def fetch_cnbc(symbol):
    return fetch_with_retry(f"https://www.cnbc.com/quotes/{symbol}", parse_cnbc)

def fetch_fred(series_id):
    return fetch_with_retry(f"https://fred.stlouisfed.org/series/{series_id}", parse_fred)

# ==============================================================================
# 4. 渲染工具
# ==============================================================================
def format_value_str(val, unit):
    if val is None: return "---"
    val_fmt = f"{val:,.2f}"
    if unit == '$': return f"{val_fmt} $"
    if unit == '%': return f"{val_fmt}%"
    if unit == 'bp': return f"{val_fmt} bp"
    if unit == 'B':  return f"$ {val:,.0f} B"
    return val_fmt

def format_change_str(pct):
    if pct is None: return "---", Colors.GREY
    if pct > 0: return f"+{pct:.2f}%", Colors.RED
    if pct < 0: return f"{pct:.2f}%", Colors.GREEN
    return f" {pct:.2f}%", Colors.WHITE

def get_status_color(val, high_risk=True, thresholds=(20, 30)):
    if val is None: return Colors.GREY
    t1, t2 = thresholds
    if high_risk:
        return Colors.GREEN if val < t1 else (Colors.YELLOW if val < t2 else Colors.RED)
    else:
        return Colors.GREEN if val > t2 else (Colors.YELLOW if val > t1 else Colors.RED)

def print_row(label, val, pct, unit, status_color, status_text):
    lbl_str = pad_label(label, COL_W_LABEL)
    val_combined = format_value_str(val, unit)
    val_final = f"{Colors.WHITE}{val_combined:>{COL_W_VAL}}{Colors.RESET}"
    pct_str_raw, pct_col = format_change_str(pct)
    pct_final = f"{pct_col}{pct_str_raw:>{COL_W_CHG}}{Colors.RESET}"
    print(f" {lbl_str} │ {val_final} │ {pct_final} │ {status_color}{status_text}{Colors.RESET}")

def print_sub_row(label, val_str, info_text, color=Colors.GREY):
    lbl_str = pad_label(label, COL_W_LABEL)
    vis_width = get_str_width(val_str)
    padding = " " * max(0, COL_W_VAL - vis_width)
    val_final = f"{color}{padding}{val_str}{Colors.RESET}"
    pct_placeholder = f"{' ':{COL_W_CHG}}"
    print(f" {lbl_str} │ {val_final} │ {pct_placeholder} │ {color}{info_text}{Colors.RESET}")

def print_category_header(title):
    l1 = '─' * COL_W_LABEL
    l2 = '─' * (COL_W_VAL + 2)
    l3 = '─' * (COL_W_CHG + 2)
    l4 = '─' * 22
    print(f"{Colors.GREY} ┌{l1}┴{l2}┴{l3}┴{l4}┐{Colors.RESET}")
    print(f" {Colors.BOLD}{title}{Colors.RESET}")

# ==============================================================================
# 5. 周期与逻辑判断模型
# ==============================================================================
def analyze_kwave(gold, cg_ratio):
    """康波周期判断"""
    if gold is None or cg_ratio is None: return Colors.GREY, "数据不足"
    # 逻辑：金价极高(>3000) 且 铜金比极低(<0.15) = 滞胀/萧条 (康波冬)
    if gold > 3000 and cg_ratio < 0.15:
        return Colors.BLUE, "❄️ 康波冬 (秩序重建)" # 这里使用了 Colors.BLUE
    elif cg_ratio > 0.25:
        return Colors.GREEN, "🌱 康波春 (复苏繁荣)"
    else:
        return Colors.YELLOW, "🍂 康波秋 (衰退过渡)"

def analyze_kuznets(curve_10y2y, hy_spread):
    """库兹涅茨(地产/信用)周期判断"""
    if curve_10y2y is None or hy_spread is None: return Colors.GREY, "数据不足"
    if curve_10y2y > 50 and hy_spread > 4.0:
        return Colors.YELLOW, "🟡 信用去杠杆 (下行)"
    elif hy_spread > 8.0:
        return Colors.RED, "🔴 信用崩塌 (危机)"
    elif curve_10y2y < 0:
        return Colors.RED, "🛑 信贷收缩 (前夜)"
    else:
        return Colors.GREEN, "🟢 信用扩张 (上行)"

def analyze_debt_cycle(gold, dxy):
    """长期债务周期判断"""
    if gold is None or dxy is None: return Colors.GREY, "数据不足"
    if gold > 3500:
        return Colors.RED, "💀 货币信用危机"
    elif dxy > 105 and gold > 2500:
        return Colors.YELLOW, "⚠️ 大去杠杆末期"
    else:
        return Colors.GREEN, "🟢 债务温和扩张"

def analyze_4th_turning(vix, gold):
    """第四次转折 (社会/地缘)"""
    if vix is None or gold is None: return Colors.GREY, "数据不足"
    if gold > 3000 and vix < 20:
        return Colors.RED, "🔴 秩序重组/地缘风险"
    elif vix > 30:
        return Colors.RED, "💥 冲突爆发 (危机)"
    else:
        return Colors.GREEN, "🟢 秩序相对稳定"

# ==============================================================================
# 主程序
# ==============================================================================
def main():
    global done
    sys.stdout.write('\033[?25l')
    
    t = threading.Thread(target=animate_loading)
    t.start()
    
    try:
        # --- 基础资产 ---
        btc, btc_chg = fetch_cnbc("BTC.CB=")
        gold, gold_chg = fetch_cnbc("@GC.1")
        silver, silver_chg = fetch_cnbc("@SI.1")
        copper, copper_chg = fetch_cnbc("@HG.1")
        oil, oil_chg = fetch_cnbc("@CL.1")

        # --- 利率 ---
        us10y, us10y_chg = fetch_cnbc("US10Y")
        us2y, us2y_chg = fetch_cnbc("US2Y")
        jp10y, jp10y_chg = fetch_cnbc("JP10Y")

        # --- 宏观数据 ---
        dxy, dxy_chg = fetch_cnbc(".DXY")
        usdcnh, usdcnh_chg = fetch_cnbc("CNH=")
        vix, vix_chg = fetch_cnbc(".VIX")
        
        # FRED 数据
        hy_spread, _ = fetch_fred("BAMLH0A0HYM2")
        real_yield_10y, _ = fetch_fred("DFII10")
        rrp_liq, _ = fetch_fred("RRPONTSYD")

    finally:
        done = True
        t.join()

    # --- 渲染 ---
    os.system('cls' if os.name == 'nt' else 'clear')
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    TOTAL_WIDTH = COL_W_LABEL + COL_W_VAL + COL_W_CHG + 22 + 9
    print(f"{Colors.CYAN}{'='*TOTAL_WIDTH}")
    title = f"📊 全能金融监控 (v2.0)  |  {now_str}"
    padding = (TOTAL_WIDTH - get_str_width(title)) // 2
    print(f"{' '*padding}{title}")
    print(f"{'='*TOTAL_WIDTH}{Colors.RESET}")

    h_lbl = pad_label(" 指标名称", COL_W_LABEL)
    h_val = f"{'数值':>{COL_W_VAL}}"
    h_chg = f"{'日内':>{COL_W_CHG}}"
    print(f"{Colors.BOLD}{h_lbl} │ {h_val} │ {h_chg} │ 状态评估{Colors.RESET}")

    # 1. 周期罗盘
    print_category_header("🧭 周期罗盘 (Historical Cycles)")
    cg_ratio = (copper * 100) / gold if (copper and gold) else None
    curve_10y2y = (us10y - us2y) * 100 if (us10y and us2y) else None
    
    kw_col, kw_txt = analyze_kwave(gold, cg_ratio)
    print_row("🌊 康波周期 (K-Wave)", None, None, "", kw_col, kw_txt)
    
    kz_col, kz_txt = analyze_kuznets(curve_10y2y, hy_spread)
    print_row("🏠 库兹涅茨 (地产信用)", None, None, "", kz_col, kz_txt)
    
    dc_col, dc_txt = analyze_debt_cycle(gold, dxy)
    print_row("💸 长期债务周期 (Dalio)", None, None, "", dc_col, dc_txt)
    
    ft_col, ft_txt = analyze_4th_turning(vix, gold)
    print_row("⚔️  第四次转折 (Howe)", None, None, "", ft_col, ft_txt)

    # 2. 核心资产
    print_category_header("🅰️  核心资产 (Risk & Commodities)")
    print_row("🪙 比特币 (BTC)", btc, btc_chg, "$", Colors.MAGENTA, "数字黄金")
    print_row("🌕 黄金 (Gold)", gold, gold_chg, "$", Colors.WHITE, "---")
    print_row("🌑 白银 (Silver)", silver, silver_chg, "$", Colors.WHITE, "---")
    print_row("🔩 铜 (Copper)", copper, copper_chg, "$", Colors.WHITE, "---")
    print_row("🛢️ 原油 (WTI)", oil, oil_chg, "$", Colors.WHITE, "---")

    # 3. 宏观比价
    print_category_header("🅱️  宏观比价 (Macro Ratios)")
    if gold and silver:
        gs = gold / silver
        c = get_status_color(gs, True, (70, 85))
        s = "🔴 通缩/避险" if gs > 85 else ("🟡 需关注" if gs > 70 else "🟢 复苏/通胀")
        print_row("⚖️  金银比 (G/S)", gs, None, "", c, s)
    if gold and oil:
        go = gold / oil
        c = get_status_color(go, True, (30, 50))
        s = "🔴 极度衰退/战争" if go > 50 else ("🟡 避险主导" if go > 30 else "🟢 需求正常")
        print_row("🛢️ 金油比 (Au/Oil)", go, None, "", c, s)
    if cg_ratio:
        c = get_status_color(cg_ratio, False, (0.15, 0.20))
        s = "🟢 经济周期强" if cg_ratio > 0.20 else ("🟡 增长放缓" if cg_ratio > 0.15 else "🔴 衰退风险")
        print_row("🏭 铜金比 (Cu/Au)", cg_ratio, None, "", c, s)
    if gold and copper:
        gc = gold / copper
        c = get_status_color(gc, True, (650, 750))
        s = "🔴 避险爆表" if gc > 750 else ("🟡 避险升温" if gc > 650 else "🟢 情绪稳定")
        print_row("🪙 金铜比 (Au/Cu)", gc, None, "", c, s)

    # 4. 流动性
    print_category_header("💧 流动性与通胀 (Liquidity)")
    if real_yield_10y is not None:
        c = Colors.GREEN if real_yield_10y < 0.5 else (Colors.RED if real_yield_10y > 2.0 else Colors.YELLOW)
        s = "🟢 利率宽松/金牛" if real_yield_10y < 1.0 else "🔴 紧缩/杀估值"
        print_row("🛡️ 10Y真实利率(TIPS)", real_yield_10y, None, "%", c, s)
    else:
        print_row("🛡️ 10Y真实利率(TIPS)", None, None, "%", Colors.GREY, "FRED数据缺失")

    if rrp_liq is not None:
        c = Colors.RED if rrp_liq < 300 else Colors.GREEN
        s = "🔴 流动性枯竭" if rrp_liq < 300 else "🟢 资金充裕"
        print_row("🏦 逆回购规模(RRP)", rrp_liq, None, "B", c, s)
    else:
        print_row("🏦 逆回购规模(RRP)", None, None, "B", Colors.GREY, "FRED数据缺失")

    # 5. 债市利率
    print_category_header("🆎 债市利率 (Bonds & Rates)")
    print_row("🇺🇸 美债 10Y", us10y, us10y_chg, "%", Colors.WHITE, "---")
    print_row("🇺🇸 美债 2Y", us2y, us2y_chg, "%", Colors.WHITE, "---")
    print_row("🇯🇵 日债 10Y", jp10y, jp10y_chg, "%", Colors.WHITE, "---")

    if us10y and jp10y:
        spread = (us10y - jp10y) * 100
        print_row("📊 美日利差", spread, None, "bp", Colors.CYAN, "资金流向")

    if curve_10y2y is not None:
        c = get_status_color(curve_10y2y, False, (0, 10))
        if curve_10y2y < 0:
            print_row("📉 10Y-2Y 利差", curve_10y2y, None, "bp", c, "🔴 倒挂中")
            start_date = datetime.date(2022, 7, 5)
            days = (datetime.date.today() - start_date).days
            print_sub_row("   ↳ ⚠️ 当前倒挂累计", f"{days}天", "衰退预警", Colors.RED)
        else:
            print_row("📈 10Y-2Y 利差", curve_10y2y, None, "bp", c, "🟢 正常陡峭")
            print_sub_row("   ↳ 🏛️ 历史倒挂纪录", "793天", "2022-2024", Colors.GREY)

    # 6. 风险风向
    print_category_header("🅾️  风险风向 (Risk & FX)")
    c_dxy = get_status_color(dxy, True, (103, 106))
    s_dxy = "🔴 极度紧缩" if dxy and dxy > 106 else ("🟡 流动性紧" if dxy and dxy > 103 else "🟢 宽裕")
    print_row("💵 美元指数 (DXY)", dxy, dxy_chg, "", c_dxy, s_dxy)
    c_cnh = get_status_color(usdcnh, True, (7.10, 7.30))
    s_cnh = "🔴 贬值压力" if usdcnh and usdcnh > 7.30 else ("🟡 汇率承压" if usdcnh and usdcnh > 7.10 else "🟢 汇率稳健")
    print_row("💴 USD/CNH (离岸)", usdcnh, usdcnh_chg, "", c_cnh, s_cnh)
    c_vix = get_status_color(vix, True, (20, 30))
    s_vix = "🔴 极度恐慌" if vix and vix > 30 else ("🟡 波动加剧" if vix and vix > 20 else "🟢 市场平稳")
    print_row("😰 VIX 恐慌指数", vix, vix_chg, "", c_vix, s_vix)
    c_hy = get_status_color(hy_spread, True, (5, 10))
    s_hy = "🔴 违约爆发" if hy_spread and hy_spread > 10 else ("🟡 信用收紧" if hy_spread and hy_spread > 5 else "🟢 风险低") if hy_spread is not None else "---"
    print_row("🧨 高收益债利差", hy_spread, None, "%", c_hy, s_hy)

    # 底部横线
    l1 = '─' * COL_W_LABEL
    l2 = '─' * (COL_W_VAL + 2)
    l3 = '─' * (COL_W_CHG + 2)
    l4 = '─' * 22
    print(f"{Colors.GREY} └{l1}┴{l2}┴{l3}┴{l4}┘{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*TOTAL_WIDTH}{Colors.RESET}\n")
    sys.stdout.write('\033[?25h')

if __name__ == "__main__":
    main()