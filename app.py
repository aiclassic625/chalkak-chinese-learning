"""📸 찰칵 중국어 — 사진으로 만드는 중국어 학습자료

핵심 변경 (v2)
  · 사진 학습은 **로그인 없이** 바로 사용 (예전에는 로그인 벽이 있었음)
  · 로그인은 '내 기록 저장/보기'에만 필요
  · **비밀번호 재설정 메일** 기능 추가
  · API 키는 secrets 에서만 읽음 (코드에 하드코딩 금지)
"""
import datetime
import os
import tempfile

import streamlit as st
from PIL import Image

from ocr import extract_text_from_image
from study_helper import generate_study_material, _api_key as _deepseek_key

st.set_page_config(page_title="찰칵 중국어", page_icon="📸", layout="centered")


# ────────────────────────── 설정 읽기 ──────────────────────────
def secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


@st.cache_resource(show_spinner=False)
def get_supabase():
    url, key = secret("SUPABASE_URL"), secret("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


supabase = get_supabase()
vision_ready = bool(secret("GOOGLE_VISION_KEY"))
deepseek_ready = bool(_deepseek_key())

for k, v in (("user", None), ("study_result", None), ("last_text", None)):
    st.session_state.setdefault(k, v)

# ────────────────────────── 머리말 ──────────────────────────
st.title("📸 찰칵 중국어")
st.caption("책 페이지를 찍으면 **병음 · 해석 · HSK 어휘 분석**을 바로 만들어 드립니다.")

if not (vision_ready and deepseek_ready):
    missing = []
    if not vision_ready:
        missing.append("GOOGLE_VISION_KEY")
    if not deepseek_ready:
        missing.append("DEEPSEEK_KEY")
    st.error("서버에 API 키가 없습니다: " + ", ".join(missing)
             + "\n\n(Streamlit → Settings → Secrets 에 추가해주세요)")

tab_photo, tab_my = st.tabs(["📸 사진으로 학습", "👤 로그인 / 내 기록"])

# ══════════════════════ 탭 1 · 사진으로 학습 (로그인 불필요) ══════════════════════
with tab_photo:
    uploaded = st.file_uploader(
        "책 페이지 사진을 선택하세요 (카메라로 찍거나 갤러리에서 고르기)",
        type=["jpg", "jpeg", "png", "webp", "JPG", "JPEG", "PNG"],
    )

    if uploaded is not None:
        image = Image.open(uploaded)
        st.image(image, caption="업로드한 사진", use_container_width=True)

        if st.button("🚀 학습 자료 만들기", type="primary", use_container_width=True):
            # 임시 파일은 매번 새로 만들어 충돌을 막는다
            path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    path = tmp.name
                    image.convert("RGB").save(path, "JPEG", quality=92)

                with st.spinner("📖 사진에서 글자를 읽는 중…"):
                    text = extract_text_from_image(path)

                if text.startswith("오류"):
                    st.error(text)
                else:
                    st.success("✅ 글자를 읽었습니다")
                    with st.expander("📝 읽어낸 원문 보기", expanded=False):
                        st.text(text)

                    with st.spinner("🧠 학습 자료를 만드는 중… (10~30초)"):
                        material = generate_study_material(text)

                    if material.startswith("오류"):
                        st.error(material)
                    else:
                        st.session_state.study_result = material
                        st.session_state.last_text = text
                        st.success("🎉 완성!")
            finally:
                if path and os.path.exists(path):
                    os.remove(path)

    if st.session_state.study_result:
        st.divider()
        st.markdown(st.session_state.study_result)
        st.download_button(
            "📥 학습 자료 저장 (텍스트 파일)",
            data=st.session_state.study_result,
            file_name="찰칵중국어_학습자료.txt",
            mime="text/plain",
            use_container_width=True,
        )

        # 저장은 로그인한 사람만
        if st.session_state.user is None:
            st.info("💾 이 자료를 **내 기록**에 저장하려면 옆 탭에서 로그인하세요. "
                    "(로그인 없이도 학습자료는 계속 만들 수 있습니다)")
        else:
            if st.button("💾 내 기록에 저장", use_container_width=True):
                try:
                    supabase.table("study_records").insert({
                        "user_id": st.session_state.user.id,
                        "original_text": st.session_state.last_text or "",
                        "study_material": st.session_state.study_result,
                        "created_at": datetime.datetime.now().isoformat(),
                    }).execute()
                    st.success("💾 저장했습니다!")
                except Exception as e:
                    st.warning(f"⚠️ 저장하지 못했습니다: {str(e)[:150]}")

# ══════════════════════ 탭 2 · 로그인 / 내 기록 ══════════════════════
with tab_my:
    if supabase is None:
        st.warning("기록 기능을 쓰려면 SUPABASE_URL / SUPABASE_ANON_KEY 가 필요합니다.")
    elif st.session_state.user is not None:
        st.success(f"👋 {st.session_state.user.email} 님으로 로그인 중")

        c1, c2 = st.columns(2)
        if c1.button("로그아웃", use_container_width=True):
            st.session_state.user = None
            st.rerun()
        show = c2.button("📚 내 학습 기록", use_container_width=True)

        if show:
            with st.spinner("기록을 불러오는 중…"):
                try:
                    res = (supabase.table("study_records")
                           .select("*")
                           .eq("user_id", st.session_state.user.id)
                           .order("created_at", desc=True)
                           .execute())
                    records = res.data or []
                    if not records:
                        st.info("📭 아직 저장된 학습 자료가 없습니다.")
                    else:
                        st.write(f"총 **{len(records)}**개")
                        for i, rec in enumerate(records):
                            day = (rec.get("created_at") or "")[:10] or "날짜 없음"
                            with st.expander(f"📖 {day} · 기록 {i + 1}"):
                                st.markdown(rec.get("study_material") or "")
                                st.download_button(
                                    "📥 저장",
                                    data=rec.get("study_material") or "",
                                    file_name=f"학습기록_{day}_{i + 1}.txt",
                                    key=f"dl_{i}",
                                )
                except Exception as e:
                    st.error(f"기록을 불러오지 못했습니다: {str(e)[:150]}")
    else:
        st.subheader("로그인")
        st.caption("학습 기록을 저장·불러오려면 로그인하세요. "
                   "**사진으로 학습은 로그인 없이도 됩니다.**")

        with st.form("auth", clear_on_submit=False):
            email = st.text_input("이메일", placeholder="you@example.com")
            password = st.text_input("비밀번호", type="password")
            c1, c2 = st.columns(2)
            do_login = c1.form_submit_button("로그인", use_container_width=True,
                                             type="primary")
            do_signup = c2.form_submit_button("회원가입", use_container_width=True)

        if do_login:
            if not email or not password:
                st.warning("이메일과 비밀번호를 모두 입력하세요.")
            else:
                try:
                    r = supabase.auth.sign_in_with_password(
                        {"email": email, "password": password})
                    st.session_state.user = r.user
                    st.success("✅ 로그인했습니다!")
                    st.rerun()
                except Exception as e:
                    msg = str(e)
                    if "Invalid login" in msg or "invalid" in msg.lower():
                        st.error("이메일 또는 비밀번호가 맞지 않습니다. "
                                 "아래 **비밀번호를 잊으셨나요?** 를 눌러보세요.")
                    elif "Email not confirmed" in msg:
                        st.error("이메일 인증이 필요합니다. 받은 메일함을 확인해주세요.")
                    else:
                        st.error(f"로그인 실패: {msg[:180]}")

        if do_signup:
            if not email or not password:
                st.warning("이메일과 비밀번호를 모두 입력하세요.")
            elif len(password) < 6:
                st.warning("비밀번호는 6자 이상으로 해주세요.")
            else:
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("✅ 가입 완료! 위에서 **로그인**을 눌러주세요. "
                               "(이메일 인증을 켜둔 경우 메일함을 확인하세요)")
                except Exception as e:
                    st.error(f"가입 실패: {str(e)[:180]}")

        # ── 비밀번호 찾기 ──
        st.divider()
        with st.expander("🔑 비밀번호를 잊으셨나요?"):
            st.caption("가입한 이메일로 재설정 메일을 보내드립니다.")
            r_email = st.text_input("가입한 이메일", key="reset_email",
                                    placeholder="you@example.com")
            if st.button("재설정 메일 보내기", use_container_width=True):
                if not r_email:
                    st.warning("이메일을 입력하세요.")
                else:
                    try:
                        supabase.auth.reset_password_email(r_email)
                        st.success(f"📧 {r_email} 로 재설정 메일을 보냈습니다. "
                                   "메일함(스팸함 포함)을 확인해주세요.")
                    except Exception as e:
                        st.error(f"메일을 보내지 못했습니다: {str(e)[:180]}")
            st.caption("메일이 오지 않으면 새 이메일로 다시 가입해도 됩니다. "
                       "학습자료는 로그인 없이도 만들 수 있습니다.")

st.divider()
st.caption("찰칵 중국어 · 사진 한 장으로 만드는 중국어 학습자료")
