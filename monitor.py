import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re

def format_date(date_str):
    """영문 날짜(May 07, 2026) 또는 기존 날짜를 YYYY/MM/DD 형식으로 변환"""
    try:
        # 1. 'May 07, 2026' 형식 대응
        if ',' in date_str:
            dt = datetime.strptime(date_str.replace(',', ''), "%B %d %Y")
            return dt.strftime("%Y/%m/%d")
        # 2. '2026/5/4' 등 숫자 형식 대응
        elif '/' in date_str:
            parts = date_str.split('/')
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
    timeout_sec = 45

    # 1. Chrome (안정적)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=timeout_sec).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d")}
    except: pass

    # 2. Microsoft Edge (이미지 힌트 기반 <li> 태그 정밀 추출)
    edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
    try:
        res = requests.get(edge_url, headers=header, timeout=timeout_sec)
        # 이미지 속 <li> 태그 내부 텍스트 패턴: Version 148.0.3967.54: May 07, 2026
        match = re.search(r'Version\s+([\d\.]+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['edge'] = {
                "version": match.group(1).strip(),
                "date": format_date(match.group(2).strip())
            }
    except: pass

    # 3. Bandizip (이미지 속 ld+json 소스 우선 추출)
    bandi_url = "https://www.bandisoft.com/bandizip/history/"
    try:
        res = requests.get(bandi_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 1순위: JSON-LD 데이터 (이미지 하단 script 탭 소스)
        json_script = soup.find('script', type='application/ld+json')
        if json_script:
            data = json.loads(json_script.string)
            versions['bandizip'] = {
                "version": data.get('softwareVersion', 'v7.43').replace('v', ''),
                "date": format_date(data.get('datePublished', '2026/05/04'))
            }
        else:
            # 2순위: 텍스트 직접 추출
            match = re.search(r'v(\d+\.\d+)\s+(\d{4}/\d+/\d+)', res.text)
            if match:
                versions['bandizip'] = {"version": match.group(1), "date": format_date(match.group(2))}
    except: pass

    # 4. Adobe Acrobat (이미지 속 link rel="next" 소스 활용)
    acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
    try:
        res = requests.get(acrobat_url, headers=header, timeout=timeout_sec)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 이미지 힌트 확인: <link rel="next" title="26.001.21529 Planned update, May 01, 2026">
        link_tag = soup.find('link', rel='next')
        if link_tag and 'title' in link_tag.attrs:
            title = link_tag['title']
            v_match = re.search(r'(\d{2}\.\d{3}\.\d{5})', title)
            d_match = re.search(r'([a-zA-Z]+\s+\d+,\s+\d+)', title)
            if v_match:
                versions['acrobat'] = {
                    "version": v_match.group(1),
                    "date": format_date(d_match.group(1)) if d_match else "2026/05/01"
                }
    except: pass

    return versions

def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not (token and chat_id): return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.get(url, params={"chat_id": chat_id, "text": message}, timeout=10)
    except: pass

def main():
    json_path = 'versions.json'
    if not os.path.exists(json_path):
        with open(json_path, 'w') as f: json.dump({}, f)

    with open(json_path, 'r', encoding='utf-8') as f:
        try: old_data = json.load(f)
        except: old_data = {}

    new_data = get_latest_versions()
    changed = False
    message = "🔔 [S/W 보안 업데이트 실시간 알림]\n\n"

    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in new_data:
            # 기존 데이터(문자열/객체) 호환성 체크
            old_info = old_data.get(name, {})
            old_v = old_info.get('version', "0.0.0") if isinstance(old_info, dict) else old_info
            new_v = new_data[name]['version']

            if old_v != new_v:
                message += f"✅ {name.upper()}\n"
                message += f"- 버전: {old_v} → {new_v}\n"
                message += f"- 날짜: {new_data[name]['date']}\n\n"
                old_data[name] = new_data[name]
                changed = True

    if changed:
        send_telegram_msg(message)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(old_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"[{datetime.now()}] 변경 사항 없음")

if __name__ == "__main__":
    main()
