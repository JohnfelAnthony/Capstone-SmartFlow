"""Upgrade safety and deterministic native behavior across legacy removal."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch

from services.scenario_migration import import_snapshot, migrate_connection, migration_report, resolve_legacy_scenario
from simulation.road_network import RoadNetwork, load_network
from simulation.traffic_engine import TrafficEngine


class ScenarioMigrationTests(unittest.TestCase):
    def legacy(self, **changes):
        row = {'id': 1, 'name': 'Historical scenario', 'intersection_id': 'tagum_1',
               'traffic_density': 'medium', 'pedestrian_density': 'low', 'emergency_mode': 'disabled',
               'road_constraint': 'None', 'engine_config': '{}', 'lane_closure_config': '{"enabled":false}'}
        row.update(changes)
        return row

    def connection(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.executescript('CREATE TABLE scenarios(id INTEGER PRIMARY KEY, name TEXT, intersection_id TEXT, engine_config TEXT);'
                           'CREATE TABLE system_settings(key TEXT PRIMARY KEY, value TEXT);')
        for number in (1, 2):
            conn.execute('INSERT INTO scenarios VALUES (?,?,?,?)', (number, f'Row {number}', 'tagum_1', '{}'))
        conn.commit()
        return conn

    def test_disabled_fields_migrate_and_native_nested_values_win(self):
        network = load_network()
        lane = next(iter(network.lanes))
        native = {'traffic_density': 'none', 'vehicle_mix': {'bus': 1}, 'closed_lanes': [lane],
                  'controlled_junction': network.intersections[-1], 'events': [{'time': 3, 'lane_id': lane, 'closed': False}]}
        row = self.legacy(engine_config=json.dumps(native))
        original = copy.deepcopy(row)
        resolved, warnings = resolve_legacy_scenario(row)
        self.assertEqual(row, original)
        self.assertEqual(resolved['network_id'], network.id)
        for key, value in native.items():
            self.assertEqual(resolved['engine_config'][key], value)
        self.assertTrue(warnings)

    def test_ambiguous_enabled_malformed_and_unmapped_inputs_block(self):
        for value in ('{"enabled":true}', '{"enabled":"false"}', '{"lane_id":"unknown"}', 'false', 'null', '[1]', 'bad json'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_legacy_scenario(self.legacy(lane_closure_config=value))
        with self.assertRaisesRegex(ValueError, 'mapping'):
            resolve_legacy_scenario(self.legacy(road_constraint='Lane Closure'))
        with self.assertRaises(ValueError):
            resolve_legacy_scenario(self.legacy(intersection_id='unknown'))
        payload = copy.deepcopy(load_network().payload)
        payload['id'] = 'replacement_network'
        with self.assertRaises(ValueError):
            resolve_legacy_scenario(self.legacy(), RoadNetwork(payload))

    def test_dry_run_apply_repeat_and_later_edits(self):
        conn = self.connection()
        before = [tuple(r) for r in conn.execute('SELECT * FROM scenarios')]
        report = migrate_connection(conn)
        self.assertEqual([i['status'] for i in report['scenarios']], ['ready', 'ready'])
        self.assertEqual([tuple(r) for r in conn.execute('SELECT * FROM scenarios')], before)
        self.assertNotIn('network_id', [r['name'] for r in conn.execute('PRAGMA table_info(scenarios)')])
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            migrate_connection(conn, apply=True)
        native = json.loads(conn.execute('SELECT engine_config FROM scenarios WHERE id=1').fetchone()[0])
        native['green_seconds'] = 22
        with conn:
            conn.execute('UPDATE scenarios SET engine_config=? WHERE id=1', (json.dumps(native),))
        with conn:
            again = migrate_connection(conn, apply=True)
        self.assertEqual([i['status'] for i in again['scenarios']], ['unchanged', 'unchanged'])
        self.assertEqual(json.loads(conn.execute('SELECT engine_config FROM scenarios WHERE id=1').fetchone()[0]), native)
        self.assertEqual(conn.execute('SELECT intersection_id FROM scenarios WHERE id=1').fetchone()[0], 'tagum_1')

    def test_transaction_failure_rolls_back_columns_and_rows(self):
        conn = self.connection()
        conn.execute("CREATE TRIGGER fail_second BEFORE UPDATE ON scenarios WHEN NEW.id=2 BEGIN SELECT RAISE(ABORT,'simulated failure'); END")
        conn.commit()
        with self.assertRaises(sqlite3.IntegrityError), conn:
            conn.execute('BEGIN IMMEDIATE')
            migrate_connection(conn, apply=True)
        self.assertNotIn('network_id', [r['name'] for r in conn.execute('PRAGMA table_info(scenarios)')])
        self.assertEqual(conn.execute('SELECT engine_config FROM scenarios WHERE id=1').fetchone()[0], '{}')

    def test_blocked_rows_remain_visible_and_unresolved(self):
        report = migration_report([self.legacy(lane_closure_config='{"enabled":true}')])
        self.assertEqual(report['scenarios'][0]['status'], 'blocked')
        self.assertIsNone(report['scenarios'][0]['resolved'])
        self.assertIn('mapping', report['scenarios'][0]['error'])

    def test_explicit_snapshot_import_preserves_original(self):
        row = self.legacy()
        original = copy.deepcopy(row)
        snapshot = import_snapshot(row)
        self.assertEqual(row, original)
        engine = TrafficEngine()
        engine.configure_from_scenario(snapshot)
        self.assertEqual(engine.config['traffic_density'], 'medium')

    def test_canonical_inputs_ignore_retained_legacy_recovery_values(self):
        engine = TrafficEngine()
        engine.configure(traffic_density='single', green_seconds=22)
        row = self.legacy(network_id=engine.network.id, engine_config=engine.config,
                          lane_closure_config='{"enabled":true}')
        original = copy.deepcopy(row)
        snapshot = import_snapshot(row)
        self.assertEqual(snapshot['engine_config'], engine.config)
        self.assertEqual(row, original)

    def test_empty_network_id_is_migrated_once(self):
        conn = self.connection()
        conn.execute('ALTER TABLE scenarios ADD COLUMN network_id TEXT')
        conn.execute("UPDATE scenarios SET network_id='' WHERE id=1")
        conn.commit()
        with conn:
            migrate_connection(conn, apply=True)
        self.assertEqual(conn.execute('SELECT network_id FROM scenarios WHERE id=1').fetchone()[0], load_network().id)
        self.assertEqual(migrate_connection(conn)['scenarios'][0]['status'], 'unchanged')


if __name__ == '__main__':
    unittest.main()
