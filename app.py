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
# 2. 시스템 프롬프트 (V2.6 + 이미지 생성 기능)
# ==========================================
SYSTEM_PROMPT = """
**[System Settings: Gemini 3.0 Pro Medical Simulator]**
너는 첨부된 **엑셀 파일(환자 DB)**과 **매뉴얼(PDF)**, 그리고 아래 정의된 **환자 프로필**을 완벽하게 숙지한 의료 시뮬레이션 엔진이다.

**[Role Definition: 절대 원칙]**
1. **NO Game Master:** 너는 진행자가 아니다. 상황 설명, 조언, 힌트, "다음 단계는~" 같은 말을 절대 하지 마라.
2. **Be the Patient & Monitor:** 너는 오직 **환자의 고통스러운 반응(청각/시각)**과 **모니터의 생체징후(V/S)**만 출력하라.
3. **Measurement Unit:** 방사선 오염도 측정 시 결과는 반드시 **'CPS(Counts Per Second)'** 단위로 출력하라.

**[Scenario Context: Cs-137 수송차량 전복]**
*아래 상황을 숙지하고 환자 상태 묘사에 반영하라.*
- **사고 개요:** 14:00경 동위원소(Cs-137) 운반 차량이 가드레일을 들이박고 전복 후 2차 추돌.
- **오염 상황:** 조사장치 파손으로 **세슘 가루(흰색)**가 외부로 분산됨. 환자들의 의복과 신체에 가루가 묻은 것이 육안으로 확인됨.
- **병원 상황:** 제염실 없음. 일반 환자 10명 내원 중.

**[Patient Profile: 기본 시나리오]**
엑셀 파일이 없으면 아래 두 환자를 기본으로 연기하라.

**1. 환자 C: 한가을 (Priority 1: Immediate)**
- **상태:** 혼미(Stupor), 축 늘어짐. **조용함(생명 위급).**
- **V/S:** BP 80/50, **HR 30 (심각한 서맥)**, SpO2 85%.
- **특징:** 중증 복합 손상. 방치 시 별다른 소리 없이 사망함.
**[제염 데이터]:** 초기 10,000 cps → (1차) 5,000 cps → (2차) 4,000 cps.
- **[판정]:** **내부오염 의심 (Internal Contamination Suspected)**.

**2. 환자 D: 최여름 (Priority 2: Delayed)**
- **상태:** 명료(Alert), 극도의 흥분. **매우 시끄러움.**
- **V/S:** BP 130/90, HR 110 (빈맥), SpO2 98%.
- **특징:** 다리 골절 및 오염. 계속 비명을 질러 의료진의 판단을 방해함.

**[Simulation Logic: 생사 판정 및 상호작용]**
1. **치명적 실수 유예:**
   - 환자(한가을)의 Vital이 불안정한데 소생술(ABC) 없이 '제염/탈의'를 먼저 시도할 경우:
     - **1차 시도 (Warning):** "환자가 컥컥거리며 몸을 뒤틉니다! 움직임 때문에 혈압이 뚝 떨어집니다!"
     - 출력: `[한가을 Monitor] ⚠ BP 60/40 (▼) | HR 20 (Critical) | SpO2 70%`
     - **2~3차 시도/지연 (Death):** "모니터의 파형이 평평해집니다."
     - 출력: `[한가을 Monitor] Asystole (심정지) | 삐---------` -> **(사망 선고)**

2. **방치 패널티:**
   - **'최여름'**에게 정신이 팔려 **3턴 이상** 시간을 보내면, **'한가을'**은 조용히 사망한다.

**[Visual Output Protocol: AI 이미지 생성 요청]**
너는 텍스트 출력 마지막 줄에 상황에 맞는 **이미지 생성 프롬프트**를 `<<<IMAGE_PROMPT: (영어 묘사)>>>` 형식으로 작성해야 한다.
단, 매번 출력하지 말고 **시나리오 시작, 환자 상태의 급격한 변화(사망, 위독), 시각적으로 중요한 처치(오염 제거 등)**가 있을 때만 출력하라.

* 예시 1 (오프닝): `<<<IMAGE_PROMPT: An overturned truck on a highway with radioactive warning signs, white dust covering injured patients on stretchers, realistic cinematic style.>>>`

**[Start Protocol]**
시뮬레이션 시작 시 오프닝을 열어라:
"🚨 **상황 발생! Cs-137 운반 차량 전복 사고!**
구급차 두 대가 도착했습니다. 환자들의 옷에 **하얀 가루(세슘 의심)**가 잔뜩 묻어있습니다!
**(침대 1) 한가을:** 축 늘어져 있고 안색이 창백합니다. 모니터 경고음만 들립니다. (삐... 삐...)
**(침대 2) 최여름:** 피투성이가 된 다리를 붙잡고 비명을 지릅니다. '아악! 나부터 살려줘요!!'
**팀장님, 누구부터 진료하시겠습니까? (이름을 호명해주세요)**"
<<<IMAGE_PROMPT: An overturned transport truck carrying radioactive materials on a highway, with two injured patients lying on stretchers covered in white dust, emergency personnel responding, realistic photo style.>>>
"""

# ==========================================
# 3. 이미지 생성 함수
# ==========================================
def generate_image(prompt):
    """Imagen 모델을 사용하여 이미지를 생성합니다."""
    try:
        imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-001")
        result = imagen_model.generate_images(
            prompt=prompt, number_of_images=1, aspect_ratio="16:9", safety_filter_level="block_some"
        )
        return result.images[0]
    except Exception as e:
        print(f"이미지 생성 실패: {e}") 
        return None

# ==========================================
# 4. 화면 구성 및 사이드바 (변수 선언을 최상단으로 이동)
# ==========================================
st.set_page_config(page_title="방사선 비상진료 시뮬레이터", page_icon="☢️", layout="wide")

# 세션 상태 초기화 (AttributeError 방지를 위해 단순 딕셔너리 구조 사용)
if "chat_history" not in st.session_state:
    # 화면 표시용 (텍스트 + 이미지 객체 혼합)
    st.session_state.chat_history = []
if "api_history" not in st.session_state:
    # API 전송용 (텍스트만 포함, Gemini 형식이 아닌 순수 딕셔너리 사용 권장)
    st.session_state.api_history = []
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None

# --- 사이드바 (NameError 방지를 위해 가장 먼저 실행) ---
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
    
    st.info("**[가이드]**\n1. 이름/소속 입력\n2. '시작' 입력하여 진행\n3. 종료 시 하단 '평가 받기' 클릭")

# ==========================================
# 5. 메인 채팅 인터페이스
# ==========================================
st.title("☢️ 방사선 비상진료 시뮬레이터")
st.caption("Trauma & Radiation Response Training System | Powered by Gemini 1.5 Flash")

# 채팅 기록 표시 (화면용 히스토리 사용)
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["type"] == "text":
            st.write(msg["content"])
        elif msg["type"] == "image":
            st.image(msg["content"], caption="현장 시각화", use_column_width=True)

# 사용자 입력 처리
if st.session_state.evaluation is None:
    if user_input := st.chat_input("명령을 입력하세요 (예: 시뮬레이션 시작)"):
        # 1. 사용자 입력 표시 및 저장
        with st.chat_message("user"):
            st.write(user_input)
        
        # 화면용 저장
        st.session_state.chat_history.append({"role": "user", "type": "text", "content": user_input})
        # API용 저장 (Gemini가 이해하는 형식)
        st.session_state.api_history.append({"role": "user", "parts": [user_input]})
        
        # 2. AI 응답 처리
        with st.chat_message("assistant"):
            with st.spinner("상황 판단 중..."):
                try:
                    # 텍스트 모델: 1.5-flash (필수!)
                    chat_model = genai.GenerativeModel(
                        model_name="gemini-flash-lite-latest", 
                        system_instruction=SYSTEM_PROMPT
                    )
                    
                    # API 호출 (API용 히스토리 전달)
                    chat = chat_model.start_chat(history=st.session_state.api_history)
                    response = chat.send_message(user_input)
                    response_text = response.text

                    # 이미지 태그 감지 (<<<IMAGE_PROMPT: ... >>>)
                    image_match = re.search(r"<<<IMAGE_PROMPT:(.*?)>>>", response_text, re.DOTALL)
                    
                    final_text_to_display = response_text
                    generated_image = None

                    if image_match:
                        img_prompt = image_match.group(1).strip()
                        # 텍스트에서 태그 제거
                        final_text_to_display = response_text.replace(image_match.group(0), "")
                        
                        # 이미지 생성
                        with st.spinner("📸 현장 상황 시각화 중..."):
                            generated_image = generate_image(img_prompt)

                    # 3. 결과 출력 및 저장
                    # (1) 텍스트
                    if final_text_to_display.strip():
                        st.write(final_text_to_display)
                        # 화면용 저장
                        st.session_state.chat_history.append({"role": "assistant", "type": "text", "content": final_text_to_display})
                        # API용 저장
                        st.session_state.api_history.append({"role": "model", "parts": [final_text_to_display]})
                    
                    # (2) 이미지 (이미지가 있을 경우만)
                    if generated_image:
                        st.image(generated_image, caption="AI 현장 재현 이미지", use_column_width=True)
                        # 화면용 저장 (이미지 객체)
                        st.session_state.chat_history.append({"role": "assistant", "type": "image", "content": generated_image})
                        # API용 저장에는 이미지를 넣지 않음 (무료 버전 한계)

                except Exception as e:
                    st.error(f"오류 발생 (잠시 후 다시 시도하세요): {e}")

# ==========================================
# 6. 평가 및 데이터 제출
# ==========================================
st.markdown("---")
if st.session_state.evaluation is None:
    st.subheader("📊 훈련 종료 및 평가")
    
    if st.button("훈련 종료 및 평가 받기"):
        # NameError 해결: 변수가 상단에서 선언되었으므로 안전함
        if not trainee_name or not trainee_id:
            st.warning("⚠️ 왼쪽 사이드바에서 '이름'과 '소속'을 먼저 입력해주세요!")
        else:
            if len(st.session_state.api_history) < 2:
                st.warning("⚠️ 대화 기록이 너무 짧습니다. 훈련을 진행한 후 종료해주세요.")
            else:
                with st.spinner("AI가 훈련 내용을 분석하여 채점 중입니다..."):
                    try:
                        eval_model = genai.GenerativeModel("gemini-flash-lite-latest")
                        
                        # API 히스토리를 텍스트로 변환
                        full_log = "\n".join([f"{msg['role']}: {msg['parts'][0]}" for msg in st.session_state.api_history])
                        
                        eval_prompt = f"""
                        너는 방사선 비상진료 평가관이다. 아래 시뮬레이션 로그를 분석해라.
                        [로그 시작]
                        {full_log}
                        [로그 끝]
                        다음 형식으로 평가 리포트를 작성해줘:
                        1. 환자 생존 여부: (생존/사망)
                        2. 주요 처치 내용: (3가지 요약)
                        3. 잘한 점:
                        4. 개선할 점:
                        5. 종합 점수: (100점 만점 기준 숫자만)
                        """
                        
                        eval_response = eval_model.generate_content(eval_prompt)
                        st.session_state.evaluation = eval_response.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"평가 중 오류 발생: {e}")

# 평가 결과 표시 및 다운로드
if st.session_state.evaluation:
    st.success("✅ 평가 완료!")
    st.info(st.session_state.evaluation)
    
    full_conversation = "\n".join([f"[{msg['role']}] {msg['parts'][0]}" for msg in st.session_state.api_history])
    
    data = {
        "이름": [trainee_name],
        "소속": [trainee_id],
        "날짜": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "평가결과": [st.session_state.evaluation],
        "대화로그": [full_conversation]
    }
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 훈련 데이터 다운로드 (CSV)",
        data=csv,
        file_name=f"결과_{trainee_name}_{datetime.now().strftime('%H%M')}.csv",
        mime="text/csv"
    )
