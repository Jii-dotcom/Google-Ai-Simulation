import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 기본 설정 (API 키 입력)
# ==========================================
# Github에 공개되지 않도록 st.secrets에서 키를 가져옵니다.
if "GOOGLE_API_KEY" in st.secrets:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("API 키가 아직 설정되지 않았습니다. secrets.toml 파일을 확인하세요.")

# API 키 설정
genai.configure(api_key=GOOGLE_API_KEY)

# ==========================================
# 2. 시스템 프롬프트 (여기에 V2.6 내용을 넣습니다)
# ==========================================
# 아까 완성한 [최종 통합본 V2.6] 전체 내용을 이 따옴표 안에 붙여넣으세요.
SYSTEM_PROMPT = """
**[System Settings: Gemini 3.0 Pro Medical Simulator]**
너는 첨부된 **엑셀 파일(환자 DB)**과 **매뉴얼(PDF)**, 그리고 아래 **[Scenario Context]**를 완벽하게 숙지한 의료 시뮬레이션 엔진이다.

(!!! 여기에 V2.6 프롬프트 전체 내용을 복사해서 붙여넣으세요 !!!)
(!!! 환자 프로필, 시나리오, 로직 등 모든 내용이 포함되어야 합니다 !!!)

**[Start Protocol]**
시뮬레이션 시작 시, [Scenario Context]의 내용을 바탕으로 다급하게 오프닝을 열어라.
"🚨 **상황 발생! Cs-137 운반 차량 전복!**
환자들 옷에 하얀 가루가 묻어있습니다.
**(침대 1) 한가을:** 축 늘어짐, 안색 창백. (조용/위급)
**(침대 2) 최여름:** 다리 골절로 비명 지름. (시끄러움)
**팀장님, 누구부터 진료하시겠습니까?**"
"""

# ==========================================
# 3. 모델 설정 함수
# ==========================================
def get_ai_response(messages):
    # 시스템 프롬프트를 설정에 포함시켜 모델을 불러옵니다.
    model = genai.GenerativeModel(
        model_name="gemini-flash-latest", # 또는 gemini-3.0-flash
        system_instruction=SYSTEM_PROMPT
    )
    
    # 채팅 세션을 시작하고 기록을 전달합니다.
    chat = model.start_chat(history=messages)
    
    # 마지막 사용자의 입력에 대한 응답을 받습니다. (빈 메시지 전송으로 트리거)
    response = chat.send_message(st.session_state.last_input)
    return response.text

# ==========================================
# 4. 웹사이트 화면 구성 (Streamlit)
# ==========================================
st.set_page_config(page_title="방사선 비상진료 시뮬레이터", page_icon="☢️")

st.title("☢️ 방사선 비상진료 시뮬레이터")
st.caption("Trauma & Radiation Response Training System | Powered by Gemini")

# 세션 상태 초기화 (대화 기록 저장소)
if "history" not in st.session_state:
    st.session_state.history = []
if "last_input" not in st.session_state:
    st.session_state.last_input = ""

# 1. 채팅 기록 화면에 표시
for message in st.session_state.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.write(message.parts[0].text)

# 2. 사용자 입력 처리
if user_input := st.chat_input("명령을 입력하세요 (예: 환자 상태 확인, 산소 투여)"):
    # 화면에 내 말 표시
    with st.chat_message("user"):
        st.write(user_input)
    
    # 로직 처리를 위해 변수에 저장
    st.session_state.last_input = user_input

    # 3. AI 응답 생성 (로딩 표시)
    with st.chat_message("assistant"):
        with st.spinner("환자 반응 관찰 중..."):
            try:
                # 모델 생성 및 채팅 연결 (히스토리 유지)
                model = genai.GenerativeModel(
                    model_name="gemini-flash-latest",
                    system_instruction=SYSTEM_PROMPT
                )
                chat = model.start_chat(history=st.session_state.history)
                
                # 메시지 전송
                response = chat.send_message(user_input)
                
                # 결과 출력
                st.write(response.text)
                
                # 대화 기록 업데이트 (Streamlit 세션 상태에 저장)
                st.session_state.history = chat.history
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# ==========================================
# 5. 사이드바 (리셋 버튼)
# ==========================================
with st.sidebar:
    st.header("📋 컨트롤 패널")
    st.markdown("시나리오를 랜덤으로 다시 시작합니다.")
    
    if st.button("🔄 시뮬레이션 초기화 (Reset)"):
        st.session_state.history = []
        st.session_state.last_input = ""
        st.rerun()
    
    st.markdown("---")

    st.info("**[가이드]**\n\n1. `시작` 입력하여 시나리오 로딩\n2. V/S 확인 및 처치 명령\n3. 오염 계측 명령")


