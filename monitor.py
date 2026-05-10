import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

def get_latest_versions():
    versions = {}
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    # 1. Chrome (API 기반이라 비교적 안정적)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=10).json()
        versions['chrome'] = {
            "version": c_data['versions'][0]['version'],
            "date": datetime.now().strftime("%Y/%m/%d")
        }
    except Exception as e:
        print(f"Chrome Error: {e}")

    # 2. Edge (선택자 강화)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header, timeout=10)
        edge_soup = BeautifulSoup(edge_res.text, 'html.parser')
        target = edge_soup.find('h2')
        if target:
            text = target.text
            versions['edge'] = {
                "version": text.split(': ')[0].replace('Version ', '').strip(),
                "date": text.split(': ')[1].strip() if ': ' in text else datetime.now().strftime("%Y/%m/%d")
            }
        else:
            print("Edge tag not found")
    except Exception as e:
        print(f"Edge Error: {e}")

    # 3. Bandizip (비교적 구조가 단순함)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_res = requests.get(bandi_url, headers=header, timeout=10)
        bandi_soup = BeautifulSoup(bandi_res.text, 'html.parser')
        v_tag = bandi_soup.select_one('.history-item h2')
        d_tag = bandi_soup.select_one('.history-item .date')
        if v_tag and d_tag:
            versions['bandizip'] = {
                "version": v_tag.text.strip(),
                "date": d_tag.text.strip()
            }
    except Exception as e:
        print(f"Bandizip Error: {e}")

    # 4. Acrobat (가장 구조가 잘 바뀜)
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        acrobat_res = requests.get(acrobat_url, headers=header, timeout=10)
        acrobat_soup = BeautifulSoup(acrobat_res.text, 'html.parser')
        a_tag = acrobat_soup.select_one('.reference.internal')
        if a_tag:
            raw_text = a_tag.text # 예: "2600121529 (Planned update)"
            versions['acrobat'] = {
                "version": raw_text.split(' ')[0],
                "date": raw_text.split('(')[1].replace(')', '') if '(' in raw_text else "Check Site"
            }
    except Exception as e:
        print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")

def main():
    if not os.path.exists('versions.json'):
        print("versions.json file not found!")
        return

    with open('versions.json', 'r') as f:
        old_data = json.load(f)

    new_data = get_latest_versions()
    changed = False
    message = "🔔 [S/W 업데이트 감지]\n\n"

    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in new_data and name in old_data:
            if new_data[name]['version'] != old_data[name]['version']:
                message += f"✅ {name.upper()}\n- 버전: {old_data[name]['version']} -> {new_data[name]['version']}\n- 출시일: {new_data[name]['date']}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        send_telegram_msg(message)
        with open('versions.json', 'w') as f:
            json.dump(old_data, f, indent=2)
        print("Update detected and notified.")
    else:
        print("변경 사항 없음")

if __name__ == "__main__":
    main()
