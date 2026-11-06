"""Smoke-test the active frontend and the migrated entry point."""
from pathlib import Path
import sys
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_sample_scan():
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=30).run()
    assert not app.exception
    next(button for button in app.button if button.label == 'Try sample').click().run()
    assert not app.exception
    assert app.session_state['result'].output is not None


def test_main_launches_streamlit():
    import main
    with patch.object(sys, 'argv', ['main.py']), patch('streamlit.web.cli.main', return_value=0) as launch:
        assert main.main() == 0
        launch.assert_called_once()
        assert sys.argv[:2] == ['streamlit', 'run']
        assert Path(sys.argv[2]) == ROOT / 'streamlit_app.py'
