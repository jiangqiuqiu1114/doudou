import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('collector', Path(__file__).resolve().parents[1] / 'scripts/collect.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectionTests(unittest.TestCase):
    def test_detail_links_and_missing_fields(self):
        html = '''<dl class="list"><p class="title"><a href="/bj/chuzu/3_123_1.htm">房源</a></p></dl>
        <dl class="list"><p class="title"><a href="https://other.example/bj/chuzu/3_123_1.htm">外部</a></p></dl>
        <dl class="list"><p class="title"><a href="/house-a012/">列表</a></p></dl>'''
        rows = collector.parse(html, collector.SOURCES[0], 'test-time')
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['price'])
        self.assertEqual(rows[0]['estate'], '未注明小区')

    def test_failure_keeps_old_timestamp_and_marks_stale(self):
        rows = collector.combine([dict(url='https://example.com/a', fetchedAt='old')], [([], {})])
        self.assertEqual(rows[0]['fetchedAt'], 'old')
        self.assertTrue(rows[0]['stale'])

    def test_fresh_record_replaces_old_record(self):
        rows = collector.combine([dict(url='a', price=100)], [([dict(url='a', price=200, stale=False)], {})])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['price'], 200)
        self.assertFalse(rows[0]['stale'])


if __name__ == '__main__':
    unittest.main()
