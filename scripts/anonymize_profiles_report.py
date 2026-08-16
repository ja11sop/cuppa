"""US spelling compatibility entry point — prefer ``scripts.anonymise_profiles_report``."""

from scripts.anonymise_profiles_report import main


if __name__ == '__main__':
    import sys

    sys.exit( main() )
