import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import re

def get_latest_versions():
    versions = {}
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    timeout_sec = 45

    # 1. Chrome
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Microsoft Edge (보내주신 페이지 텍스트 구조 분석 기반)
    edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
    try:
        edge_res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        if edge_res.status_code == 200:
            # 패턴 1: "Version 148.0.3967.54: May 07, 2026" 형태 탐색
            match = re.search(r'Version\s+(\d+\.\d+\.\d+\.\d+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', edge_res.text)
            if match:
                versions['edge'] = {
                    "version": match.group(1).strip(),
                    "date": match.group(2).strip()
                }
            else:
                # 패턴 2: 표(Table) 내부의 버전 번호 탐색
                soup = BeautifulSoup(edge_res.text, 'html.parser')
                table_cell = soup.find('td', string=re.compile(r'\d+\.\d+\.\d+\.\d+'))
                if table_cell:
                    v_text = table_cell.text.strip()
                    # 버전 번호만 추출 (괄호 등 제외)
                    v_only = re.search(r'(\d+\.\d+\.\d+\.\d+)', v_text).group(1)
                    versions['edge'] = {"version": v_only, "date": datetime.now().strftime("%Y/%m/%d")}
        
        if 'edge' not in versions: print("Edge: 텍스트 패턴을 찾을 수 없습니다.")
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_soup = BeautifulSoup(requests.get(bandi_url, headers=header, timeout=timeout_sec).text, 'html.parser')
        v_tag = next((h2 for h2 in bandi_soup.find_all('h2') if 'v' in h2.text.lower()), None)
        if v_tag:
            versions['bandizip'] = {"version": v_tag.text.strip(), "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Adobe Acrobat
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        acrobat_soup = BeautifulSoup(requests.get(acrobat_url, headers=header, timeout=timeout_sec).text, 'html.parser')
        a_tag = acrobat_soup.find('a', string=re.compile(r'^\d+\.\d+'))
        if a_tag:
            raw = a_tag.text.strip()
            versions['acrobat'] = {
                "version": raw.split(' ')[0],
                "date": raw.split('(')[1].replace(')', '') if '(' in raw else "사이트 확인"
            }
    except Exception as e: print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=15)
        print("Telegram message sent successfully!")
    except Exception as e: print(f"Telegram error: {e}")

def main():
    json_path = 'versions.json'
    if not os.path.exists(json_path): return
    with open(json_path, 'r', encoding='utf-8') as f:
        old_data = json.load(f)

    new_data = get_latest_versions()
    changed = False
    message = "🔔 [S/W 보안 업데이트 감지]\n\n"

    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in new_data and name in old_data:
            old_info = old_data[name]
            old_v = old_info.get('version') if isinstance(old_info, dict) else old_info
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n- 이전: {old_v}\n- 현재: {new_v}\n- 날짜: {new_data[name]['date']}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        send_telegram_msg(message)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else: print("변경 사항 없음")

if __name__ == "__main__":
    main()
