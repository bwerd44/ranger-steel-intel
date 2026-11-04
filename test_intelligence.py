import copy
import datetime as dt
import unittest
from unittest.mock import patch
import intelligence as intel

DAY=dt.date(2026,11,4)
NOW=dt.datetime(2026,11,4,18,tzinfo=dt.timezone.utc)
SOURCE={'url':'https://example.com/dated-plate-report','publisher':'Test primary source'}
def obs(metric='pricing',condition='Rising',date='2026-10-31',scope='discrete_plate'):
    return {'metric':metric,'condition':condition,'evidence_date':date,'scope':scope,'verified':True,'basis':'Fixture evidence','source':SOURCE}

class PulseTests(unittest.TestCase):
    def test_pressure_colors_and_arrows_follow_conditions(self):
        for metric,(_,conditions) in intel.METRICS.items():
            self.assertEqual([intel.pressure(metric,c)[0] for c in conditions],['red','orange','green'])
        self.assertEqual(intel.pressure('pricing','Unknown'),('gray','—'))

    def test_stale_future_and_other_product_evidence_cannot_set_pulse(self):
        data=[obs(date='2026-01-01'),obs(date='2026-12-01'),obs(scope='all_steel')]
        self.assertTrue(all(r['condition']=='Insufficient Data' for r in intel.derive_readings(data,DAY)))

    def test_low_inventory_and_strong_demand_are_not_trends(self):
        brief={'briefing':{'sources':[{'id':'ssab-market','evidence_date':'2026-09-30','url':'https://example.com','observations':{'domestic':'Inventories somewhat low','demand':'Market was strong'}}]}}
        self.assertEqual(intel.observed_from_briefing(brief),[])

    def test_conflicting_same_date_observations_are_mixed(self):
        reading=intel.derive_readings([obs(),obs(condition='Falling')],DAY)[0]
        self.assertEqual((reading['condition'],reading['color']),('Mixed','orange'))

    def test_weekly_baseline_requires_real_saved_previous_week(self):
        self.assertIsNone(intel.baseline({'snapshots':[]},DAY))
        history={'snapshots':[{'as_of':'2026-10-28','generated_at':'a'},{'as_of':'2026-10-30','generated_at':'b'}]}
        self.assertEqual(intel.baseline(history,DAY)['as_of'],'2026-10-28')
        self.assertIsNone(intel.baseline({'snapshots':[{'as_of':'2026-10-01','generated_at':'a'}]},DAY))

    def test_coverage_loss_is_not_a_market_change(self):
        previous={'as_of':'2026-10-28','readings':intel.derive_readings([obs(date='2026-10-27')],dt.date(2026,10,28)),'mills':[]}
        current={'as_of':'2026-11-04','readings':intel.derive_readings([],DAY),'mills':[]}
        result=intel.weekly_change(current,previous)
        self.assertEqual(result['changes'][0]['type'],'coverage_change')
        self.assertIn('No material verified change',result['summary'])

    def test_append_only_and_same_day_idempotence(self):
        empty={'schema_version':1,'snapshots':[]}
        with patch('intelligence.mill_tracker',return_value=[]):
            output,first=intel.build({}, {'observations':[obs()]},{}, {'editions':[]},empty,NOW,True)
            before=copy.deepcopy(first)
            _,same=intel.build({}, {'observations':[obs()]},{}, {'editions':[]},first,NOW+dt.timedelta(hours=1),True)
            self.assertEqual(same,before)
            _,later=intel.build({}, {'observations':[obs(condition='Falling')]},{}, {'editions':[]},first,NOW+dt.timedelta(days=7),True)
            self.assertEqual(later['snapshots'][0],before['snapshots'][0])
            self.assertEqual(len(later['snapshots']),2)
            later['snapshots'][0]['readings'][0]['condition']='Stable'
            with self.assertRaises(AssertionError):intel.validate_history(later)

    def test_accuracy_rejects_incomplete_coil_and_noncomparable_results(self):
        forecasts={'editions':[{'id':'2026-09','as_of':'2026-09-15','quarters':[{'id':'2026-Q4','year':2026,'quarter':4,'label':'Q4 2026','price_direction':'Firming'}]}]}
        self.assertEqual(intel.accuracy(forecasts,[],DAY)['results'],[])
        actual={'quarter_id':'2026-Q4','direction':'Rising','scope':'coil','basis':'quarter_over_quarter','verified':True,'reviewed_at':'2027-01-15','source':SOURCE,'evidence_date':'2027-01-15'}
        self.assertEqual(intel.accuracy(forecasts,[actual],dt.date(2027,2,1))['results'],[])
        actual['scope']='discrete_plate';actual['basis']='within_quarter'
        self.assertEqual(intel.accuracy(forecasts,[actual],dt.date(2027,2,1))['results'],[])
        actual['basis']='quarter_over_quarter'
        self.assertTrue(intel.accuracy(forecasts,[actual],dt.date(2027,2,1))['results'][0]['agreement'])
        forecasts['editions'][0]['as_of']='2026-11-04'
        self.assertEqual(intel.accuracy(forecasts,[actual],dt.date(2027,2,1))['results'],[])
        actual.update(basis='remaining_period_vs_issue',period_start='2026-11-04',period_end='2026-12-31')
        self.assertTrue(intel.accuracy(forecasts,[actual],dt.date(2027,2,1))['results'][0]['agreement'])

if __name__=='__main__':unittest.main()
