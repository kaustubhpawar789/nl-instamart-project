import os
import re
from bs4 import BeautifulSoup

def get_file_path(filename):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'ui', filename)

def test_ui_010_index_html_structure():
    """Verify that the AI search layout has the Google-style updates."""
    html_path = get_file_path('index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # Check for new layout ID
    layout = soup.find('div', id='aisearchLayout')
    assert layout is not None, "aisearchLayout ID not found"

    # Check for branding header
    brand_header = layout.find('div', class_='aisearch-brand-header')
    assert brand_header is not None, "aisearch-brand-header class not found"

    # Check brand title h1
    brand_title = layout.find('h1', class_='aisearch-brand-title')
    assert brand_title is not None, "aisearch-brand-title h1 not found"

    # Check for the pill search bar container
    search_bar = layout.find('div', class_='aisearch-input-wrap')
    assert search_bar is not None, "aisearch-input-wrap not found"

    # Check the round submit button
    search_btn = layout.find('button', id='aisearchBtn')
    assert search_btn is not None, "aisearchBtn not found"

    # Check preset chips
    presets = layout.find_all('button', class_='aisearch-preset')
    assert len(presets) >= 4, f"Expected at least 4 preset chips, found {len(presets)}"

def test_ui_010_styles_css_updates():
    """Verify that the global UI polish CSS changes were applied."""
    css_path = get_file_path('styles.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    # AI Search tab panel overrides
    assert '#tab-aisearch' in css_content, "Missing #tab-aisearch custom panel styles"
    assert 'search-active' in css_content, "Missing .search-active transition styles"

    # Verify search bar is pill-shaped (border-radius: 28px)
    assert 'border-radius: 28px' in css_content, "Missing pill-shaped border-radius (28px) for search bar"

    # Verify submit button is circular
    assert 'border-radius: 50%' in css_content, "Missing circular border-radius (50%) for submit button"

    # Check global polish padding updates (increased to 14px 18px)
    assert 'padding: 14px 18px;' in css_content, "Missing increased padding (14px 18px) for tables"

    # Check for enhanced button hover lift
    assert 'transform: translateY(-1px);' in css_content, "Missing enhanced button hover transform"

    # Ensure broken variables are now defined
    assert '--surface-elevated' in css_content, "Missing --surface-elevated CSS variable definition"
    assert '--border-subtle' in css_content, "Missing --border-subtle CSS variable definition"

    # AI answer card has real padding
    assert 'padding: 20px 24px;' in css_content, "Missing generous padding for .aisearch-ai card"

if __name__ == '__main__':
    print("Running UI-010 Tests...")
    test_ui_010_index_html_structure()
    print("  [PASS] HTML structure")
    test_ui_010_styles_css_updates()
    print("  [PASS] CSS styles")
    print("\nAll UI-010 Polish tests passed successfully!")
