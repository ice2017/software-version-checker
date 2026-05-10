import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import re

def get_latest_versions():
    versions = {}
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    timeout_sec = 40

    # 1. Chrome (API 기반 - 신뢰도 높음)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {
            "version": c_data['versions'][0]['version'],
            "date": datetime.now().strftime("%Y/%m/%d"),
            "note": "보안 패치 및 엔진 업데이트"
        }
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Microsoft Edge (보내주신 relnote 경로 및 표 구조 대응)
    # 이미지 힌트의 URL: .../microsoft-edge-relnote-stable-channel
    edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
    try:
        res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        # 이미지 속 "148.0.3967.54 (May 07, 2026)" 패턴 추출
        match = re.search(r'(\d{3}\.0\.\d{4}\.\d{2})\s*\((.*?2026)\)', res.text)
        if match:
            versions['edge'] = {"version": match.group(1), "date": match.group(2), "note": "Edge Stable Release"}
        else:
            # 백업 패턴: Version 148.0.3967.54: May 07, 2026
            match2 = re.search(r'Version\s+(\d+\.\d+\.\d+\.\d+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
            if match2:
                versions['edge'] = {"version": match2.group(1), "date": match2.group(2), "note": "Edge Stable Release"}
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (v7.43 / 2026/5/4 및 KVE 번호 추출)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 첫 번째 테이블 행(tr) 또는 history-item 탐색
        v_tag = soup.find(string=re.compile(r'v\d\.\d+'))
        if v_tag:
            parent = v_tag.find_parent('tr') or v_tag.find_parent(class_='history-item')
            note = parent.find('li').text.strip() if parent.find('li') else "보안 취약점 수정"
            versions['bandizip'] = {
                "version": v_tag.strip(),
                "date": "2026/05/04", # 이미지 힌트 기준 날짜
                "note": note
            }
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Adobe Acrobat (26.001.21529 Planned update, May 01, 2026)
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
        # 이미지 힌트의 "26.001.21529 Planned update, May 01, 2026" 패턴
        match = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+Planned\s+update,\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['acrobat'] = {
                "version": match.group(1),
                "date": match.group(2),
                "note": "Acrobat Continuous Track"
            }
    except Exception as e: print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not (token and chat_id): return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=10)
    except: pass

def main():
    json_path = 'versions.json'
    # 초기 파일 없을 시 자가 생성 로직
    if not os.path.exists(json_path):
        with open(json_path, 'w') as f: json.dump({}, f)

    with open(json_path, 'r', encoding='utf-8') as f:
        try: old_data = json.load(f)
        except: old_data = {}

    new_data = get_latest_versions()
    changed = False
    message = "🔔 [S/W 보안 업데이트 실시간 감지]\n\n"

    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in new_data:
            # 기존 데이터가 없거나 버전이 다를 경우
            old_v = old_data.get(name, {}).get('version', "0.0.0")
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n- 버전: {old_v} → {new_v}\n- 날짜: {new_data[name]['date']}\n- 요약: {new_data[name].get('note', '-')}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        print(message)
        send_telegram_msg(message)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"[{datetime.now()}] 모든 소프트웨어 최신 상태 유지 중")

if __name__ == "__main__":
    main()
