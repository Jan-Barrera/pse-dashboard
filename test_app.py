from unittest.mock import patch

import app


def test_render_table_uses_native_dataframe():
    with patch.object(app.st, "dataframe") as mock_dataframe:
        app.render_table(app.watchlist)

    mock_dataframe.assert_called_once()
    kwargs = mock_dataframe.call_args.kwargs
    assert kwargs.get("use_container_width") is True
    assert kwargs.get("hide_index") is True
