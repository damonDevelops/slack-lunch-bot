import pytest
import yaml
from eval_prompt import load_cases, rating_to_score


def test_load_cases(tmp_path):
    yaml_file = tmp_path / "cases.yaml"
    yaml_file.write_text("- 'a slice of pizza'\n- 'bibimbap'\n")
    result = load_cases(str(yaml_file))
    assert result == ["a slice of pizza", "bibimbap"]


def test_load_cases_missing_file():
    with pytest.raises(FileNotFoundError):
        load_cases("nonexistent.yaml")


def test_rating_to_score_good():
    assert rating_to_score("good") == 1.0


def test_rating_to_score_could_be_better():
    assert rating_to_score("could_be_better") == 0.5


def test_rating_to_score_poor():
    assert rating_to_score("poor") == 0.0


def test_rating_to_score_error():
    assert rating_to_score("error") == 0.0


def test_rating_to_score_unknown():
    assert rating_to_score("anything_else") == 0.0


from unittest.mock import patch, MagicMock
from eval_prompt import judge_emoji, run_eval


def test_judge_emoji_returns_rating_and_reason():
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content[0].text = '{"rating": "good", "reason": "pizza is exact"}'
    mock_client.messages.create.return_value = mock_message

    result = judge_emoji(mock_client, "a slice of pizza", ":pizza:", [":pizza:", ":hamburger:"])

    assert result["rating"] == "good"
    assert result["reason"] == "pizza is exact"
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert ":pizza:" in call_kwargs["messages"][0]["content"]
    assert "a slice of pizza" in call_kwargs["messages"][0]["content"]


def test_run_eval_returns_average_score(capsys):
    cases = ["a slice of pizza", "bibimbap"]
    mock_client = MagicMock()

    parse_results = [
        {"emoji": ":pizza:", "status_text": "a slice of pizza", "verb": "Eating", "duration_minutes": None},
        {"emoji": ":rice:", "status_text": "bibimbap", "verb": "Eating", "duration_minutes": None},
    ]
    judge_results = [
        {"rating": "good", "reason": "pizza is exact"},
        {"rating": "could_be_better", "reason": ":bowl_with_spoon: would be better"},
    ]

    with patch("eval_prompt.parse_lunch", side_effect=parse_results), \
         patch("eval_prompt.judge_emoji", side_effect=judge_results):
        score = run_eval(cases, client=mock_client)

    assert score == pytest.approx(0.75)
    out = capsys.readouterr().out
    assert "0.75" in out
    assert "pizza is exact" in out
    assert ":bowl_with_spoon: would be better" in out


def test_run_eval_parse_error_counts_as_zero(capsys):
    cases = ["a slice of pizza"]
    mock_client = MagicMock()

    with patch("eval_prompt.parse_lunch", side_effect=ValueError("boom")):
        score = run_eval(cases, client=mock_client)

    assert score == pytest.approx(0.0)
    out = capsys.readouterr().out
    assert "error" in out.lower()


def test_run_eval_judge_error_counts_as_zero(capsys):
    cases = ["a slice of pizza"]
    mock_client = MagicMock()
    parse_result = {"emoji": ":pizza:", "status_text": "pizza", "verb": "Eating", "duration_minutes": None}

    with patch("eval_prompt.parse_lunch", return_value=parse_result), \
         patch("eval_prompt.judge_emoji", side_effect=ValueError("bad json")):
        score = run_eval(cases, client=mock_client)

    assert score == pytest.approx(0.0)
    out = capsys.readouterr().out
    assert "error" in out.lower()
