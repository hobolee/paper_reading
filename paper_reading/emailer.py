from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any


def _env_first(names: list[str] | str) -> str:
    if isinstance(names, str):
        names = [names]
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _recipients(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value or "") if item.strip()]


def _inline_styles(html: str, report_path: Path) -> str:
    link_patterns = [
        r'<link rel="stylesheet" href="assets/styles.css">\s*',
        r'<link rel="stylesheet" href="../assets/styles.css">\s*',
    ]
    css_path = report_path.parent / "assets" / "styles.css"
    if not css_path.exists():
        css_path = report_path.parent.parent / "assets" / "styles.css"
    if not css_path.exists():
        return html
    css = css_path.read_text(encoding="utf-8")
    style_tag = f"<style>\n{css}\n</style>\n"
    for pattern in link_patterns:
        html, count = re.subn(pattern, style_tag, html, count=1)
        if count:
            return html
    return html


def _absolutize_links(html: str, base_url: str) -> str:
    if not base_url:
        return html
    normalized_base = base_url.rstrip("/") + "/"

    def replace(match: re.Match[str]) -> str:
        attr = match.group(1)
        url = match.group(2)
        if re.match(r"^(https?:|mailto:|data:|#)", url):
            return match.group(0)
        cleaned = url.lstrip("./")
        while cleaned.startswith("../"):
            cleaned = cleaned[3:]
        return f'{attr}="{normalized_base}{cleaned}"'

    return re.sub(r'(href|src)="([^"]+)"', replace, html)


def _email_html(report_path: Path, report_url: str) -> str:
    html = report_path.read_text(encoding="utf-8")
    html = _inline_styles(html, report_path)
    html = _absolutize_links(html, report_url)
    if report_url:
        link = f'<p><a href="{report_url}">打开在线报告</a></p>'
        html = html.replace("</body>", f"{link}\n</body>")
    return html


def send_report_email(config: dict[str, Any], report_path: str | Path, run_date: str = "") -> None:
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled", True):
        print("Email disabled by configuration.")
        return

    username = _env_first(email_cfg.get("username_env") or ["GMAIL_USERNAME", "SMTP_USERNAME"])
    password = _env_first(email_cfg.get("password_env") or ["GMAIL_APP_PASSWORD", "SMTP_PASSWORD"])
    if email_cfg.get("provider") == "gmail-smtp":
        password = password.replace(" ", "")
    from_addr = _env_first(email_cfg.get("from_env") or ["MAIL_FROM"]) or username
    to_addrs = _recipients(_env_first(email_cfg.get("to_env") or ["MAIL_TO"]))
    if not username or not password or not from_addr or not to_addrs:
        raise RuntimeError(
            "Missing email settings. Set GMAIL_USERNAME, GMAIL_APP_PASSWORD, and MAIL_TO."
        )

    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"Report HTML not found: {path}")

    report_url = os.getenv("REPORT_URL", "")
    subject_prefix = str(email_cfg.get("subject_prefix") or "[Paper Reading]")
    subject_date = run_date or os.getenv("REPORT_DATE", "")
    subject = f"{subject_prefix} {subject_date}".strip()
    plain = "今日论文阅读报告已生成。"
    if report_url:
        plain += f"\n\n在线阅读：{report_url}"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = ", ".join(to_addrs)
    message.set_content(plain)
    message.add_alternative(_email_html(path, report_url), subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(
        str(email_cfg.get("host") or "smtp.gmail.com"),
        int(email_cfg.get("port") or 587),
        timeout=int(email_cfg.get("timeout_seconds") or 60),
    ) as server:
        if bool(email_cfg.get("use_tls", True)):
            server.starttls(context=context)
        server.login(username, password)
        server.send_message(message)
    print(f"Email sent to {', '.join(to_addrs)}.")
