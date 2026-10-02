"""Google Cloud Vision 으로 이미지에서 중국어 텍스트 추출

키는 Streamlit secrets 또는 환경변수에서 읽습니다.
(코드에 직접 쓰지 마세요 — 공개 저장소에 올라가면 키가 털립니다)
"""
import base64
import os

import requests

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"


def _api_key():
    """secrets → 환경변수 순서로 키를 찾는다."""
    try:
        import streamlit as st
        if "GOOGLE_VISION_KEY" in st.secrets:
            return st.secrets["GOOGLE_VISION_KEY"]
    except Exception:
        pass
    for name in ("GOOGLE_VISION_KEY", "GOOGLE_API_KEY", "VISION_API_KEY"):
        v = os.environ.get(name)
        if v:
            return v
    return None


def extract_text_from_image(image_path, timeout=60):
    """이미지 파일 경로 → 추출된 텍스트 (실패 시 '오류: ...')"""
    key = _api_key()
    if not key:
        return "오류: GOOGLE_VISION_KEY 가 설정되지 않았습니다."

    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"오류: 이미지를 읽을 수 없습니다 ({e})"

    payload = {
        "requests": [{
            "image": {"content": encoded},
            "features": [{"type": "TEXT_DETECTION"}],
            # 중국어(번체/간체) 우선 인식
            "imageContext": {"languageHints": ["zh-TW", "zh-CN", "zh"]},
        }]
    }

    try:
        r = requests.post(VISION_URL, params={"key": key},
                          json=payload, timeout=timeout)
    except Exception as e:
        return f"오류: Vision 서버에 연결하지 못했습니다 ({e})"

    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            msg = r.text[:200]
        return f"오류: Vision API {r.status_code} — {msg}"

    try:
        result = r.json()
    except Exception:
        return "오류: Vision 응답을 해석할 수 없습니다."

    resp = (result.get("responses") or [{}])[0]
    if "error" in resp:
        return f"오류: {resp['error'].get('message', '알 수 없는 오류')}"

    # fullTextAnnotation 이 줄바꿈을 가장 잘 보존한다
    full = (resp.get("fullTextAnnotation") or {}).get("text")
    if full and full.strip():
        return full.strip()

    anns = resp.get("textAnnotations") or []
    if anns:
        return anns[0].get("description", "").strip()

    return "오류: 사진에서 글자를 찾지 못했습니다. 더 밝고 선명하게 다시 찍어주세요."
