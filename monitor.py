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
    # 브라우저와 거의 동일한 수준의 헤더 구성
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Referer': 'https://www.google.com/'
    }
    
    # 1. Chrome (API)
    try:
        res = requests.get("https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions", timeout=20)
        versions['chrome'] = {"version": str(res.json()['versions'][0]['version']), "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: errors.append(f"Chrome: {str(e)}")

    # 2. Microsoft Edge
    try:
        res = requests.get("https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel", headers=header, timeout=30)
        match = re.search(r'Version\s+([\d\.]+):\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
        if match:
            versions['edge'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
        else: errors.append("Edge: 패턴 매칭 실패")
    except Exception as e: errors.append(f"Edge: {str(e)}")

    # 3. Bandizip (BeautifulSoup으로 안전하게 접근)
    try:
        res = requests.get("https://www.bandisoft.com/bandizip/history/", headers=header, timeout=30)
        soup = BeautifulSoup(res.text, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')
        found_b = False
        for s in scripts:
            if not s.string: continue
            try:
                data = json.loads(s.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if 'softwareVersion' in item:
                        v = item['softwareVersion'].replace('v', '').strip()
                        versions['bandizip'] = {"version": f"v{v}", "date": format_date(item.get('datePublished', ''))}
                        found_b = True; break
            except: continue
            if found_b: break
        if not found_b: errors.append("Bandizip: JSON 데이터 추출 실패")
    except Exception as e: errors.append(f"Bandizip: {str(e)}")

    # 4. Adobe Acrobat (타임아웃 및 재시도 로직 강화)
    acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
    try:
        with requests.Session() as s:
            s.headers.update(header)
            # 타임아웃은 45초로 유지하되, 실패 시 1회 즉시 재시도
            try:
                res = s.get(acrobat_url, timeout=45)
            except:
                time.sleep(5)
                res = s.get(acrobat_url, timeout=45)
            
            # 파싱 로직
            match = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+Planned\s+update,\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
            if match:
                versions['acrobat'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
            else:
                soup = BeautifulSoup(res.text, 'html.parser')
                link_tag = soup.find('link', rel='next')
                if link_tag and 'title' in link_tag.attrs:
                    t = link_tag['title']
                    v_m = re.search(r'(\d{2}\.\d{3}\.\d{5})', t)
                    d_m = re.search(r'([a-zA-Z]+\s+\d+,\s+\d+)', t)
                    if v_m:
                        versions['acrobat'] = {"version": v_m.group(1), "date": format_date(d_m.group(1)) if d_m else "2026/05/01"}
                
            if 'acrobat' not in versions: errors.append("Acrobat: 파싱 실패")
    except Exception as e: errors.append(f"Acrobat: {str(e)}")

    return versions, errors

def main():
    json_path = 'versions.json'
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
    except:
        user_data = {}

    web_data, errors = get_latest_versions()
    changed_keys = []

    # 비교 로직
    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in web_data:
            old_v = str(user_data.get(name, {}).get('version', '')).strip()
            new_v = str(web_data[name]['version']).strip()
            if old_v != new_v:
                changed_keys.append(name.upper())
                user_data[name] = web_data[name]

    # 알림 발송 (업데이트가 있거나, 에러가 발생한 경우 무조건 발송)
    if changed_keys or errors:
        msg = "🔔 [S/W 업데이트 모니터링 리포트]\n\n"
        if changed_keys:
            msg += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        if errors:
            msg += "❌ 수집 오류 내역:\n" + "\n".join([f"• {e}" for e in errors]) + "\n\n"
        
        msg += "━━━━━ 현재 상태 ━━━━━\n"
        for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
            info = user_data.get(name, {"version": "Error", "date": "-"})
            mark = "✅" if name.upper() in changed_keys else "ℹ️"
            if any(name.lower() in err.lower() for err in errors): mark = "⚠️"
            msg += f"{mark} {name.upper()}\n- 버전: {info['version']}\n- 날짜: {info['date']}\n\n"
        
        # 텔레그램 발송
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if token and chat_id:
            try:
                requests.get(f"https://api.telegram.org/bot{token}/sendMessage", 
                             params={"chat_id": chat_id, "text": msg}, timeout=15)
            except Exception as te:
                print(f"텔레그램 발송 실패: {te}")
        
        # 파일 저장
        if changed_keys:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
    else:
        print("모든 제품이 최신 상태이며 에러가 없습니다.")

if __name__ == "__main__":
    main()
