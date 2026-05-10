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

    # 4. Acrobat Reader
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

    # 5. Windows 11 24H2 (인덱스 탐색 방식 - 가장 확실함)
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=15)
        if res.stdout:
            content_24h2 = res.stdout.split("24H2")[-1]
            # 태그 제거 후 순수 텍스트 행 리스트 생성
            lines = [l.strip() for l in re.sub(r'<[^>]*>', '\n', content_24h2).split('\n') if l.strip()]
            
            u_date, u_build, u_kb = "-", "-", "-"
            
            for i, line in enumerate(lines):
                # '2026-04 B' 와 같은 패턴을 찾음
                if re.search(r'\d{4}-\d{2}\s+B$', line):
                    # 찾은 위치 근처(아래로 5줄 이내)에서 날짜, 빌드, KB를 각각 찾음
                    search_range = lines[i:i+6]
                    for item in search_range:
                        if u_date == "-" and re.match(r'^\d{4}-\d{2}-\d{2}$', item):
                            u_date = item
                        if u_build == "-" and re.match(r'^26100\.\d+$', item):
                            u_build = item
                        if u_kb == "-" and re.match(r'^KB\d{7}$', item):
                            u_kb = item
                    
                    if u_build != "-" and "26100" in u_build:
                        break # 최신 B타입 데이터를 찾았으므로 종료
            
            versions['windows_11_24h2'] = {
                'version': f"Build {u_build} ({u_kb})" if u_kb != "-" else f"Build {u_build}",
                'date': u_date.replace('-', '/')
            }
    except:
        versions['windows_11_24h2'] = {'version': '오류', 'date': '-'}

    return versions # [핵심 수정] None 반환 방지를 위해 반드시 필요

def main():
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            try: user_data = json.load(f)
            except: user_data = {}
    else: user_data = {}

    if 'acrobat' in user_data: del user_data['acrobat']

    # web_data가 None일 경우를 대비해 빈 딕셔너리로 초기화
    web_data = get_latest_versions() or {}
    
    changed_keys = []
    # [수정] 요청하신 출력 순서 정의
    display_order = [
        ('windows_11_24h2', '윈도우 보안 업데이트'),
        ('edge', 'Edge'),
        ('acrobat_reader', '아크로뱃리더'),
        ('bandizip', '반디집'),
        ('chrome', 'Chrome')
    ]

    # 데이터 업데이트 체크
    for key, display_name in display_order:
        sw_info = web_data.get(key)
        if not sw_info or not isinstance(sw_info, dict):
            continue
            
        latest_v = sw_info.get('version', '')
        if any(x in latest_v for x in ["오류", "실패", "-", "None"]):
            continue

        current_v = user_data.get(key, {}).get('version', '0')
        
        if latest_v != current_v:
            changed_keys.append(display_name)
            save_date = today if key == 'chrome' else sw_info.get('date', '-')
            user_data[key] = {"version": latest_v, "date": save_date}

    if changed_keys:
        # [수정] 제목 변경: S/W 업데이트 모니터링
        report = "🔔 [S/W 업데이트 모니터링]\n\n"
        report += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        
        # [수정] 요청하신 순서대로 리포트 생성
        for key, display_name in display_order:
            info = user_data.get(key, {"version": "데이터 없음", "date": "-"})
            mark = "✅" if display_name in changed_keys else "ℹ️"
            
            # 크롬만 날짜 라벨을 '조회 날짜'로 표시 (선택 사항)
            date_label = "조회 날짜" if key == 'chrome' else "날짜"
            
            report += f"{mark} {display_name}\n"
            report += f"- 버전: {info.get('version')}\n"
            report += f"- {date_label}: {info.get('date')}\n\n"
        
        send_telegram_msg(report)
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
