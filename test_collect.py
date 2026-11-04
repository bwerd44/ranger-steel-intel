import datetime as dt
import unittest
import collect

NOW = dt.datetime(2026, 11, 4, 18, tzinfo=dt.timezone.utc)

class CollectorTests(unittest.TestCase):
    def test_no_evidence_is_explicit_not_fabricated(self):
        report = collect.build_briefing([], NOW)
        self.assertEqual(len(report['sections']), 6)
        self.assertTrue(all(s['paragraphs'][0]['kind'] == 'unavailable' for s in report['sections'][:5]))
        self.assertNotIn('$', str(report))

    def test_expired_and_future_evidence_excluded(self):
        sources = [{'id': 'old', 'evidence_date': '2025-01-01', 'reviewed_at': '2025-01-01', 'max_age_days': 14}, {'id': 'future', 'evidence_date': '2026-12-01', 'reviewed_at': '2026-11-04', 'max_age_days': 45}]
        active, _ = collect.refresh_evidence(sources, [], NOW, offline=True)
        self.assertEqual(active, [])

    def test_retained_evidence_keeps_original_date(self):
        source = {'id': 'test', 'evidence_date': '2026-11-01', 'reviewed_at': '2026-11-02', 'max_age_days': 14}
        active, _ = collect.refresh_evidence([source], [], NOW, offline=True)
        self.assertEqual(active[0]['evidence_date'], '2026-11-01')
        self.assertIn('not reverified', active[0]['access'])

    def test_syndicated_and_repeated_urls_removed(self):
        news = [{'title': 'Plate mill restarts - Publisher A', 'url': 'https://example.com/a?utm_source=x', 'date': '2026-11-03'}, {'title': 'Plate mill restarts - Publisher B', 'url': 'https://example.com/b', 'date': '2026-11-02'}, {'title': 'A different title', 'url': 'https://example.com/a', 'date': '2026-11-01'}]
        result = collect.dedupe(news)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'Domestic Mill News')
        self.assertEqual(collect.news_category('SSAB plate import tariffs'), 'Import News')
        self.assertEqual(collect.canonical('javascript:alert(1)'), '')

    def test_official_parser_rejects_missing_and_future_periods(self):
        self.assertIsNone(collect.parse_official(collect.SSAB, '<p>Plate prices might rise</p>', NOW))
        self.assertIsNone(collect.parse_official(collect.SSAB, '<h3>The market during Q4 2026</h3><p>The North American plate market was strong and prices increased.</p>', NOW))

    def test_unknown_direction_not_inferred(self):
        source = collect.parse_official(collect.SSAB, '<h3>The market during Q3 2026</h3><p>The North American plate market is uncertain.</p>', NOW)
        self.assertIsNone(source)

    def test_recognized_primary_source_has_dated_claims(self):
        raw = '<h3>The market during Q3 2026</h3><p>The North American plate market was strong during the third quarter and prices continued to increase. Inventory levels among North American distributors are assessed to be somewhat low.</p><p>Market prices in China recovered.</p>'
        source = collect.parse_official(collect.SSAB, raw, NOW)
        self.assertEqual(source['evidence_date'], '2026-09-30')
        self.assertIn('quarterly trend', source['observations']['pricing'])
        data = {'schema_version': 2, 'briefing': collect.build_briefing([source], NOW), 'articles': []}
        collect.validate(data)
        data['briefing']['sections'][0]['paragraphs'][0]['source_ids'] = ['missing']
        with self.assertRaises(AssertionError):
            collect.validate(data)

if __name__ == '__main__':
    unittest.main()
