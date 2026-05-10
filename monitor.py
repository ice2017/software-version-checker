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
    
    # [1] Windows 11 24H2 (파이썬 내부 문자열 처리로 우회 - 가장 안전)
    try:
        # 정규표현식이 깨지는 grep 대신, 텍스트만 뽑아서 파이썬이 직접 처리합니다.
        cmd = (
            'curl -fsSL "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information" | '
            'sed -n "/24H2/,$p" | sed "s/<[^>]*>/ /g" | tr -s " "'
        )
        res = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        
        if res:
            parts = res.split()
            u_date, u_build, u_kb = "-", "-", "-"
            # 터미널 결과와 동일하게 'B' 타입을 기점으로 데이터 세트 탐색
            for i, word in enumerate(parts):
                if word == "B" and i > 0 and len(parts[i-1]) == 7: # 2026-04 B 형태
                    # B 지점 이후 10개 단어 내에서 날짜, 빌드, KB 획득
                    window = parts[i+1 : i+11]
                    for item in window:
                        if u_date == "-" and re.match(r'^\d{4}-\d{2}-\d{2}$', item): u_date = item
                        if u_build == "-" and item.startswith("26100."): u_build = item
                        if u_kb == "-" and item.startswith("KB") and len(item) == 9: u_kb = item
                    if u_build != "-" and u_kb != "-": break
            
            versions['windows_11_24h2'] = {
                'version': f"Build {u_build} ({u_kb})",
                'date': u_date.replace('-', '/')
            }
    except: versions['windows_11_24h2'] = {'version': '파싱 실패', 'date': '-'}

    # [2] Microsoft Edge
    try:
        url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        v_m = re.search(r'Version\s+([\d.]+)', res.stdout)
        d_m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.stdout)
        d_str = "-"
        if d_m:
            try: d_str = datetime.strptime(d_m.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
            except: d_str = d_m.group(1)
        versions['edge'] = {'version': v_m.group(1) if v_m else "실패", 'date': d_str}
    except: versions['edge'] = {'version': '오류', 'date': '-'}

    # [3] Acrobat Reader
    try:
        url = "https://helpx.adobe.com/acrobat/release-note/release-notes-acrobat-reader.html"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=15)
        v_match = re.search(r'title="(\d{2}\.\d{3}\.\d{5})', res.stdout)
        d_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', res.stdout)
        d_str = "-"
        if d_match:
            try: d_str = datetime.strptime(d_match.group(1).replace(',', ''), "%B %d %Y").strftime("%Y/%m/%d")
            except: d_str = d_match.group(1)
        versions['acrobat_reader'] = {'version': v_match.group(1) if v_match else "실패", 'date': d_str}
    except: versions['acrobat_reader'] = {'version': '오류', 'date': '-'}

    # [4] Bandizip
    try:
        url = "https://www.bandisoft.com/bandizip/history/"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        v = re.search(r'class="cell1">v?([\d.]+)<', res.stdout)
        d = re.search(r'class="cell2">([A-Za-z]{3}\s\d{1,2},\s\d{4})<', res.stdout)
        d_str = "-"
        if d:
            try: d_str = datetime.strptime(d.group(1).strip(), '%b %d, %Y').strftime('%Y/%m/%d')
            except: d_str = d.group(1)
        versions['bandizip'] = {'version': v.group(1) if v else "실패", 'date': d_str}
    except: versions['bandizip'] = {'version': '오류', 'date': '-'}

    # [5] Chrome
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

    if 'acrobat' in user_data: del user_data['acrobat']

    web_data = get_latest_versions() or {}
    changed_keys = []
    
    # [순서 보장] 요청하신 출력 순서
    display_order = [
        ('windows_11_24h2', '윈도우 보안 업데이트'),
        ('edge', 'Edge'),
        ('acrobat_reader', '아크로뱃리더'),
        ('bandizip', '반디집'),
        ('chrome', 'Chrome')
    ]

    for key, display_name in display_order:
        sw_info = web_data.get(key)
        if not sw_info: continue
        
        latest_v = sw_info.get('version', '')
        if any(x in latest_v for x in ["오류", "실패", "파싱 실패"]): continue

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
