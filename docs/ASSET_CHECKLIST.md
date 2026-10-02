# 에셋 점검표

Island 사이트: https://sakurayuki89.github.io/iland/  
LLM은 먼저 `llms.txt`와 `data/world.json`을 읽어 섬의 최신 데이터를 확인합니다.

설계서(`DESIGN_AND_TECH_PLAN.md`)의 기능과 일반적인 2D 모바일 게임 에셋 분류(캐릭터 · 환경 · UI · 아이템 아이콘 · 효과 · 오디오 · 스토어)를 기준으로 정리했다. 2026-10-02 기준.

원본 시트는 `content/`, 잘라 낸 게임용 PNG는 `assets/`. 다시 만들기:
```
uv run tools/env_slicer.py      # 아이콘·UI·환경·타일 → assets/...   (검수: assets/env/_contact.png)
uv run tools/build_sprites.py   # 캐릭터·NPC·곤충 아틀라스          (검수: assets/{sprites,insects}/*_contact.png)
```

## 있는 것

| 분류 | 내용 | 위치 |
|---|---|---|
| 플레이어 | 고양이 2종 + 팔레트 7종, 넘어짐·기쁨·놀람·포충망 포즈 | `assets/sprites/cat_*`, `siamese_*` |
| NPC | 박사님·수집가(새끼)·낚시꾼 아틀라스(4방향 걷기 + `talk`/`cheer`/`cast`), 초상화 4명(요리사 포함) | `assets/sprites/npc_*`, `assets/npc/portraits/` |
| 곤충 | 10종 아틀라스(4방향 날기·걷기 + `flee`), 도감 아이콘 10 + 비·호수 생물 4종 아틀라스(지렁이·달팽이·물방개·소금쟁이, Grok — 아이콘·단어 카드는 아직) | `assets/insects/` |
| 물고기 | 도감 아이콘 9종(금붕어·붕어·메기·도미·고등어·흰동가리·게·문어·복어) | `assets/fish/icons/` |
| UI | 타이밍 링·바늘, 별(채움/빈), 하트, 탭 표시, 시계(낮/밤), 둥근 버튼, 말풍선, 대화창, 단어 카드 틀, 도감 책, 칸(빈/잠김), 가방 칸, 나무 배너, 버튼(기본/눌림), 역할 카드 7장+뒷면 | `assets/ui/` |
| 작물 | 꽃 4색 × 5단계(씨앗→싹→잎→봉오리→꽃) | `assets/crops/` |
| 단어 그림 | unit1 12단어 (`unit1.csv`의 `assets/words/<id>.png`와 일치) | `assets/words/` |
| 아이템 | 도구 9(포충망·병·벌레 든 병·물뿌리개·씨앗 봉투·가방·낚싯대·모종삽·바구니), 음식 16, 꾸미기·이벤트 9(편지·병 편지·보물 지도·소포·화분·돌탑·통나무 의자·전구 줄·풍경) | `assets/items/` |
| 장비 (3단계) | 장갑(면·정원·별), 신발(캔버스·장화·날개 운동화), 채집망(대나무·튼튼·무지개) 9 — Grok | `assets/items/gear/` |
| 보상 | 조개 코인·코인 더미·스티커 시트·선물 상자·도장 카드·별 메달·보물 상자·잎사귀 배지·강화 티켓 9 — Grok | `assets/items/rewards/` |
| 꾸미기 착용 | 모자 6·가방 2·리본 | `assets/wearables/` |
| 효과 | 반짝이·별·빛·잎·꽃잎·흙·물·먼지·연기·감정(!·?·하트·음표·땀)·색종이 16, 날씨·밤 9(빗방울·웅덩이·비구름·구름·불빛·켜진 창·달·별·무지개) | `assets/fx/` |
| 환경 | 나무·풀·꽃·건물·소품·물가 54 + 손님 배 | `assets/env/` (`manifest.json`에 월드 크기) |
| 바닥 | 반복 텍스처 9, 경계 타일 6세트(볼록 3 + 오목 3) | `assets/tiles/` |
| 스토어 | 앱 아이콘 원본 1024 | `assets/app/icon_1024.png` |
| 기획 | 섬 구상도(4×4), 크기 비교표 | `docs/img/` |

### 알려진 한계
- **경계 타일**은 AI 그림을 3×3으로 자른 것이라 같은 변 타일을 길게 이으면 이음새가 보일 수 있다. `*_inner` 세트의 네 모서리가 오목(안쪽) 모서리 타일이다. Tiled에 실제로 깔아 보며 확인 필요.
- **박사님 `up_talk`**은 뒤에서 말을 걸어도 앞을 보고 손을 흔드는 그림이다(돌아보는 연출로 사용).
- **나비 `down_flee`**는 옆모습으로 그려졌다.
- **곤충 아틀라스**는 날개 모양이 프레임마다 달라 몸통 아래 중심으로 맞췄다(`--pivot-x feet`). 잠자리 등은 날개짓 때 살짝 흔들려 보일 수 있다 — `tools/atlas_preview.html`로 검수.
- **빛 번짐 그림**(`fx/glow`, `fx/weather/light_glow`)은 흰 배경 제거 때 가장자리 번짐이 일부 잘린다. 게임에서는 코드로 그린 방사형 그라데이션이 더 낫다.
- 딱정벌레류 걷기 두 프레임은 다리 차이가 작다. 이동 시 몸을 살짝 위아래로 흔들어 보완.

## 아직 없는 것

| 에셋 | 이유 |
|---|---|
| **오디오 전부**: 단어·대사 TTS 17개(`assets/audio/en/`), 효과음, 배경음 | 이미지 생성 도구로 만들 수 없음. TTS 제공자 결정 후 `tts-batch`(설계서 §6), 효과음은 라이선스가 명확한 음원 사용(설계서 §6) |
| 그림자 | 발밑 타원은 코드로 그리는 쪽이 크기 조절이 쉬움 |
| 요리사·우체부 걷기 시트 | 초상화만 있음(요리사). M3에서 필요할 때 |
| 물고기 물속 그림자, 철새, 희귀 나비 | 그림자는 코드(타원+물결)로 충분. 이벤트 생물은 M3 |
| 물 반짝임 애니메이션 | 셰이더/트윈으로 처리 권장 |
| 스플래시·로고·스토어 스크린샷·보호자/설정 UI·폰트 | 출시(M6) 단계. 스크린샷은 실제 게임 화면으로 |

## 조사 메모

- 상용 "코지 농장" 에셋 팩은 보통 **지형 8종 정도를 자동 연결(autotile) 세트로 제공**하고, Tiled용 Wang 세트를 함께 준다.
- Tiled 기준 지형 두 개를 잇는 완전한 세트는 **모서리 방식 16장**, 모서리+변 방식은 256장이고, 흔히 줄인 **47장 "blob"** 세트를 쓴다. 우리는 볼록 9 + 오목 4로 13종(가운데 포함)을 갖췄다.
- UI 키트는 보통 **9-slice 창·버튼(기본/눌림 상태)·바·아이콘 묶음**으로 구성된다.

출처: [Tiled 지형 문서](https://doc.mapeditor.org/en/stable/manual/terrain/), [47장 blob 세트 설명](https://rasterloom.itch.io/top-down-tileset-autotiling/devlog/1644351/why-an-auto-tiling-terrain-set-has-exactly-47-tiles), [Cozy Farm Tileset(autotile 예)](https://antahonist.itch.io/cozy-farm-tileset-autotiles-for-godot-tiled/devlog/1682886/cozy-farm-tileset-is-live), [Cozy Farming Icons & UI Kit](https://www.fab.com/listings/605a4b5c-5ba9-4736-9ab0-50431994d82b?lang=en), [Cozy Pixel UI Kit](https://lungucristian1980.itch.io/cozy-pixel-ui-kit-farm-rpg)
