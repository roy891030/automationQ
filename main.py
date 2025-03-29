import json
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
import os

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 讀取帳密
with open('credentials.txt') as f:
    username, password = json.load(f)

SIMULATION_URL = 'https://api.worldquantbrain.com/simulations'
ALPHAS_URL = f'https://api.worldquantbrain.com/users/YL98528/alphas'
ALPHA_DETAIL_URL = 'https://api.worldquantbrain.com/alphas/{}'
SUBMIT_URL = 'https://api.worldquantbrain.com/alphas/{}/submit'

# 從檔案讀取 alpha 表達式清單
if not os.path.exists('alpha_list.txt'):
    with open('alpha_list.txt', 'w') as f:
        f.write('rank(ts_delta(close, 5))\n')
        f.write('-ts_rank(volume, 10)\n')
        f.write('log(divide(close, ts_mean(close, 5)))\n')
    logging.warning("alpha_list.txt 不存在，已自動建立範例檔案，請確認內容後重新執行。")
    exit(0)

with open('alpha_list.txt') as f:
    alpha_expressions = [line.strip() for line in f if line.strip()]

results_log = []

# 等待 alpha_id 出現（包含錯誤判斷）
def wait_for_alpha_id(session, expr, max_wait=60, check_interval=5):
    waited = 0
    while waited < max_wait:
        resp = session.get(ALPHAS_URL)
        if resp.status_code == 200:
            alphas = resp.json().get("results", [])
            for entry in alphas:
                if entry.get("regular", {}).get("code") == expr:
                    if entry.get("status") == "ERROR":
                        logging.warning("❌ 模擬已建立，但系統標記此 alpha 為錯誤，跳過")
                        results_log.append({
                            "expression": expr,
                            "status": "simulation_status_error"
                        })
                        return None
                    return entry.get("id")
        time.sleep(check_interval)
        waited += check_interval
        logging.info(f"⏳ 等待 alpha_id 中... 已等候 {waited} 秒")
    logging.warning("⌛ 超過等待時間，未取得 alpha_id")
    results_log.append({"expression": expr, "status": "timeout"})
    return None

# 查詢詳細績效（移除年度表現）
def fetch_alpha_metrics(session, alpha_id):
    detail_resp = session.get(ALPHA_DETAIL_URL.format(alpha_id))
    if detail_resp.status_code == 200:
        data = detail_resp.json()
        is_data = data.get("is", {})

        metrics = {
            "sharpe": is_data.get("sharpe"),
            "turnover": is_data.get("turnover"),
            "fitness": is_data.get("fitness"),
            "returns": is_data.get("returns"),
            "drawdown": is_data.get("drawdown"),
            "margin": is_data.get("margin"),
            "alpha_id": alpha_id,
            "status": "unknown"
        }

        return metrics
    else:
        logging.warning(f"❗ 無法取得 alpha_id={alpha_id} 的績效資料")
        return {
            "sharpe": None,
            "turnover": None,
            "fitness": None,
            "status": "detail_error"
        }

# 建立 session 並登入
session = requests.Session()
session.auth = HTTPBasicAuth(username, password)
resp = session.post('https://api.worldquantbrain.com/authentication')
if resp.status_code != 201:
    logging.error("登入失敗")
    exit(1)

# 開始模擬流程
for expr in alpha_expressions:
    logging.info(f"🚀 模擬 alpha: {expr}")

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
            'visualization': False,
            'testPeriod': 'P1Y'
        },
        'regular': expr
    }

    try:
        r = session.post(SIMULATION_URL, json=payload)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.warning(f"模擬建立失敗: {e}")
        results_log.append({
            "expression": expr,
            "status": "simulation_error",
            "error_message": str(e),
            "details": r.text if 'r' in locals() else "no response"
        })
        continue

    logging.info("⌛ 開始等待 alpha_id 出現...")
    alpha_id = wait_for_alpha_id(session, expr)
    if not alpha_id:
        continue

    # 查詢詳細績效
    metrics = fetch_alpha_metrics(session, alpha_id)
    sharpe = metrics.get("sharpe")
    turnover = metrics.get("turnover")
    fitness = metrics.get("fitness")

    if sharpe is not None and turnover is not None and fitness is not None:
        logging.info(f"📊 Sharpe: {sharpe:.2f}, Turnover: {turnover:.2f}, Fitness: {fitness:.2f}")
        logging.info(f"📈 Returns: {metrics.get('returns')}%, Drawdown: {metrics.get('drawdown')}%, Margin: {metrics.get('margin')}‱")

        metrics["expression"] = expr
        if sharpe > 1.25 and 0.01 < turnover < 0.7 and fitness > 1.0:
            logging.info("✅ 此 alpha 通過條件，將提交")
            metrics["status"] = "pass"
            submit_resp = session.post(SUBMIT_URL.format(alpha_id))
            if submit_resp.status_code == 200:
                logging.info(f"📩 已成功提交 alpha_id={alpha_id}")
            else:
                logging.warning(f"❗ 提交失敗：{submit_resp.status_code}")
        else:
            metrics["status"] = "fail"
            logging.info("❌ 此 alpha 未通過條件")
    else:
        logging.warning("⚠️ 無法取得完整績效資料")
        metrics["expression"] = expr
        metrics["status"] = "no_data"

    results_log.append(metrics)

# 儲存所有模擬結果
if os.path.exists("results.json") and os.path.getsize("results.json") > 0:
    with open("results.json") as f:
        existing = json.load(f)
else:
    existing = []

existing.extend(results_log)

with open("results.json", "w") as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)

logging.info("✅ 所有模擬結果已寫入 results.json")