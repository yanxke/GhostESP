import base64
import io
import unittest

from decode_capture_log import decode_capture


class DecodeCaptureTests(unittest.TestCase):
    def transfer(self, data):
        lines = [
            "Boot log\n", "SD:READ:BEGIN:/mnt/ghostesp/pcaps/test.pcap\n",
            f"SD:READ:SIZE:{len(data)}\n", "SD:READ:OFFSET:0\n",
            f"SD:READ:LENGTH:{len(data)}\n", "SD:READ:ENCODING:base64\n",
        ]
        for start in range(0, len(data), 360):
            lines.append("SD:READ:DATA:" + base64.b64encode(data[start:start + 360]).decode() + "\n")
        return lines + [f"SD:READ:END:bytes={len(data)}\n", "SD:OK\n"]

    def test_binary_round_trip_with_multiple_lines(self):
        data = bytes(range(256)) * 7 + b"\x00\xff"
        output = io.BytesIO()
        self.assertEqual(decode_capture(self.transfer(data), output), len(data))
        self.assertEqual(output.getvalue(), data)

    def test_missing_data_detected_by_size(self):
        lines = self.transfer(b"pcap")
        lines = [line for line in lines if not line.startswith("SD:READ:DATA:")]
        with self.assertRaises(ValueError):
            decode_capture(lines, io.BytesIO())

    def test_invalid_base64_rejected(self):
        lines = self.transfer(b"pcap")
        lines[6] = "SD:READ:DATA:!!!\n"
        with self.assertRaises(ValueError):
            decode_capture(lines, io.BytesIO())

    def test_truncated_or_failed_transfer_rejected(self):
        lines = self.transfer(b"pcap")
        for damaged in (lines[:-1], lines[:-2], lines[:-1] + ["SD:ERR:file_read_failed\n"]):
            with self.subTest(damaged=damaged), self.assertRaises(ValueError):
                decode_capture(damaged, io.BytesIO())

    def test_partial_offset_rejected(self):
        lines = self.transfer(b"pcap")
        lines[3] = "SD:READ:OFFSET:10\n"
        with self.assertRaises(ValueError):
            decode_capture(lines, io.BytesIO())


if __name__ == "__main__":
    unittest.main()
