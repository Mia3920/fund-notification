import os
import re
import json
import base64
import smtplib
import requests
import pandas as pd
from bs4 import BeautifulSoup
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
# 配置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
from io import BytesIO
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ============================================================
# 基金列表配置 - 在此修改您关注的基金
# 格式: {"code": "基金代码", "name": "基金名称"}
# ============================================================
FUND_LIST = [
    {"code": "968168", "name": "百达策略收益M人民币"},
    {"code": "968075", "name": "百达策略收益人民币"},
    {"code": "377240", "name": "摩根新兴动力混合A类"},
]

# 邮件配置（从环境变量读取，本地测试可直接填写）
EMAIL_USER = os.environ.get("EMAIL_USER", "")   # 163 邮箱地址
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")   # 163 邮箱授权码
EMAIL_TO   = os.environ.get("EMAIL_TO", "")     # 收件人邮箱


def fetch_fund_realtime(code: str) -> dict:
    """获取基金实时估值（天天基金网）"""
    url = f"https://fundgz.1234567.com.cn/js/{code}.js"
    headers = {"Referer": "https://fund.eastmoney.com/"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        # 响应格式: jsonpgz({...});
        match = re.search(r"jsonpgz\((\{.*?\})\)", resp.text)
        if match:
            data = json.loads(match.group(1))
            if data:  # 确保返回的数据不为空
                return data
    except Exception as e:
        print(f"[WARN] 获取实时估值失败 {code}: {e}")
    return {}


def fetch_fund_history(code: str, days: int = 30) -> pd.DataFrame:
    """获取基金历史净值（天天基金网 HTML 接口）"""
    url = f"https://fundf10.eastmoney.com/F10DataApi.aspx?type=lsjz&code={code}&page=1&per={days}"
    headers = {
        "Referer": "https://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        # 响应格式: var apidata={ content:"<table>...</table>", ... }
        match = re.search(r'content:"(.*?)",records:', resp.text, re.DOTALL)
        if not match:
            print(f"[WARN] 历史净值解析失败 {code}: 未找到 content 字段")
            return pd.DataFrame()
        html_table = match.group(1).replace('\\"', '"')
        soup = BeautifulSoup(html_table, "html.parser")
        rows = soup.select("tbody tr")
        records = []
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 4:
                records.append({
                    "date":       cols[0],
                    "nav":        cols[1],
                    "change_pct": cols[3].replace("%", ""),
                })
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        return df[["date", "nav", "change_pct"]]
    except Exception as e:
        print(f"[WARN] 获取历史净值失败 {code}: {e}")
    return pd.DataFrame()


def generate_chart(fund_name: str, history: pd.DataFrame) -> str:
    """生成净值走势图，返回 base64 编码的 PNG"""
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(history["date"], history["nav"], color="#1a73e8", linewidth=1.5)
    ax.fill_between(history["date"], history["nav"], alpha=0.1, color="#1a73e8")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=30, fontsize=8)
    plt.yticks(fontsize=8)
    ax.set_title(f"{fund_name} 近30日净值走势", fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_advice(history: pd.DataFrame) -> str:
    """基于历史净值生成简单投资建议"""
    if history.empty or len(history) < 5:
        return "数据不足，暂无建议"

    recent5 = history.tail(5)["change_pct"].dropna().tolist()
    nav_30d_start = history.iloc[0]["nav"]
    nav_latest    = history.iloc[-1]["nav"]

    if nav_30d_start and nav_30d_start != 0:
        gain_30d = (nav_latest - nav_30d_start) / nav_30d_start * 100
    else:
        gain_30d = 0

    if len(recent5) >= 5 and all(x > 0 for x in recent5):
        trend = "📈 近5日连续上涨，短期强势，可关注"
    elif len(recent5) >= 5 and all(x < 0 for x in recent5):
        trend = "📉 近5日连续下跌，短期弱势，谨慎操作"
    elif gain_30d > 5:
        trend = "✅ 近30日涨幅超5%，表现良好"
    elif gain_30d < -5:
        trend = "⚠️ 近30日跌幅超5%，表现较差"
    else:
        trend = "➡️ 近期震荡，建议持观望态度"

    return f"{trend}（近30日涨幅：{gain_30d:+.2f}%）"


def _calc_return(history: pd.DataFrame, days: int) -> str:
    """计算指定天数内的收益率"""
    if history.empty or len(history) < 2:
        return "N/A"
    subset = history.tail(days)
    if len(subset) < 2:
        return "N/A"
    start = subset.iloc[0]["nav"]
    end   = subset.iloc[-1]["nav"]
    if start and start != 0:
        return f"{(end - start) / start * 100:+.2f}%"
    return "N/A"


def build_html_email(funds_data: list) -> str:
    """构建 HTML 邮件内容"""
    today = datetime.now().strftime("%Y年%m月%d日")

    rows_html = ""
    charts_html = ""

    for fd in funds_data:
        name     = fd["name"]
        code     = fd["code"]
        rt       = fd.get("realtime", {})
        history  = fd.get("history", pd.DataFrame())
        advice   = fd.get("advice", "")
        chart_b64 = fd.get("chart", "")

        # 实时估值字段
        dwjz  = rt.get("dwjz", "—")   # 单位净值（最新公布）
        jzrq  = rt.get("jzrq", "")    # 净值日期
        gsz   = rt.get("gsz", "—")    # 估算净值
        gszzl = rt.get("gszzl", "—")  # 估算涨跌幅
        gztime = rt.get("gztime", "")

        try:
            gszzl_f = float(gszzl)
            color = "#d32f2f" if gszzl_f >= 0 else "#388e3c"
            gszzl_str = f'<span style="color:{color}">{gszzl_f:+.2f}%</span>'
        except (ValueError, TypeError):
            gszzl_str = gszzl

        ret_1w  = _calc_return(history, 5)
        ret_1m  = _calc_return(history, 21)
        ret_3m  = _calc_return(history, 63)

        rows_html += f"""
        <tr>
          <td>{name}</td>
          <td>{code}</td>
          <td><strong>{dwjz}</strong><br/><span style="font-size:11px;color:#999">{jzrq}</span></td>
          <td><strong>{gsz}</strong></td>
          <td>{gszzl_str}</td>
          <td>{ret_1w}</td>
          <td>{ret_1m}</td>
          <td>{ret_3m}</td>
          <td style="font-size:12px;color:#555">{advice}</td>
        </tr>"""

        if chart_b64:
            charts_html += f"""
        <div style="margin:20px 0">
          <h3 style="margin-bottom:6px;color:#333">{name}（{code}）</h3>
          <img src="data:image/png;base64,{chart_b64}"
               style="max-width:100%;border:1px solid #e0e0e0;border-radius:4px" />
          <p style="margin-top:6px;font-size:13px;color:#555">{advice}</p>
        </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         color: #333; max-width: 900px; margin: 0 auto; padding: 20px; }}
  h1   {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th   {{ background: #1a73e8; color: #fff; padding: 8px 12px; text-align: left; font-size: 13px; }}
  td   {{ padding: 8px 12px; border-bottom: 1px solid #e0e0e0; font-size: 13px; }}
  tr:hover td {{ background: #f5f9ff; }}
  .footer {{ margin-top: 30px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 10px; }}
</style>
</head>
<body>
  <h1>基金净值日报 · {today}</h1>
  <p style="color:#666;font-size:13px">数据来源：天天基金网 | 估值时间仅供参考，以基金公司公布为准</p>

  <table>
    <thead>
      <tr>
        <th>基金名称</th><th>代码</th><th>单位净值</th><th>估算净值</th><th>今日涨跌</th>
        <th>近1周</th><th>近1月</th><th>近3月</th><th>投资建议</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <h2 style="color:#333;margin-top:30px">净值走势图</h2>
  {charts_html}

  <div class="footer">
    本报告由 GitHub Actions 自动生成，仅供参考，不构成投资建议。
    投资有风险，入市需谨慎。
  </div>
</body>
</html>"""
    return html


def send_email(html: str, subject: str) -> None:
    """通过 163 SMTP 发送 HTML 邮件"""
    if not all([EMAIL_USER, EMAIL_PASS, EMAIL_TO]):
        raise ValueError("邮件配置不完整，请检查 EMAIL_USER / EMAIL_PASS / EMAIL_TO")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.163.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_TO.split(","), msg.as_string())
    print(f"[OK] 邮件已发送至 {EMAIL_TO}")


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    funds_data = []

    for fund in FUND_LIST:
        code = fund["code"]
        name = fund["name"]
        print(f"[INFO] 处理基金: {name} ({code})")

        realtime = fetch_fund_realtime(code)
        history  = fetch_fund_history(code, days=90)  # 多取一些用于3月收益计算

        # 如果实时API返回空（海外基金等），用历史数据填充
        if not realtime and not history.empty:
            print(f"[INFO] 实时数据为空，使用历史数据填充 {code}")
            latest = history.iloc[-1]
            realtime = {
                "fundcode": code,
                "name": name,
                "dwjz": str(latest["nav"]),
                "jzrq": latest["date"].strftime("%Y-%m-%d"),
                "gsz": str(latest["nav"]),
                "gszzl": str(latest["change_pct"]) if pd.notna(latest["change_pct"]) else "0",
                "gztime": latest["date"].strftime("%Y-%m-%d"),
            }

        advice   = generate_advice(history)

        chart_b64 = ""
        if not history.empty:
            chart_b64 = generate_chart(name, history.tail(30))

        funds_data.append({
            "code":     code,
            "name":     name,
            "realtime": realtime,
            "history":  history,
            "advice":   advice,
            "chart":    chart_b64,
        })

    html    = build_html_email(funds_data)
    subject = f"基金净值日报 {today}"
    send_email(html, subject)


if __name__ == "__main__":
    main()
