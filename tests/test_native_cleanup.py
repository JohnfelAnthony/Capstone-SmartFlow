"""Native-only public contracts, retained evidence and unchanged RL encoding."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('SMARTFLOW_SECRET_KEY', 'native-cleanup-tests-only')
from fastapi.testclient import TestClient
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from simulation.model_contract import native_contract
from simulation import dql_training, ppo_training
from simulation.rl_reward import REWARD_VERSION
from simulation.rl_state import APPROACH_ORDER, MAX_ACTIVE_VEHICLES, MAX_QUEUE_COUNT, OBSERVATION_VERSION, extract_rl_snapshot
from simulation.traffic_engine import TrafficEngine
from simulation.timeline_engine import TimelinePlaybackEngine
from services import backup_bundle


class NativeCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.directory.cleanup)
        self.db_patch = patch.object(config, 'DB_PATH', str(Path(self.directory.name) / 'test.db'))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.password_patch = patch.object(config, 'BOOTSTRAP_ADMIN_PASSWORD', 'CleanupAdmin42!')
        self.password_patch.start()
        self.addCleanup(self.password_patch.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))
        self.addCleanup(lambda: simulation_runtime.reset(force=True))
        self.assertEqual(self.client.post('/api/auth/login', json={'username':'admin','password':'CleanupAdmin42!'}).status_code, 200)

    def test_canonical_seed_restart_and_strict_public_fields(self):
        scenarios = self.client.get('/api/scenarios').json()['scenarios']
        # One ready-made scenario per study site; the old test networks get none.
        self.assertEqual(sorted(scenario['network_id'] for scenario in scenarios), ['tagum_site_a', 'tagum_site_b'])
        for scenario in scenarios:
            self.assertIsNone(scenario['migration_error'])
            self.assertIn('controlled_junction', scenario['engine_config'])
            self.assertNotIn('traffic_density', scenario)
            self.assertNotIn('intersection_id', scenario)
        database.init_db(); database.seed_data()
        self.assertEqual(len(database.get_scenarios()), 2)
        for field, value in (('intersection_id','tagum_1'),('traffic_density','high'),('road_constraint','None'),('lane_closure_config',{})):
            rejected = self.client.post('/api/scenarios', json={'name':'Legacy public request',field:value})
            self.assertEqual(rejected.status_code, 422, rejected.text)
        rejected = self.client.post('/api/scenarios', json={'name':'Legacy nested preset','engine_config':{'road_constraint':'None'}})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(self.client.post('/api/simulation/configure', json={'traffic_density':'low'}).status_code, 422)
        self.assertEqual(self.client.get('/api/visual-network', params={'network_id':'tagum_1'}).status_code, 422)
        self.assertEqual(self.client.get('/api/visual-network', params={'intersection_id':'tagum_network'}).status_code, 422)

    def test_blocked_legacy_row_is_visible_and_cannot_run(self):
        with database.get_db() as conn:
            cursor = conn.execute("INSERT INTO scenarios(name,intersection_id,lane_closure_config) VALUES (?,?,?)",
                                  ('Unmapped historical closure','tagum_1','{"enabled":true}'))
            scenario_id = cursor.lastrowid
        database.init_db()
        result = self.client.get(f'/api/scenarios/{scenario_id}')
        self.assertEqual(result.status_code, 200)
        self.assertIn('mapping', result.json()['migration_error'])
        self.assertEqual(self.client.get(f'/api/scenarios/{scenario_id}/native-config').status_code, 422)
        self.assertEqual(self.client.post('/api/simulation/start', json={'scenario_id':scenario_id}).status_code, 409)
        self.assertIsNone(database.get_scenario_by_id(scenario_id)['network_id'])
        with database.get_db() as conn:
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(scenarios)')}
        self.assertIn('lane_closure_config', columns)

    def test_explicit_audit_metadata_and_registered_recording_path(self):
        database.log_audit_event(action='cleanup_context',ip_address='127.0.0.1',user_agent='test')
        row = database.get_audit_logs(action='cleanup_context')[0]
        self.assertEqual((row['ip_address'],row['user_agent']),('127.0.0.1','test'))
        with self.assertRaisesRegex(ValueError, 'registered'):
            TimelinePlaybackEngine(1)

    def test_native_ordinary_traffic_observation_positions(self):
        engine = TrafficEngine()
        self.assertFalse(hasattr(engine,'connection'))
        lanes = engine.current_approach_lanes()
        approach, lane_ids = next((a, ids) for a,ids in lanes.items() if ids)
        lane = lane_ids[0]
        runtime = engine.build_rl_runtime_state()
        runtime.update(vehicles=[{'lane_id':lane,'wait_time':30,'lane_position':engine.network.lanes[lane].length/2},
                                 {'lane_id':lane,'wait_time':90}],
                       pedestrians=[{'lane_id':engine.controlled_junction,'stopped':True},
                                    {'lane_id':'other-junction','stopped':True}],
                       metrics={'queue_by_approach':{approach:3}})
        with patch.object(engine,'build_rl_runtime_state',return_value=runtime):
            snapshot = extract_rl_snapshot(engine)
        index = APPROACH_ORDER.index(approach)
        self.assertEqual(len(snapshot.observation),20)
        self.assertEqual(snapshot.observation[7+index],.042857)
        self.assertEqual(snapshot.observation[11+index],.5)
        self.assertEqual(snapshot.observation[15+index],.028571)
        self.assertEqual(snapshot.observation[19],.05)
        self.assertEqual(native_contract()['engine'],'native-7')
        self.assertEqual(native_contract()['observation'],'native-local-20-v4')
        self.assertEqual(native_contract()['actions'],'phase-service-5-v2')

    def test_observation_scales_cover_tagum_queues(self):
        report = json.loads((Path(__file__).resolve().parents[1]/'docs/reports/mixed-traffic-acceptance.json').read_text(encoding='utf-8'))
        largest = max(max(case['queue_count_p95'], case['active_count_p95']) for name, case in report['cases'].items() if 'tagum' in name)
        self.assertGreaterEqual(MAX_QUEUE_COUNT, largest)
        self.assertGreaterEqual(MAX_ACTIVE_VEHICLES, largest)
        self.assertEqual((OBSERVATION_VERSION, REWARD_VERSION), ('obs_v4', 'reward_v4'))
        self.assertEqual({dql_training.OBSERVATION_VERSION, ppo_training.OBSERVATION_VERSION}, {OBSERVATION_VERSION})

    def test_restore_compacts_deep_import_paths_without_changing_source_bytes(self):
        source_dir = Path(self.directory.name).joinpath(*(['deep-import-source-folder'] * 3))
        source_dir.mkdir(parents=True)
        source = source_dir / ('a' * 64 + '.csv')
        original = b'time_s,source,destination\r\n0,boundary_1,boundary_2\r\n'
        source.write_bytes(original)
        scenario_id = database.create_scenario('Deep imported source', engine_config={
            'demand_source': {'kind':'synthetic','datasets':[{'source_path':str(source)}]}})
        filename = backup_bundle.create_bundle(1)
        backup_id = next(row['id'] for row in database.list_backups() if row['filename'] == filename)
        stage = backup_bundle.restore_bundle_to_stage(backup_id)
        with patch.object(config, 'DB_PATH', str(stage / 'smartflow.db')):
            settings = json.loads(database.get_scenario_by_id(scenario_id)['engine_config'])
            restored = Path(settings['demand_source']['datasets'][0]['source_path'])
        self.assertEqual(restored.read_bytes(), original)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(restored.name, source.name)
        self.assertLess(len(str(restored)), len(str(stage / 'files/project' / source.relative_to(Path(config.BASE_DIR)))))


if __name__ == '__main__':
    unittest.main()
