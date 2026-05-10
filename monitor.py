import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import re

def get_latest_versions():
    versions = {}
    # 실제 브라우저처럼 보이기 위한 강화된 헤더
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    timeout_sec = 55 # 타임아웃 최대치 증액

    # 1. Chrome (안정적)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d"), "note": "보안 패치 포함"}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Microsoft Edge (정규식 전수 조사 강화)
    # 404를 피하기 위한 가장 최상위 공식 경로
    edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
    try:
        res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        # 텍스트를 모두 긁어와서 '148.0.3967.54' 패턴 탐색
        all_text = res.text
        v_match = re.search(r'(\d{3}\.0\.\d{4}\.\d{2})', all_text)
        if v_match:
            versions['edge'] = {"version": v_match.group(1), "date": datetime.now().strftime("%Y/%m/%d"), "note": "Edge 안정 채널"}
        else:
            # 보조 패턴 (버전 뒤에 날짜가 오는 형태)
            v_match_backup = re.search(r'Version\s+([\d\.]+)', all_text)
            if v_match_backup:
                versions['edge'] = {"version": v_match_backup.group(1), "date": "사이트 확인", "note": "최신 릴리즈"}
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (보안 취약점 KVE 번호 포함 추출)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        item = soup.select_one('.history-item')
        if item:
            v_tag = item.find('h2')
            d_tag = item.select_one('.date')
            note_tag = item.find('li') # 첫 번째 보안 패치 내역
            versions['bandizip'] = {
                "version": v_tag.text.strip() if v_tag else "v7.x",
                "date": d_tag.text.strip() if d_tag else datetime.now().strftime("%Y/%m/%d"),
                "note": note_tag.text.strip() if note_tag else "보안 업데이트"
            }
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Adobe Acrobat (타임아웃 우회용 helpx 경로 사용)
    # 공식 devnet 사이트보다 helpx 사이트가 봇 차단이 상대적으로 덜함
    acrobat_url = "https://helpx.adobe.com/acrobat/release-note/release-notes-acrobat-reader.html"
    try:
        res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
        # 숫자로 시작하는 버전 링크 탐색 (26.001.21529 등)
        soup = BeautifulSoup(res.text, 'html.parser')
        a_tag = soup.find('a', string=re.compile(r'^\d{2}\.'))
        if a_tag:
            versions['acrobat'] = {
                "version": a_tag.text.split(' ')[0],
                "date": datetime.now().strftime("%Y/%m/%d"),
                "note": "Acrobat Continuous Track"
            }
        else:
            # 텍스트 전체에서 버전 패턴 강제 추출
            v_match = re.search(r'(\d{2}\.\d{3}\.\d{5})', res.text)
            if v_match:
                versions['acrobat'] = {"version": v_match.group(1), "date": "상세내역 확인", "note": "최신 보안 패치"}
    except Exception as e: print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not (token and chat_id): return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=15)
    except: pass

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
            # 데이터 구조 호환성 처리
            old_v = old_data[name]['version'] if isinstance(old_data[name], dict) else old_data[name]
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n- 버전: {old_v} → {new_v}\n- 날짜: {new_data[name]['date']}\n- 내용: {new_data[name].get('note', '-')}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        send_telegram_msg(message)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else: print("변경 사항 없음")

if __name__ == "__main__":
    main()
