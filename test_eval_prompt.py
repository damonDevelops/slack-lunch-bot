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
