"""Tests for content extraction."""

from spectral.research.extractor import CodeBlockParser, ContentExtractor


def test_extract_title():
    """Test title extraction from HTML."""
    html = "<html><head><title>Test Page</title></head><body></body></html>"
    extractor = ContentExtractor()

    title = extractor.extract_title(html)
    assert title == "Test Page"


def test_extract_headings():
    """Test heading extraction from HTML."""
    html = """
    <html><body>
        <h1>Main Heading</h1>
        <h2>Sub Heading</h2>
        <h3>Sub Sub Heading</h3>
        <h4>Not Extracted</h4>
    </body></html>
    """
    extractor = ContentExtractor()

    headings = extractor.extract_headings(html)
    assert len(headings) == 3
    assert "Main Heading" in headings
    assert "Sub Heading" in headings
    assert "Sub Sub Heading" in headings
    assert "Not Extracted" not in headings


def test_extract_code_blocks_html():
    """Test code block extraction from HTML."""
    html = """
    <html><body>
        <pre><code>print("Hello, World!")</code></pre>
        <code>inline_code()</code>
    </body></html>
    """
    extractor = ContentExtractor()

    code_blocks = extractor.extract_code_blocks(html)
    assert len(code_blocks) >= 1
    assert 'print("Hello, World!")' in code_blocks[0]


def test_extract_main_content():
    """Test main content extraction."""
    html = """
    <html><body>
        <nav>Navigation</nav>
        <main>
            <p>This is the main content of the page.</p>
            <p>It should be extracted.</p>
        </main>
        <footer>Footer</footer>
    </body></html>
    """
    extractor = ContentExtractor()

    text = extractor.extract_main_content(html)
    assert "main content" in text.lower()
    assert "navigation" not in text.lower() or "footer" not in text.lower()


def test_parse_markdown_code_blocks():
    """Test Markdown code block parsing."""
    text = """
    Here is some Python code:

    ```python
    def hello():
        print("Hello")
    ```

    And some JavaScript:

    ```javascript
    console.log("Hello");
    ```
    """

    blocks = CodeBlockParser.parse_markdown_code_blocks(text)
    assert len(blocks) == 2
    assert blocks[0]["language"] == "python"
    assert "def hello" in blocks[0]["code"]
    assert blocks[1]["language"] == "javascript"
    assert "console.log" in blocks[1]["code"]


def test_extract_meta_description():
    """Test meta description extraction."""
    html = """
    <html>
        <head>
            <meta name="description" content="This is a test page description">
        </head>
        <body></body>
    </html>
    """
    extractor = ContentExtractor()

    description = extractor.extract_meta_description(html)
    assert description == "This is a test page description"
