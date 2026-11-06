"""Launch the Streamlit frontend or the existing headless CLI."""
from pathlib import Path
import sys


def main():
    if '--cli' in sys.argv:
        from src.cli import main as cli_main
        return cli_main([arg for arg in sys.argv[1:] if arg != '--cli'])
    from streamlit.web import cli as streamlit_cli
    sys.argv = ['streamlit', 'run', str(Path(__file__).with_name('streamlit_app.py')), *sys.argv[1:]]
    return streamlit_cli.main()


if __name__ == '__main__':
    raise SystemExit(main())
