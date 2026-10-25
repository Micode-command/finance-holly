from holly.budget import Budget


def test_budget_multiple_windows():
    b = Budget("t", [(2, 60), (3, 3600)])
    assert b.take(now=0) and b.take(now=1)
    assert not b.take(now=2)                 # 每分鐘 2 次用完
    assert b.take(now=61)                    # 下一分鐘可以
    assert not b.take(now=200)               # 每小時 3 次用完
    assert b.remaining(now=200) == 0
    assert b.take(now=3700)                  # 一小時後恢復


def test_budget_take_many_is_all_or_nothing():
    b = Budget("t", [(5, 60)])
    assert b.take(4, now=0)
    assert not b.take(2, now=1) and b.remaining(now=1) == 1


def test_finmind_requests_stop_at_budget(monkeypatch):
    import pytest
    from holly import budget, taiwan
    monkeypatch.setattr(budget, "finmind", Budget("FinMind", [(0, 3600)]))
    with pytest.raises(RuntimeError, match="額度保護"):
        taiwan._finmind("TaiwanStockPER", "2026-01-01")


def test_gemini_calls_stop_at_budget(monkeypatch):
    import pytest
    from holly import ai_advisor, budget
    monkeypatch.setattr(budget, "gemini", Budget("Gemini", [(0, 60)]))
    with pytest.raises(RuntimeError, match="用量保護"):
        ai_advisor.ask_gemini_json("hi", "key")
