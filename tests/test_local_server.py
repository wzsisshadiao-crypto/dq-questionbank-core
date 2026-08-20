import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from dq_questionbank_local.server import create_server


def sample_payload():
    return {
        "schema_version": "1.0",
        "id": "synthetic-set",
        "title": "Synthetic set",
        "language": "en",
        "questions": [
            {
                "schema_version": "1.0",
                "id": "q-1",
                "type": "short_answer",
                "language": "en",
                "stem": "Example",
            }
        ],
    }


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.server = create_server(Path(self.temporary_directory.name), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temporary_directory.cleanup()

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        body = None if payload is None else json.dumps(payload)
        headers = (
            {}
            if body is None
            else {"Content-Type": "application/json", "Content-Length": str(len(body.encode()))}
        )
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = (
            json.loads(response.read())
            if response.getheader("Content-Type", "").startswith("application/json")
            else None
        )
        connection.close()
        return response.status, data

    def test_import_list_and_load(self):
        status, body = self.request("POST", "/api/import", sample_payload())
        self.assertEqual(201, status)
        self.assertEqual("synthetic-set", body["id"])
        status, body = self.request("GET", "/api/sets")
        self.assertEqual(200, status)
        self.assertEqual(["synthetic-set"], [item["id"] for item in body["sets"]])
        status, body = self.request("GET", "/api/sets/synthetic-set")
        self.assertEqual(200, status)
        self.assertEqual(sample_payload(), body)

    def test_serves_local_visual_workspace(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/")
        response = connection.getresponse()
        page = response.read().decode("utf-8")
        connection.close()
        self.assertEqual(200, response.status)
        self.assertIn("DQ QuestionBank Local", page)
        for required_control in (
            'id="question-bank-nav"',
            'id="paper-nav"',
            'id="import-nav"',
            'id="editor-nav"',
            'id="data-nav"',
            'id="quality-nav"',
            'id="review-nav"',
            'id="export-nav"',
            'id="question-search"',
            'id="question-year"',
            'id="question-search-scope"',
            'id="collection-search"',
            'id="subject-filter"',
            'id="type-filter"',
            'id="question-results"',
            'id="question-list"',
            'id="editor-question-select"',
            'id="editor-field-nav"',
            'class="question-choice-answer"',
            'class="question-grade"',
            'class="question-category"',
            'class="question-difficulty"',
            'class="question-tags"',
            'add-choice',
            'id="paper-view"',
            'id="import-view"',
            'id="data-view"',
            'id="quality-view"',
            'id="review-view"',
            'id="export-view"',
        ):
            self.assertIn(required_control, page)

        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", "/app.js")
        response = connection.getresponse()
        script = response.read().decode("utf-8")
        connection.close()
        self.assertEqual(200, response.status)
        self.assertIn('document.createElement("table")', script)
        self.assertIn("globalThis.katex.render", script)
        self.assertIn("function renderTextWithMath(container, value)", script)
        self.assertIn("renderTextWithMath(cell, value)", script)
        self.assertIn("renderTextWithMath(value, answer)", script)
        self.assertIn('throwOnError: true', script)
        self.assertIn("function renderQuestionResults()", script)
        self.assertIn("function makeQuestionCard(question, index)", script)
        self.assertIn("function updateEditorSelection()", script)
        self.assertIn("function renderPaperCenter()", script)
        self.assertIn("function renderImportCenter()", script)
        self.assertIn("function renderBankData()", script)
        self.assertIn("function runQualityChecks()", script)
        self.assertIn("function renderReviewCenter()", script)
        self.assertIn("function renderExportCenter()", script)
        self.assertIn("function paperPayload()", script)
        self.assertIn("function refreshChoiceAnswerControls", script)
        self.assertIn("function editorValidationIssues", script)
        self.assertIn("function parseEditableContent", script)
        self.assertIn("function setSaveInFlight", script)
        self.assertIn("beforeunload", script)
        self.assertIn("question.choices = rows.map", script)
        self.assertIn('searchScope.value === "all"', script)
        self.assertIn("question.source?.year ?? question.metadata?.year", script)
        self.assertIn("Expand answer and solution", script)
        self.assertNotIn("innerHTML", script)

        static_checks = (
            ("/vendor/katex/katex.min.js", "javascript", b"KaTeX"),
            ("/vendor/katex/katex.min.css", "text/css", b".katex"),
            ("/vendor/katex/fonts/KaTeX_Main-Regular.woff2", "font/woff2", b"wOF2"),
        )
        for path, content_type, marker in static_checks:
            with self.subTest(path=path):
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
                connection.request("GET", path)
                response = connection.getresponse()
                content = response.read()
                connection.close()
                self.assertEqual(200, response.status)
                self.assertIn(content_type, response.getheader("Content-Type"))
                self.assertTrue(content.startswith(marker) or marker in content)

    def test_loads_bundled_database_case_into_workspace(self):
        status, info = self.request("GET", "/api/case")
        self.assertEqual(200, status)
        self.assertEqual(10, info["question_count"])
        status, payload = self.request("POST", "/api/case/load")
        self.assertEqual(200, status)
        self.assertEqual("synthetic-database-case", payload["id"])
        self.assertEqual("en", payload["language"])
        self.assertTrue(all(item["language"] == "en" for item in payload["questions"]))
        self.assertEqual(2023, payload["questions"][0]["source"]["year"])
        group_question = next(item for item in payload["questions"] if item["id"] == "DEMO_MATH_004")
        self.assertIn("table", [block["type"] for block in group_question["stem"]["blocks"]])
        status, listing = self.request("GET", "/api/sets")
        self.assertEqual(["synthetic-database-case"], [item["id"] for item in listing["sets"]])

    def test_put_fails_closed_when_url_id_does_not_match(self):
        status, body = self.request("PUT", "/api/sets/other-set", sample_payload())
        self.assertEqual(400, status)
        self.assertIn("does not match", body["error"])

    def test_non_loopback_bind_is_rejected(self):
        with self.assertRaises(ValueError):
            create_server(Path(self.temporary_directory.name), host="0.0.0.0", port=0)

    def test_cross_origin_mutation_is_rejected(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request(
            "POST",
            "/api/case/load",
            headers={"Origin": "http://example.com", "Sec-Fetch-Site": "cross-site"},
        )
        response = connection.getresponse()
        response.read()
        connection.close()
        self.assertEqual(403, response.status)
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))

    def test_preflight_does_not_grant_cross_origin_access(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("OPTIONS", "/api/import", headers={"Origin": "http://example.com"})
        response = connection.getresponse()
        response.read()
        connection.close()
        self.assertEqual(204, response.status)
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
        self.assertIn("default-src 'self'", response.getheader("Content-Security-Policy"))
