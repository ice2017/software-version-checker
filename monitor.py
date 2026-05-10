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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
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
        else: errors.append("Edge: 패턴 매칭 실패 (HTML 구조 변경 의심)")
    except Exception as e: errors.append(f"Edge: {str(e)}")

    # --- 3. Bandizip ---
    try:
        res = requests.get("https://www.bandisoft.com/bandizip/history/", headers=header, timeout=30)
        # ld+json 정밀 분석
        data = re.search(r'<script type="application/ld\+json">(.*?)</script>', res.text, re.S)
        if data:
            js_data = json.loads(data.group(1))
            items = js_data if isinstance(js_data, list) else [js_data]
            for item in items:
                if item.get('@type') == 'SoftwareApplication':
                    v = item.get('softwareVersion', '').replace('v', '').strip()
                    versions['bandizip'] = {"version": f"v{v}", "date": format_date(item.get('datePublished', ''))}
                    break
        if 'bandizip' not in versions: errors.append("Bandizip: JSON 데이터 추출 실패")
    except Exception as e: errors.append(f"Bandizip: {str(e)}")

    # --- 4. Acrobat ---
    try:
        # Acrobat 전용 세션 및 타임아웃 증액
        with requests.Session() as s:
            s.headers.update(header)
            res = s.get("https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html", timeout=45)
            # 메타 태그 우선 탐색
            match = re.search(r'<link rel="next" title="(.*?) Planned update, (.*?)"', res.text)
            if match:
                versions['acrobat'] = {"version": match.group(1).strip(), "date": format_date(match.group(2).strip())}
            else:
                # 본문 정규식 백업
                match_text = re.search(r'(\d{2}\.\d{3}\.\d{5})\s+Planned\s+update,\s+([a-zA-Z]+\s+\d+,\s+\d+)', res.text)
                if match_text:
                    versions['acrobat'] = {"version": match_text.group(1).strip(), "date": format_date(match_text.group(2).strip())}
                else: errors.append("Acrobat: 모든 파싱 패턴 실패")
    except Exception as e: errors.append(f"Acrobat: {str(e)}")

    return versions, errors

def send_telegram(msg):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if token and chat_id:
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={"chat_id": chat_id, "text": msg})

def main():
    json_path = 'versions.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        user_data = json.load(f)

    web_data, errors = get_latest_versions()
    changed_list = []

    # 비교 로직
    for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
        if name in web_data:
            old_v = str(user_data.get(name, {}).get('version', ''))
            new_v = str(web_data[name]['version'])
            if old_v != new_v:
                changed_list.append(name.upper())
                user_data[name] = web_data[name]

    # 알림 발송 로직
    if changed_list or errors:
        report = "🔔 [S/W 보안 모니터링 리포트]\n\n"
        
        if changed_list:
            report += f"🚀 업데이트 발견: {', '.join(changed_list)}\n\n"
        
        if errors:
            report += "❌ 수집 실패 리스트:\n"
            report += "\n".join([f"• {e}" for e in errors]) + "\n\n"

        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        for name in ['chrome', 'edge', 'bandizip', 'acrobat']:
            info = user_data.get(name, {"version": "수집실패", "date": "-"})
            mark = "✅" if name.upper() in changed_list else "ℹ️"
            if any(name.lower() in err.lower() for err in errors): mark = "⚠️"
            report += f"{mark} {name.upper()}\n- 버전: {info['version']}\n- 날짜: {info['date']}\n\n"
        
        send_telegram(report)
        if changed_list:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
    else:
        print("모든 데이터가 최신이며 에러가 없습니다.")

if __name__ == "__main__":
    main()
