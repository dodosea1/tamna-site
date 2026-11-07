"""JSON 표 데이터를 HTML로 그린다. 값은 전부 escape한다."""

from __future__ import annotations

from html import escape

FEEDBACK_STATUSES = ("검토", "예정", "완료", "안 함")
ROADMAP_STATUSES = ("계획", "진행", "완료")


def _e(value: object) -> str:
    return escape(str(value if value is not None else ""))


def _table(headers: list[str], rows: list[list[str]], css: str) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="tablewrap"><table class="{css}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def feedback_table(rows: list[dict]) -> str:
    if not rows:
        return "<p>아직 받은 의견이 없습니다.</p>"
    out: list[list[str]] = []
    for row in rows:
        status = row.get("status", "")
        if status not in FEEDBACK_STATUSES:
            raise ValueError(f"반영 현황 상태가 잘못됨: {status!r} (가능: {', '.join(FEEDBACK_STATUSES)})")
        summary = _e(row.get("summary"))
        if status == "완료":
            summary = "📢 " + summary
        out.append([_e(row.get("period")), _e(row.get("category")), summary, f'<span class="status status-{FEEDBACK_STATUSES.index(status)}">{_e(status)}</span>', _e(row.get("reason")), _e(row.get("applied"))])
    return _table(["접수 기간", "분류", "의견 요약", "상태", "사유", "적용일"], out, "feedback")


def roadmap_section(data: dict) -> str:
    rows: list[list[str]] = []
    for item in data.get("items", []):
        status = item.get("status", "")
        if status not in ROADMAP_STATUSES:
            raise ValueError(f"로드맵 상태가 잘못됨: {status!r} (가능: {', '.join(ROADMAP_STATUSES)})")
        rows.append([_e(item.get("topic")), f'<span class="status">{_e(status)}</span>', _e(item.get("note"))])
    parts = [
        f'<p class="note">{_e(data.get("note"))} <span class="muted">갱신 {_e(data.get("updated"))}</span></p>',
        _table(["주제", "상태", "메모"], rows, "roadmap"),
    ]
    checklist = data.get("steam_checklist", [])
    if checklist:
        items = "".join(
            f'<li class="{"done" if c.get("done") else "todo"}">{"✅" if c.get("done") else "⬜"} {_e(c.get("item"))}</li>' for c in checklist
        )
        parts.append(f'<h3>스팀 페이지를 열기 전에 갖출 것</h3><ul class="checklist">{items}</ul>')
    return "\n".join(parts)


def support_section(data: dict) -> str:
    ledger = data.get("ledger", [])
    total = sum(int(row.get("received_krw", 0)) for row in ledger)
    cap = int(data.get("cap_krw", 0))
    parts = [f'<p class="total">누적 {total:,}원 / 상한 {cap:,}원</p>']
    notice = data.get("notice", [])
    if notice:
        parts.append("<ul class=\"notice\">" + "".join(f"<li>{_e(n)}</li>" for n in notice) + "</ul>")
    if ledger:
        rows = [[_e(r.get("month")), f'{int(r.get("received_krw", 0)):,}', f'{int(r.get("spent_krw", 0)):,}', _e(r.get("use"))] for r in ledger]
        parts.append(_table(["달", "받은 금액(원)", "쓴 금액(원)", "쓴 곳"], rows, "support"))
    else:
        parts.append("<p>아직 받은 후원이 없습니다.</p>")
    thanks = data.get("thanks", [])
    if thanks:
        parts.append("<h3>고마운 분들(동의한 분만)</h3><p>" + ", ".join(_e(t) for t in thanks) + "</p>")
    return "\n".join(parts)


def ai_table(rows: list[dict]) -> str:
    out = [[_e(r.get("area")), _e(r.get("who")), _e(r.get("tool")), _e(r.get("changed"))] for r in rows]
    return _table(["영역", "누가", "도구", "바뀐 날"], out, "ai")
