from vaulty import main


def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert "Hello from vaulty!" in captured.out
