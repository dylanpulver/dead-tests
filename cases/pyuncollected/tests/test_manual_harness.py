# Pillow's Tests/test_uploader.py shape: a module with NO collected test at
# all. These exist to FAIL on purpose so a developer can check the error-image
# uploader, and they are named check_* precisely so pytest skips them.
# Reporting them as forgotten tests inverts the author's intent.


def check_upload_equal():
    assert 1 == 2


def check_upload_similar():
    assert 1 == 2
