import tushare as ts
import pandas as pd
import datetime
import time
import os
import sys
import unicodedata  # <--- 新增引用，用于处理中文字符宽度

# ==============================================================================
# 0. 配置区域
# ==============================================================================
# 【重要】请在此处填入您的 Tushare Token
TS_TOKEN = 'YOUR_TUSHARE_TOKEN'  # <-- 在此填入你的Token

# 2025年确切GDP总量 (万亿)
MANUAL_GDP_ESTIMATE = 140.19

# 历史风险参考值
RISK_MARGIN_PEAK_2015 = 2.27
RISK_BUFFETT_PEAK_2007 = 125
RISK_BUFFETT_PEAK_2015 = 110

# ==============================================================================
# 1. 终端颜色与工具
# ==============================================================================
os.system('') 
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'    # 危险/过热/收缩
    GREEN = '\033[92m'  # 安全/低估/扩张
    YELLOW = '\033[93m' # 警戒/过渡
    CYAN = '\033[96m'   # 标题
    WHITE = '\033[97m'
    GREY = '\033[90m'
    BLUE = '\033[94m'

def get_status_color(val, high, low, reverse=False):
    if val is None: return Colors.GREY
    if not reverse:
        return Colors.RED if val >= high else (Colors.YELLOW if val >= low else Colors.GREEN)
    else:
        return Colors.RED if val <= low else (Colors.YELLOW if val <= high else Colors.GREEN)

# ==============================================================================
# 2. Tushare 数据引擎
# ==============================================================================
class TushareEngine:
    def __init__(self, token):
        self.pro = ts.pro_api(token)
        self.start_month_macro = (datetime.datetime.now() - datetime.timedelta(days=400)).strftime('%Y%m')

    def get_latest_margin(self):
        print(f"{Colors.GREY}   正在获取两融数据 (强制双市校验)...{Colors.RESET}")
        for i in range(15):
            date_check = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y%m%d')
            try:
                df = self.pro.margin(trade_date=date_check)
                if not df.empty and len(df) >= 2: 
                    total_margin = df['rzye'].sum() / 1e12 # 万亿
                    return total_margin, date_check
            except: continue
        return None, None

    def get_market_metrics(self):
        print(f"{Colors.GREY}   正在计算全市场市值...{Colors.RESET}")
        try:
            for i in range(10):
                date_check = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%Y%m%d')
                df = self.pro.daily_basic(trade_date=date_check, fields='total_mv,circ_mv')
                if not df.empty:
                    t_mv = df['total_mv'].sum() / 1e8 
                    c_mv = df['circ_mv'].sum() / 1e8 
                    return {'total_mv': t_mv, 'float_mv': c_mv}
        except: pass
        return None

    def get_macro_data(self):
        print(f"{Colors.GREY}   正在获取宏观经济数据 (PMI/GDP/CPI/社融)...{Colors.RESET}")
        data = {}
        
        # 1. GDP
        try:
            df = self.pro.cn_gdp(start_q=self.start_month_macro[:4]+"Q1")
            if not df.empty:
                latest = df.iloc[0]
                data['gdp_yoy'] = float(latest['gdp_yoy'])
                data['gdp_quarter'] = latest['quarter']
                acc_gdp = float(latest['gdp']) / 10000
                if "Q4" in latest['quarter']: data['annual_gdp'] = acc_gdp
                else: data['annual_gdp'] = MANUAL_GDP_ESTIMATE
        except: 
            data['annual_gdp'] = MANUAL_GDP_ESTIMATE

        # 2. PMI
        try:
            df = self.pro.cn_pmi(start_m=self.start_month_macro, fields='month,pmi010000')
            if not df.empty: 
                data['pmi'] = float(df.iloc[0]['pmi010000'])
                data['pmi_month'] = df.iloc[0]['month']
        except: pass
        
        # 3. M1/M2
        try:
            df = self.pro.cn_m(start_m=self.start_month_macro)
            if not df.empty: 
                data['m1'] = float(df.iloc[0]['m1_yoy'])
                data['m2'] = float(df.iloc[0]['m2_yoy'])
                data['scissors'] = data['m1'] - data['m2']
        except: pass

        # 4. CPI/PPI
        try:
            df_c = self.pro.cn_cpi(start_m=self.start_month_macro)
            df_p = self.pro.cn_ppi(start_m=self.start_month_macro)
            if not df_c.empty: 
                data['cpi'] = float(df_c.iloc[0]['nt_yoy'])
                data['cpi_month'] = df_c.iloc[0]['month']
            if not df_p.empty: data['ppi'] = float(df_p.iloc[0]['ppi_yoy'])
        except: pass
        
        # 5. 社融
        try:
            df = self.pro.sf_month(start_m=self.start_month_macro)
            if not df.empty: data['sf_inc'] = float(df.iloc[0]['inc_month'])
        except: pass

        return data

# ==============================================================================
# 3. 智能研判逻辑 (Brain)
# ==============================================================================
def analyze_pmi(val):
    if val is None: return Colors.GREY, "无数据"
    if val > 50.0: return Colors.GREEN, "🟢 行业扩张 (利好)"
    elif val == 50.0: return Colors.YELLOW, "🟡 景气持平"
    else: return Colors.RED, "🔴 行业收缩 (利空)"

def analyze_scissors(val):
    if val is None: return Colors.GREY, "无数据"
    if val > 0: return Colors.GREEN, "🟢 资金活化 (牛市动力)"
    elif val > -5: return Colors.YELLOW, "🟡 存款定期化 (温和利空)"
    else: return Colors.RED, "🔴 流动性陷阱 (极差)"

def analyze_cpi(val):
    if val is None: return Colors.GREY, "无数据"
    if val < 0: return Colors.RED, "🔴 通缩 (需求不足)"
    elif val <= 3.0: return Colors.GREEN, "🟢 温和通胀 (健康)"
    else: return Colors.RED, "🔴 高通胀 (政策收紧)"

def analyze_ppi(val):
    if val is None: return Colors.GREY, "无数据"
    if val > 0: return Colors.GREEN, "🟢 工业回暖 (利润修复)"
    else: return Colors.YELLOW, "🟡 工业通缩 (利润承压)"

# ==============================================================================
# 4. 渲染工具 (核心修改区域：解决中文对齐问题)
# ==============================================================================

def get_display_width(s):
    """计算字符串的显示宽度 (中文=2, 英文=1)"""
    w = 0
    for char in s:
        # 'W' (Wide) 和 'F' (Full-width) 代表宽字符
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            w += 2
        else:
            w += 1
    return w

def pad_str(s, width, align='left'):
    """基于显示宽度的自动填充"""
    current_width = get_display_width(s)
    padding_len = max(0, width - current_width)
    padding = ' ' * padding_len
    
    if align == 'left':
        return s + padding
    elif align == 'right':
        return padding + s
    else: # center
        left_pad = padding_len // 2
        right_pad = padding_len - left_pad
        return ' ' * left_pad + s + ' ' * right_pad

def print_row(label, val_str, status_color, status_text):
    # 调整宽度配置: Label宽22, Val宽14
    label_padded = pad_str(label, 22, 'left')
    val_padded = pad_str(val_str, 14, 'right')
    print(f" {label_padded} │ {Colors.WHITE}{val_padded}{Colors.RESET} │ {status_color}{status_text}{Colors.RESET}")

def print_sub_row(label, val_str, status_text):
    # 子行缩进对齐
    label_padded = pad_str(label, 17, 'left')
    val_padded = pad_str(val_str, 14, 'right')
    print(f"    ↳ {label_padded} │ {Colors.GREY}{val_padded}{Colors.RESET} │ {Colors.GREY}{status_text}{Colors.RESET}")

def print_header(title):
    # 标题对齐 (总宽54)
    title_padded = pad_str(title, 54, 'left')
    print(f"{Colors.GREY} ┌──────────────────────┬────────────────┬──────────────────────┐{Colors.RESET}")
    print(f"{Colors.GREY} │ {Colors.BOLD}{title_padded}{Colors.GREY} │{Colors.RESET}")
    print(f"{Colors.GREY} ├──────────────────────┼────────────────┼──────────────────────┤{Colors.RESET}")

def print_footer():
    print(f"{Colors.GREY} └──────────────────────┴────────────────┴──────────────────────┘{Colors.RESET}")

# ==============================================================================
# 主程序
# ==============================================================================
def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    if TS_TOKEN == '请在这里填入您的Tushare_Token':
        print(f"{Colors.RED}错误：请先在代码第12行填入您的 Tushare Token！{Colors.RESET}")
        return

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{Colors.CYAN}{'='*66}")
    print(f" 📈 A股宏观风控终端 | {now_str}")
    print(f"{'='*66}{Colors.RESET}")

    ts_engine = TushareEngine(TS_TOKEN)
    
    # 获取数据
    margin_val, _ = ts_engine.get_latest_margin()
    mkt_metrics = ts_engine.get_market_metrics()
    macro = ts_engine.get_macro_data()

    # --- 开始渲染 ---
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Colors.CYAN}{'='*66}")
    print(f" 📈 A股宏观风控终端 (V2.4) | {now_str}")
    print(f"{'='*66}{Colors.RESET}")
    
    # 手动构建表头以匹配 print_row 的宽度逻辑
    # "核心指标" (22) | "数值" (14) | "智能研判..."
    h1 = pad_str("核心指标", 22)
    h2 = pad_str("数值", 14, 'right')
    print(f" {Colors.BOLD}{h1} │ {h2} │ 智能研判/历史对标{Colors.RESET}")

    # =========================================
    # 1. 资金杠杆 (Leverage)
    # =========================================
    print_header("🏛️  资金杠杆与情绪 (Leverage)")
    
    if margin_val and mkt_metrics:
        # 两融余额
        c_mb = get_status_color(margin_val, 2.0, 1.8)
        s_mb = "🔴 极度疯狂" if margin_val > 2.0 else ("🟡 情绪过热" if margin_val > 1.8 else "🟢 情绪温和")
        print_row("💰 两融余额", f"{margin_val:.2f} 万亿", c_mb, s_mb)
        
        # 占比
        margin_ratio = (margin_val / mkt_metrics['float_mv']) * 100
        c_mr = get_status_color(margin_ratio, 4.0, 3.0)
        s_mr = "🔴 杠杆爆表" if margin_ratio > 4.0 else ("🟡 杠杆偏高" if margin_ratio > 3.0 else "🟢 结构健康")
        print_row("📊 两融/流通市值比", f"{margin_ratio:.2f} %", c_mr, s_mr)
        
        print_footer()
        print(f"{Colors.GREY}   📚 2015牛市顶参考: 两融余额 2.27万亿 / 占比 4.5%{Colors.RESET}")
    else:
        print_row("数据获取失败", "---", Colors.RED, "检查接口")
        print_footer()

    # =========================================
    # 2. 经济景气度 (Growth) - 集成PMI与GDP
    # =========================================
    print_header("🏭 经济景气度 (Growth)")
    
    # 1. PMI (动态研判)
    pmi = macro.get('pmi')
    c_pmi, s_pmi = analyze_pmi(pmi)
    pmi_month = macro.get('pmi_month', '')[4:]
    print_row(f"🏭 制造业PMI ({pmi_month})", f"{pmi:.1f}", c_pmi, s_pmi)

    # 2. GDP 增速
    if 'gdp_yoy' in macro:
        val = macro['gdp_yoy']
        c_gdp = get_status_color(val, 6.0, 5.0, reverse=True)
        s_gdp = f"{macro.get('gdp_quarter','')} 增速"
        print_row("🌏 GDP同比增速", f"{val:.1f} %", c_gdp, s_gdp)
    else:
        print_row("🌏 GDP同比增速", "---", Colors.GREY, "数据待更新")
        
    print_footer()

    # =========================================
    # 3. 估值锚 (Valuation)
    # =========================================
    print_header("🌏 整体估值锚 (Valuation)")
    
    if mkt_metrics:
        total_mv = mkt_metrics['total_mv']
        gdp = macro.get('annual_gdp', MANUAL_GDP_ESTIMATE)
        
        print_row("📉 A股总市值", f"{total_mv:.2f} 万亿", Colors.WHITE, "---")
        print_row("🌏 2025年GDP总量", f"{gdp:.2f} 万亿", Colors.WHITE, "---")
        
        # 巴菲特指标
        buffett = (total_mv / gdp) * 100
        c_bf = get_status_color(buffett, 100, 80)
        
        if buffett > 120: s_bf = "🔴 07年级泡沫"
        elif buffett > 100: s_bf = "🔴 15年级泡沫"
        elif buffett > 80: s_bf = "🟡 估值偏高"
        else: s_bf = "🟢 估值安全"
        
        print_row("📏 市值/GDP (巴菲特)", f"{buffett:.1f} %", c_bf, s_bf)
        
        print_footer()
        # --- 历史参考 ---
        print(f"{Colors.GREY}   📚 历史大顶比值参考:{Colors.RESET}")
        print(f"{Colors.GREY}      • 2007年疯牛顶: ~{RISK_BUFFETT_PEAK_2007}%{Colors.RESET}")
        print(f"{Colors.GREY}      • 2015年疯牛顶: ~{RISK_BUFFETT_PEAK_2015}%{Colors.RESET}")
        print(f"{Colors.GREY}      • 底部安全区间: 40% - 60%{Colors.RESET}")
    else:
        print_footer()

    # =========================================
    # 4. 通胀与货币 (Inflation & Liquidity)
    # =========================================
    print_header("💸 通胀与货币 (Inflation & Money)")
    
    # 1. CPI (动态研判)
    cpi = macro.get('cpi')
    c_cpi, s_cpi = analyze_cpi(cpi)
    # 截取月份
    cpi_m_str = macro.get('cpi_month','')[4:]
    print_row(f"🛒 CPI同比 ({cpi_m_str})", f"{cpi:.1f} %", c_cpi, s_cpi)
    
    # 2. PPI (动态研判)
    ppi = macro.get('ppi')
    c_ppi, s_ppi = analyze_ppi(ppi)
    print_row("🏭 PPI同比", f"{ppi:.1f} %", c_ppi, s_ppi)

    # 3. 剪刀差 (动态研判)
    sci = macro.get('scissors')
    m2 = macro.get('m2')
    c_sci, s_sci = analyze_scissors(sci)
    
    print_row("✂️  M1-M2 剪刀差", f"{sci:.1f} %", c_sci, s_sci)
    if m2:
        print_sub_row("M2增速", f"{m2:.1f} %", "印钞速度")

    # 4. 社融
    if 'sf_inc' in macro:
        print_row("💧 社融当月增量", f"{macro['sf_inc']:.0f} 亿", Colors.WHITE, "信用扩张")

    print_footer()
    print(f"\n{Colors.CYAN}{'='*66}{Colors.RESET}")

if __name__ == "__main__":
    main()
    input("按回车键退出...")