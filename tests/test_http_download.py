import unittest

from app.http_server import content_disposition_value


class HttpDownloadTests(unittest.TestCase):
    def test_content_disposition_supports_chinese_filename(self) -> None:
        value = content_disposition_value("胶质瘤的康复治疗.pptx")

        value.encode("latin-1")
        self.assertIn("filename=", value)
        self.assertIn("filename*=UTF-8''", value)
        self.assertIn("%E8%83%B6", value)


if __name__ == "__main__":
    unittest.main()
