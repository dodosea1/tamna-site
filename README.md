# 탐라(가제) 공개 사이트

개발 과정을 매일 기록하고, 의견을 받고, 무엇을 반영했는지 공개하는 정적 사이트다. 생성기는 `build.py`(Python 3.12, 의존성은 `markdown` 하나), 배포는 GitHub Pages(`.github/workflows/pages.yml`)다.

## 어떻게 올라가나

- 매일 기록은 `content/log/YYYY-MM-DD.md`에 쓰이고, 작업 세션이 끝날 때 `python tools/publish.py --message "log: YYYY-MM-DD"`가 검사 → 빌드 → 커밋 → 푸시를 한 번에 한다. 푸시가 되면 GitHub Actions가 다시 빌드해 사이트를 갱신한다.
- 이달의 정리(`content/monthly/YYYY-MM.md`)는 초안을 사람이 읽고 "올려"라고 한 뒤에만 같은 명령으로 올린다.
- 표 데이터는 `data/*.json`(반영 현황·로드맵·후원·AI 사용 범위·사이트 설정)이다. 글과 표를 고쳤으면 같은 명령으로 올린다.

## 스레드 자동 게시

`tools/threads_post.py`가 공개된 기록을 하루 한 편 공식 API로 올린다. 직접 쓴 글은 `content/threads/YYYY-MM-DD.md`에 둔다. 토큰과 상태는 저장소 밖 `~/.claude/tamna-threads/`에만 있고, 토큰이 없거나 꺼져 있으면 올리지 않는다. `--status`로 상태를, `--dry-run`으로 올릴 글을 본다.

## 검사에 걸리면

`tools/lint_public.py`가 비공개 단어·경로·주소·전화번호 패턴을 찾으면 게시가 멈춘다. 금지어 목록은 저장소 밖(`~/.claude/tamna-private-terms.txt`)에 있고, 목록이 없으면 검사 자체가 실패해 게시되지 않는다. 걸린 줄(`경로:줄: 규칙`)을 고친 뒤 다시 실행한다. 목록은 고치지 않는다.

## 로컬에서 보기

```
pip install -r requirements.txt
python -m unittest discover -s tests
python build.py --out _site --base ""
cd _site && python -m http.server 8765
```
