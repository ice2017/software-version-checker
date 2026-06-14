import os
import re
import json
import requests
import smtplib
import sys
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timedelta

EMAIL_ADDR      = os.environ.get('EMAIL_ADDR')
EMAIL_PASS      = os.environ.get('EMAIL_PASS')
RECEIVER_ADDR   = os.environ.get('RECEIVER_ADDR')
TELEGRAM_TOKEN  = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID= os.environ.get('TELEGRAM_CHAT_ID')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=10)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def send_email_msg(subject, body):
    if not all([EMAIL_ADDR, EMAIL_PASS, RECEIVER_ADDR]):
        print("이메일 환경변수 미설정으로 발송을 건너뜁니다.")
        return
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From']    = EMAIL_ADDR
    msg['To']      = RECEIVER_ADDR
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDR, EMAIL_PASS)
            server.sendmail(EMAIL_ADDR, [RECEIVER_ADDR], msg.as_string())
            print("이메일 발송 완료")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def get_sw_versions():
    versions = {}

    # Windows 11 24H2
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            rows = re.findall(r'<tr>(.*?)</tr>', res.text, re.DOTALL)
            for row in rows:
                clean = re.sub(r'<[^>]*>', ' ', row)
                clean = re.sub(r'\s+', ' ', clean).strip()
                if '26100.' in clean and ' B ' in f" {clean} ":
                    u_date  = re.search(r'(\d{4}-\d{2}-\d{2})', clean)
                    u_build = re.search(r'(26100\.\d+)', clean)
                    u_kb    = re.search(r'(KB\d{7})', clean)
                    if u_build and u_kb:
                        versions['windows_11_24h2'] = {
                            'version': f"Build {u_build.group(1)} ({u_kb.group(1)})",
                            'date': u_date.group(1).replace('-', '/') if u_date else '-'
                        }
                        break
            if 'windows_11_24h2' not in versions:
                build = re.search(r'(26100\.\d+)', res.text)
                versions['windows_11_24h2'] = {
                    'version': f"Build {build.group(1)}" if build else 'B타입 미탐지',
                    'date': '-'
                }
        else:
            versions['windows_11_24h2'] = {'version': f'HTTP {res.status_code}', 'date': '-'}
    except Exception as e:
        versions['windows_11_24h2'] = {'version': f'오류: {e}', 'date': '-'}

    # Microsoft Edge
    try:
        res = requests.get("https://edgeupdates.microsoft.com/api/products", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for product in res.json():
                if product.get('Product') == 'Stable':
                    for release in product.get('Releases', []):
                        if release.get('Platform') == 'Windows' and release.get('Architecture') == 'x64':
                            pub = release.get('PublishedTime', '')
                            versions['edge'] = {
                                'version': release.get('ProductVersion', '실패'),
                                'date': pub[:10].replace('-', '/') if pub else '-'
                            }
                            break
                    break
        if 'edge' not in versions:
            versions['edge'] = {'version': '실패', 'date': '-'}
    except Exception as e:
        versions['edge'] = {'version': f'오류: {e}', 'date': '-'}

    # Google Chrome
    try:
        res = requests.get(
            "https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Windows&num=1",
            headers=HEADERS, timeout=10
        )
        if res.status_code == 200:
            data = res.json()[0]
            ts = data.get('time', 0)
            versions['chrome'] = {
                'version': data.get('version', '실패'),
                'date': datetime.utcfromtimestamp(ts / 1000).strftime('%Y/%m/%d') if ts else '-'
            }
        else:
            versions['chrome'] = {'version': f'HTTP {res.status_code}', 'date': '-'}
    except Exception as e:
        versions['chrome'] = {'version': f'오류: {e}', 'date': '-'}

    # Bandizip
    try:
        res = requests.get("https://www.bandisoft.com/bandizip/history/", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            v = re.search(r'<div class="cell1">v?([\d.]+)</div>', res.text)
            d = re.search(r'<div class="cell2">([A-Za-z]+ \d{1,2}, \d{4})</div>', res.text)
            d_str = '-'
            if d:
                try:
                    d_str = datetime.strptime(d.group(1).strip(), '%B %d, %Y').strftime('%Y/%m/%d')
                except:
                    d_str = d.group(1)
            versions['bandizip'] = {
                'version': v.group(1) if v else '실패',
                'date': d_str
            }
        else:
            versions['bandizip'] = {'version': f'HTTP {res.status_code}', 'date': '-'}
    except Exception as e:
        versions['bandizip'] = {'version': f'오류: {e}', 'date': '-'}

    return versions

def get_rocky_errata():
    results = []
    cutoff  = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    for ver in ['Rocky Linux 8', 'Rocky Linux 9']:
        for severity in ['Critical', 'Important']:
            try:
                url = (
                    f"https://errata.rockylinux.org/api/v2/advisories"
                    f"?filters.product={requests.utils.quote(ver)}"
                    f"&filters.type=Security"
                    f"&filters.severity={severity}"
                    f"&pageSize=50"
                )
                res = requests.get(url, headers=HEADERS, timeout=15)
                if res.status_code != 200:
                    continue
                for a in res.json().get('advisories', []):
                    pub = a.get('publishedAt', '')[:10]
                    if pub < cutoff:
                        continue
                    cves = [c.get('name', '') for c in a.get('cves', [])]
                    max_score = 0.0
                    for c in a.get('cves', []):
                        try:
                            score = float(c.get('cvss3BaseScore', 0))
                            if score > max_score:
                                max_score = score
                        except:
                            pass
                    results.append({
                        'name'    : a.get('name', ''),
                        'product' : ver,
                        'severity': severity,
                        'synopsis': a.get('synopsis', ''),
                        'date'    : pub,
                        'cves'    : cves,
                        'score'   : max_score
                    })
            except Exception as e:
                print(f"Rocky 에라타 오류 [{ver}/{severity}]: {e}")

    results.sort(key=lambda x: x['date'], reverse=True)
    return results

def get_cisa_kev():
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    try:
        res = requests.get(
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            headers=HEADERS, timeout=15
        )
        if res.status_code != 200:
            return []
        data = res.json()
        recent = [v for v in data.get('vulnerabilities', []) if v.get('dateAdded', '') >= cutoff]
        recent.sort(key=lambda x: x.get('dateAdded', ''), reverse=True)
        return recent
    except Exception as e:
        print(f"CISA KEV 오류: {e}")
        return []

def build_report(sw_data, sw_changed, rocky_errata, cisa_kev, force_report):
    today   = datetime.now().strftime('%Y/%m/%d')
    title   = "[보안 모니터링 정기보고]" if force_report else "[보안 모니터링 업데이트 감지]"
    report  = f"{title} {today}\n"
    report += "=" * 50 + "\n\n"

    display_order = [
        ('windows_11_24h2', 'Windows 11 24H2'),
        ('edge',            'Microsoft Edge'),
        ('chrome',          'Google Chrome'),
        ('bandizip',        'Bandizip'),
    ]

    # SW 업데이트 현황
    report += "【 S/W 업데이트 현황 】\n"
    report += "─" * 40 + "\n"
    for key, label in display_order:
        info = sw_data.get(key, {'version': '데이터 없음', 'date': '-'})
        mark = "🆕" if label in sw_changed else "ℹ️"
        report += f"{mark} {label}\n"
        report += f"   버전: {info.get('version')}\n"
        report += f"   날짜: {info.get('date', '-')}\n\n"

    # Rocky Linux 에라타
    report += "【 Rocky Linux 보안 에라타 (최근 30일) 】\n"
    report += "─" * 40 + "\n"
    if rocky_errata:
        # Critical 먼저, 그 다음 Important
        for sev, mark in [('Critical', '🔴'), ('Important', '🟠')]:
            items = [a for a in rocky_errata if a['severity'] == sev]
            if items:
                report += f"\n[{sev}] {len(items)}건\n"
                for a in items:
                    score_str = f" (CVSS {a['score']})" if a['score'] > 0 else ""
                    report += f"{mark} [{a['product']}] {a['name']} | {a['date']}{score_str}\n"
                    report += f"   {a['synopsis']}\n"
                    if a['cves']:
                        report += f"   CVE: {', '.join(a['cves'])}\n"
                    report += "\n"
    else:
        report += "   해당 기간 내 에라타 없음\n\n"

    # CISA KEV
    report += "【 CISA KEV 신규 등록 (최근 30일) 】\n"
    report += "─" * 40 + "\n"
    if cisa_kev:
        report += f"총 {len(cisa_kev)}건\n\n"
        for v in cisa_kev:
            report += f"⚠️  {v.get('cveID')} | {v.get('dateAdded')} | {v.get('vendorProject')} - {v.get('product')}\n"
            desc = v.get('shortDescription', '')
            if desc:
                report += f"   {desc}\n"
            due = v.get('dueDate', '')
            if due:
                report += f"   조치 기한: {due}\n"
            report += "\n"
    else:
        report += "   해당 기간 내 신규 등록 없음\n\n"

    report += "=" * 50 + "\n"
    report += f"수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    return report

def main():
    force_report   = "--report" in sys.argv
    debug          = "--debug" in sys.argv
    user_data_file = "versions.json"
    today          = datetime.now().strftime("%Y/%m/%d")

    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            try:
                user_data = json.load(f)
            except:
                user_data = {}
    else:
        user_data = {}

    print("SW 버전 수집 중...")
    sw_data    = get_sw_versions()
    sw_changed = []

    display_order = [
        ('windows_11_24h2', 'Windows 11 24H2'),
        ('edge',            'Microsoft Edge'),
        ('chrome',          'Google Chrome'),
        ('bandizip',        'Bandizip'),
    ]

    for key, label in display_order:
        info     = sw_data.get(key, {})
        latest_v = info.get('version', '')
        if any(x in str(latest_v) for x in ['오류', '실패', '미탐지', 'HTTP']):
            continue
        current_v = user_data.get(key, {}).get('version', '')
        if latest_v != current_v:
            sw_changed.append(label)
            user_data[key] = {'version': latest_v, 'date': info.get('date', '-')}

    print("Rocky Linux 에라타 수집 중...")
    rocky_errata = get_rocky_errata()

    print("CISA KEV 수집 중...")
    cisa_kev = get_cisa_kev()

    if debug:
        print("\n=== SW 버전 ===")
        for key, label in display_order:
            info = sw_data.get(key, {})
            print(f"  {label}: {info.get('version')} ({info.get('date', '-')})")
        print(f"\n=== Rocky 에라타: {len(rocky_errata)}건 ===")
        for a in rocky_errata[:5]:
            print(f"  [{a['product']}] {a['name']} | {a['severity']} | {a['date']}")
        print(f"\n=== CISA KEV: {len(cisa_kev)}건 ===")
        for v in cisa_kev[:5]:
            print(f"  {v.get('cveID')} | {v.get('dateAdded')} | {v.get('vendorProject')} - {v.get('product')}")
        print("\n=== 리포트 미리보기 ===")
        print(build_report(sw_data, sw_changed, rocky_errata, cisa_kev, force_report))
        return

    if sw_changed or force_report:
        report = build_report(sw_data, sw_changed, rocky_errata, cisa_kev, force_report)
        send_telegram_msg(report)
        send_email_msg(f"{today} 보안 모니터링 정기보고", report)
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)
        print(f"완료 - SW 변경: {sw_changed if sw_changed else '없음'}, Rocky 에라타: {len(rocky_errata)}건, CISA KEV: {len(cisa_kev)}건")
    else:
        print("SW 변경 없음 - 발송 건너뜀 (--report 옵션으로 강제 발송 가능)")

if __name__ == "__main__":
    main()
