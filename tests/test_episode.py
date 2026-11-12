"""Goal-only orchestration checks; scripted responses are not model evidence."""
import copy
from pathlib import Path
import tempfile
import unittest

from test_interaction import Controller, response
from household_agents.episode import goal_prompt, run_episode
from household_agents.executor import ActionExecutor, BRIDGE
from household_agents.model import OllamaModel, validate_response
from household_agents.navigation import NAVIGATION
from household_agents.tasks import ObjectTask


def tv_task():
    return ObjectTask('TOGGLE_ON', 'Television', allowed_actions=tuple(BRIDGE) + tuple(NAVIGATION),
                      instruction='Turn on the TV.')


class TVController(Controller):
    def __init__(self, visible=False, powered=False, power_changes=True):
        super().__init__(objects=[{'objectId': 'tv-id', 'objectType': 'Television',
                                  'visible': visible, 'toggleable': True,
                                  'isToggled': powered, 'distance': 1.0}])
        self.power_changes = power_changes

    def step(self, **command):
        self.commands.append(command)
        event = copy.deepcopy(self.last_event)
        obj = event.metadata['objects'][0]
        if command['action'] == 'MoveAhead':
            obj['visible'] = True
        elif command['action'] == 'ToggleObjectOn' and self.power_changes:
            obj['isToggled'] = True
        event.metadata.update(lastActionSuccess=True, errorMessage='')
        self.last_event = event
        return event


class EpisodeTests(unittest.TestCase):
    def run_goal(self, responses, controller=None, max_steps=4, max_failures=3):
        controller = controller or TVController()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        answers = iter(responses)
        requests = []
        def request(body, directory):
            requests.append(body)
            return next(answers)
        result = run_episode(controller, tv_task(), OllamaModel(request=request, prompt_builder=goal_prompt),
                             folder, max_steps=max_steps, max_failures=max_failures)
        return result, controller, requests, folder

    def test_model_selects_move_then_power_with_updated_choices(self):
        r, controller, requests, folder = self.run_goal([
            response('{"action":"MOVE_AHEAD","object":"None"}'),
            response('{"action":"TOGGLE_ON","object":"Television"}')])
        self.assertTrue(r['goal_success'])
        self.assertEqual([c['action'] for c in controller.commands], ['MoveAhead', 'ToggleObjectOn'])
        self.assertNotIn('TOGGLE_ON', requests[0]['format']['properties']['action']['enum'])
        self.assertIn('TOGGLE_ON', requests[1]['format']['properties']['action']['enum'])
        self.assertIn('simulator_success', requests[1]['messages'][0]['content'])
        self.assertTrue((folder/'decision_02/after.png').exists())

    def test_valid_navigation_does_not_count_as_goal_completion(self):
        r, controller, requests, folder = self.run_goal([
            response('{"action":"MOVE_AHEAD","object":"None"}')], max_steps=1)
        self.assertFalse(r['goal_success'])
        self.assertEqual(r['stop_reason'], 'decision_limit')
        self.assertTrue(r['decisions'][0]['simulator_success'])

    def test_invalid_output_stops_at_failure_limit_without_execution(self):
        r, controller, requests, folder = self.run_goal([response('{}')]*2, max_failures=2)
        self.assertEqual(r['stop_reason'], 'consecutive_failure_limit')
        self.assertFalse(r['goal_success'])
        self.assertEqual(controller.commands, [])
        self.assertEqual(len(requests), 2)
        self.assertIn('exactly action and object', requests[1]['messages'][0]['content'])

    def test_power_goal_requires_actual_power_state(self):
        r, controller, requests, folder = self.run_goal([
            response('{"action":"TOGGLE_ON","object":"Television"}')],
            controller=TVController(visible=True, power_changes=False), max_steps=1)
        self.assertFalse(r['goal_success'])
        self.assertIn('power state did not match', r['decisions'][0]['error'])

    def test_already_powered_skips_model(self):
        r, controller, requests, folder = self.run_goal([], controller=TVController(powered=True))
        self.assertTrue(r['goal_success'])
        self.assertEqual(r['stop_reason'], 'already_satisfied')
        self.assertEqual(requests, [])
        self.assertEqual(controller.commands, [])

    def test_navigation_uses_explicit_adapter_and_rejects_object_target(self):
        action, name, text = validate_response(response('{"action":"ROTATE_LEFT","object":"None"}'),
                                               {'ROTATE_LEFT': ['None']})
        self.assertEqual((action, name), ('ROTATE_LEFT', 'None'))
        with self.assertRaises(ValueError):
            validate_response(response('{"action":"ROTATE_LEFT","object":"Television"}'),
                              {'ROTATE_LEFT': ['None']})
        executor = ActionExecutor(TVController())
        with self.assertRaises(ValueError):
            executor.command('ROTATE_LEFT', 'Television', tv_task())

    def test_prompt_contains_goal_and_controls_without_task_decomposition(self):
        prompt = goal_prompt('Turn on the TV.', {'MOVE_AHEAD': ['None']}, [])
        self.assertIn('Goal: Turn on the TV.', prompt)
        for hint in ('find the', 'approach the', 'first ', 'then ', 'coordinates', 'FloorPlan', 'Action:'):
            self.assertNotIn(hint, prompt)
        self.assertNotIn('TOGGLE_ON', prompt)
