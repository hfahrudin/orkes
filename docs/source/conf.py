import os
import sys
import datetime
from datetime import datetime

# This allows Sphinx to find 'orkes' in the directory above /docs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_copybutton',
    'sphinxcontrib.autodoc_pydantic',
    'sphinx.ext.autosummary'
]

# 3. Theme setup
html_theme = 'pydata_sphinx_theme'
project = 'orkes'  # This is the text in the header
version = "0.1.3"
html_title = f'orkes v{version} documentation' # Appears in the browser tab and header

# To add a logo image (relative to your html_static_path)
# Standard practice is to put logo.png in docs/source/_static/
html_logo = "../../assets/logo-sideway.png" 
templates_path = ['_templates']
# 4. Simplify options to avoid the 'split' error
html_theme_options = {
    "external_links": [
        {"name": "Release Notes", "url": "https://github.com/hfahrudin/orkes/releases"},
    ],
    "navbar_align": "left",
    "github_url": "https://github.com/hfahrudin/orkes",
    "footer_start": ["orkes_footer"],
    "secondary_sidebar_items": {
        "**": ["page-toc"],
        "index": ["page-toc"],
    }

}

html_favicon = "../../assets/orkes_icon.png"
# (Keep your other existing configurations below)
project = "orkes"
# We have our custom "pandas_footer.html" template, using copyright for the current year
copyright = f'{datetime.now().year}, orkes '


autodoc_pydantic_model_show_json = False
autodoc_pydantic_settings_show_json = False

autodoc_default_options = {
    'imported-members': False, 
}

autodoc_typehints = "description"
