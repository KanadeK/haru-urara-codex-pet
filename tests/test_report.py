from haru_urara_pet.report import Report


def test_report_merge_and_counts() -> None:
    first = Report("first", facts={"one": 1})
    first.add("warning", "contrast", "subtle")
    second = Report("second", facts={"two": 2})
    second.add("error", "broken", "bad", "asset", "replace it")
    first.merge(second, "child")
    payload = first.to_dict()
    assert payload["ok"] is False
    assert payload["counts"] == {"error": 1, "warning": 1, "info": 0}
    assert payload["facts"] == {"one": 1, "two": 2}
    assert payload["issues"][1]["code"] == "child.broken"
    assert payload["issues"][1]["repair"] == "replace it"
