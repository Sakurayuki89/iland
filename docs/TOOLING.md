# Island — 기본 도구 준비 현황 (TOOLING)

> 범위: **게임 설계와 무관한 기본 도구**만 다룬다. 캐릭터 선정·게임 진행 방식·보상 등은 나중에 정하며, 이 문서는 그 결정을 기다리지 않는다.
> 조사·준비일: 2026-09-30 · 버전은 이날 npm/공식 페이지 기준.

## 1. 한눈에

| 영역 | 도구 | 비용 | 상태 |
|------|------|------|------|
| 런타임 | Node 20.20, pnpm 10.34, uv 0.11 | 무료 | ✅ 있음 |
| 엔진 | **Phaser 4.2.1** (MIT) | 무료 | ✅ `apps/client`에 설치, 샌드박스 씬으로 확인 |
| 빌드·타입·테스트 | Vite 8.3, TypeScript 7.0, Vitest 5.0 | 무료 | ✅ 타입체크·테스트 3건·빌드 통과 |
| 맵 에디터 | **Tiled 1.12.2** | 무료 | ✅ 설치됨 (`open -a Tiled`) |
| 스프라이트 파이프라인 | `sprite_slicer` · `palette_swap` · `atlas_preview` | 자체 | ✅ (`tools/README.md`) |
| 콘텐츠 검증 | `content_lint` + 스키마 + 테스트 | 자체 | ✅ |
| 환경 점검 | `tools/doctor.py` | 자체 | ✅ |
| **액션 랩** | 타임라인 = animation-timeline-js 2.3.5, 패널 = Tweakpane 4.0.5 (둘 다 MIT) + 자체 액션 데이터 모델 | 무료 | ✅ `/lab.html` (§6) |
| 성능 측정 | `tools/bench.py` (군중 부하), `tools/shot.py` (실시간 캡처) | 자체 | ✅ (§7) |
| 버전 관리 | git 로컬 저장소 (`.gitignore`, `.env.example`) | 무료 | ✅ 초기화만, **커밋 없음** |
| 길찾기 | EasyStar.js 0.4.4 / navmesh 2.3.1 (둘 다 MIT) | 무료 | ⏸ 맵 방식 결정 후 설치 |
| 멀티플레이 서버 | Colyseus 0.18 + @colyseus/schema 5 (MIT) | 무료(자체 호스팅) | ⏸ 서버 단계에서 |
| 모바일 래퍼 | Capacitor 8.5 (MIT) | 무료 | ⏸ Xcode/Android 준비 후 |
| 음성(TTS) | 후보 조사 완료 (Gemini 3.8 / Fish / ElevenLabs) | 사용량 과금 | ⏸ API 키·청취 테스트 후 |
| 효과음 | 생성 AI 비권장 → 라이선스 음원 선정 | — | ⏸ |
| 모바일 빌드 | Xcode, JDK 17, Android Studio | 무료(계정비 별도) | ❌ **직접 설치 필요** (아래 §4) |

## 2. 조사 결과와 결정 근거

**엔진: Phaser 3 → 4로 정정.** 이전 설계 문서는 Phaser 3을 적었지만 Phaser 4가 2026-04에 정식 출시됐고 공식 글도 [신규 프로젝트는 4로 시작하라](https://phaser.io/news/2026/05/phaser-3-vs-phaser-4)고 한다. 스프라이트·Tilemap·Arcade 물리·Tween 등 핵심 API는 대부분 그대로다. 대신 `import * as Phaser from 'phaser'` 형태로 불러오고, 커스텀 WebGL 파이프라인·Mesh/Plane 등은 바뀌거나 제거됐다 ([전환 안내](https://phaser.io/news/2026/04/migrating-from-phaser-3-to-phaser-4-what-you-need-to-know)). **v3용 플러그인이 v4에서 동작하는지는 확인하지 못했으므로** v3 플러그인(예: `phaser-navmesh`)에 의존하지 않는다.

**맵 에디터: Tiled 선택.** 둘 다 무료 오픈소스다. Tiled는 Phaser에 기본 지원이 있어 바로 읽힌다. LDtk는 엔티티 편집이 더 편하지만 [Phaser용 임포터가 없고](https://ldtk.io/docs/game-dev/loading/) Tiled 형식으로 내보내야 한다 ([비교](https://egmatic.com/blog/best-level-design-software)). 그림 배경(섬 일러스트) 위에 **이미지 레이어 + 논리 레이어(이동 가능/구역/앵커)** 를 얹는 용도라 Tiled로 충분하다. 시점(탑다운/아이소)이 미정이어도 Tiled는 둘 다 지원한다.

**길찾기: 그리드 A*(EasyStar)부터.** [navmesh](https://github.com/mikewesthad/navmesh)는 코어가 엔진 독립이고 EasyStar보다 빠르지만 **볼록 폴리곤만** 지원해서, 그림 배경의 오목한 이동 영역을 쓰려면 분해 도구가 따로 필요하다. 논리 그리드 하나로 이동·충돌·배치 가능 칸을 함께 표현하면 도구가 줄어든다. 길이 어색하면 그때 navmesh를 붙인다. (설치는 이 결정 뒤로 미룸.)

**가구 배치·집 짓기는 외부 툴이 아니라 런타임 기능.** 격자 스냅은 Phaser의 `Phaser.Math.Snap.To`로 해결되고 ([예](https://phaser.discourse.group/t/snap-to-grid-on-drag-in-phaser-3/5062)), 필요한 "기본 도구"는 (1) 정적 아이템 시트를 자르는 슬라이서, (2) 아이템 카탈로그 린트, (3) 서버 저장이다. 집 짓는 방식(단계 업그레이드 vs 자유 건축)과 소유 방식이 **나중에 정할 설계 사항**이므로 이 도구들은 그때 만든다.

**서버 저장.** [Colyseus](https://docs.colyseus.io/room)의 방은 휘발성이라 영속 데이터(집·가구·작물)는 Postgres에 두고 방 생성 시 읽고 종료 시 저장한다. `StateView`로 클라이언트별 가시 범위를 줄일 수 있다.

**운영 비용.** 개발 도구는 전부 무료다. 돈이 드는 것은 (a) Apple 개발자 연 $99, Google Play 일회 $25, (b) 호스팅 — [Railway Hobby](https://docs.railway.com/pricing/plans)는 월 $5(사용량 $5 포함), 트라이얼은 일회성 $5·30일, [Colyseus Cloud](https://colyseus.io/pricing/)는 월 $15부터이며 무료 티어 없음, 개발 중에는 로컬 서버로 무료, (c) TTS·AI API 사용량.

## 3. 바로 쓰는 명령

```bash
pnpm install                  # 의존성 (이미 설치됨)
pnpm dev                      # http://127.0.0.1:5173  (샌드박스 씬)
pnpm typecheck && pnpm test   # 타입체크 + 단위 테스트
pnpm build                    # 프로덕션 빌드
pnpm doctor                   # 환경 점검 (읽기 전용)
pnpm lint:content             # 단어/대사/퀘스트 검증
pnpm test:tools               # 콘텐츠 린트 + 플랫폼 탐색 자체 테스트
pnpm build:sprites            # 캐릭터 아틀라스 전체 재생성
open -a Tiled                 # 맵 에디터 (macOS). Windows는 시작 메뉴에서 Tiled 실행
```

샌드박스 씬 쿼리: `?char=cat_base|siamese_base` · `?dir=left&act=walk|idle|net`(애니메이션 고정 재생) · `?grid=0`. 클릭/탭하면 그 지점으로 걷는다(게임 규칙 아님, 파이프라인 검증용).

## 4. 직접 설치해야 하는 것 (모바일 빌드용 — 지금은 불필요)

큰 다운로드이거나 계정이 필요해서 자동으로 설치하지 않았다. `pnpm doctor`가 현황을 보여 준다.

1. **Xcode** — App Store에서 설치(약 15GB+) 후 `sudo xcode-select -s /Applications/Xcode.app`
2. **JDK 17** — `brew install --cask temurin@17`
3. **Android Studio** — `brew install --cask android-studio` 후 한 번 실행해 SDK 설치
4. (출시 때) Apple Developer Program, Google Play Console 계정

## 5. 나중에 정하면 만들 도구 (설계 결정 대기)

| 결정 대기 | 그때 준비할 것 |
|-----------|----------------|
| 맵 시점·이동 방식 | `map_export.py`(Tiled → 논리 그리드 JSON + 검증), 길찾기 라이브러리 설치 |
| 집 짓기·가구 방식 | `item_slicer`(정적 아이템 시트 → 아틀라스+앵커), 카탈로그 스키마·린트 |
| 캐릭터 선정 | 캐릭터별 시트 생성·슬라이스, 팔레트 스왑 영역 설정 일반화 |
| 진행 방식·보상 | 스폰/드롭 테이블 시뮬레이터(세션 길이 검증) |
| TTS 제공자 | `tts_batch.py`, `.env` 키 |
| 서버 착수 | Colyseus 뼈대, 7인 봇, 디버그 오버레이, `fx-lab` |

## 6. 액션 랩 — 표정·액션·효과를 타임라인으로 보고 고치는 도구

`pnpm dev` 후 **http://127.0.0.1:5173/lab.html** (개발 서버 전용, 출시 빌드에는 포함되지 않음).

- **원리**: 아틀라스의 포즈(대기·걷기 A/B·포충망 + 넘어짐 `fallen`·기쁨 `joy`·놀람 `surprised`)에 **키프레임 변형**(앞으로 이동 `x`, 높이 `lift`, 늘림/눌림 `scaleX·scaleY`, 회전 `rotation`, 앞 기울임 `lean`, 투명도 `alpha`)과 **효과 이벤트**를 얹는다. 달리기·살금살금처럼 기존 포즈로 되는 액션은 텍스처를 늘리지 않고, 표정·자세가 달라야 하는 것만 포즈를 그려 넣는다.
- **캐릭터 2종** (`apps/client/src/lib/characters.ts`): 주황 무늬 고양이 `cat_base`, 샴 고양이 `siamese_base`. 각 27프레임(3방향 × 9포즈: idle, walk_a, walk_b, net, fallen, joy, surprised, net_up, net_down).
- **들어 있는 액션 8종** (`data/actions/*.json`): 대기, 걷기, 달리기, 살금살금 걷기, 놀람, 넘어짐, 기쁨, 포충망 휘두르기. 넘어짐·기쁨·놀람·포충망은 그린 포즈를 쓴다. 값은 출발점일 뿐이고 랩에서 다듬는 것이 목적이다.
- **포충망 휘두르기(타격감)**: 준비 자세 `net_up`(뒤로 젖힘) → 내리침 `net_down`(몸을 던짐) → 복귀. 내리치는 순간에 궤적 `swoosh`, 충돌 `impact`, 잔상 `ghost`, 화면 흔들림 `shake`, **순간 정지 `hitstop`(0.08초)** 이 겹친다. 충돌 지점과 궤적은 방향별로 그림의 그물 위치에 맞춰 두었다(`lib/fx.ts`의 `STRIKE`, `SWING`).
- **효과 12종** (코드로 그린 임시 효과, 나중에 그림으로 교체 가능): dust, exclaim(!), question(?), stars, sweat, sparkle, heart, shake, swoosh(휘두르는 궤적), impact(충돌), ghost(잔상), hitstop(순간 정지 — 그리는 것 없이 액션 시간만 멈춤).
- 재생 시계 `ActionClock`(`lib/action.ts`)이 시간 진행·이벤트 발사·순간 정지를 담당한다. 랩과 게임이 같은 시계를 써야 타이밍이 같아진다.
- **조작**: 키 드래그로 시간 이동, 눈금 클릭/드래그로 스크럽, `+`로 재생 위치에 키 추가, 오른쪽 패널에서 값·이징·포즈·효과 변경, 배속 0.1~2×, 한 프레임씩 이동(←/→), Space 재생/정지, Delete 키 삭제. **저장**을 누르면 `data/actions/<id>.json`에 기록된다.
- **바닥 눈금**이 `이동 px/s` 속도로 흘러가므로 발이 미끄러지는지 눈으로 확인할 수 있다.
- URL 프리셋: `?action=fall&dir=left&char=siamese_base&t=0.4&play=0&speed=0.5`
- 게임과 **같은 코드**로 재생한다: `apps/client/src/lib/action.ts`(샘플링·검증, 순수 로직) · `actionPlayer.ts` · `fx.ts`. `pnpm test`가 모든 액션 파일의 형식과 "두 캐릭터 모두 가진 포즈만 쓰는지"를 검사한다.

**한계 (정직하게)**
- 표정은 **그린 포즈가 있는 것만**(넘어짐·기쁨·놀람) 바뀐다. 새 표정이 필요하면 포즈 시트를 생성해 `tools/build_sprites.py`의 `--extra`에 추가하면 랩의 `포즈` 트랙에서 바로 쓸 수 있다. 뒷모습은 얼굴이 안 보이므로 팔·꼬리 자세로만 구분된다.
- 타임라인에 "액션 길이" 표시선은 없다(길이는 오른쪽 패널). 길이를 넘는 키는 저장 시 검증에서 걸린다.
- 저장 API는 개발 서버에서만, 같은 출처의 JSON 요청만 받고 파일 이름은 검증된 id로만 만든다.

**이번에 드러난 자산 결함과 처리**
- 고양이 시트의 옆모습 줄에서 대기는 왼쪽, 걷기 2칸은 오른쪽을 보고 있었다 → 슬라이서 `--flip left_walk_a,left_walk_b`로 반전.
- 반전하자 귀 무늬가 반대쪽 귀로 넘어가 걷는 동안 무늬가 귀 사이를 오갔다(사용자 발견, 2026-09-30). 또 원본부터 걷기 칸의 무늬가 대기보다 작게 그려져 있었다 → `--marking-hue 18,50`으로 대기 칸의 무늬를 걷기 칸에 옮겨 그려 위치·크기를 통일.
- **고양이 시트는 항상** `--clear-enclosed --flip left_walk_a,left_walk_b --marking-hue 18,50` 로 자른 뒤 `palette_swap.py`를 다시 돌린다.
- 남은 불일치(미수정): 주황 고양이 옆모습 **포충망 칸의 무늬가 더 작다**(머리 각도가 달라 그대로 둠).
- 샴 고양이 시트는 옆모습 포충망 칸만 오른쪽을 보고 있어 `--flip left_net`. 무늬가 좌우 대칭이라 반전 부작용이 없다.
- `--clear-enclosed`는 그물 안쪽 순백을 투명하게 하는 옵션인데 **눈 흰자·하이라이트도 지운다.** 그래서 추가 포즈 시트에는 적용하지 않고, 샴 고양이 시트에도 쓰지 않는다.
- 새싹 캐릭터는 2026-09-30에 샴 고양이로 교체했다. 원본 시트는 `content/`에 남아 있고 아틀라스만 지웠다.

**방향 대응 범위 (2D 스프라이트 기준)**
- 방향은 4개(아래·위·왼쪽, 오른쪽은 왼쪽의 좌우 반전)이고 액션 데이터는 방향과 무관하게 하나다. `x`는 바라보는 쪽으로, `rotation`은 왼쪽을 볼 때 반대로, `lean`은 좌우를 볼 때만 적용된다.
- 넘어짐: 네 방향 모두 **그린 포즈**를 쓴다. 아래를 볼 때는 보는 사람 쪽으로, 위를 볼 때는 멀어지는 쪽으로, 좌우는 보는 방향으로 엎어진다(오른쪽은 왼쪽 그림 반전).
- 아직 없는 것: 바라보는 방향과 다른 쪽으로 넘어지기(밀려서 뒤로 등), 대각선 8방향, 액션 도중 방향 고정 규칙(게임 로직 단계에서 결정).

## 7. 성능 — 여러 캐릭터가 동시에 움직일 때

`pnpm bench` (= `uv run tools/bench.py`): 프로덕션 빌드를 헤드리스 Chrome으로 열고, 무작위로 걸어 다니는 스프라이트 N개의 프레임 간격을 잰다. 프레임 제한을 풀고 재므로 `fps`는 **여유분**이다.

| 동시 스프라이트 | 이 Mac의 GPU (M3) | 소프트웨어 렌더링(GPU 없음 가정) |
|---:|---|---|
| 7 | 786 fps (1.27 ms) | 154 fps (6.5 ms, p95 11.7 ms) |
| 30 | 782 fps | 114 fps (8.8 ms, p95 15.3 ms) |
| 100 | 771 fps | 38 fps (26.5 ms) |
| 300 | 650 fps | 측정 불가 (프레임 1장에 8초) |
| 600 | 614 fps | — |

(2026-09-30, 캔버스 960×540, 스프라이트 0.5배, 아틀라스 2장. 이동·깊이 정렬·애니메이션 전환 포함. 업데이트 CPU는 600개에서도 0.03 ms.)

**읽는 법**
- 7인 파티 + NPC + 채집 대상 수준(수십 개)은 **CPU·드로우콜 쪽으로는 여유가 크다.**
- 병목은 **픽셀을 칠하는 양(fill rate)** 이다. GPU가 약하면 100개 부근에서 30fps대로 떨어진다. 현재 프레임은 사각형의 **66~75%가 투명 픽셀**이라 낭비가 크다.
- **이 수치는 Mac 기준이다. 저사양 안드로이드 웹뷰에서는 아직 재지 않았다.** 실기기 측정 전에는 "문제없다"고 말할 수 없다.

**설계에 반영할 예산**
- 화면 안 움직이는 스프라이트 **40개 이하**를 목표로 한다(7인 + NPC + 생물 + 효과).
- 텍스처 메모리: 캐릭터 아틀라스 1장 ≈ 3.5 MB(27프레임, 여백을 잘라 담은 상태; 잘라 담지 않으면 7 MB). 그린 포즈 1프레임 추가 ≈ 0.18 MB. 배경 원본 2752×1536은 16.9 MB이므로 축소·분할한다.
- 색 변형 7종을 아틀라스 7장으로 두면 ≈ 25 MB → **한 장에 묶거나 실행 중 색 치환**으로 바꾼다.
- 프레임은 **여백 없이 잘라 담는다(trim)** — 슬라이서가 적용함(2026-09-30). 아틀라스가 절반 수준(52~54%)으로 줄고 칠하는 면적도 같이 준다. 캐릭터 크기는 "서 있는 키 183px"(`--char-height`)에 고정되어, 크거나 넓은 포즈를 추가해도 캐릭터가 작아지지 않는다.
- 액션은 가능한 한 **변형+효과 방식**(§6)으로 만들어 프레임 수를 늘리지 않는다.
- 다른 플레이어 위치는 초당 10~15회만 받고 화면에서 보간한다.

`tools/shot.py`: 페이지를 **실제 시간으로 N초 돌린 뒤** 캡처한다(`chrome --screenshot`은 로드 직후라 움직임·효과가 안 찍힘). 연속 프레임 캡처 가능.

## 8. GitHub · Hugging Face 조사 — 만들지 않고 가져다 쓸 것 (2026-09-30)

| 용도 | 후보 | 상태 | 판단 |
|------|------|------|------|
| 타임라인 편집 UI | [animation-timeline-js](https://github.com/ievgennaida/animation-timeline-control) | MIT, ★469, 마지막 갱신 2024-07 | **채택** (개발 도구 전용이라 갱신 중단 위험은 감수) |
| 값 조절 패널 | [Tweakpane](https://github.com/cocopon/tweakpane) | MIT, ★4.6k, 2026-03 갱신 | **채택** — 나중의 효과 조절(fx-lab)에도 재사용 |
| 모션 편집기 통째 | [Theatre.js](https://github.com/theatre-js/theatre) | ★12.7k, **2024-08 이후 갱신 없음**, 편집기는 AGPL | 보류 — 자체 형식, 이벤트 트랙 없음 |
| 뼈대 애니메이션 | Rive, DragonBones | 런타임 MIT | 보류 — 캐릭터를 부위별로 나눠 그려야 함(현재는 통그림) |
| 격자·길찾기·제스처 | [phaser4-rex-plugins](https://github.com/rexrainbow/phaser3-rex-notes) 4.2.0 | MIT, 2026-09 활발, Phaser 4용 | **유력 후보** — 가구 배치·이동 방식 결정 때 먼저 검토 |
| 길찾기 단독 | EasyStar.js / navmesh | MIT, 각각 2024-01 / 2023-11 이후 갱신 없음 | 위 rex 플러그인을 먼저 검토 |
| 배경 제거 | [rembg](https://github.com/danielgatis/rembg) | MIT, ★24.9k, 활발 | 흰 배경이 아닌 그림이 생기면 사용. `briaai/RMBG`는 비상업 라이선스라 제외 |
| 시트 자르기 | GitHub 검색 결과 ★0~1 수준뿐 | — | 자체 슬라이서 유지가 타당 |
| 사물 4방향 시트 생성 | [fal/flux-2-klein-4b-spritesheet-lora](https://huggingface.co/fal/flux-2-klein-4b-spritesheet-lora) | Apache-2.0, 2×2 다시점 | 가구 그림 때 시험 후보 (미검증, 실행 환경 필요) |
| 픽셀아트 시트 생성 모델들 | HF 다수 | Apache-2.0 | 수채화 그림체와 안 맞아 제외 |
| 무료 로컬 TTS | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache-2.0, ♥7k | **영어 전용 무료 후보** — 음성 목록에 한국어 없음. 한국어는 기존 후보 유지 |

## 9. Windows에서 개발하기 (RTX 노트북)

개발 도구는 맥·윈도우 공통으로 동작하도록 고쳤다(2026-10-01). **맥에서만 실행해 검증했고 윈도우 실기는 아직 확인하지 못했다.** 경로 탐색 로직은 윈도우 환경을 흉내 낸 테스트(`tools/tests/test_common.py`)로 확인했다.

**설치** (PowerShell, 관리자 권한 불필요한 것이 대부분):
```powershell
winget install OpenJS.NodeJS.LTS     # Node 20.19 이상
winget install astral-sh.uv          # 파이썬 도구 실행기 (파이썬도 알아서 받는다)
winget install Git.Git
winget install Gyan.FFmpeg
winget install Google.Chrome         # 캡처·벤치용 (Edge만 있어도 자동으로 사용)
corepack enable                      # pnpm (또는 npm install -g pnpm)
```
Tiled는 https://www.mapeditor.org/ 에서 설치. 설치 후 새 터미널에서 `pnpm install`, `pnpm doctor`.

**바뀐 것**
- Chrome/Edge 위치를 Program Files·LocalAppData에서 자동으로 찾는다. 다른 곳에 있으면 환경변수 `CHROME_PATH`로 지정.
- `pnpm`이 윈도우에서는 `pnpm.cmd`라 그냥 실행하면 못 찾는 문제를 경로를 풀어서 해결했다.
- 벤치/캡처가 끝나면 `taskkill /T`로 자식 프로세스까지 종료한다.
- 한국어 윈도우의 기본 인코딩(cp949) 때문에 생기던 문제 두 가지를 막았다: 파일을 읽고 쓸 때 UTF-8을 명시했고, 콘솔 출력이 한글에서 죽지 않게 했다(`PYTHONIOENCODING=ascii`로 재현해 확인).
- `build_sprites.sh`(셸 필요)를 `build_sprites.py`로 옮겼다. `.sh`는 이것을 부르는 래퍼.
- `.gitattributes`로 줄바꿈을 고정했다(`.sh`·`.py`는 LF).
- `pnpm doctor`는 윈도우에서 `winget` 설치 명령을 안내하고, iOS(Xcode) 항목은 "해당 없음(Mac 필요)"으로 표시한다.

**윈도우에서 달라지는 점**
- **iOS 빌드는 Mac이 필요하다.** 윈도우에서는 안드로이드만 가능하다.
- 성능 수치는 기기마다 다르다. 노트북 GPU로 잰 값은 폰 성능의 대용이 아니다.
- 벤치의 `GPU:` 줄이 `ANGLE (NVIDIA ...)`인지 `SwiftShader`/`Basic Render`인지 확인해야 한다. 소프트웨어 렌더링으로 잡히면 GPU 가속이 꺼진 것이다.
