import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re

def format_date(date_str):
    """모든 날짜 형식을 YYYY/MM/DD로 통일"""
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 1. Chrome
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=30).json()
        versions['chrome'] = {"version": str(c_data['versions'][0]['version']), "date": datetime.now().strftime("%Y/%m/%d")}
    except: pass

    # 2. Edge (이미지에서 확인한 relnote 경로)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = requests.get(edge_url, headers=header, timeout=30)
        match = re.search(r'Version\s+([\d\.]+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['edge'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
    except: pass

    # 3. Bandizip (ld+json 구조 정밀 순회)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        res = requests.get(bandi_url, headers=header, timeout=30)
        soup = BeautifulSoup(res.text, 'html.parser')
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') == 'SoftwareApplication':
                    # 사용자님 형식(v포함)에 맞춰 저장할지 결정 (여기서는 웹 기준 숫자만 추출)
                    v_raw = item.get('softwareVersion', '').replace('v', '').strip()
                    if v_raw:
                        versions['bandizip'] = {"version": f"v{v_raw}", "date": format_date(item.get('datePublished', ''))}
                        break
    except: pass

    # 4. Adobe Acrobat (link rel="next" 타이틀 파싱)
    try:
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        res = requests.get(acrobat_url, headers=header, timeout=30)
        soup = BeautifulSoup(res.text, 'html.parser')
        link_tag = soup.find('link', rel='next')
        if link_tag and 'title' in link_tag.attrs:
            title = link_tag['title']
            v_match = re.search(r'(\d{2}\.\d{3}\.\d{5})', title)
            d_match = re.search(r'([a-zA-Z]+\s+\d+,\s+\d+)', title)
            if v_match:
                versions['acrobat'] = {"version": v_match.group(1), "date": format_date(d_match.group(1))}
    except: pass

    return versions

def main():
    json_path = 'versions.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        user_data = json.load(f)

    web_data = get_latest_versions()
    changed_keys = []

    # 비교 및 업데이트 (사용자 데이터 보존 중심)
    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in web_data:
            # 사용자 데이터의 기존 값을 문자열로 변환하여 비교
            current_v = str(user_data.get(name, {}).get('version', ''))
            latest_v = str(web_data[name]['version'])

            if current_v != latest_v:
                changed_keys.append(name)
                user_data[name] = web_data[name] # 최신 정보로 갱신

    # 변경 사항이 하나라도 있으면 전체 리포트 전송
    if changed_keys:
        report = "🔔 [보안 업데이트 통합 리포트]\n\n"
        report += "🚀 새 업데이트 발견: " + ", ".join([n.upper() for n in changed_keys]) + "\n\n"
        report += "━━━━ 제품별 전체 현황 ━━━━\n"
        for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
            info = user_data.get(name, {"version": "N/A", "date": "-"})
            status = "✅" if name in changed_keys else "ℹ️"
            report += f"{status} {name.upper()}\n- 버전: {info['version']}\n- 날짜: {info['date']}\n\n"
        
        # 텔레그램 발송 (환경변수 체크)
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if token and chat_id:
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage", 
                         params={"chat_id": chat_id, "text": report})
        
        # JSON 파일 업데이트
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
    else:
        print("변경 사항 없음")

if __name__ == "__main__":
    main()
