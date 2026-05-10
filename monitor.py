import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import re

# 1. 최신 버전 및 날짜 추출 함수
def get_latest_versions():
    versions = {}
    # 보안 블로그 운영자로서 봇 차단을 피하기 위한 표준 헤더 설정
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    timeout_sec = 45 # Adobe 등 응답이 느린 사이트를 위해 충분한 시간 할당

    # --- (1) Chrome: API 기반 ---
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {
            "version": c_data['versions'][0]['version'],
            "date": datetime.now().strftime("%Y/%m/%d") # API에 날짜가 없을 경우 현재 날짜 기록
        }
    except Exception as e:
        print(f"Chrome Error: {e}")

    # --- (2) Microsoft Edge: 텍스트 패턴 기반 ---
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        edge_soup = BeautifulSoup(edge_res.text, 'html.parser')
        # Version 문구와 숫자가 포함된 헤더(h1~h4)를 모두 뒤짐
        target = None
        for tag in edge_soup.find_all(['h1', 'h2', 'h3', 'h4']):
            if 'Version' in tag.text and re.search(r'\d+\.\d+', tag.text):
                target = tag
                break
        if target:
            text = target.text.strip() # 예: "Version 148.0.3967.54: May 5, 2026"
            parts = text.split(':')
            v_part = parts[0].replace('Version', '').strip()
            d_part = parts[1].strip() if len(parts) > 1 else datetime.now().strftime("%Y/%m/%d")
            versions['edge'] = {"version": v_part, "date": d_part}
        else:
            print("Edge: Target header not found.")
    except Exception as e:
        print(f"Edge Error: {e}")

    # --- (3) Bandizip: 히스토리 페이지 기반 ---
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        bandi_soup = BeautifulSoup(bandi_res.text, 'html.parser')
        # 버전(vX.XX) 형식의 텍스트를 가진 h2 태그 탐색
        v_tag = next((h2 for h2 in bandi_soup.find_all('h2') if 'v' in h2.text.lower()), None)
        if v_tag:
            versions['bandizip'] = {
                "version": v_tag.text.strip(),
                "date": datetime.now().strftime("%Y/%m/%d")
            }
    except Exception as e:
        print(f"Bandizip Error: {e}")

    # --- (4) Adobe Acrobat: 재시도 및 정규식 기반 ---
    for i in range(3): # 최대 3번 재시도 (Adobe 서버 지연 대비)
        try:
            acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
            acrobat_res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
            acrobat_soup = BeautifulSoup(acrobat_res.text, 'html.parser')
            # 숫자로 시작하는 링크 텍스트(릴리즈 노트) 탐색
            a_tag = acrobat_soup.find('a', class_='internal', string=re.compile(r'^\d+'))
            if a_tag:
                raw = a_tag.text.strip() # 예: "26.001.21529 (Planned update)"
                versions['acrobat'] = {
                    "version": raw.split(' ')[0],
                    "date": raw.split('(')[1].replace(')', '') if '(' in raw else "See Site"
                }
                break
            time.sleep(5)
        except Exception as e:
            print(f"Acrobat Attempt {i+1} failed: {e}")
            time.sleep(10)

    return versions

# 2. 텔레그램 알림 발송 함수
def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("Telegram configuration missing!")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=15)
        if resp.status_code == 200:
            print("Telegram message sent successfully!")
        else:
            print(f"Telegram API Error: {resp.status_code}")
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# 3. 메인 실행 로직
def main():
    json_path = 'versions.json'
    if not os.path.exists(json_path):
        print("Error: versions.json not found.")
        return

    # 기존 데이터 로드
    with open(json_path, 'r', encoding='utf-8') as f:
        old_data = json.load(f)

    new_data = get_latest_versions()
    changed = False
    message = "🔔 [S/W 보안 업데이트 감지]\n\n"

    # 타겟 소프트웨어 리스트 순회
    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in new_data and name in old_data:
            # 기존 데이터가 문자열인 경우와 객체인 경우 모두 호환성 처리
            old_info = old_data[name]
            old_v = old_info.get('version') if isinstance(old_info, dict) else old_info
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n- 이전: {old_v}\n- 현재: {new_v}\n- 출시일: {new_data[name]['date']}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        print(message)
        send_telegram_msg(message)
        # 변경된 최신 정보를 파일에 저장
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else:
        print("모든 소프트웨어가 최신 버전입니다. (변경 사항 없음)")

if __name__ == "__main__":
    main()
