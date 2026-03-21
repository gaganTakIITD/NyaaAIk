import pandas as pd

from nyaya_dhwani.text_utils import clean_cols


def test_clean_cols_normalizes_whitespace_and_punctuation():
    df = pd.DataFrame([{"a b": 1, "Foo,Bar": 2}])
    out = clean_cols(df)
    assert list(out.columns) == ["a_b", "Foo_Bar"]
    assert out["a_b"].iloc[0] == 1
