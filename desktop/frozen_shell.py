"""Entry point for the disposable frozen desktop shell."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from desktop.launcher import main
    main()
