# tools/

Island 제작용 자체 툴. 모두 **Python 단일 파일 + `uv run`** (의존성은 파일 머리의 PEP 723 블록에 선언되어 별도 설치 불필요).
원본 `content/*.png`는 읽기만 하고 수정하지 않는다.

| 툴 | 역할 | 실행 |
|----|------|------|
| `sprite_slicer.py` | AI 캐릭터 시트(흰 배경) → 배경 제거·12프레임 분리·정렬 → Phaser 아틀라스 | `uv run tools/sprite_slicer.py content/<시트>.png --clear-enclosed` |
| `build_sprites.sh` | **모든 캐릭터 아틀라스를 한 번에 다시 만든다.** 시트별 보정 옵션이 여기 적혀 있으니 슬라이서를 직접 부르지 말고 이걸 쓴다 | `./tools/build_sprites.sh` |
| `palette_swap.py` | 털 무늬/꼬리 끝 + 스카프 색만 바꿔 플레이어 7인 외형 생성 | `uv run tools/palette_swap.py` |
| `atlas_preview.html` | 아틀라스 애니메이션 재생·검수 (피벗선, 어니언 스킨, 바닥 스크롤) | 아래 참고 |
| `content_lint.py` | 단어/대사/퀘스트 JSON·CSV 검증 (12단어 제한, 허용 어휘, 한글 번역, 중복 id, 에셋 경로) | `uv run tools/content_lint.py [--strict] [-v]` |
| `doctor.py` | 개발 환경 점검(읽기 전용): 필수/권장/모바일/API 키(값은 출력 안 함) | `uv run tools/doctor.py` (= `pnpm doctor`) |
| `bench.py` | 군중 성능 측정: 스프라이트 N개가 걸어 다닐 때 프레임 간격 (`--software`로 GPU 없는 상황 가정) | `uv run tools/bench.py --stress 7,30,100` (= `pnpm bench`) |
| `shot.py` | 페이지를 실제 시간으로 돌린 뒤 캡처. `--until "JS조건"`으로 특정 순간(예: 랩의 `window.__labTime >= 0.27`)을 기다렸다 찍을 수 있다 | `uv run tools/shot.py URL out.png --wait 1.2 --frames 3` |
| `tests/test_content_lint.py` | 린트가 정상 데이터는 통과시키고 깨진 픽스처는 잡는지 확인 | `uv run tools/tests/test_content_lint.py` |

## 파이프라인 (캐릭터)
```
content/…시트.png (+ 추가 포즈 시트)
  └─ build_sprites.sh → sprite_slicer  →  assets/sprites/<캐릭터>.{png,json,anims.json} + <캐릭터>_contact.png
        └─ palette_swap  →  cat_p1..p7.{png,json,anims.json} + cat_palettes_contact.png
              └─ atlas_preview 로 눈 검수
```
- 시트 규격: 3행×4열. 행 = `down / up / left`, 열 = `idle / walk_a / walk_b / net`. **오른쪽은 `left`의 flipX**(애니메이션 JSON의 `flipX: true`, 클라이언트가 적용).
- 걷기 루프는 `[idle, walk_a, idle, walk_b]`, `net`은 단발.
- 셀 수가 12개가 아니면 **조용히 넘어가지 않고 오류 종료**한다 (`--merge-gap`, `--min-area`, `--tol`로 조정).
- 프레임 정렬: 발바닥 높이는 맞추고(bottom align), 가로는 같은 행의 idle 실루엣과 상관 정합(`--pivot-x register`, 기본) 또는 발 중심(`feet`).
- 그물 안쪽 흰 면은 `--clear-enclosed`로 투명 처리.
- AI 시트가 한 줄 안에서 방향을 섞어 그리면 `--flip 칸이름,...`으로 그 칸만 좌우 반전한다.
- 반전하면 한쪽에만 있는 머리 무늬(한쪽 귀 색 등)가 반대쪽으로 넘어간다. `--marking-hue 시작,끝`(색상 각도)을 주면
  반전한 칸의 무늬를 지우고 **같은 줄 idle 칸의 무늬를 머리 위치·크기에 맞춰 다시 칠한다**(볼터치·윤곽선·눈은 건드리지 않음).
  **고양이 시트는 반드시** `--clear-enclosed --flip left_walk_a,left_walk_b --marking-hue 18,50` 로 자른다.
- 오른쪽 방향은 왼쪽 그림의 좌우 반전이라, 한쪽에만 있는 무늬는 오른쪽을 볼 때 반대편에 보인다(프레임 사이에서는 일정). 이것까지 맞추려면 오른쪽 전용 그림이 필요하다.
- 포즈 추가: `--extra 시트.png:ref,포즈이름,...` — 행 구성이 같은(3방향) 추가 시트의 칸을 같은 아틀라스에 넣는다. `ref` 열은 서 있는 기준 그림으로, 크기를 맞추는 데만 쓰고 버린다. 서 있는 포즈는 idle에 맞춰 정렬하고 누운 포즈는 실루엣 중심에 맞춘다. 현재 `fallen`, `joy`, `surprised`, `net_up`, `net_down`. 몸에서 떨어져 그려진 조각(머리 뒤로 넘어간 그물 테 등)은 가장 가까운 칸에 자동으로 붙인다.
- `--clear-enclosed`는 눈 흰자·하이라이트까지 지우므로 추가 시트에는 적용되지 않는다.
- 크기 기준은 프레임이 아니라 **서 있는 키**(`--char-height`, 기본 183px)다. 포즈에 따라 프레임(논리 칸)은 커질 수 있지만 캐릭터는 같은 크기로 유지된다.
- 아틀라스에는 프레임을 **불투명 영역만 잘라 빽빽하게** 담는다(`trimmed`/`spriteSourceSize`/`sourceSize` 기록). 엔진과 미리보기는 논리 칸과 피벗을 그대로 쓴다.
- 액션(달리기·넘어짐 등)은 가능한 한 프레임을 새로 그리지 않고 `data/actions/*.json` + 액션 랩(`/lab.html`, `docs/TOOLING.md` §6)에서 만든다.

## atlas_preview.html
파일만 더블클릭해서 열고 **PNG + .json + .anims.json 3개를 드롭**하면 된다. 또는 저장소 루트에서
```
python3 -m http.server 8765
# http://127.0.0.1:8765/tools/atlas_preview.html   (cat_base 자동 로드)
```
URL 파라미터: `?base=../assets/sprites/cat_p3&dir=left&act=walk&fps=8&sc=2&gs=120&onion=1&bg=grass&guides=0`
- **바닥 스크롤 속도**를 올리고 발이 바닥 눈금과 같이 밀리는지 본다 (발 미끄러짐 검사).
- **어니언 스킨**은 루프 전 프레임을 겹쳐 머리 위치 튐을 확인한다.

## content_lint 데이터 규칙
```
data/vocab/unitN.csv        id,word,ko,unit,image,audio
data/vocab/function_words.txt   모든 유닛에서 허용되는 기능어 (# 주석)
data/dialogue/*.json        npc 대사 (schema: data/schema/dialogue.schema.json)
data/quest/*.json           파티 퀘스트 (schema: data/schema/quest.schema.json)
```
- 대사의 영어 단어는 **기능어 + 그 파일의 `unit` 이하 유닛 단어(복수형 s/es 허용) + `names`/`npc`** 만 쓸 수 있다.
- 에셋 경로가 비었거나 파일이 없으면 기본은 경고, `--strict`면 오류. (아직 이미지/음성이 없어 기본 실행은 경고만 낸다.)
- 종료 코드 0/1 → 나중에 pre-commit/CI에 그대로 연결 가능.
- `unit1.csv`의 12단어는 콘셉트 이미지에서 뽑은 **시드 목록**이다. 설계 문서의 유닛 구성(인사→동물·곤충→색·꽃…)에 맞춰 재배치할 것.
