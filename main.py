import json
import requests
from requests.auth import HTTPBasicAuth
import time
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 讀取帳密
with open('credentials.txt') as f:
    username, password = json.load(f)

# 模擬設定
SIMULATION_URL = 'https://api.worldquantbrain.com/simulations'
SUBMIT_URL = 'https://api.worldquantbrain.com/alphas/{}/submit'
HEADERS = {
    'Content-Type': 'application/json'
}

# 預設 alpha 表達式清單
alpha_expressions = [
    "rank(ts_delta(close, 5))",
    "-ts_rank(volume, 10)",
    "zscore(ts_min(low, 20))",
    "log(divide(close, ts_mean(close, 5)))",
]

# 判斷條件
def is_promising(result):
    try:
        is_data = result['is']
        sharpe = is_data['sharpe']
        turnover = is_data['turnover']
        fitness = is_data['fitness']
        logging.info(f"Sharpe: {sharpe}, Turnover: {turnover}, Fitness: {fitness}")

        if sharpe > 1.25 and 0.01 < turnover < 0.7 and fitness > 1.0:
            return True
        return False
    except:
        return False

# 執行模擬與提交
session = requests.Session()
session.auth = HTTPBasicAuth(username, password)

# 登入（一次）
resp = session.post('https://api.worldquantbrain.com/authentication')
if resp.status_code != 201:
    logging.error("登入失敗")
    exit(1)

for expr in alpha_expressions:
    logging.info(f"模擬 alpha: {expr}")

    payload = {
        'type': 'REGULAR',
        'settings': {
            'instrumentType': 'EQUITY',
            'region': 'USA',
            'universe': 'TOP3000',
            'delay': 1,
            'decay': 0,
            'neutralization': 'INDUSTRY',
            'truncation': 0.08,
            'pasteurization': 'ON',
            'unitHandling': 'VERIFY',
            'nanHandling': 'OFF',
            'language': 'FASTEXPR',
            'visualization': False
        },
        'regular': expr
    }

    r = session.post(SIMULATION_URL, json=payload)
    if r.status_code != 201:
        logging.warning(f"模擬失敗: {r.text}")
        continue

    sim_url = r.headers.get('location')
    time.sleep(10)  # 等待模擬完成
    result = session.get(sim_url).json()

    if result.get("status") == "COMPLETE" and is_promising(result):
        alpha_id = result.get("alpha")
        if alpha_id:
            submit_resp = session.post(SUBMIT_URL.format(alpha_id))
            logging.info(f"已提交 alpha_id={alpha_id}, status={submit_resp.status_code}")
        else:
            logging.warning("未取得 alpha_id")
    else:
        logging.info("此 alpha 未通過條件")