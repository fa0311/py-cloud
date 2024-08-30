import requests

host = "http://localhost:8000"


class TestUpload:
    def test_upload(self):
        res = requests.post(
            f"{host}/api/upload/test_upload.png",
            files={
                "file": open("image.png", "rb"),
            },
        )
        assert res.status_code == 200

    def test_upload_moons(self):
        res = requests.post(
            f"{host}/api/upload/test_upload.mp4",
            files={
                "file": open(
                    "Voice Genius - AI x ゆっくり解説 [g0Ookp-8yUI].mp4", "rb"
                ),
            },
        )
        assert res.status_code == 200
