🌸 Bloom U  -  README
: “Where You Begin to Bloom” – 20대의 모든 ‘처음’을 함께 합니다.  
  내 상황 · 수준 · 성향에 맞춰 함께 성장해주는 개인 트레이너형 AI 코칭 서비스
 - 주요 타겟층: 20대 대학생
---

📌 서비스 소개
Bloom U는 20대 대학생을 위한 상담 · 목표관리 · 루틴관리 · 성장기록 통합 코칭 플랫폼입니다. 
  - [상담/코칭 챗봇 + 주간 플래너 + A/B 전략 측정 + 루틴(데일리 패턴) 트래커 + 성장 대시보드]를 한 번에 제공하는 Streamlit 앱
  - 앱 링크를 통해 접속하여 별도의 설치 없이 바로 사용할 수 있습니다.


✨ 주요 기능 소개
# 💬 1. AI 코칭 채팅
  - 말투 / 레벨 / 분야 선택을 통한 그에 맞춘 코칭 출력 (JSON 스키마 기반)
  - 공감 + 실행 중심 코칭 제공, 코칭 내용에서 [사실(증거 기반, 링크 있음) + 전략(개인 맞춤, 추정화)] 구분
  - A/B 전략 자동 생성 – 서로 다른 전략을 나누어 제공함으로써, 사용자의 실제 실천 및 평가(전략 평가 탭 이용)를 통해 누적된 데이터로 보다 개인 맞춤화 된 전략 코칭을 제공할 수 있도록 합니다. 

# 🗓️ 2. 주간 액티브 플랜
  - 요일별 목표 관리
  - 상태 관리: 체크 / 진행중 / 미루기 (미루기 시 자동 일정 이동)
  
# 🧪 3. 전략 A/B 측정
  - 전략별 불안도 / 실천도 / 성과 기록
  - 다음 코칭에 자동 반영을 통한 개인화된 전략 추천 가능 

# 📊 4. 데일리 패턴 체크
  - 수분 / 운동 / 수면 / 컨디션 / 개인목표 기록
  - 월간 / 연간 통계 제공
  - 성장 추이 시각화 

# 🏅 5. 뱃지 시스템
  - 첫 사용 / 연속 사용 / 목표 달성 등
  - 자기관리 및 초기 동기부여에 도움이 되도록 합니다.

# 📈 6. 주간 리포트 & 대시보드
  - 자신감 / 불안 / 에너지 변화 추적 / 실천률 시각화 대시보드 제공
  - 개인 성장추이 요약 제공 서비스

# 📤 7. Notion 저장 (Export) (선택)
  - 주간 플랜을 개인 Notion에 저장 가능 (DB에 페이지 1개로 저장)
  - 자동 페이지 생성

# 🔎 8. 증거기반 모드(선택)
  - Serper 검색 결과(또는 큐레이션 소스) 기반으로 “사실(정보)” 섹션에 근거 링크 출력
  - 사이드바의 증거기반모드를 켜면, “사실(정보)” 섹션에 근거 링크가 붙습니다.
    •	Serper API Key가 있으면: 사용자 입력과 도메인을 기반으로 검색 → 결과 링크 중 허용 도메인만 사용
    •	Serper API Key가 없으면: 앱 내부 curated_sources()에 있는 큐레이션 링크 사용
 ** 허용 도메인(예시):
  •	.gov, .edu, who.int, oecd.org, nih.gov, cdc.gov, apa.org
  •	indeed.com, glassdoor.com
  •	(한국) moel.go.kr, korea.kr 등


🔗 Bloom U 사용 방법
1. 제공된 Bloom U 앱 링크 접속
2. 사이드바에서 기본 설정 선택
3. 채팅 또는 플래너 사용 시작
4. 필요 시 Notion 연동하여 주간 액티브 플랜을 개인별 데이터베이스로 저장
※ 별도 프로그램 설치 필요 없음
  ※ 이 앱은 기본적으로 OpenAI API Key가 필요합니다.
     또한 “증거기반 모드(Serper)”를 쓰려면 Serper API Key가 있으면 좋아요(없어도 동작은 합니다. 대신 큐레이션 링크를 사용).



#📝 Notion 저장 기능 사용법 (선택 기능)

  : Bloom U는 사용자의 주간 플랜을 사용자 본인의 Notion Database에 저장할 수 있습니다. 사이드바에서 Notion Token, Database ID, Title 속성 이름을 입력하면 됩니다.

 1️⃣ Notion Integration 생성
   1. Notion에서 Settings & members → Integrations(또는 Notion Developers)로 이동 후 New Integration 생성
   2. Internal integration으로 만들고, 권한은 최소한 아래를 추천:
     o	Read content
     o	Insert content
     o	Update content (선택)
   3. 생성 후 Internal Integration Token(secret_로 시작)을 복사
   
2️⃣ Database 준비 및 공유 (필수)
  1. Notion에서 Database 생성 (/database 입력) 후 이름 설정 
  2. 해당 Database → Share 클릭
  3. Integration 초대(Invite)
  ※ 공유하지 않으면 저장이 실패합니다.

3️⃣ Database 정보 확인
  - Database ID: 페이지 URL의 긴 해시 문자열
  - Title 속성 이름: 보통 `Name` 또는 `제목`
  ※ Bloom U 사이드바의 DB Title 속성 이름에 정확히 입력해야 저장이 성공합니다.

4️⃣ 앱에 입력
: 사이드바 → 🔗 Notion 연결 영역에 입력
  - Token
  - Database ID
  - Title 속성 이름
    
5️⃣ 저장
: 주간 액티브 플랜 탭 → `Notion에 저장(혹은 Notion으로 내보내기)` 클릭
  - 성공 시 Notion 페이지 URL이 표시됩니다. 


⚠️ 유의사항
- Bloom U는 자기관리·코칭 보조 도구입니다.
- 의료·법률·재정 관련 전문 상담을 대체하지 않습니다.
- 위기 상황 시 반드시 전문가와 상담하세요.


❓ 자주 발생하는 문제
1.  Notion 저장이 안 될 때
✅ Database에 Integration을 Share 했는지 확인
✅ Database ID가 맞는지 확인
✅ Title 속성 이름(Name/제목)이 정확한지 확인
✅ Token이 secret_로 시작하는 값인지 확인
2. 앱이 정상 작동하지 않을 때
✅ 새로고침 후 재시도
✅ 네트워크 상태 확인
✅ OpenAI API Key가 유효한지 확인
✅ 사이드바 입력이 비어있지 않은지 확인 


⚠️사용된 기술
  •	Streamlit (UI/상태관리)
  •	OpenAI API (Responses API 기반 호출)
  •	Notion API (Database에 주간 플랜 페이지 생성)
  •	Pandas (대시보드/통계)
  •	(선택) Serper.dev (검색 기반 근거 링크)

📜 License & Copyright
© 2026 Bloom U. All rights reserved.
  본 서비스 및 관련 소스코드, 문서, 디자인, 기능 구조는 저작권자의 소유입니다.
  사전 허가 없이 다음 행위를 금지합니다:
     - 코드 복제 및 배포
     - 수정 및 2차 저작물 제작
     - 상업적 활용
     - 서비스 모방
  * 본 프로젝트는 앱 링크를 통한 이용만 허용됩니다. *


💌 Contact
 서비스 관련 문의는 운영자에게 별도 문의 바랍니다.
  - yoolia0920@gmail.com
