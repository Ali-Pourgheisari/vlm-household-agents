"""Separate visual location, bounded failures, fresh images, and target recovery."""
import json
from pathlib import Path
import tempfile
import unittest

from test_episode import TVController, tv_task
from test_interaction import response
from household_agents.episode import goal_prompt, run_episode
from household_agents.model import OllamaModel, OutputValidationError
from household_agents.perception import TargetLocator


def location(position):
    return response(json.dumps({'target_position': position}))


def action(name, obj='None'):
    return response(json.dumps({'action': name, 'object': obj}))


class ThreeStepController(TVController):
    def __init__(self):
        super().__init__()
        self.moves = 0

    def step(self, **command):
        event = super().step(**command)
        if command['action'] == 'MoveAhead':
            self.moves += 1
            event.metadata['objects'][0]['visible'] = self.moves >= 3
        event.frame.fill(len(self.commands))
        return event


class PerceptionTests(unittest.TestCase):
    def setup_model(self, replies):
        answers = iter(replies)
        requests = []
        def request(body, folder):
            requests.append(body)
            value = next(answers)
            if isinstance(value, Exception):
                raise value
            return value
        return OllamaModel(request=request, prompt_builder=goal_prompt), requests

    def test_fresh_perception_precedes_each_action_and_range_controls_interaction(self):
        replies = []
        for _ in range(3):
            replies.extend([location('CENTER'), action('MOVE_AHEAD')])
        replies.extend([location('CENTER'), action('TOGGLE_ON', 'Television')])
        model, requests = self.setup_model(replies)
        controller = ThreeStepController()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_episode(controller, tv_task(), model, output, max_steps=5,
                                 target_locator=TargetLocator(model))
            self.assertTrue(result['goal_success'])
            self.assertEqual(len(requests), 8)
            self.assertEqual([d['target_tracking']['phase'] for d in result['decisions']],
                             ['approach', 'approach', 'approach', 'interact'])
            self.assertEqual([c['action'] for c in controller.commands],
                             ['MoveAhead'] * 3 + ['ToggleObjectOn'])
            self.assertNotIn('TOGGLE_ON', requests[5]['format']['properties']['action']['enum'])
            self.assertIn('TOGGLE_ON', requests[7]['format']['properties']['action']['enum'])
            for index in range(0, 8, 2):
                self.assertEqual(set(requests[index]['format']['properties']), {'target_position'})
                self.assertEqual(requests[index]['messages'][0]['images'], requests[index+1]['messages'][0]['images'])
                self.assertNotIn('tv-id', requests[index]['messages'][0]['content'])
                self.assertNotIn('VISUAL TARGET TRACKING', requests[index]['messages'][0]['content'])
            self.assertNotEqual(requests[0]['messages'][0]['images'], requests[2]['messages'][0]['images'])
            self.assertTrue((output / 'decision_04/perception/result.json').exists())

    def test_lost_target_preserves_last_seen_and_requests_recovery_without_selecting_action(self):
        model, requests = self.setup_model([
            location('LEFT'), action('ROTATE_RIGHT'),
            location('NOT_VISIBLE'), action('ROTATE_LEFT'),
            location('CENTER'), action('MOVE_AHEAD'),
        ])
        controller = TVController()
        with tempfile.TemporaryDirectory() as directory:
            result = run_episode(controller, tv_task(), model, Path(directory), max_steps=3,
                                 target_locator=TargetLocator(model))
        lost = result['decisions'][1]['target_tracking']
        self.assertEqual(lost['phase'], 'recover')
        self.assertTrue(lost['target_lost'])
        self.assertEqual(lost['last_seen'], {'target_position': 'LEFT', 'at_decision': 1})
        self.assertIn('bring it back into view', requests[3]['messages'][0]['content'])
        self.assertEqual(result['decisions'][2]['target_tracking']['phase'], 'approach')
        self.assertFalse(result['decisions'][2]['target_tracking']['target_lost'])
        self.assertEqual([c['action'] for c in controller.commands], ['RotateRight', 'RotateLeft', 'MoveAhead'])

    def test_invalid_perception_skips_action_and_retries_with_validation_error(self):
        model, requests = self.setup_model([
            response('{}'), location('CENTER'), action('MOVE_AHEAD'),
            location('CENTER'), action('TOGGLE_ON', 'Television'),
        ])
        controller = TVController()
        with tempfile.TemporaryDirectory() as directory:
            result = run_episode(controller, tv_task(), model, Path(directory), max_steps=3,
                                 target_locator=TargetLocator(model))
            self.assertTrue(result['goal_success'])
            self.assertEqual(result['decisions'][0]['failure_stage'], 'perception')
            self.assertFalse(result['decisions'][0]['action_executed'])
            self.assertIn('Previous location output failed validation', requests[1]['messages'][0]['content'])
            self.assertEqual(len(controller.commands), 2)
            self.assertFalse((Path(directory)/'decision_01/simulator_command.json').exists())

    def test_repeated_invalid_perception_stops_at_failure_limit(self):
        model, requests = self.setup_model([response('{}'), response('{}')])
        controller = TVController()
        with tempfile.TemporaryDirectory() as directory:
            result = run_episode(controller, tv_task(), model, Path(directory), max_steps=5, max_failures=2,
                                 target_locator=TargetLocator(model))
        self.assertEqual(result['stop_reason'], 'consecutive_failure_limit')
        self.assertEqual(len(requests), 2)
        self.assertEqual(controller.commands, [])

    def test_locator_rejects_malformed_extra_duplicate_unknown_and_truncated_output(self):
        invalid = ['{}', '[]', '{"target_position":"CENTER","action":"MOVE_AHEAD"}',
                   '{"target_position":"LEFT","target_position":"RIGHT"}',
                   '{"target_position":"BEHIND"}', '{"target_position":false}',
                   '{"target_position":"CENTER"']
        for text in invalid:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                (output/'before.png').write_bytes(b'example image bytes')
                model, _ = self.setup_model([response(text)])
                with self.assertRaises(OutputValidationError):
                    TargetLocator(model).locate('Cabinet', output)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output/'before.png').write_bytes(b'example image bytes')
            model, _ = self.setup_model([response('{"target_position":"CENTER"}', reason='length')])
            with self.assertRaises(OutputValidationError):
                TargetLocator(model).locate('Cabinet', output)

    def test_perception_transport_failure_is_terminal_without_action(self):
        model, requests = self.setup_model([RuntimeError('connection unavailable')])
        controller = TVController()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaises(RuntimeError):
                run_episode(controller, tv_task(), model, output, target_locator=TargetLocator(model))
            result = json.loads((output/'result.json').read_text())
        self.assertEqual(result['stop_reason'], 'runtime_error')
        self.assertEqual(len(requests), 1)
        self.assertEqual(controller.commands, [])
