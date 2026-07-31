"""Entry point for the frozen build. PyInstaller cannot use a package-relative
__main__, so this imports the package normally."""
from promptbox.app import main

if __name__ == "__main__":
    main()
