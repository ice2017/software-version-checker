import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re

def format_date(date_str):
    """영문 날짜 또는 숫자 날짜를 YYYY/MM/DD 형식으로 변환"""
    try:
        if ',' in date_str:
            dt = datetime.strptime(date_str.replace(',', ''), "%B %d %Y")
            return dt.strftime("%Y/%m/%d")
        elif '/' in date_str:
            parts = [p.strip() for p in date_str.split('/')]
            return f"{parts[0]}/{int(parts[1]):02d}/{int(parts[2]):02d}"
        return date_str
    except:
        return datetime.now().strftime("%Y/%m/%d")

def get_latest_versions():
    versions = {}
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8'
    }
    timeout_sec = 50

    # 1. Chrome
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Microsoft Edge (relnote 경로 정밀 탐색)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        match = re.search(r'Version\s+([\d\.]+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['edge'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (ld+json 스크립트 데이터 직접 파싱)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        json_script = soup.find('script', type='application/ld+json')
        if json_script:
            data = json.loads(json_script.string)
            # v7.43 -> 7.43 형식으로 통일
            v_raw = data.get('softwareVersion', '7.43').replace('v', '').strip()
            versions['bandizip'] = {"version": v_raw, "date": format_date(data.get('datePublished', '2026/05/04'))}
        else:
            # 백업 정규식
            v_match = re.search(r'v(\d+\.\d+)\s+(\d{4}/\d+/\d+)', res.text)
            if v_match:
                versions['bandizip'] = {"version": v_match.group(1), "date": format_date(v_match.group(2))}
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Adobe Acrobat (link rel="next" 타이틀 정밀 파싱)
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        link_tag = soup.find('link', rel='next')
        if link_tag and 'title' in link_tag.attrs:
            title = link_tag['title'] # "26.001.21529 Planned update, May 01, 2026"
            v_match = re.search(r'(\d{2}\.\d{3}\.\d{5})', title)
            d_match = re.search(r'([a-zA-Z]+\s+\d+,\s+\d+)', title)
            if v_match:
                versions['acrobat'] = {
                    "version": v_match.group(1),
                    "date": format_date(d_match.group(1)) if d_match else "2026/05/01"
                }
    except Exception as e: print(f"Acrobat Error: {e}")

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not (token and chat_id): return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=15)
    except: pass

def main():
    json_path = 'versions.json'
    if not os.path.exists(json_path):
        with open(json_path, 'w') as f: json.dump({}, f)

    with open(json_path, 'r', encoding='utf-8') as f:
        try: old_data = json.load(f)
        except: old_data = {}

    new_data = get_latest_versions()
    changed_list = []

    # 변경 사항 확인 및 업데이트
    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in new_data:
            old_info = old_data.get(name, {})
            old_v = old_info.get('version', "0.0.0") if isinstance(old_info, dict) else old_info
            new_v = new_data[name]['version']

            if old_v != new_v:
                changed_list.append(name)
                old_data[name] = new_data[name]

    if changed_list:
        msg = "🔔 [S/W 보안 업데이트 실시간 리포트]\n\n"
        msg += "⚠️ 업데이트 감지: " + ", ".join([n.upper() for n in changed_list]) + "\n\n"
        
        msg += "━━━━ 현재 전체 현황 ━━━━\n"
        for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
            v_info = old_data.get(name, {"version": "연결 실패", "date": "-"})
            mark = "✅" if name in changed_list else "ℹ️"
            msg += f"{mark} {name.upper()}\n- 버전: {v_info['version']}\n- 날짜: {v_info['date']}\n\n"
        
        send_telegram_msg(msg)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"[{datetime.now()}] 모든 제품이 최신 상태입니다.")

if __name__ == "__main__":
    main()
