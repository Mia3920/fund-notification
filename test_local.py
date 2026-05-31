#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""本地测试脚本 - 不发送邮件，仅生成 HTML 预览"""

import os
os.environ['EMAIL_USER'] = 'test@163.com'
os.environ['EMAIL_PASS'] = 'test'
os.environ['EMAIL_TO'] = 'test@example.com'

from fund_report import *

def main():
    print("=" * 60)
    print("基金数据获取测试")
    print("=" * 60)

    funds_data = []

    for fund in FUND_LIST:
        code = fund["code"]
        name = fund["name"]
        print(f"\n[INFO] 处理基金: {name} ({code})")

        realtime = fetch_fund_realtime(code)
        if realtime:
            print(f"  ✓ 实时估值: {realtime.get('gsz', 'N/A')} ({realtime.get('gszzl', 'N/A')}%)")
        else:
            print(f"  ✗ 实时估值获取失败")

        history = fetch_fund_history(code, days=90)

        # 如果实时API返回空（海外基金等），用历史数据填充
        if not realtime and not history.empty:
            print(f"  ℹ 使用历史数据填充实时信息")
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
            print(f"  ✓ 单位净值: {realtime['dwjz']} (日期: {realtime['jzrq']})")

        if not history.empty:
            print(f"  ✓ 历史数据: {len(history)} 条 ({history.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {history.iloc[-1]['date'].strftime('%Y-%m-%d')})")
            advice = generate_advice(history)
            print(f"  ✓ 投资建议: {advice}")
            chart_b64 = generate_chart(name, history.tail(30))
            print(f"  ✓ 走势图生成成功 (base64 长度: {len(chart_b64)})")
        else:
            print(f"  ✗ 历史数据获取失败")
            advice = "数据不足，暂无建议"
            chart_b64 = ""

        funds_data.append({
            "code": code,
            "name": name,
            "realtime": realtime,
            "history": history,
            "advice": advice,
            "chart": chart_b64,
        })

    print("\n" + "=" * 60)
    print("生成 HTML 邮件预览")
    print("=" * 60)

    html = build_html_email(funds_data)
    output_file = "preview.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✓ HTML 邮件已保存到: {output_file}")
    print(f"  用浏览器打开查看效果")
    print("\n提示: 配置好邮箱信息后，运行 python fund_report.py 即可发送邮件")

if __name__ == "__main__":
    main()
