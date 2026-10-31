"""Baris database (snake_case) ke JSON API (camelCase, persis seperti data.ts)."""

from pydantic.alias_generators import to_camel

from app.logic import attempt_statuses, pending_of, transcript_of, verify_quote


def camel(row: dict, drop: tuple[str, ...] = ()) -> dict:
    return {to_camel(k): v for k, v in row.items() if k not in drop}


def session_out(row: dict) -> dict:
    return camel(row, drop=("boby_script", "instruction", "goal", "penerapan"))


def findings_out(attempt: dict) -> list[dict]:
    """Status yang dikirim sudah melewati pemverifikasi; status asli AI tetap terlihat di aiStatus."""
    transcript = transcript_of(attempt) if attempt.get("findings") else ""
    out = []
    for f in attempt.get("findings") or []:
        verified = verify_quote(f["quote"], transcript)
        out.append({**f, "status": f["status"] if verified else "ambigu", "aiStatus": f["status"],
                    "verified": verified})
    return out


def attempt_out(attempt: dict) -> dict:
    out = camel(attempt, drop=("created_at",))
    out["findings"] = findings_out(attempt)
    out["statuses"] = attempt_statuses(attempt)
    out["pending"] = pending_of(attempt)
    return out
