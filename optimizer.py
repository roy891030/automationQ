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
auth_resp = session.post('https://api.worldquantbrain.com/authentication')
if auth_resp.status_code != 201:
    logging.error("登入失敗")
    exit(1)

# 等待 alpha_id 並回傳績效

def simulate_and_evaluate(expr, settings):
    payload = {
        'type': 'REGULAR',
        'settings': settings,
        'regular': expr
    }
    try:
        r = session.post(SIMULATION_URL, json=payload)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.warning(f"模擬失敗: {e}")
        return None

    # 等待 alpha_id
    logging.info("⌛ 等待 alpha_id 出現...")
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
                    detail = session.get(ALPHA_DETAIL_URL.format(alpha_id))
                    if detail.status_code == 200:
                        data = detail.json().get("is", {})
                        sharpe = data.get("sharpe")
                        fitness = data.get("fitness")
                        turnover = data.get("turnover")
                        logging.info(f"📊 Sharpe: {sharpe:.2f}, Fitness: {fitness:.2f}, Turnover: {turnover:.2f}")
                        return {
                            'expression': expr,
                            'alpha_id': alpha_id,
                            'sharpe': sharpe,
                            'turnover': turnover,
                            'fitness': fitness,
                            'settings': settings
                        }
        time.sleep(5)
        waited += 5
    return None

# 儲存候選結果
candidate_results = []

# 執行每組 alpha
for expr in alpha_expressions:
    logging.info(f"🔍 測試 alpha: {expr}")

    combinations = itertools.product(UNIVERSE_LIST, DECAY_LIST, NEUTRALIZATION_LIST, TRUNCATION_LIST)
    for universe, decay, neutral, trunc in combinations:
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

        logging.info(f"🧪 組合: {settings}")
        result = simulate_and_evaluate(expr, settings)

        if result and result['sharpe'] and result['fitness'] and result['turnover']:
            s, f, t = result['sharpe'], result['fitness'], result['turnover']
            if s > 1.25 and 0.01 < t < 0.7 and f > 1.0:
                result['status'] = 'candidate'
                result['source'] = 'optimizer'
                candidate_results.append(result)
                logging.info("✅ 加入 candidate.json")
            else:
                logging.info("❌ 未通過篩選條件")
        else:
            logging.warning("⚠️ 無法取得完整績效資料")

# 寫入檔案
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