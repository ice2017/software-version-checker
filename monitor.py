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
        except Exception as e:
            pass # 전송 실패 시 무시

def get_latest_versions():
    versions = {}
    
    # 1. Chrome
    try:
        url = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            versions['chrome'] = {'version': json.loads(res.stdout)['versions'][0]['version']}
    except:
        versions['chrome'] = {'version': 'API 오류'}

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
    except:
        versions['edge'] = {'version': '연결 실패', 'date': '-'}

    # 3. Bandizip
    try:
        url = "https://www.bandisoft.com/bandizip/history/"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            pattern = r'class="cell1">v?([\d.]+)<[\s\S]*?class="cell2">([a-zA-Z]+\s+\d{1,2},\s+\d{4})<'
            match = re.search(pattern, res.stdout)
            if match:
                v = match.group(1).strip()
                d_raw = match.group(2).strip()
                try:
                    dt = datetime.strptime(d_raw, '%b %d, %Y')
                    d = dt.strftime('%Y/%m/%d')
                except: d = d_raw
                versions['bandizip'] = {'version': v, 'date': d}
    except:
        versions['bandizip'] = {'version': '연결 실패', 'date': '-'}

    # 4. Acrobat Reader (사용자 검증 curl 주소 및 37번 라인 패턴 반영)
    try:
        url = "https://helpx.adobe.com/acrobat/release-note/release-notes-acrobat-reader.html"
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=15)
        html_source = res.stdout
        if html_source:
            # title="26.001.21529" 패턴 추출
            v_match = re.search(r'title="(\d{2}\.\d{3}\.\d{5})', html_source)
            d_match = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', html_source)
            d_str = "-"
            if d_match:
                try:
                    d_raw = d_match.group(1).replace(',', '')
                    d_str = datetime.strptime(d_raw, "%B %d %Y").strftime("%Y/%m/%d")
                except: d_str = d_match.group(1)
            versions['acrobat_reader'] = {'version': v_match.group(1) if v_match else "파싱 실패", 'date': d_str}
    except:
        versions['acrobat_reader'] = {'version': '실행 오류', 'date': '-'}

    # 5. Windows 11 24H2 보안 업데이트
    try:
        url = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
        # 보안 정책 우회를 위해 curl 사용
        res = subprocess.run(f'curl -fsSL "{url}"', shell=True, capture_output=True, text=True, timeout=10)
        if res.stdout:
            # 24H2 섹션 근처에서 가장 상단의 빌드 번호와 KB 번호 추출
            # 패턴: 빌드 번호 (26100으로 시작) 및 KB5로 시작하는 번호 매칭
            build_match = re.search(r'26100\.\d+', res.stdout)
            kb_match = re.search(r'KB\d{7}', res.stdout)
            
            # 날짜 추출 (페이지 상단의 최신 업데이트 날짜)
            d_match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', res.stdout)
            d_str = "-"
            if d_match:
                try: d_str = datetime.strptime(d_match.group(1).replace(',',''), "%B %d %Y").strftime("%Y/%m/%d")
                except: pass
                
            versions['windows_11_24h2'] = {
                'version': f"Build {build_match.group(0)} ({kb_match.group(0)})" if build_match and kb_match else "추출 실패",
                'date': d_str
            }
    except:
        versions['windows_11_24h2'] = {'version': '연결 실패', 'date': '-'}

    return versions

def main():
    user_data_file = "versions.json"
    today = datetime.now().strftime("%Y/%m/%d")
    
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
    else:
        user_data = {}

    web_data = get_latest_versions()
    changed_keys = []

    for name in ['chrome', 'edge', 'bandizip', 'acrobat_reader', 'windows_11_24h2']:
        if name in web_data and "실패" not in web_data[name].get('version', '') and "오류" not in web_data[name].get('version', ''):
            latest_v = web_data[name]['version']
            current_v = user_data.get(name, {}).get('version', '0')
            
            if latest_v != current_v:
                changed_keys.append(name.upper().replace('_', ' '))
                save_date = today if name == 'chrome' else web_data[name].get('date', '-')
                user_data[name] = {"version": latest_v, "date": save_date}

    # 업데이트가 감지되었을 때만 텔레그램 전송
    if changed_keys:
        report = "🔔 [S/W 업데이트 모니터링 최종 정합성 리포트]\n\n"
        report += f"🚀 업데이트 감지: {', '.join(changed_keys)}\n\n"
        report += "━━━━━ 현재 전체 현황 ━━━━━\n"
        for sw in ['chrome', 'edge', 'bandizip', 'acrobat_reader']:
            info = user_data.get(sw, {"version": "데이터 없음", "date": "-"})
            mark = "✅" if sw.upper().replace('_', ' ') in changed_keys else "ℹ️"
            date_label = "조회 날짜" if sw == 'chrome' else "날짜"
            report += f"{mark} {sw.upper().replace('_', ' ')}\n"
            report += f"- 버전: {info['version']}\n"
            report += f"- {date_label}: {info['date']}\n\n"
        
        send_telegram_msg(report)
        
        # 새로운 버전 정보 파일 저장
        with open(user_data_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
