import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import re
from PIL import Image

# ==========================================
# 1. API 키 설정
# ==========================================
if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🚨 API 키가 설정되지 않았습니다. secrets.toml 파일을 확인해주세요.")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# ==========================================
# 2. 시스템 프롬프트 (Lite 모델용으로 태그 지시 강화)
# ==========================================
SYSTEM_PROMPT = """
**[System Settings: Medical Simulator]**
너는 첨부된 엑셀 파일과 매뉴얼을 숙지한 의료 시뮬레이션 엔진이다.

**[Role Definition: 절대 원칙]**
1. **NO Game Master:** 너는 진행자가 아니다. 조언이나 힌트를 주지 마라.
2. **Be the Patient & Monitor:** 너는 오직 **환자의 고통스러운 반응**과 **모니터의 생체징후(V/S)**만 출력하라.
3. **Measurement Unit:** 방사선 오염도는 반드시 **'CPS'** 단위로 출력하라.

**[Scenario Context: Cs-137 수송차량 전복]**
- 사고: 14:00경 동위원소 운반 차량 전복.
- 오염: **세슘 가루(흰색)**가 환자들의 의복과 신체에 묻음.
- 병원: 제염실 없음. 일반 환자 10명 내원 중.

**[Patient Profile]**
1. **한가을 (위급):** 혼미, 축 늘어짐, BP 80/50, HR 30, SpO2 85%. 내부오염 의심.
2. **최여름 (지연):** 명료, 극도의 흥분, 비명 지름. 다리 골절.

**[Logic]**
- 한가을에게 소생술 없이 제염 먼저 시도 시 상태 급격 악화.
- 최여름에게 3턴 이상 정신 팔리면 한가을 사망.

**[★★★ Visual Output Protocol: 중요 ★★★]**
너는 답변을 마칠 때마다 **반드시** 현재 상황을 묘사하는 이미지 생성 코드를 마지막 줄에 추가해야 한다.
형식: `<<<IMAGE_PROMPT: (영어 상황 묘사)>>>`

* (예시 1 - 시작 시): `<<<IMAGE_PROMPT: An overturned truck on a highway, white dust covering injured patients, realistic photo style.>>>`
* (예시 2 - 위독): `<<<IMAGE_PROMPT: A medical monitor showing flatline Asystole, red alarm lights flashing, dark atmosphere.>>>`
* (예시 3 - 일반 진료): `<<<IMAGE_PROMPT: A doctor checking patient's eyes with a flashlight, first person view, realistic medical drama style.>>>`

**[Start Protocol]**
시뮬레이션 시작 시 오프닝을 열어라:
"🚨 **상황 발생! Cs-137 운반 차량 전복 사고!**
환자들의 옷에 **하얀 가루(세슘 의심)**가 잔뜩 묻어있습니다!
**(침대 1) 한가을:** 축 늘어져 있고 안색이 창백합니다. (삐... 삐...)
**(침대 2) 최여름:** 다리를 붙잡고 비명을 지릅니다. '아악! 나부터 살려줘요!!'
**팀장님, 누구부터 진료하시겠습니까?**"
<<<IMAGE_PROMPT: An overturned transport truck carrying radioactive materials on a highway, with two injured patients lying on stretchers covered in white dust, emergency personnel responding, realistic photo style.>>>
"""

# ==========================================
# 3. 이미지 생성 함수 (여기는 Imagen 모델 사용 필수)
# ==========================================
def generate_image(prompt):
    """Imagen 모델을 사용하여 이미지를 생성합니다."""
    try:
        # 텍스트 모델은 Flash-lite를 쓰더라도, 그림은 화가(Imagen)가 그려야 합니다.
        imagen_model = genai.ImageGenerationModel("imagen-4.0-generate-001")
        result = imagen_model.generate_images(
            prompt=prompt, number_of_images=1, aspect_ratio="16:9", safety_filter_level="block_some"
        )
        return result.images[0]
    except Exception as e:
        # 에러가 나면 사용자에게 보여줍니다 (디버깅용)
        st.warning(f"이미지 생성 실패 (텍스트만 출력합니다): {e}") 
        return None

# ==========================================
# 4. 화면 구성 및 사이드바
# ==========================================
st.set_page_config(page_title="방사선 비상진료 시뮬레이터", page_icon="☢️", layout="wide")

# 세션 상태 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "api_history" not in st.session_state:
    st.session_state.api_history = []
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None

# --- 사이드바 ---
with st.sidebar:
    st.header("👤 교육생 정보")
    trainee_name = st.text_input("이름", placeholder="예: 홍길동")
    trainee_id = st.text_input("소속", placeholder="예: 원자력병원")
    
    st.markdown("---")
    st.header("📋 컨트롤 패널")
    if st.button("🔄 시뮬레이션 초기화 (Reset)"):
        st.session_state.chat_history = []
        st.session_state.api_history = []
        st.session_state.evaluation = None
        st.rerun()

# ==========================================
# 5. 메인 채팅 인터페이스
# ==========================================
st.title("☢️ 방사선 비상진료 시뮬레이터")
st.caption(f"Trauma & Radiation Response Training System | Model: gemini-flash-lite-latest")

# 채팅 기록 표시
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["type"] == "text":
            st.write(msg["content"])
        elif msg["type"] == "image":
            st.image(msg["content"], caption="현장 시각화", use_column_width=True)

# 사용자 입력 처리
if st.session_state.evaluation is None:
    if user_input := st.chat_input("명령을 입력하세요 (예: 시뮬레이션 시작)"):
        # 1. 사용자 입력 표시
        with st.chat_message("user"):
            st.write(user_input)
        
        st.session_state.chat_history.append({"role": "user", "type": "text", "content": user_input})
        st.session_state.api_history.append({"role": "user", "parts": [user_input]})
        
        # 2. AI 응답 처리
        with st.chat_message("assistant"):
            with st.spinner("상황 판단 및 이미지 생성 중..."):
                try:
                    # 요청하신 [gemini-flash-lite-latest] 모델 사용
                    # 만약 이 모델명이 API 오류가 나면 'gemini-1.5-flash'로 바꿔야 합니다.
                    chat_model = genai.GenerativeModel(
                        model_name="gemini-flash-lite-latest", 
                        system_instruction=SYSTEM_PROMPT
                    )
                    
                    chat = chat_model.start_chat(history=st.session_state.api_history)
                    response = chat.send_message(user_input)
                    response_text = response.text

                    # 이미지 태그 감지 (<<<IMAGE_PROMPT: ... >>>)
                    image_match = re.search(r"<<<IMAGE_PROMPT:(.*?)>>>", response_text, re.DOTALL)
                    
                    final_text_to_display = response_text
                    generated_image = None

                    if image_match:
                        img_prompt = image_match.group(1).strip()
                        # 텍스트에서 태그 제거 (화면엔 안 보이게)
                        final_text_to_display = response_text.replace(image_match.group(0), "")
                        
                        # 이미지 생성 시도
                        generated_image = generate_image(img_prompt)
                    else:
                        # 태그가 없으면 강제로라도 이미지를 만들지, 아니면 넘어갈지 결정
                        # Lite 모델이 태그를 빼먹는 경우를 대비해 로그만 출력
                        print("AI가 이미지 태그를 생성하지 않았습니다.")

                    # 3. 결과 출력
                    if final_text_to_display.strip():
                        st.write(final_text_to_display)
                        st.session_state.chat_history.append({"role": "assistant", "type": "text", "content": final_text_to_display})
                        st.session_state.api_history.append({"role": "model", "parts": [final_text_to_display]})
                    
                    if generated_image:
                        st.image(generated_image, caption="AI 현장 재현 이미지", use_column_width=True)
                        st.session_state.chat_history.append({"role": "assistant", "type": "image", "content": generated_image})

                except Exception as e:
                    st.error(f"오류 발생: {e}")
                    st.info("팁: 모델명 오류라면 'gemini-1.5-flash'로 변경해보세요.")

# ==========================================
# 6. 평가 및 데이터 제출
# ==========================================
st.markdown("---")
if st.session_state.evaluation is None:
    st.subheader("📊 훈련 종료 및 평가")
    
    if st.button("훈련 종료 및 평가 받기"):
        if not trainee_name or not trainee_id:
            st.warning("⚠️ 왼쪽 사이드바에서 '이름'과 '소속'을 먼저 입력해주세요!")
        else:
            if len(st.session_state.api_history) < 2:
                st.warning("⚠️ 대화 기록이 너무 짧습니다.")
            else:
                with st.spinner("평가 분석 중..."):
                    try:
                        # 평가 모델도 요청하신 모델로 통일
                        eval_model = genai.GenerativeModel("gemini-flash-lite-latest")
                        full_log = "\n".join([f"{msg['role']}: {msg['parts'][0]}" for msg in st.session_state.api_history])
                        
                        eval_prompt = f"""
                        너는 평가관이다. 아래 로그를 분석해라.
                        [로그] {full_log}
                        [형식]
                        1. 생존 여부:
                        2. 주요 처치:
                        3. 잘한 점:
                        4. 개선할 점:
                        5. 점수(100점 만점):
                        """
                        eval_response = eval_model.generate_content(eval_prompt)
                        st.session_state.evaluation = eval_response.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"평가 중 오류: {e}")

if st.session_state.evaluation:
    st.success("✅ 평가 완료!")
    st.info(st.session_state.evaluation)
    
    full_conversation = "\n".join([f"[{msg['role']}] {msg['parts'][0]}" for msg in st.session_state.api_history])
    data = {
        "이름": [trainee_name], "소속": [trainee_id],
        "날짜": [datetime.now().strftime("%Y-%m-%d")],
        "평가결과": [st.session_state.evaluation], "대화로그": [full_conversation]
    }
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 결과 다운로드 (CSV)", data=csv, file_name="result.csv", mime="text/csv")

