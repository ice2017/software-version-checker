import os
import re
import json
import requests
import smtplib
import sys
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

# [보안 설정] 환경 변수에서 민감 정보 로드
EMAIL_ADDR = os.environ.get('EMAIL_ADDR')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
RECEIVER_ADDR = os.environ.get('RECEIVER_ADDR')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def send_email_msg(subject, body):
    if not all([EMAIL_ADDR, EMAIL_PASS, RECEIVER_ADDR]):
        print("⚠️ 이메일 환경변수 미설정으로 발송을 건너뜁니다.")
        return
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = EMAIL_ADDR
    msg['To'] = RECEIVER_ADDR
    
    try:
        # Gmail SMTP 서버 (SSL 방식)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDR, EMAIL_PASS)
            server.sendmail(EMAIL_ADDR, [RECEIVER_ADDR], msg.as_string())
            print("✉️ 이메일 리포트 발송 완료")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")

def get_latest_versions():
    versions = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # [1] Windows 11 24H2 보안 업데이트 (B타입 정기 패치 전용)
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            start_idx = res.text.find('id="release-information"')
            search_area = res.text[start_idx:] if start_idx != -1 else res.text
            rows = re.findall(r'<tr>(.*?)</tr>', search_area, re.DOTALL)
            for row in rows:
                clean_row = re.sub(r'<[^>]*>', ' ', row)
                clean_row = re.sub(r'\s+', ' ', clean_row).strip()
                
                # B 타입(정기 패치) 및 24H2 빌드(26100) 조건 확인
                is_b_type = ' B ' in f" {clean_row} " or 'Security Update' in clean_row
                if '26100.' in clean_row and is_b_type:
                    u_date = re.search(r'(\d{4}-\d{2}-\d{2})', clean_row)
                    u_build = re.search(r'(26100\.\d+)', clean_row)
                    u_kb = re.search(r'(KB\d{7})', clean_row)
                    if u_build and u_kb:
                        versions['windows_11_24h2'] = {
                            'version': f"Build {u_build.group(1)} ({u_kb.group(1)})",
                            'date': u_date.group(1).replace('-', '/') if u_date else "-"
                        }
                        break
        if 'windows_11_24h2' not in versions:
            versions['windows_11_24h2'] = {'version': 'B타입 미탐지', 'date': '-'}
    except:
        versions['windows_11_24h2'] = {'version': '파싱 오류', 'date': '-'}

    # [2] Microsoft Edge
    try:
        url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = requests.get(url, headers=headers, timeout=10)
        v_m = re.search(r'Version\s+([\d.]+)', res.text)
        d_m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.text)
        d_str = "-"
        if d_m:
            try: d_str = datetime.strptime(d_m.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
            except: d_str = d_m.group(1)
        versions['edge'] = {'version': v_m.group(1) if v_m else "실패", 'date': d_str}
    except:
        versions['edge'] = {'version': '오류', 'date': '-'}

    # [3] Acrobat Reader
    try:
        url = "https://helpx.adobe.com/acrobat/release-note/release-notes-acrobat-reader.html"
        res = requests.get(url, headers=headers, timeout=15)
        v_match = re.search(r'title="(\d{2}\.\d{3}\.\d{5})', res.text)
        d_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', res.text)
        d_str = "-"
        if d_match:
            try: d_str = datetime.strptime(d_match.group(1).replace(',', ''), "%B %d %Y").strftime("%Y/%m/%d")
            except: d_str = d_match.group(1)
        versions['acrobat_reader'] = {'version': v_match.group(1) if v_match else "실패", 'date': d_str}
    except:
        versions['acrobat_reader'] = {'version': '오류', 'date': '-'}

    # [4] Bandizip
    try:
        url = "https://www.bandisoft.com/bandizip/history/"
        res = requests.get(url, headers=headers, timeout=10)
        v = re.search(r'class="cell1">v?([\d.]+)<', res.text)
        d = re.search(r'class="cell2">([A-Za-z]{3}\s\d{1,2},\s\d{4})<', res.text)
        d_str = "-"
        if d:
            try: d_str = datetime.strptime(d.group(1).strip(), '%b %d, %Y').strftime('%Y/%m/%d')
            except: d_str = d.group(1)
        versions['bandizip'] = {'version': v.group(1) if v else "실패", 'date': d_str}
    except:
        versions['bandizip'] = {'version': '오류', 'date': '-'}

    # [5] Chrome
    try:
        url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            versions['chrome'] = {'version': res.json()['versions'][0]['version']}
    except:
        versions['chrome'] = {'version': '오류'}

    return versions

def main():
    force_report = "--report" in sys.argv
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            try: user_data = json.load(f)
            except: user_data = {}
    else:
        user_data = {}

    web_data = get_latest_versions()
    changed_keys = []
    
    display_order = [
        ('windows_11_24h2', 'Windows 11 24H2 보안 업데이트'),
        ('edge', 'Edge'),
        ('acrobat_reader', '아크로뱃리더'),
        ('bandizip', '반디집'),
        ('chrome', 'Chrome')
    ]

    for key, display_name in display_order:
        sw_info = web_data.get(key)
        if not sw_info: continue
        
        latest_v = sw_info.get('version', '')
        if any(x in str(latest_v) for x in ["오류", "실패", "미탐지"]): continue

        current_v = user_data.get(key, {}).get('version', '0')
        if latest_v != current_v:
            changed_keys.append(display_name)
            save_date = today if key == 'chrome' else sw_info.get('date', '-')
            user_data[key] = {"version": latest_v, "date": save_date}

    # 알림 발송 조건: 변동이 있거나, 9시 정기 보고 모드인 경우
    if changed_keys or force_report:
        title = "📢 [S/W 업데이트 모니터링 정기보고]" if force_report else "🔔 [S/W 업데이트 감지]"
        report = f"{title}\n\n"
        if changed_keys:
            report += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        
        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        for key, display_name in display_order:
            info = user_data.get(key, {"version": "데이터 없음", "date": "-"})
            mark = "✅" if display_name in changed_keys else "ℹ️"
            date_label = "조회 날짜" if key == 'chrome' else "날짜"
            report += f"{mark} {display_name}\n- 버전: {info.get('version')}\n- {date_label}: {info.get('date')}\n\n"
        
        # 메시지 전송
        send_telegram_msg(report)
        send_email_msg(f"{today} S/W 보안 업데이트 현황", report)
        
        # 파일 저장
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
