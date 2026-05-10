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
    
    # 1. Chrome
    try:
        url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            versions['chrome'] = {'version': json.loads(res.stdout)['versions'][0]['version']}
    except: versions['chrome'] = {'version': '오류'}

    # 2. Microsoft Edge
    try:
        url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            v_m = re.search(r'Version\s+([\d.]+)', res.stdout)
            d_m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.stdout)
            d_str = "-"
            if d_m:
                try: d_str = datetime.strptime(d_m.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
                except: pass
            versions['edge'] = {'version': v_m.group(1) if v_m else "실패", 'date': d_str}
    except: versions['edge'] = {'version': '오류', 'date': '-'}

    # 3. Bandizip
    try:
        url = "https://www.bandisoft.com/bandizip/history/"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            pattern = r'class="cell1">v?([\d.]+)<[\s\S]*?class="cell2">([a-zA-Z]+\s+\d{1,2},\s+\d{4})<'
            match = re.search(pattern, res.stdout)
            if match:
                v = match.group(1).strip()
                try: d = datetime.strptime(match.group(2).strip(), '%b %d, %Y').strftime('%Y/%m/%d')
                except: d = match.group(2)
                versions['bandizip'] = {'version': v, 'date': d}
    except: versions['bandizip'] = {'version': '오류', 'date': '-'}

    # 4. Acrobat Reader (보내주신 curl 소스 기반 고정)
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

    # 5. Windows 11 24H2 (터미널 검증 로직 이식)
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=15)
        if res.stdout:
            # 24H2 섹션 분리
            content_24h2 = res.stdout.split("24H2")[-1]
            # 태그 제거 및 줄바꿈/연속공백을 단일 공백으로 통합 (터미널의 tr -d '\n' 효과)
            clean_text = ' '.join(re.sub(r'<[^>]*>', ' ', content_24h2).split())

            # 터미널에서 성공한 정규표현식 패턴
            pattern = r'(\d{4}-\d{2}\s+B)\s+(\d{4}-\d{2}-\d{2})\s+(26100\.\d+)\s+(KB\d{7})'
            match = re.search(pattern, clean_text)
            
            if match:
                u_type, u_date, u_build, u_kb = match.groups()
                versions['windows_11_24h2'] = {
                    'version': f"Build {u_build} ({u_kb})",
                    'date': u_date.replace('-', '/')
                }
            else:
                versions['windows_11_24h2'] = {'version': '매칭 실패', 'date': '-'}
    except:
        versions['windows_11_24h2'] = {'version': '오류', 'date': '-'}

def main():
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
    else: user_data = {}

    if 'acrobat' in user_data: del user_data['acrobat']

    web_data = get_latest_versions()
    changed_keys = []
    targets = ['chrome', 'edge', 'bandizip', 'acrobat_reader', 'windows_11_24h2']

    for name in targets:
        if name in web_data and "오류" not in web_data[name].get('version', '') and "실패" not in web_data[name].get('version', ''):
            latest_v = web_data[name]['version']
            current_v = user_data.get(name, {}).get('version', '0')
            
            # 버전이 '-'인 경우도 업데이트 감지에서 제외
            if latest_v != "-" and latest_v != current_v:
                changed_keys.append(name.upper().replace('_', ' '))
                save_date = today if name == 'chrome' else web_data[name].get('date', '-')
                user_data[name] = {"version": latest_v, "date": save_date}

    if changed_keys:
        report = "🔔 [S/W 업데이트 모니터링 최종 정합성 리포트]\n\n"
        report += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        for sw in targets:
            info = user_data.get(sw, {"version": "데이터 없음", "date": "-"})
            mark = "✅" if sw.upper().replace('_', ' ') in changed_keys else "ℹ️"
            date_label = "조회 날짜" if sw == 'chrome' else "날짜"
            report += f"{mark} {sw.upper().replace('_', ' ')}\n"
            report += f"- 버전: {info['version']}\n"
            report += f"- {date_label}: {info['date']}\n\n"
        
        send_telegram_msg(report)
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
