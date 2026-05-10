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
        try:
            requests.post(url, json=payload, timeout=10)
        except:
            pass

def get_latest_versions():
    versions = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # [1] Windows 11 24H2 보안 업데이트 (B 타입 정기 패치 전용)
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            # 24H2 테이블 섹션 추출
            start_idx = res.text.find('id="release-information"')
            search_area = res.text[start_idx:] if start_idx != -1 else res.text
            
            # 행(tr) 단위로 분리하여 B 타입 탐색
            rows = re.findall(r'<tr>(.*?)</tr>', search_area, re.DOTALL)
            for row in rows:
                # 태그 제거 및 텍스트 정규화
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
    except Exception as e:
        versions['windows_11_24h2'] = {'version': f'파싱 오류', 'date': '-'}

    # [2] Microsoft Edge
    try:
        url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = requests.get(url, headers=headers, timeout=10)
        v_m = re.search(r'Version\s+([\d.]+)', res.text)
        d_m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.text)
        d_str = "-"
        if d_m:
            try:
                d_str = datetime.strptime(d_m.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
            except:
                d_str = d_m.group(1)
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
            try:
                d_str = datetime.strptime(d_match.group(1).replace(',', ''), "%B %d %Y").strftime("%Y/%m/%d")
            except:
                d_str = d_match.group(1)
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
            try:
                d_str = datetime.strptime(d.group(1).strip(), '%b %d, %Y').strftime('%Y/%m/%d')
            except:
                d_str = d.group(1)
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
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            try:
                user_data = json.load(f)
            except:
                user_data = {}
    else:
        user_data = {}

    if 'acrobat' in user_data: del user_data['acrobat']

    web_data = get_latest_versions() or {}
    changed_keys = []
    
    display_order = [
        ('windows_11_24h2', 'Windows 11 24H2 보안 업데이트(B타입:정기 패치 전용)'),
        ('edge', 'Edge'),
        ('acrobat_reader', '아크로뱃리더'),
        ('bandizip', '반디집'),
        ('chrome', 'Chrome')
    ]

    for key, display_name in display_order:
        sw_info = web_data.get(key)
        if not sw_info: continue
        
        latest_v = sw_info.get('version', '')
        if any(x in latest_v for x in ["오류", "실패", "파싱 실패", "None", "미탐지"]): 
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
