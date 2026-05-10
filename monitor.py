import os
import re
import json
import subprocess
import requests
from datetime import datetime

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message}
        try: requests.post(url, json=payload, timeout=10)
        except: pass

def get_latest_versions():
    versions = {}
    
    # [순서 변경 1] Windows 11 24H2 (가장 먼저 수행)
    try:
        # 터미널 성공 로직을 파이썬 쉘에서 안전하게 실행하기 위해 구조화
        shell_cmd = (
            'curl -fsSL "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information" | '
            'sed -n "/24H2/,$p" | '
            'sed "s/<[^>]*>/ /g" | '
            'tr -d "\\n" | tr -s " "'
        )
        res = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True, timeout=20)
        
        if res.stdout:
            text = res.stdout.strip()
            parts = text.split()
            u_date, u_build, u_kb = "-", "-", "-"
            
            for i in range(len(parts)):
                # 'B' 업데이트 지점 탐색
                if parts[i] == 'B' and i > 0 and '-' in parts[i-1]:
                    window = parts[i+1 : i+11]
                    for item in window:
                        if u_date == "-" and re.match(r'^\d{4}-\d{2}-\d{2}$', item): u_date = item
                        if u_build == "-" and "26100." in item: u_build = item
                        if u_kb == "-" and "KB" in item and len(item) == 9: u_kb = item
                    if u_build != "-" and u_kb != "-": break
            
            versions['windows_11_24h2'] = {
                'version': f"Build {u_build} ({u_kb})",
                'date': u_date.replace('-', '/')
            }
    except: versions['windows_11_24h2'] = {'version': '오류', 'date': '-'}

    # [순서 변경 2] Microsoft Edge
    try:
        url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            v_m = re.search(r'Version\s+([\d.]+)', res.stdout)
            d_m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.stdout)
            d_str = "-"
            if d_m:
                try: d_str = datetime.strptime(d_m.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
                except: d_str = d_m.group(1)
            versions['edge'] = {'version': v_m.group(1) if v_m else "실패", 'date': d_str}
    except: versions['edge'] = {'version': '오류', 'date': '-'}

    # [순서 변경 3] Acrobat Reader
    try:
        url = "https://helpx.adobe.com/acrobat/release-note/release-notes-acrobat-reader.html"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=15)
        if res.stdout:
            v_match = re.search(r'title="(\d{2}\.\d{3}\.\d{5})', res.stdout)
            d_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', res.stdout)
            d_str = "-"
            if d_match:
                try: d_str = datetime.strptime(d_match.group(1).replace(',', ''), "%B %d %Y").strftime("%Y/%m/%d")
                except: d_str = d_match.group(1)
            versions['acrobat_reader'] = {'version': v_match.group(1) if v_match else "실패", 'date': d_str}
    except: versions['acrobat_reader'] = {'version': '오류', 'date': '-'}

    # [순서 변경 4] Bandizip
    try:
        url = "https://www.bandisoft.com/bandizip/history/"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            v = re.search(r'class="cell1">v?([\d.]+)<', res.stdout)
            d = re.search(r'class="cell2">([a-zA-Z]+\s+\d{1,2},\s+\d{4})<', res.stdout)
            d_str = "-"
            if d:
                try: d_str = datetime.strptime(d.group(1).strip(), '%b %d, %Y').strftime('%Y/%m/%d')
                except: d_str = d.group(1)
            versions['bandizip'] = {'version': v.group(1) if v else "실패", 'date': d_str}
    except: versions['bandizip'] = {'version': '오류', 'date': '-'}

    # [순서 변경 5] Chrome
    try:
        url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            versions['chrome'] = {'version': json.loads(res.stdout)['versions'][0]['version']}
    except: versions['chrome'] = {'version': '오류'}

    return versions

def main():
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            try: user_data = json.load(f)
            except: user_data = {}
    else: user_data = {}

    web_data = get_latest_versions() or {}
    changed_keys = []

    # 출력 및 처리 순서 정의
    display_order = [
        ('windows_11_24h2', '윈도우 보안 업데이트'),
        ('edge', 'Edge'),
        ('acrobat_reader', '아크로뱃리더'),
        ('bandizip', '반디집'),
        ('chrome', 'Chrome')
    ]

    for key, display_name in display_order:
        sw_info = web_data.get(key)
        if not sw_info or not isinstance(sw_info, dict): continue
            
        latest_v = sw_info.get('version', '')
        if any(x in latest_v for x in ["오류", "실패", "-", "None"]) or "Build - (-)" in latest_v:
            continue

        current_v = user_data.get(key, {}).get('version', '0')
        
        if latest_v != current_v:
            changed_keys.append(display_name)
            save_date = today if key == 'chrome' else sw_info.get('date', '-')
            user_data[key] = {"version": latest_v, "date": save_date}

    if changed_keys:
        report = "🔔 [S/W 업데이트 모니터링]\n\n"
        report += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        
        for key, display_name in display_order:
            info = user_data.get(key, {"version": "데이터 없음", "date": "-"})
            mark = "✅" if display_name in changed_keys else "ℹ️"
            date_label = "조회 날짜" if key == 'chrome' else "날짜"
            report += f"{mark} {display_name}\n- 버전: {info.get('version')}\n- {date_label}: {info.get('date')}\n\n"
        
        send_telegram_msg(report)
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
