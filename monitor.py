import requests
from bs4 import BeautifulSoup
import json
import os

# 1. 대상 소프트웨어별 버전 추출 함수
def get_latest_versions():
    versions = {}
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    try:
        # Chrome (Google API)
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        versions['chrome'] = requests.get(chrome_api).json()['versions'][0]['version']

        # Edge (Release Notes)
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header)
        edge_soup = BeautifulSoup(edge_res.text, 'html.parser')
        versions['edge'] = edge_soup.select_one('h2').text.split(' ')[2] # "Version 148.0..." 에서 추출

        # Bandizip (History Page)
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_res = requests.get(bandi_url, headers=header)
        bandi_soup = BeautifulSoup(bandi_res.text, 'html.parser')
        versions['bandizip'] = bandi_soup.select_one('.history-item h2').text.strip()

        # Acrobat (Release Notes - 최신 msp 파일명 패턴 추출)
        acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
        acrobat_res = requests.get(acrobat_url, headers=header)
        acrobat_soup = BeautifulSoup(acrobat_res.text, 'html.parser')
        # 가장 상단의 링크 텍스트 추출
        versions['acrobat'] = acrobat_soup.select_one('.reference.internal').text.split(' ')[0]
        
    except Exception as e:
        print(f"Error fetching versions: {e}")
        
    return versions

# 2. 메인 로직: 비교 및 갱신
def main():
    # 기존 버전 로드
    with open('versions.json', 'r') as f:
        old_versions = json.load(f)

    new_versions = get_latest_versions()
    changed = False
    message = "🔔 [소프트웨어 업데이트 감지]\n\n"

    for name, new_v in new_versions.items():
        old_v = old_versions.get(name)
        if new_v and old_v != new_v:
            message += f"✅ {name.capitalize()}: {old_v} -> {new_v}\n"
            old_versions[name] = new_v
            changed = True

    if changed:
        print(message)
        # 변경된 버전 저장
        with open('versions.json', 'w') as f:
            json.dump(old_versions, f, indent=2)
        # 여기에 나중에 텔레그램 알림 코드를 추가할 수 있습니다.
    else:
        print("변경 사항 없음")

if __name__ == "__main__":
    main()
