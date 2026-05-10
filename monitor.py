import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

def get_latest_versions():
    versions = {}
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    timeout_sec = 20 # 타임아웃 시간을 늘림

    # 1. Chrome
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Edge (선택자 및 로직 개선)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        edge_soup = BeautifulSoup(edge_res.text, 'html.parser')
        # h2 태그 중 'Version' 문구가 포함된 첫 번째 요소 탐색
        target = next((h for h in edge_soup.find_all('h2') if 'Version' in h.text), None)
        if target:
            text = target.text.strip() # "Version 148.0.3967.54: May 5, 2026"
            v_part = text.split(':')[0].replace('Version', '').strip()
            d_part = text.split(':')[1].strip() if ':' in text else "Check Site"
            versions['edge'] = {"version": v_part, "date": d_part}
        else: print("Edge tag not found")
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_soup = BeautifulSoup(requests.get(bandi_url, headers=header, timeout=timeout_sec).text, 'html.parser')
        v_tag = bandi_soup.select_one('.history-item h2')
        d_tag = bandi_soup.select_one('.history-item .date')
        if v_tag:
            versions['bandizip'] = {"version": v_tag.text.strip(), "date": d_tag.text.strip() if d_tag else "Check Site"}
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Acrobat
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        acrobat_soup = BeautifulSoup(requests.get(acrobat_url, headers=header, timeout=timeout_sec).text, 'html.parser')
        a_tag = acrobat_soup.select_one('.reference.internal')
        if a_tag:
            raw = a_tag.text
            versions['acrobat'] = {
                "version": raw.split(' ')[0],
                "date": raw.split('(')[1].replace(')', '') if '(' in raw else "Check Site"
            }
    except Exception as e: print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try: requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=timeout_sec)
        except Exception as e: print(f"Telegram error: {e}")

def main():
    if not os.path.exists('versions.json'): return

    with open('versions.json', 'r') as f:
        old_data = json.load(f)

    new_data = get_latest_versions()
    changed = False
    message = "🔔 [S/W 업데이트 감지]\n\n"

    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        # 데이터가 정상적으로 수집되었고, 기존 데이터와 형식이 맞는지 확인
        if name in new_data and name in old_data:
            # 안전하게 .get() 사용 또는 타입 체크
            old_v = old_data[name].get('version') if isinstance(old_data[name], dict) else old_data[name]
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n- 이전: {old_v}\n- 현재: {new_v}\n- 날짜: {new_data[name]['date']}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        send_telegram_msg(message)
        with open('versions.json', 'w') as f:
            json.dump(old_data, f, indent=2)
    else:
        print("변경 사항 없음")

if __name__ == "__main__":
    main()
