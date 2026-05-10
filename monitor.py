import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

def get_latest_versions():
    versions = {}
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    # 1. Chrome (안정적)
    try:
        chrome_api = "https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions"
        c_data = requests.get(chrome_api, timeout=20).json()
        versions['chrome'] = {"version": c_data['versions'][0]['version'], "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Chrome Error: {e}")

    # 2. Edge (선택자 범위를 h1~h3로 확대)
    try:
        edge_url = "https://learn.microsoft.com/en-us/deployedge/microsoft-edge-relnotes-stable-channel"
        edge_res = requests.get(edge_url, headers=header, timeout=20)
        edge_soup = BeautifulSoup(edge_res.text, 'html.parser')
        # "Version" 단어가 포함된 모든 태그 탐색
        target = None
        for tag in edge_soup.find_all(['h2', 'h1', 'h3']):
            if 'Version' in tag.text:
                target = tag
                break
        if target:
            text = target.text.strip()
            v_part = text.split(':')[0].replace('Version', '').strip()
            d_part = text.split(':')[1].strip() if ':' in text else datetime.now().strftime("%Y/%m/%d")
            versions['edge'] = {"version": v_part, "date": d_part}
        else: print("Edge tag not found")
    except Exception as e: print(f"Edge Error: {e}")

    # 3. Bandizip (안정적)
    try:
        bandi_url = "https://www.bandisoft.com/bandizip/history/"
        bandi_soup = BeautifulSoup(requests.get(bandi_url, headers=header, timeout=20).text, 'html.parser')
        v_tag = bandi_soup.select_one('.history-item h2')
        if v_tag:
            versions['bandizip'] = {"version": v_tag.text.strip(), "date": datetime.now().strftime("%Y/%m/%d")}
    except Exception as e: print(f"Bandizip Error: {e}")

    # 4. Acrobat (재시도 로직 추가)
    for i in range(2): # 최대 2번 시도
        try:
            acrobat_url = "https://www.adobe.com/devnet-docs/acrobatetk/tools/ReleaseNotesDC/index.html"
            acrobat_res = requests.get(acrobat_url, headers=header, timeout=30) # 30초로 증액
            acrobat_soup = BeautifulSoup(acrobat_res.text, 'html.parser')
            a_tag = acrobat_soup.select_one('li.toctree-l1 a.reference.internal')
            if a_tag:
                raw = a_tag.text.strip() # "26.001.21529 (Planned update)"
                versions['acrobat'] = {
                    "version": raw.split(' ')[0],
                    "date": raw.split('(')[1].replace(')', '') if '(' in raw else "Check Site"
                }
                break # 성공 시 루프 탈출
        except Exception as e:
            print(f"Acrobat Attempt {i+1} Error: {e}")
            time.sleep(5) # 5초 대기 후 재시도

    return versions

# ... (main 함수와 send_telegram_msg는 이전과 동일)
