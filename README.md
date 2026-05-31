# 基金净值通知工具

每个工作日自动发送基金净值日报到指定邮箱，包含当日估算净值、涨跌幅、近30日走势图和投资建议。

## 快速开始

### 1. Fork 本仓库

点击右上角 **Fork** 按钮，将仓库复制到你的 GitHub 账号下。

### 2. 配置 GitHub Secrets

进入你 Fork 后的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，依次添加：

| Secret 名称  | 说明                                      |
|-------------|-------------------------------------------|
| `EMAIL_USER` | 163 邮箱地址，例如 `yourname@163.com`      |
| `EMAIL_PASS` | 163 邮箱**授权码**（非登录密码，见下方说明）|
| `EMAIL_TO`   | 收件人邮箱，多个用英文逗号分隔              |

> **如何获取 163 授权码：**
> 登录 163 邮箱 → 设置 → POP3/SMTP/IMAP → 开启 SMTP 服务 → 按提示获取授权码

### 3. 修改基金列表

编辑 `fund_report.py` 顶部的 `FUND_LIST`：

```python
FUND_LIST = [
    {"code": "110011", "name": "易方达中小盘混合"},
    {"code": "161725", "name": "招商中证白酒指数"},
    # 添加更多基金...
]
```

基金代码可在 [天天基金网](https://fund.eastmoney.com/) 搜索获取。

### 4. 启用 Actions

进入仓库 → **Actions** → 如提示启用，点击 **I understand my workflows, go ahead and enable them**。

---

## 触发时间

- **自动触发**：每个工作日北京时间 15:05（A 股收盘后）
- **手动触发**：Actions → Daily Fund Report → Run workflow

---

## 本地测试

### 方式一：生成 HTML 预览（推荐，无需邮箱配置）

```bash
pip install -r requirements.txt
python test_local.py
```

会生成 `preview.html` 文件，用浏览器打开查看邮件效果。

### 方式二：实际发送邮件测试

```bash
pip install -r requirements.txt

export EMAIL_USER="yourname@163.com"
export EMAIL_PASS="your_auth_code"
export EMAIL_TO="recipient@example.com"

python fund_report.py
```

---

## 邮件内容

- 所有基金的估算净值、今日涨跌幅、近1周/1月/3月收益汇总表
- 每只基金近30日净值走势图
- 基于涨跌趋势的简单投资建议

> 数据来源：天天基金网（eastmoney）公开接口，仅供参考，不构成投资建议。
