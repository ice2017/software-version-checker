import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re
import time

def format_date(date_str):
    try:
        if ',' in date_str:
            dt = datetime.strptime(date_str.replace(',', ''), "%B %d %Y")
            return dt.strftime("%Y/%m/%d")
        return date_str.replace('-', '/').strip()
    except:
        return datetime.now().strftime("%Y/%m/%d")

def get_latest_versions():
    versions = {}
    errors = []
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    # --- 1. Chrome ---
    try:
        res = requests.get("https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions", timeout=20)
        versions['chrome'] = {"version": str(res.json()['versions'][0]['version']), "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: errors.append(f"Chrome: {str(e)}")

    # --- 2. Edge ---
    try:
        res = requests.get("https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel", headers=header, timeout=30)
        match = re.search(r'Version\s+([\d\.]+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['edge'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
        else: errors.append("Edge: 패턴 매칭 실패")
    except Exception as e: errors.append(f"Edge: {str(e)}")

    # --- 3. Bandizip (BeautifulSoup 기반 JSON-LD 정밀 필터링) ---
    try:
        res = requests.get("https://www.bandisoft.com/bandizip/history/", headers=header, timeout=30)
        soup = BeautifulSoup(res.text, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')
        found_v = False
        for s in scripts:
            try:
                js_data = json.loads(s.string)
                items = js_data if isinstance(js_data, list) else [js_data]
                for item in items:
                    if 'softwareVersion' in item:
                        v = item['softwareVersion'].replace('v', '').strip()
                        versions['bandizip'] = {"version": f"v{v}", "date": format_date(item.get('datePublished', ''))}
                        found_v = True; break
            except: continue
            if found_v: break
        if not found_v: errors.append("Bandizip: JSON 내 버전 정보 부재")
    except Exception as e: errors.append(f"Bandizip: {str(e)}")

    # --- 4. Acrobat (타임아웃 강화 및 60초 대기) ---
    try:
        with requests.Session() as s:
            s.headers.update(header)
            # Adobe 사이트는 매우 느리므로 timeout을 60초로 상향
            res = s.get("https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html", timeout=60)
            # link rel="next" 추출 시 공백 제거 및 정규식 완화
            soup = BeautifulSoup(res.text, 'html.parser')
            link_tag = soup.find('link', rel='next')
            if link_tag and 'title' in link_tag.attrs:
                title = link_tag['title']
                v_m = re.search(r'(\d{2}\.\d{3}\.\d{5})', title)
                d_m = re.search(r'([a-zA-Z]+\s+\d+,\s+\d+)', title)
                if v_m:
                    versions['acrobat'] = {"version": v_m.group(1).strip(), "date": format_date(d_m.group(1).strip()) if d_m else "2026/05/01"}
            
            if 'acrobat' not in versions:
                # 본문 내 전수 조사
                match_text = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+Planned\s+update,\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
                if match_text:
                    versions['acrobat'] = {"version": match_text.group(1).strip(), "date": format_date(match_text.group(2).strip())}
                else: errors.append("Acrobat: 파싱 실패")
    except Exception as e: errors.append(f"Acrobat: {str(e)}")

    return versions, errors

def main():
    json_path = 'versions.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        user_data = json.load(f)

    web_data, errors = get_latest_versions()
    changed_list = []

    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in web_data:
            old_v = str(user_data.get(name, {}).get('version', '')).strip()
            new_v = str(web_data[name]['version']).strip()
            if old_v != new_v:
                changed_list.append(name.upper())
                user_data[name] = web_data[name]

    if changed_list or errors:
        report = "🔔 [S/W 보안 모니터링 리포트]\n\n"
        if changed_list: report += f"🚀 업데이트 감지: {', '.join(changed_list)}\n\n"
        if errors:
            report += "❌ 수집 에러 리스트:\n"
            report += "\n".join([f"• {e}" for e in errors]) + "\n\n"

        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
            info = user_data.get(name, {"version": "N/A", "date": "-"})
            # 마커 설정
            mark = "✅" if name.upper() in changed_list else "ℹ️"
            if any(name.lower() in err.lower() for err in errors): mark = "⚠️"
            report += f"{mark} {name.upper()}\n- 버전: {info['version']}\n- 날짜: {info['date']}\n\n"
        
        # 텔레그램 전송 (환경변수 설정 확인)
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if token and chat_id:
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={"chat_id": chat_id, "text": report})
        
        if changed_list:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
    else:
        print("모든 데이터가 일치하며 에러가 없습니다.")

if __name__ == "__main__":
    main()
