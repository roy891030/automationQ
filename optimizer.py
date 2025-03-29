import json
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
import os
import itertools

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 讀取帳密
with open('credentials.txt') as f:
    username, password = json.load(f)

SIMULATION_URL = 'https://api.worldquantbrain.com/simulations'
ALPHAS_URL = f'https://api.worldquantbrain.com/users/YL98528/alphas'
ALPHA_DETAIL_URL = 'https://api.worldquantbrain.com/alphas/{}'

# 可調參數
UNIVERSE_LIST = ['TOP3000', 'TOP1000', 'TOP500', 'TOP200', 'TOPSP500']
DECAY_LIST = [0, 1, 3, 5]
NEUTRALIZATION_LIST = ['NONE', 'MARKET', 'SECTOR', 'INDUSTRY', 'SUBINDUSTRY']
TRUNCATION_LIST = [0.02, 0.05, 0.08, 0.1]

# 讀取待優化的 alpha list
with open('tune_alpha_list.txt') as f:
    alpha_expressions = [line.strip() for line in f if line.strip()]

# 登入
session = requests.Session()
session.auth = HTTPBasicAuth(username, password)
resp = session.post('https://api.worldquantbrain.com/authentication')
if resp.status_code != 201:
    logging.error("登入失敗")
    exit(1)

# 函式：模擬 alpha 並回傳績效
def simulate_alpha(expr, settings):
    payload = {
        'type': 'REGULAR',
        'settings': settings,
        'regular': expr
    }
    try:
        time.sleep(2)  # 避免頻繁請求觸發 rate limit
        r = session.post(SIMULATION_URL, json=payload)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.warning(f"模擬失敗: {e}")
        return None

    waited = 0
    while waited < 60:
        resp = session.get(ALPHAS_URL)
        if resp.status_code == 200:
            alphas = resp.json().get("results", [])
            for entry in alphas:
                if entry.get("regular", {}).get("code") == expr:
                    if entry.get("status") == "ERROR":
                        return None
                    alpha_id = entry.get("id")
                    detail_resp = session.get(ALPHA_DETAIL_URL.format(alpha_id))
                    if detail_resp.status_code == 200:
                        data = detail_resp.json().get("is", {})
                        return {
                            'expression': expr,
                            'alpha_id': alpha_id,
                            'sharpe': data.get("sharpe"),
                            'turnover': data.get("turnover"),
                            'fitness': data.get("fitness"),
                            'settings': settings
                        }
        time.sleep(5)
        waited += 5
    return None

# 搜集所有結果
candidate_results = []

# 嘗試所有參數組合
for expr in alpha_expressions:
    logging.info(f"🔍 最佳化 alpha: {expr}")
    for universe, decay, neutral, trunc in itertools.product(UNIVERSE_LIST, DECAY_LIST, NEUTRALIZATION_LIST, TRUNCATION_LIST):
        logging.info(f"🧪 測試組合: universe={universe}, decay={decay}, neutralization={neutral}, truncation={trunc}")
        settings = {
            'instrumentType': 'EQUITY',
            'region': 'USA',
            'universe': universe,
            'delay': 1,
            'decay': decay,
            'neutralization': neutral,
            'truncation': trunc,
            'pasteurization': 'ON',
            'unitHandling': 'VERIFY',
            'nanHandling': 'OFF',
            'language': 'FASTEXPR',
            'visualization': False,
            'testPeriod': 'P1Y'
        }
        result = simulate_alpha(expr, settings)
        if result and result['sharpe'] and result['fitness'] and result['turnover']:
            sharpe = result['sharpe']
            fitness = result['fitness']
            turnover = result['turnover']
            if sharpe > 1.25 and 0.01 < turnover < 0.7 and fitness > 1.0:
                logging.info(f"✅ 符合條件！Sharpe: {sharpe}, Fitness: {fitness}, Turnover: {turnover}")
                result['status'] = 'candidate'
                result['source'] = 'optimizer'
                candidate_results.append(result)

# 寫入 candidate.json
if candidate_results:
    if os.path.exists("candidate.json") and os.path.getsize("candidate.json") > 0:
        with open("candidate.json") as f:
            existing = json.load(f)
    else:
        existing = []
    existing.extend(candidate_results)
    with open("candidate.json", "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    logging.info("✅ 所有優化結果已寫入 candidate.json")
else:
    logging.info("❌ 沒有找到更好的參數組合")