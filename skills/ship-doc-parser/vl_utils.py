"""
Общие утилиты для VL-обработки (qwen3-vl через Ollama).
Используется process_app.py и night_runner.py.
"""
import base64, json, re, subprocess, time
from pathlib import Path

OLLAMA   = "http://localhost:11434/api/generate"
VL_MODEL = "qwen3-vl:latest"


def log(tag, msg):
    print(f"[{tag:<8}] {msg}", flush=True)


def call_ollama_vl(png, prompt, *, retries=1, retry_delay=30,
                   timeout=600, req_file="/tmp/vl_req.json"):
    """Один VL-запрос к Ollama.

    Возвращает raw response (markdown-фенсы убраны).
    Делает до `retries` попыток с `retry_delay` сек между ними при пустом
    stdout или пустом response. На parse-ошибке retry не делает.
    Raises RuntimeError при пустом/невалидном ответе или ошибке Ollama.
    """
    img_b64 = base64.b64encode(Path(png).read_bytes()).decode()
    req = {"model": VL_MODEL, "prompt": prompt, "images": [img_b64],
           "stream": False, "options": {"temperature": 0.1, "repeat_penalty": 1.15, "num_predict": 2048}}
    Path(req_file).write_text(json.dumps(req))

    r = None
    for attempt in range(retries):
        r = subprocess.run(["curl", "-s", OLLAMA, "-d", f"@{req_file}"],
                           capture_output=True, text=True, timeout=timeout)
        if r.stdout.strip():
            try:
                if json.loads(r.stdout).get("response", "").strip():
                    break
            except Exception:
                break
        if attempt < retries - 1:
            log("VL", f"retry {attempt+1}/{retries} — жду {retry_delay} сек...")
            time.sleep(retry_delay)

    if r is None or not r.stdout.strip():
        exit_code = r.returncode if r else -1
        raise RuntimeError(f"Ollama вернул пустой ответ после {retries} попыток (exit={exit_code})")
    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        preview = r.stdout[:120].replace('\n', '\\n')
        raise RuntimeError(f"Ollama вернул невалидный JSON (len={len(r.stdout)}): {preview!r}")
    if "error" in resp:
        raise RuntimeError(f"Ollama error: {resp['error']}")
    raw = resp.get("response", "").strip()
    if not raw:
        raise RuntimeError("VL вернул пустой response (модель ещё остывает?)")
    return re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
