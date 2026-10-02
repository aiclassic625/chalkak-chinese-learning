"""중국어 원문 → 학습자료 (병음 · 해석 · HSK 어휘 분석)

DeepSeek API 를 사용합니다. 키는 secrets/환경변수에서 읽습니다.
"""
import json
import os
import re

from openai import OpenAI

MODEL = "deepseek-v4-pro"          # 검증 완료 (deepseek-flash 도 가능)
EFFORT = "none"                    # 사고 토큰 0 → 6배 빠르고 저렴

SYSTEM = (
    "당신은 중국어 교육 전문가입니다. "
    "학습자가 원문의 맥락을 끊지 않고 바로 이해할 수 있게, "
    "깔끔하고 읽기 쉬운 학습자료를 만듭니다."
)

PROMPT = """중국어 텍스트를 학습 자료로 변환해주세요.

텍스트:
{text}

출력 형식 (반드시 아래 형식을 그대로 지켜주세요):

---

**📌 문장 1**
- **원문:** [중국어 문장]
- **병음:** [전체 병음]
- **해석:** [한국어 뜻]
- **📝 간체 변환:** (원문이 번체일 경우에만 추가)

- **HSK 4급 이상 단어 분석 (한 글자씩 뜻 풀이):**
  - [단어] (병음): 뜻
    - (한자 풀이) [첫째 글자]: [그 글자의 뜻] + [둘째 글자]: [그 글자의 뜻]

---

**📌 문장 2**
- **원문:** [중국어 문장]
- **병음:** [병음]
- **해석:** [한국어 뜻]

- **HSK 4급 이상 단어 분석:**
  - [단어] (병음): 뜻
    - (한자 풀이) [첫째 글자]: [뜻] + [둘째 글자]: [뜻]

---

규칙:
- 간체 변환 항목은 원문이 번체(正體字/繁體字)일 때만 넣고, 간체(简体字)면 완전히 생략하세요.
- HSK 4급 이상 단어만 추출하세요.
- 부수와 획수는 절대 표시하지 마세요.
- 각 단어의 한 글자씩 뜻 풀이만 제공하세요.
- 모든 문장에 대해 위 형식을 반복하세요.
- 표는 사용하지 마세요.
"""


def _api_key():
    try:
        import streamlit as st
        if "DEEPSEEK_KEY" in st.secrets:
            return st.secrets["DEEPSEEK_KEY"]
    except Exception:
        pass
    for name in ("DEEPSEEK_KEY", "DEEPSEEK_API_KEY"):
        v = os.environ.get(name)
        if v:
            return v
    return None


def _client():
    key = _api_key()
    if not key:
        return None
    return OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")


def generate_study_material(chinese_text):
    """중국어 텍스트 → 마크다운 학습자료 (실패 시 '오류: ...')"""
    if not chinese_text or len(chinese_text.strip()) < 2:
        return "오류: 텍스트가 너무 짧습니다."

    client = _client()
    if client is None:
        return "오류: DEEPSEEK_KEY 가 설정되지 않았습니다."

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": PROMPT.format(text=chinese_text)},
            ],
            temperature=1.0,
            reasoning_effort=EFFORT,
            max_tokens=4096,
            extra_body={"reasoning_effort": EFFORT},
        )
        out = (resp.choices[0].message.content or "").strip()
        if not out:
            return "오류: 빈 응답을 받았습니다. 다시 시도해주세요."
        return out
    except Exception as e:
        msg = str(e)
        if "402" in msg or "Insufficient Balance" in msg:
            return "오류: DeepSeek 잔액이 부족합니다. 충전 후 다시 시도해주세요."
        if "401" in msg or "Authentication" in msg:
            return "오류: DeepSeek 키가 유효하지 않습니다."
        if "429" in msg:
            return "오류: 요청이 몰렸습니다. 잠시 후 다시 시도해주세요."
        return f"오류: {msg[:250]}"
