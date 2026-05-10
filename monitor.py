import os
import re
import json
import subprocess
import requests
from datetime import datetime

# 텔레그램 전송 함수
def send_telegram_msg(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message}
        try:
            requests.post(url, json=payload, timeout=10)
        except:
            pass

def get_latest_versions():
    versions = {}
    
    # 1. Chrome
    try:
        url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            versions['chrome'] = {'version': json.loads(res.stdout)['versions'][0]['version']}
    except: versions['chrome'] = {'version': '오류'}

    # 2. Microsoft Edge
    try:
        url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnote-stable-channel"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            v_m = re.search(r'Version\s+([\d.]+)', res.stdout)
            d_m = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.stdout)
            d_str = "-"
            if d_m:
                try: d_str = datetime.strptime(d_m.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
                except: pass
            versions['edge'] = {'version': v_m.group(1) if v_m else "실패", 'date': d_str}
    except: versions['edge'] = {'version': '오류', 'date': '-'}

    # 3. Bandizip
    try:
        url = "https://www.bandisoft.com/bandizip/history/"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            pattern = r'class="cell1">v?([\d.]+)<[\s\S]*?class="cell2">([a-zA-Z]+\s+\d{1,2},\s+\d{4})<'
            match = re.search(pattern, res.stdout)
            if match:
                v = match.group(1).strip()
                try: d = datetime.strptime(match.group(2).strip(), '%b %d, %Y').strftime('%Y/%m/%d')
                except: d = match.group(2)
                versions['bandizip'] = {'version': v, 'date': d}
    except: versions['bandizip'] = {'version': '오류', 'date': '-'}

    # 4. Acrobat Reader (보내주신 helpx 소스 37번 라인 기반)
    try:
        url = "https://helpx.adobe.com/acrobat/release-note/release-notes-acrobat-reader.html"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=15)
        if res.stdout:
            # v_match: title="26.001.21529" 추출
            v_match = re.search(r'title="(\d{2}\.\d{3}\.\d{5})', res.stdout)
            # d_match: "May 01, 2026" 추출
            d_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', res.stdout)
            d_str = "-"
            if d_match:
                try: d_str = datetime.strptime(d_match.group(1).replace(',', ''), "%B %d %Y").strftime("%Y/%m/%d")
                except: d_str = d_match.group(1)
            versions['acrobat_reader'] = {'version': v_match.group(1) if v_match else "실패", 'date': d_str}
    except: versions['acrobat_reader'] = {'version': '오류', 'date': '-'}

# 5. Windows 11 24H2 (보안 업데이트 및 실제 출시일 추출)
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        # Rocky 9의 curl을 사용하여 차단 우회
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        
        if res.stdout:
            # 24H2 섹션 이후만 남김
            content_24h2 = res.stdout.split("24H2")[-1] 
            
            # 빌드 번호(26100.xxxx)를 기준으로 텍스트를 쪼개어 표 내부 데이터에 접근
            # 첫 번째 빌드 번호가 적힌 주변 텍스트에서 KB와 날짜를 찾음
            builds = re.findall(r'26100\.\d+', content_24h2)
            kbs = re.findall(r'KB\d{7}', content_24h2)
            
            # 날짜 패턴 (YYYY-MM-DD 또는 영문 날짜)
            # 지원 종료일 같은 미래 날짜를 피하기 위해 2024~2026년 범위로 한정
            dates = re.findall(r'202[4-6]-\d{2}-\d{2}|[A-Z][a-z]+ \d{1,2}, \d{4}', content_24h2)
            
            # 데이터 정합성 체크: 빌드 번호가 나온 지점 이후의 첫 번째 날짜가 실제 출시일임
            latest_build = builds[0] if builds else "추출 실패"
            latest_kb = kbs[0] if kbs else ""
            
            # 지원 종료일(상단)이 아닌 실제 업데이트 날짜(표 내부)를 가져오기 위해 
            # 보통 빌드/KB 번호 근처에 있는 날짜를 선택 (결과 리스트에서 적절한 인덱스 탐색)
            d_str = "-"
            if dates:
                # 리스트를 돌며 오늘 날짜보다 미래가 아닌 첫 번째 날짜 선택
                for d_raw in dates:
                    clean_d = d_raw.replace(',', '')
                    try:
                        if '-' in clean_d: # YYYY-MM-DD
                            dt = datetime.strptime(clean_d, "%Y-%m-%d")
                        else: # May 01, 2026
                            dt = datetime.strptime(clean_d, "%B %d %Y")
                        
                        # 미래 날짜(예: 2028년 지원종료일)가 아니면 선택
                        if dt <= datetime.now():
                            d_str = dt.strftime("%Y/%m/%d")
                            break
                    except: continue

            versions['windows_11_24h2'] = {
                'version': f"Build {latest_build} ({latest_kb})" if latest_kb else f"Build {latest_build}",
                'date': d_str
            }
    except Exception as e:
        versions['windows_11_24h2'] = {'version': '오류', 'date': '-'}

    return versions

def main():
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
    else: user_data = {}

    # acrobat_reader로 키를 통일하기 위해 기존 acrobat 키 제거 (정리 로직)
    if 'acrobat' in user_data:
        del user_data['acrobat']

    web_data = get_latest_versions()
    changed_keys = []
    
    # 순서 보장을 위한 대상 리스트
    targets = ['chrome', 'edge', 'bandizip', 'acrobat_reader', 'windows_11_24h2']

    for name in targets:
        if name in web_data and "오류" not in web_data[name]['version'] and "실패" not in web_data[name]['version']:
            latest_v = web_data[name]['version']
            current_v = user_data.get(name, {}).get('version', '0')
            
            if latest_v != current_v:
                changed_keys.append(name.upper().replace('_', ' '))
                save_date = today if name == 'chrome' else web_data[name].get('date', '-')
                user_data[name] = {"version": latest_v, "date": save_date}

    if changed_keys:
        report = "🔔 [S/W 업데이트 모니터링 최종 정합성 리포트]\n\n"
        report += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        for sw in targets:
            info = user_data.get(sw, {"version": "데이터 없음", "date": "-"})
            mark = "✅" if sw.upper().replace('_', ' ') in changed_keys else "ℹ️"
            date_label = "조회 날짜" if sw == 'chrome' else "날짜"
            report += f"{mark} {sw.upper().replace('_', ' ')}\n"
            report += f"- 버전: {info['version']}\n"
            report += f"- {date_label}: {info['date']}\n\n"
        
        send_telegram_msg(report)
        
        # 파일 저장
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
