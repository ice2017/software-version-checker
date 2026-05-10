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

    # 1. Chrome
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d"), "note": "보안 업데이트"}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Microsoft Edge (텍스트 패턴 기반)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        if edge_res.status_code == 200:
            page_text = BeautifulSoup(edge_res.text, 'html.parser').get_text(separator=' ')
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+[:\(]?\s*([a-zA-Z]+\s+\d+,\s+\d+)', page_text)
            if match:
                versions['edge'] = {"version": match.group(1).strip(), "date": match.group(2).strip(), "note": "안정화 채널 업데이트"}
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (보안 패치 내역 추출 추가)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        bandi_soup = BeautifulSoup(bandi_res.text, 'html.parser')
        
        # 가장 최신 버전 아이템 찾기
        item = bandi_soup.select_one('.history-item')
        if item:
            v_tag = item.select_one('h2')
            d_tag = item.select_one('.date')
            # 첫 번째 리스트 항목(가장 중요한 보안 수정사항) 추출
            summary = item.select_one('li') 
            
            versions['bandizip'] = {
                "version": v_tag.text.strip() if v_tag else "v?.??",
                "date": d_tag.text.strip() if d_tag else datetime.now().strftime("%Y/%m/%d"),
                "note": summary.text.strip() if summary else "상세 내용 홈페이지 참조"
            }
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Adobe Acrobat (Planned update 패턴 매칭)
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
        if res.status_code == 200:
            page_content = BeautifulSoup(res.text, 'html.parser').get_text(separator=' ')
            match = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+(.*?update),\s+([a-zA-Z]+\s+\d+,\s+\d+)', page_content)
            if match:
                versions['acrobat'] = {
                    "version": match.group(1).strip(),
                    "date": match.group(3).strip(),
                    "note": match.group(2).strip()
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
                message += f"✅ {name.upper()}\n"
                message += f"- 버전: {old_v} -> {new_v}\n"
                message += f"- 날짜: {new_data[name]['date']}\n"
                message += f"- 요약: {new_data[name].get('note', '내용 없음')}\n\n"
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
