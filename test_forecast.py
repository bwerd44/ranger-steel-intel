import copy
import datetime as dt
import unittest
from unittest.mock import patch
import forecast

NOW = dt.datetime(2026,11,4,18,tzinfo=dt.timezone.utc)
EMPTY = {'schema_version':1,'latest_id':None,'editions':[]}
SOURCES = [{'id':'ssab-market','publisher':'SSAB','evidence_date':'2026-09-30','max_age_days':105,'observations':{'pricing':'North American plate prices increased in Q3.','domestic':'Inventories somewhat low.'},'url':'https://www.ssab.com/'}]

class ForecastTests(unittest.TestCase):
    def test_horizon_rolls_at_quarter_and_year_boundaries(self):
        self.assertEqual(forecast.horizon(NOW.date()), [(2026,4),(2027,1),(2027,2),(2027,3),(2027,4)])
        self.assertEqual(len(forecast.horizon(dt.date(2027,1,1))), 8)
        self.assertEqual(forecast.horizon(dt.date(2027,4,1))[0], (2027,2))
        self.assertEqual(forecast.horizon(dt.date(2027,12,31))[-1], (2028,4))

    def test_monthly_idempotence_and_immutable_revision(self):
        with patch('forecast.gather', return_value=(SOURCES,[])):
            first, changed = forecast.update(EMPTY, {}, {}, NOW)
            before = copy.deepcopy(first)
            same, changed_again = forecast.update(first, {}, {}, NOW+dt.timedelta(days=2))
            self.assertTrue(changed)
            self.assertFalse(changed_again)
            self.assertEqual(same,before)
            revised, _ = forecast.update(first, {}, {}, NOW, 'New reviewed inputs')
            self.assertEqual(revised['editions'][0],before['editions'][0])
            self.assertEqual(revised['latest_id'],'2026-11-r2')
            self.assertEqual(len(revised['editions']),2)

    def test_next_month_appends_and_preserves_old_horizon(self):
        with patch('forecast.gather',return_value=(SOURCES,[])):
            first,_=forecast.update(EMPTY,{}, {}, NOW)
            later,_=forecast.update(first,{}, {},dt.datetime(2027,1,1,18,tzinfo=dt.timezone.utc))
            self.assertEqual(later['editions'][0],first['editions'][0])
            self.assertEqual(len(later['editions'][1]['quarters']),8)

    def test_tampered_archive_is_rejected(self):
        e=forecast.make_edition(SOURCES,[],NOW,'2026-11')
        history={'schema_version':1,'latest_id':e['id'],'editions':[e]}
        history['editions'][0]['quarters'][0]['analysis']='silently changed'
        with self.assertRaises(AssertionError):forecast.validate(history)

    def test_missing_or_expired_plate_input_does_not_invent_direction(self):
        self.assertFalse(forecast.fresh(SOURCES[0],dt.date(2027,5,1)))
        edition=forecast.make_edition([],[],NOW,'2026-11')
        self.assertTrue(all(q['price_direction']=='Insufficient evidence' for q in edition['quarters']))
        self.assertTrue(all(s['chart_value'] is None for q in edition['quarters'] for s in q['scenarios']))

    def test_bull_base_bear_are_ordered_and_not_dollar_targets(self):
        e=forecast.make_edition(SOURCES,[],NOW,'2026-11')
        for q in e['quarters']:
            values=[s['chart_value'] for s in q['scenarios']]
            self.assertGreaterEqual(values[0],values[1]);self.assertGreaterEqual(values[1],values[2])
            self.assertNotIn('$',q['analysis'])
            self.assertEqual(len(q['drivers']),7)
        self.assertEqual(e['grades'],['A36','A572 Grade 50','A516 Grade 70'])

    def test_macro_parser_requires_date_and_rejects_future(self):
        self.assertIsNone(forecast.parse_macro(forecast.FED,'Manufacturing output rose 0.3 percent in September',NOW))
        self.assertIsNone(forecast.parse_macro(forecast.FED,'Release Date: December 16, 2026 Manufacturing output rose 0.3 percent in November',NOW))
        result=forecast.parse_macro(forecast.FED,'Release Date: October 16, 2026 Manufacturing output fell 0.3 percent in September',NOW)
        self.assertEqual(result['manufacturing_change'],-.3)
        self.assertIn('/20261016/',result['url'])

if __name__=='__main__':unittest.main()
