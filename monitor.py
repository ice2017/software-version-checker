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
    timeout_sec = 50

    # 1. Chrome (API)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Edge (정규식 전수 조사 방식으로 변경)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        # 페이지 전체 텍스트에서 'Version 123.0.1234.56' 패턴 검색
        version_match = re.search(r'Version\s+(\d+\.\d+\.\d+\.\d+)', edge_res.text)
        if version_match:
            v_part = version_match.group(1)
            # 날짜는 버전 바로 뒤에 오는 패턴을 찾거나 오늘 날짜로 대체
            versions['edge'] = {"version": v_part, "date": datetime.now().strftime("%Y/%m/%d")}
        else: print("Edge: Version pattern not found.")
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (안정적)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        bandi_soup = BeautifulSoup(bandi_res.text, 'html.parser')
        v_tag = next((h2 for h2 in bandi_soup.find_all('h2') if 'v' in h2.text.lower()), None)
        if v_tag:
            versions['bandizip'] = {"version": v_tag.text.strip(), "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Acrobat (릴리즈 노트 인덱스 페이지의 첫 번째 숫자 링크)
    for i in range(3):
        try:
            acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
            acrobat_res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
            acrobat_soup = BeautifulSoup(acrobat_res.text, 'html.parser')
            # 링크 텍스트가 숫자로 시작하는 모든 <a> 태그 탐색
            links = acrobat_soup.find_all('a', href=True)
            for link in links:
                link_text = link.text.strip()
                if re.match(r'^\d+\.\d+', link_text):
                    versions['acrobat'] = {
                        "version": link_text.split(' ')[0],
                        "date": link_text.split('(')[1].replace(')', '') if '(' in link_text else "See Site"
                    }
                    break
            if 'acrobat' in versions: break
        except Exception as e:
            print(f"Acrobat Attempt {i+1} failed: {e}")
            time.sleep(10)

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=15)
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
            # 기존 데이터 형식(문자열/객체) 호환성 처리
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
