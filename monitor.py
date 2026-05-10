import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re
import time

def format_date(date_str):
    """날짜 형식을 YYYY/MM/DD로 통일 (May 01, 2026 -> 2026/05/01)"""
    try:
        if ',' in date_str:
            dt = datetime.strptime(date_str.replace(',', ''), "%B %d %Y")
            return dt.strftime("%Y/%m/%d")
        return date_str.replace('-', '/').strip()
    except:
        return datetime.now().strftime("%Y/%m/%d")

def get_latest_versions():
    versions = {}
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    # --- 1. Chrome (Google API) ---
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        res = requests.get(chrome_api, timeout=30)
        if res.status_code == 200:
            c_data = res.json()
            versions['chrome'] = {"version": str(c_data['versions'][0]['version']), "date": datetime.now().strftime("%Y/%m/%d")}
    except: pass

    # --- 2. Microsoft Edge (정밀 정규식 추출) ---
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = requests.get(edge_url, headers=header, timeout=30)
        # 이미지 힌트 패턴: Version 148.0.3967.54: May 07, 2026
        match = re.search(r'Version\s+([\d\.]+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['edge'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
    except: pass

    # --- 3. Bandizip (ld+json 및 정규식 교차 검증) ---
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        res = requests.get(bandi_url, headers=header, timeout=30)
        # 루프 테스트: ld+json 먼저 시도
        found_bandi = False
        soup = BeautifulSoup(res.text, 'html.parser')
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if 'softwareVersion' in item:
                    v_raw = item['softwareVersion'].replace('v', '').strip()
                    versions['bandizip'] = {"version": f"v{v_raw}", "date": format_date(item.get('datePublished', ''))}
                    found_bandi = True; break
            if found_bandi: break
        
        # 피드백: JSON 실패 시 정규식 강제 시도
        if not found_bandi:
            v_match = re.search(r'v(\d+\.\d+)\s+(\d{4}/\d+/\d+)', res.text)
            if v_match:
                versions['bandizip'] = {"version": f"v{v_match.group(1)}", "date": format_date(v_match.group(2))}
    except: pass

    # --- 4. Adobe Acrobat (메타 데이터 & 텍스트 전수 조사) ---
    # Acrobat은 차단이 잦으므로 루프 테스트 2회 수행
    acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
    for attempt in range(2):
        try:
            res = requests.get(acrobat_url, headers=header, timeout=40)
            if res.status_code == 200:
                # 시도 1: link rel="next" 추출
                soup = BeautifulSoup(res.text, 'html.parser')
                link_tag = soup.find('link', rel='next')
                if link_tag and 'title' in link_tag.attrs:
                    title = link_tag['title']
                    v_m = re.search(r'(\d{2}\.\d{3}\.\d{5})', title)
                    d_m = re.search(r'([a-zA-Z]+\s+\d+,\s+\d+)', title)
                    if v_m:
                        versions['acrobat'] = {"version": v_m.group(1), "date": format_date(d_m.group(1)) if d_m else "2026/05/01"}
                        break
                # 시도 2: 본문 텍스트 패턴 추출
                text_match = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+Planned\s+update,\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
                if text_match:
                    versions['acrobat'] = {"version": text_match.group(1), "date": format_date(text_match.group(2))}
                    break
        except:
            time.sleep(5) # 지연 후 재시도
    return versions

def main():
    json_path = 'versions.json'
    # 1. 기존 데이터 로드
    with open(json_path, 'r', encoding='utf-8') as f:
        user_data = json.load(f)

    # 2. 웹 데이터 수집
    web_data = get_latest_versions()
    changed_items = []

    # 3. 초논리적 비교 로직 (문자열 강제 형변환 및 v접두사 통일)
    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in web_data:
            # 사용자 데이터의 version을 문자열로 가져옴 (2000000 -> "2000000")
            old_info = user_data.get(name, {})
            current_v = str(old_info.get('version', '')).strip()
            latest_v = str(web_data[name]['version']).strip()

            if current_v != latest_v:
                changed_items.append(name.upper())
                user_data[name] = web_data[name]

    # 4. 결과 발송 및 저장
    if changed_items:
        report = f"🔔 [S/W 보안 업데이트 통합 리포트]\n\n"
        report += f"🚀 업데이트 감지: {', '.join(changed_items)}\n\n"
        report += "━━━━━ 전 제품 현황 ━━━━━\n"
        for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
            info = user_data.get(name, {"version": "N/A", "date": "-"})
            status = "✅" if name.upper() in changed_items else "ℹ️"
            report += f"{status} {name.upper()}\n- 버전: {info['version']}\n- 날짜: {info['date']}\n\n"
        
        # 텔레그램 전송
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if token and chat_id:
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage", 
                         params={"chat_id": chat_id, "text": report})
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"[{datetime.now()}] 변경 사항 없음 - 모든 데이터가 웹과 일치합니다.")

if __name__ == "__main__":
    main()
