"""Explicit, deterministic conversion of historical scenario storage and inputs."""
from __future__ import annotations

import copy
import json

from simulation.road_network import load_network
from simulation.scenario_config import DEFAULTS, object_config, normalize_vehicle_scope

MIGRATION_VERSION = 1
LEGACY_DISRUPTIONS = ('lane_closure_config', 'construction_config', 'accident_config', 'flooding_config')
LEGACY_ALIASES = {'tagum_1', 'tagum_2', 'tagum_3'}


def resolve_legacy_scenario(scenario: dict, network=None) -> tuple[dict, list[str]]:
    """Interpret old fields only at an import/upgrade boundary; never guess lanes."""
    from simulation.traffic_engine import TrafficEngine

    scenario = normalize_vehicle_scope(scenario)
    network = network or load_network()
    warnings = []
    requested = scenario.get('network_id') or scenario.get('intersection_id') or network.id
    if requested in LEGACY_ALIASES and network.id == 'tagum_network':
        warnings.append(f'{requested} mapped to the connected tagum_network; historical geography/demand is not field calibration.')
        requested = network.id
    if requested != network.id:
        raise ValueError(f'Network {requested!r} cannot be mapped to configured network {network.id!r}.')
    for field in LEGACY_DISRUPTIONS:
        value = object_config(scenario.get(field, {}), field)
        if value and value.get('enabled') is not False:
            raise ValueError(f'{field} needs explicit native lane/event mapping; enabled or ambiguous legacy settings cannot be migrated automatically.')
        if value:
            warnings.append(f'{field}: explicitly disabled; original value retained in legacy storage.')
    native = object_config(scenario.get('engine_config', {}), 'engine_config')
    settings = {key: copy.deepcopy(scenario[key]) for key in DEFAULTS if key in scenario}
    if 'controlled_junction' in scenario:
        settings['controlled_junction'] = scenario['controlled_junction']
    settings.update(native)
    preset = native.get('road_constraint', scenario.get('road_constraint', 'None'))
    settings.pop('road_constraint', None)
    if not isinstance(preset, str):
        raise ValueError('Legacy road_constraint must be a string; migrate it to explicit native restrictions.')
    if preset.strip().lower() not in {'none', '', 'no constraints'}:
        if not any(key in native for key in ('closed_lanes', 'slow_lanes', 'events')):
            raise ValueError('Legacy road_constraint requires explicit native lane/event mapping; no physical lane is chosen automatically.')
        warnings.append('Explicit native restrictions take precedence over the legacy road_constraint preset.')
    engine = TrafficEngine(network=network)
    engine.configure(**settings)
    if 'controlled_junction' not in settings:
        warnings.append(f'Existing default controlled junction retained: {engine.controlled_junction}.')
    return {'network_id': network.id, 'engine_config': copy.deepcopy(engine.config)}, warnings


def migration_report(rows, network=None, registry_path=None) -> dict:
    network = network or load_network()
    results = []
    for row in rows:
        original = dict(row)
        try:
            if original.get('network_id'):
                from simulation.traffic_engine import TrafficEngine
                from simulation.network_registry import load_registered_network
                registry_args = {'registry_path': registry_path} if registry_path is not None else {}
                scenario_network = network if original['network_id'] == network.id else load_registered_network(original['network_id'], **registry_args)
                engine = TrafficEngine(network=scenario_network)
                engine.configure_from_scenario(original)
                resolved = {'network_id': original['network_id'], 'engine_config': engine.config}
                status, warnings = 'unchanged', []
            else:
                resolved, warnings = resolve_legacy_scenario(original, network)
                status = 'ready'
            results.append({'id': original.get('id'), 'status': status, 'source': original,
                            'resolved': resolved, 'warnings': warnings, 'error': None})
        except (ValueError, TypeError, OSError) as exc:
            results.append({'id': original.get('id'), 'status': 'blocked', 'source': original,
                            'resolved': None, 'warnings': [], 'error': str(exc)})
    return {'migration_version': MIGRATION_VERSION, 'network_id': network.id,
            'network_sha256': network.fingerprint, 'scenarios': results}


def migrate_connection(conn, *, apply=False, network=None, registry_path=None) -> dict:
    """Caller owns the transaction. Dry runs perform SELECT only."""
    rows = [dict(row) for row in conn.execute('SELECT * FROM scenarios ORDER BY id')]
    report = migration_report(rows, network, registry_path=registry_path)
    if apply:
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(scenarios)')}
        if 'network_id' not in columns:
            conn.execute('ALTER TABLE scenarios ADD COLUMN network_id TEXT')
        if 'engine_config' not in columns:
            conn.execute("ALTER TABLE scenarios ADD COLUMN engine_config TEXT DEFAULT '{}'")
        for item in report['scenarios']:
            if item['status'] == 'ready':
                conn.execute("UPDATE scenarios SET network_id = ?, engine_config = ? WHERE id = ? AND (network_id IS NULL OR network_id = '')",
                             (item['resolved']['network_id'], json.dumps(item['resolved']['engine_config']), item['id']))
        if any(item['status'] != 'unchanged' for item in report['scenarios']):
            conn.execute("INSERT OR REPLACE INTO system_settings (key,value) VALUES (?,?)",
                         ('native_scenario_migration_v1', json.dumps(report)))
    return report


def native_snapshot(scenario: dict) -> dict:
    """Project migrated storage onto the native envelope, preserving artifact keys."""
    scenario = normalize_vehicle_scope(scenario)
    if not scenario.get('network_id'):
        # Produce the specific error where possible; otherwise require the upgrade.
        resolve_legacy_scenario(scenario)
        raise ValueError('Scenario needs native migration before execution.')
    from simulation.network_registry import load_registered_network
    from simulation.traffic_engine import TrafficEngine
    engine = TrafficEngine(network=load_registered_network(scenario['network_id']))
    engine.configure_from_scenario(scenario)
    return {'id': scenario.get('id'), 'name': scenario.get('name', ''),
            'intersection_id': scenario['network_id'],
            'network_id': scenario['network_id'], 'network_sha256': engine.network.fingerprint,
            'engine_config': copy.deepcopy(engine.config)}


def import_snapshot(scenario: dict) -> dict:
    """Convert CLI/import snapshots in memory; their original evidence stays intact."""
    if scenario.get('network_id'):
        return native_snapshot(scenario)
    resolved, _ = resolve_legacy_scenario(scenario)
    return {'id': scenario.get('id'), 'name': scenario.get('name', ''),
            'intersection_id': resolved['network_id'], 'engine_config': resolved['engine_config']}
