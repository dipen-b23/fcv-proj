"""Desktop entry point; imports Qt only for GUI use."""
import sys

def main():
    if '--cli' in sys.argv:
        from src.cli import main as cli_main
        args=[arg for arg in sys.argv[1:] if arg!='--cli']
        return cli_main(args)
    from src.gui import launch
    return launch()

if __name__=='__main__':
    raise SystemExit(main())
