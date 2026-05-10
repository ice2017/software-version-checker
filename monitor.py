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
    timeout_sec = 50

    # 1. Chrome (가장 안정적)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d"), "note": "Google 공식 배포"}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Microsoft Edge (정밀 정규식 탐색)
    edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
    try:
        res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        # HTML을 텍스트로 변환 후 "148.0.3967.54" 형태의 4단위 숫자 패턴 검색
        soup = BeautifulSoup(res.text, 'html.parser')
        full_text = soup.get_text(separator=' ')
        v_match = re.search(r'(\d{2,3}\.\d\.\d{4}\.\d{2})', full_text) # Edge 특유의 4단위 패턴
        if v_match:
            versions['edge'] = {
                "version": v_match.group(1),
                "date": datetime.now().strftime("%Y/%m/%d"),
                "note": "MS 안정화 채널 릴리즈"
            }
        else: print("Edge: 패턴 매칭 실패")
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (보안 취약점 내용 포함 추출)
    bandi_url = "https://www.bandisoft.com/bandizip/history/"
    try:
        res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        # h2 태그 중 'v7.xx' 형식을 찾음
        v_tag = next((h for h in soup.find_all('h2') if re.search(r'v\d\.\d+', h.text)), None)
        if v_tag:
            # 해당 h2의 부모 요소 내에서 날짜와 리스트 첫 줄(보안패치) 추출
            parent = v_tag.find_parent()
            d_tag = parent.select_one('.date') if parent else None
            note_tag = parent.select_one('li') if parent else None
            versions['bandizip'] = {
                "version": v_tag.text.strip(),
                "date": d_tag.text.strip() if d_tag else datetime.now().strftime("%Y/%m/%d"),
                "note": note_tag.text.strip() if note_tag else "보안 업데이트"
            }
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Adobe Acrobat (Planned update 텍스트 정밀 추적)
    acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
    try:
        res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        text = soup.get_text(separator=' ')
        # "26.001.21529 Planned update, May 01, 2026" 패턴 매칭
        match = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+Planned\s+update,\s+([a-zA-Z]+\s+\d+,\s+\d+)', text)
        if match:
            versions['acrobat'] = {
                "version": match.group(1),
                "date": match.group(2),
                "note": "Planned Update (보안 패치 포함)"
            }
        else:
            # 백업: 단순 버전 패턴 검색
            v_backup = re.search(r'(\d{2}\.\d{3}\.\d{5})', text)
            if v_backup:
                versions['acrobat'] = {"version": v_backup.group(1), "date": "사이트 확인", "note": "최신 릴리즈 감지"}
    except Exception as e: print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not (token and chat_id): return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=15)
        print("Telegram 전송 완료")
    except: print("Telegram 전송 실패")

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
            # 문자열/객체 혼용 대응
            old_v = old_info.get('version') if isinstance(old_info, dict) else old_info
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n"
                message += f"- 버전: {old_v} → {new_v}\n"
                message += f"- 날짜: {new_data[name]['date']}\n"
                message += f"- 내용: {new_data[name].get('note', '-')}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        print(message)
        send_telegram_msg(message)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else: print("변경 사항 없음")

if __name__ == "__main__":
    main()
