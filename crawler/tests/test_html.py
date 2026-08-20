from __future__ import annotations

import unittest

from rel_crawler import canonicalize_url, extract_links, extract_page_metadata


class LinkExtractionTests(unittest.TestCase):
    def test_extracts_rendered_links_in_dom_order(self) -> None:
        links = extract_links(
            """
            <a href="/release/one#reviews" rel="nofollow"> Album <b>One</b> </a>
            <a href="https://EXAMPLE.com:443/release/two" target="_blank">Two</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="#local">Same page</a>
            """,
            "https://example.com/new-music/",
        )

        self.assertEqual(
            [link.url for link in links],
            [
                "https://example.com/release/one",
                "https://example.com/release/two",
            ],
        )
        self.assertEqual(links[0].text, "Album One")
        self.assertEqual(links[0].rel, ("nofollow",))
        self.assertEqual(links[1].target, "_blank")

    def test_canonicalize_preserves_query_order_and_removes_fragment(self) -> None:
        self.assertEqual(
            canonicalize_url("HTTP://Example.COM:80/path?b=2&a=1#top"),
            "http://example.com/path?b=2&a=1",
        )

    def test_canonicalize_converts_iris_to_ascii_uris(self) -> None:
        self.assertEqual(
            canonicalize_url(
                "https://müsic.example/release/友達がいました/?q=café au lait"
            ),
            "https://xn--msic-0ra.example/release/"
            "%E5%8F%8B%E9%81%94%E3%81%8C%E3%81%84%E3%81%BE%E3%81%97%E3%81%9F/"
            "?q=caf%C3%A9%20au%20lait",
        )

    def test_canonicalize_normalizes_existing_percent_escapes(self) -> None:
        self.assertEqual(
            canonicalize_url("https://example.com/a%2fb/%e5%8f%8b?x=100%25"),
            "https://example.com/a%2Fb/%E5%8F%8B?x=100%25",
        )

    def test_canonicalize_does_not_change_unicode_normalization(self) -> None:
        composed = canonicalize_url(
            "https://example.com/caf\N{LATIN SMALL LETTER E WITH ACUTE}"
        )
        decomposed = canonicalize_url(
            "https://example.com/cafe\N{COMBINING ACUTE ACCENT}"
        )

        self.assertEqual(composed, "https://example.com/caf%C3%A9")
        self.assertEqual(decomposed, "https://example.com/cafe%CC%81")
        self.assertNotEqual(composed, decomposed)

    def test_canonicalize_encodes_an_ipv6_scope_identifier(self) -> None:
        self.assertEqual(
            canonicalize_url("http://[FE80::1%en0]:80/path"),
            "http://[fe80::1%25en0]/path",
        )

    def test_extracted_unicode_link_keeps_original_and_uses_ascii_uri(self) -> None:
        [link] = extract_links(
            '<a href="/posts/hello-world/友達がいました/">Post</a>',
            "https://example.com/feed/",
        )

        self.assertEqual(
            link.url,
            "https://example.com/posts/hello-world/"
            "%E5%8F%8B%E9%81%94%E3%81%8C%E3%81%84%E3%81%BE%E3%81%97%E3%81%9F/",
        )
        self.assertEqual(
            link.original_url,
            "https://example.com/posts/hello-world/友達がいました/",
        )

    def test_rejects_non_http_url(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_url("file:///tmp/page.html")

    def test_rejects_url_credentials(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_url("https://user:secret@example.com/page")

    def test_extracts_rendered_page_metadata(self) -> None:
        metadata = extract_page_metadata(
            """
            <html><head>
              <title> Post &amp; Comments </title>
              <link rel="alternate canonical" href="/posts/example/">
              <meta name="description" content="A post">
              <meta property="og:type" content="article">
              <meta property="datePublished" content="2024-11-01">
              <meta property="article:published_time" content="2025-02-03T04:05:06Z">
              <time itemprop="datePublished" datetime="2025-02-03">Released</time>
              <script type="application/ld+json">
                {
                  "@type": "Article",
                  "datePublished": "2025-02-03T04:05:06+00:00",
                  "dateModified": "2025-02-04T07:08:09Z"
                }
              </script>
              <meta charset="utf-8">
            </head></html>
            """,
            "https://example.com/posts/example/?ref=feed",
        )

        self.assertEqual(metadata["title"], "Post & Comments")
        self.assertEqual(
            metadata["canonical_url"],
            "https://example.com/posts/example/",
        )
        self.assertEqual(
            metadata["meta"],
            [
                {"name": "description", "content": "A post"},
                {"property": "og:type", "content": "article"},
                {"property": "datePublished", "content": "2024-11-01"},
                {
                    "property": "article:published_time",
                    "content": "2025-02-03T04:05:06Z",
                },
                {"charset": "utf-8"},
            ],
        )
        self.assertEqual(
            metadata["content_timestamps"],
            {
                "published": [
                    {
                        "value": "2024-11-01",
                        "source": "meta",
                        "field": "datePublished",
                        "attribute": "property",
                    },
                    {
                        "value": "2025-02-03T04:05:06Z",
                        "source": "meta",
                        "field": "article:published_time",
                        "attribute": "property",
                    },
                    {
                        "value": "2025-02-03",
                        "source": "element",
                        "field": "datePublished",
                        "element": "time",
                    },
                    {
                        "value": "2025-02-03T04:05:06+00:00",
                        "source": "json-ld",
                        "field": "datePublished",
                        "script_index": 0,
                    },
                ],
                "modified": [
                    {
                        "value": "2025-02-04T07:08:09Z",
                        "source": "json-ld",
                        "field": "dateModified",
                        "script_index": 0,
                    }
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
