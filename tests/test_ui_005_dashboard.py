import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, "ui")
DATA_FILE = os.path.join(ROOT, "database", "ai_insights.json")
LIVE_DATA_FILE = os.path.join(ROOT, "database", "live_scraped_data.json")


class TestUI005Dashboard(unittest.TestCase):
    def test_index_html_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(UI_DIR, "index.html")))

    def test_styles_css_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(UI_DIR, "styles.css")))

    def test_app_js_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(UI_DIR, "app.js")))

    def test_index_html_has_tab_structure(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("tab-nav", html)
        self.assertIn("tab-panel", html)
        self.assertIn("tab-btn", html)

    def test_index_html_has_four_tabs(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        for tab in ["scraping", "insights", "matrix", "research"]:
            self.assertIn(f'tab-btn-{tab}', html, f"Missing tab: {tab}")
            self.assertIn(f'tab-{tab}', html, f"Missing panel: {tab}")

    def test_index_html_has_kpi_strip(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("kpiStrip", html)

    def test_index_html_has_virtual_table(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("vt-container", html)
        self.assertIn("vtRows", html)
        self.assertIn("vt-head-row", html)

    def test_index_html_has_chart_section(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("sentimentChart", html)
        self.assertIn("blockerChart", html)
        self.assertIn("chart.js", html.lower())

    def test_index_html_has_chart_builder(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("builderModal", html)
        self.assertIn("builderPreviewCanvas", html)

    def test_index_html_has_drill_down_matrix(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("matrixTable", html)
        self.assertIn("matrixBody", html)

    def test_index_html_has_survey_form(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("surveyModal", html)
        self.assertIn("sf-name", html)
        self.assertIn("sf-email", html)
        self.assertIn("sf-city", html)

    def test_index_html_has_kpi_drawer(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("kpiDrawer", html)
        self.assertIn("drawerOverlay", html)

    def test_index_html_has_research_buttons(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("btnCreateForm", html, "Missing Create Form button")
        self.assertIn("btnGoogleForm", html, "Missing Google Form link")
        self.assertIn("btnExportCSV", html, "Missing Export CSV button")

    def test_index_html_no_recommendations_section(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertNotIn("recommendationsSection", html)

    def test_index_html_no_phase1_in_title(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        title_section = html.split("</header>")[0] if "</header>" in html else html[:500]
        self.assertNotIn("Phase 1", title_section)

    def test_index_html_no_ops004_prefix(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertNotIn("OPS-004", html)

    def test_index_html_has_inter_font(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("Inter", html)

    def test_index_html_has_filter_selects(self):
        with open(os.path.join(UI_DIR, "index.html"), "r") as f:
            html = f.read()
        self.assertIn("filterSource", html)
        self.assertIn("filterIntent", html)
        self.assertIn("filterCategory", html)

    def test_json_data_valid(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_json_has_required_keys(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for key in ["themes", "insights", "sentiment", "categories"]:
            self.assertIn(key, data)

    def test_json_no_recommendations_key(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        self.assertNotIn("recommendations", data)

    def test_json_themes_have_evidence(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for theme in data["themes"]:
            self.assertIn("evidence", theme)
            self.assertGreater(len(theme["evidence"]), 0)
            self.assertIn("blockers", theme)
            self.assertIn("triggers", theme)

    def test_json_repetitive_cart_has_45_mentions(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        cart = [t for t in data["themes"] if t["name"] == "Repetitive Cart Experience"][0]
        self.assertEqual(cart["mentions"], 45)

    def test_json_repetitive_cart_has_exact_quote(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        cart = [t for t in data["themes"] if t["name"] == "Repetitive Cart Experience"][0]
        quotes = [e["quote"] for e in cart["evidence"]]
        self.assertIn(
            "I keep ordering the same vegetables every week. There are so many other items on the app I never see.",
            quotes
        )

    def test_json_sentiment_matches_screenshots(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        s = data["sentiment"]
        self.assertEqual(s["positive"]["count"], 34)
        self.assertEqual(s["positive"]["percentage"], 23)
        self.assertEqual(s["neutral"]["count"], 48)
        self.assertEqual(s["neutral"]["percentage"], 32)
        self.assertEqual(s["negative"]["count"], 66)
        self.assertEqual(s["negative"]["percentage"], 45)

    def test_json_research_data_has_scores(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        if "mock_research_data" in data:
            for entry in data["mock_research_data"]:
                self.assertIn("quality_score", entry)
                self.assertGreaterEqual(entry["quality_score"], 0)
                self.assertLessEqual(entry["quality_score"], 100)

    def test_json_insights_titles(self):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        titles = [i["title"] for i in data["insights"]]
        self.assertIn("Cart Loop Trap", titles)
        self.assertIn("Hidden Categories Problem", titles)
        self.assertIn("Discovery UX Failure", titles)

    def test_app_js_has_api_module(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("const API", js)
        self.assertIn("async get", js)
        self.assertIn("async post", js)
        self.assertIn("async del", js)

    def test_app_js_has_tab_manager(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("TabManager", js)
        self.assertIn("switchTo", js)

    def test_app_js_has_kpi_strip(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("KPIStrip", js)
        self.assertIn("/api/kpis", js)

    def test_app_js_has_live_data_module(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("const LiveData", js)
        self.assertIn("/api/records", js)
        self.assertIn("prevPage", js)
        self.assertIn("nextPage", js)

    def test_app_js_has_charts_module(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("const Charts", js)
        self.assertIn("sentimentChart", js)
        self.assertIn("blockerChart", js)
        self.assertIn("new Chart", js)

    def test_app_js_has_chart_builder(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("ChartBuilder", js)
        self.assertIn("/api/charts/configs", js)

    def test_app_js_has_drill_down_matrix(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("DrillDownMatrix", js)
        self.assertIn("TREE", js)
        self.assertIn("expandAll", js)
        self.assertIn("collapseAll", js)

    def test_app_js_has_survey_form(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("SurveyForm", js)
        self.assertIn("/api/survey/submit", js)

    def test_app_js_has_open_tracker(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("OpenTracker", js)
        self.assertIn("/api/survey/responses", js)

    def test_app_js_has_toggle_insight(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("toggleInsight", js)
        self.assertIn("classList.toggle", js)

    def test_app_js_has_scrape_functionality(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("/api/scrape", js)
        self.assertIn("scrape", js.lower())

    def test_app_js_has_tooltip(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("Tooltip", js)

    def test_app_js_has_init_function(self):
        with open(os.path.join(UI_DIR, "app.js"), "r") as f:
            js = f.read()
        self.assertIn("DOMContentLoaded", js)
        self.assertIn("async function init", js)

    def test_css_has_dark_theme(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("--bg-body", css)
        self.assertIn("--bg-surface", css)
        self.assertIn("--bg-card", css)

    def test_css_has_tab_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("tab-nav", css)
        self.assertIn("tab-btn", css)
        self.assertIn("tab-panel", css)

    def test_css_has_virtual_table_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("vt-container", css)
        self.assertIn("vt-cell", css)

    def test_css_has_kpi_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("kpi-chip", css)
        self.assertIn("kpi-drawer", css)

    def test_css_has_chart_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("chart-card", css)
        self.assertIn("chart-canvas-wrap", css)

    def test_css_has_modal_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("modal-overlay", css)
        self.assertIn("modal", css)

    def test_css_has_matrix_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("matrix-table", css)
        self.assertIn("priority-score", css)

    def test_css_has_inter_font(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("Inter", css)

    def test_css_has_badge_styles(self):
        with open(os.path.join(UI_DIR, "styles.css"), "r") as f:
            css = f.read()
        self.assertIn("badge", css)

    def test_live_data_file_exists(self):
        self.assertTrue(os.path.isfile(LIVE_DATA_FILE))

    def test_live_data_has_records(self):
        with open(LIVE_DATA_FILE, "r") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_live_data_record_fields(self):
        with open(LIVE_DATA_FILE, "r") as f:
            data = json.load(f)
        required = ["id", "source", "date", "text", "intent", "categories", "rating"]
        for record in data:
            for field in required:
                self.assertIn(field, record)


if __name__ == "__main__":
    unittest.main()
