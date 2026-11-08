"""Offline failure-path tests; scripted responses are not model reliability evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from household_agents import model as demo
from household_agents.engine import run_interaction
from household_agents.tasks import ObjectTask
from household_agents.executor import ActionExecutor


def response(text='{"action":"OPEN","object":"Fridge"}', reason='stop'):
    return {'done': True, 'done_reason': reason, 'message': {'content': text}}


class Controller:
    def __init__(self, failures=0, change_state=True, objects=None):
        self.commands = []
        self.failures = failures
        self.change_state = change_state
        self.last_event = SimpleNamespace(frame=np.zeros((8, 8, 3), dtype=np.uint8), metadata={
            'objects': [{'objectId': 'fridge-id', 'objectType': 'Fridge',
                         'visible': True, 'openable': True, 'isOpen': False, 'distance': 1.0}],
            'lastActionSuccess': True, 'errorMessage': '', 'inventoryObjects': []})
        if objects is not None:
            self.last_event.metadata['objects'] = objects

    def step(self, **command):
        self.commands.append(command)
        event = copy.deepcopy(self.last_event)
        failed = len(self.commands) <= self.failures
        event.metadata.update(lastActionSuccess=not failed,
                              errorMessage='Door blocked by obstacle' if failed else '')
        if not failed and self.change_state:
            obj = next(o for o in event.metadata['objects'] if o['objectId'] == command['objectId'])
            if command['action'] == 'PickupObject':
                obj['isPickedUp'] = True
                event.metadata['inventoryObjects'] = [{'objectId': obj['objectId']}]
            else:
                obj['isOpen'] = command['action'] == 'OpenObject'
        self.last_event = event
        return event


class RecoveryTests(unittest.TestCase):
    def run_loop(self, responses, retries=2, controller=None, task=None):
        controller = controller or Controller()
        result = {'task': 'Open the fridge.', 'task_success': False, 'action_executed': False}
        requests = []
        answers = iter(responses)
        def request(body, folder):
            requests.append(body)
            value = next(answers)
            if isinstance(value, Exception):
                raise value
            return value
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        with patch.object(demo, 'make_prompt', side_effect=lambda task, names, feedback: json.dumps(feedback)):
            try:
                run_interaction(controller, task or ObjectTask('OPEN', 'Fridge', 'fridge-id'),
                                demo.OllamaModel('test-model', request=request), folder, retries, result)
                error = None
            except Exception as exc:
                error = exc
        return result, requests, controller, folder, error

    def test_rejects_malformed_missing_extra_duplicate_unknown_and_truncated(self):
        for text in ('Action: OPEN', '{"action":"OPEN"}',
                     '{"action":"OPEN","object":"Fridge","extra":1}',
                     '{"action":"OPEN","action":"CLOSE","object":"Fridge"}',
                     '{"action":"PICKUP","object":"Fridge"}',
                     '{"action":"OPEN","object":"Refrigerator"}',
                     '{"action":[],"object":"Fridge"}', '[]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                demo.validate_response(response(text), {'OPEN': ['Fridge']})
        with self.assertRaises(ValueError):
            demo.validate_response(response(reason='length'), {'OPEN': ['Fridge']})

    def test_missing_field_then_valid_choice_recovers_without_executing_invalid_output(self):
        result, requests, controller, folder, error = self.run_loop([
            response('{"action":"OPEN"}'), response()])
        self.assertIsNone(error)
        self.assertEqual(len(controller.commands), 1)
        self.assertTrue(result['recovered'])
        self.assertFalse(result['first_attempt_success'])
        self.assertFalse(result['attempts'][0]['action_executed'])
        self.assertIn('exactly action and object', requests[1]['messages'][0]['content'])
        self.assertEqual(requests[0]['format'], demo.output_schema({'OPEN': ['Fridge']}))
        self.assertTrue((folder / 'attempt_01/after.png').exists())
        self.assertTrue((folder / 'attempt_02/result.json').exists())

    def test_simulator_rejection_is_reported_and_next_request_has_current_image(self):
        result, requests, controller, folder, error = self.run_loop(
            [response(), response()], controller=Controller(failures=1))
        self.assertIsNone(error)
        self.assertTrue(result['recovered'])
        self.assertEqual(len(controller.commands), 2)
        self.assertIn('Door blocked by obstacle', requests[1]['messages'][0]['content'])
        self.assertEqual(result['attempts'][0]['failure_stage'], 'execution')
        self.assertIn('images', requests[1]['messages'][0])

    def test_invalid_output_exhausts_exact_budget_without_any_execution(self):
        result, requests, controller, folder, error = self.run_loop([response('{}')] * 3)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(len(requests), 3)
        self.assertEqual(controller.commands, [])
        self.assertFalse(result['task_success'])

    def test_success_stops_without_retry(self):
        result, requests, controller, folder, error = self.run_loop([response()])
        self.assertIsNone(error)
        self.assertTrue(result['first_attempt_success'])
        self.assertFalse(result['recovered'])
        self.assertEqual(len(requests), 1)

    def test_no_retries_and_impossible_noop_are_rejected(self):
        result, requests, controller, folder, error = self.run_loop(
            [response('{"action":"CLOSE","object":"Fridge"}')], retries=0)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(controller.commands, [])
        self.assertIn('Unsupported action', result['attempts'][0]['error'])

    def test_simulator_success_flag_without_state_change_is_not_task_success(self):
        result, requests, controller, folder, error = self.run_loop(
            [response()], retries=0, controller=Controller(change_state=False))
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(result['task_success'])
        self.assertIn('state did not match', result['attempts'][0]['error'])

    def test_runtime_failure_is_terminal(self):
        result, requests, controller, folder, error = self.run_loop([httpx.ConnectError("Ollama unavailable")])
        self.assertIsInstance(error, httpx.ConnectError)
        self.assertEqual(len(requests), 1)
        self.assertEqual(controller.commands, [])
        self.assertEqual(result['attempts'][0]['failure_stage'], 'runtime')

    def test_cabinet_goal_uses_shared_engine(self):
        cabinet = {'objectId': 'cabinet-id', 'objectType': 'Cabinet', 'visible': True,
                   'openable': True, 'isOpen': False, 'distance': 1.0}
        result, requests, controller, folder, error = self.run_loop(
            [response('{"action":"OPEN","object":"Cabinet"}')],
            controller=Controller(objects=[cabinet]), task=ObjectTask('OPEN', 'Cabinet', 'cabinet-id'))
        self.assertIsNone(error)
        self.assertTrue(result['task_success'])
        self.assertEqual(controller.commands[0], {'action': 'OpenObject', 'objectId': 'cabinet-id'})

    def test_close_goal_uses_shared_engine(self):
        cabinet = {'objectId': 'cabinet-id', 'objectType': 'Cabinet', 'visible': True,
                   'openable': True, 'isOpen': True, 'distance': 1.0}
        result, requests, controller, folder, error = self.run_loop(
            [response('{"action":"CLOSE","object":"Cabinet"}')],
            controller=Controller(objects=[cabinet]), task=ObjectTask('CLOSE', 'Cabinet', 'cabinet-id'))
        self.assertIsNone(error)
        self.assertTrue(result['task_success'])
        self.assertEqual(controller.commands[0]['action'], 'CloseObject')

    def test_pickup_checks_inventory_and_object_state(self):
        apple = {'objectId': 'apple-id', 'objectType': 'Apple', 'visible': True,
                 'pickupable': True, 'isPickedUp': False, 'distance': 1.0}
        result, requests, controller, folder, error = self.run_loop(
            [response('{"action":"PICKUP","object":"Apple"}')],
            controller=Controller(objects=[apple]), task=ObjectTask('PICKUP', 'Apple', 'apple-id'))
        self.assertIsNone(error)
        self.assertTrue(result['task_success'])
        self.assertEqual(controller.commands[0], {'action': 'PickupObject', 'objectId': 'apple-id'})
        metadata = controller.last_event.metadata
        metadata['inventoryObjects'] = []
        self.assertFalse(ObjectTask('PICKUP', 'Apple').complete(metadata))

    def test_capabilities_state_and_full_hand_filter_choices(self):
        controller = Controller(objects=[
            {'objectId': 'apple', 'objectType': 'Apple', 'visible': True, 'pickupable': True},
            {'objectId': 'cabinet', 'objectType': 'Cabinet', 'visible': True, 'openable': True, 'isOpen': True},
            {'objectId': 'hidden', 'objectType': 'Fridge', 'visible': False, 'openable': True, 'isOpen': False}])
        executor = ActionExecutor(controller)
        task = ObjectTask('PICKUP', 'Apple')
        self.assertEqual(executor.legal_choices(task), {'CLOSE': ['Cabinet'], 'PICKUP': ['Apple']})
        controller.last_event.metadata['inventoryObjects'] = [{'objectId': 'held'}]
        self.assertNotIn('PICKUP', executor.legal_choices(task))
        with self.assertRaises(ValueError):
            executor.command('OPEN', 'Apple', task)

    def test_bound_instance_is_not_replaced_by_closer_same_type(self):
        objects = [{'objectId': oid, 'objectType': 'Cabinet', 'visible': True,
                    'openable': True, 'isOpen': False, 'distance': dist}
                   for oid, dist in [('wrong', 0.5), ('target', 1.0)]]
        executor = ActionExecutor(Controller(objects=objects))
        task = ObjectTask('OPEN', 'Cabinet', 'target')
        self.assertEqual(executor.command('OPEN', 'Cabinet', task)['objectId'], 'target')
        objects[1]['visible'] = False
        self.assertNotIn('OPEN', executor.legal_choices(task))

    def test_already_completed_goal_skips_model_and_execution(self):
        controller = Controller()
        controller.last_event.metadata['objects'][0]['isOpen'] = True
        result, requests, controller, folder, error = self.run_loop([], controller=controller)
        self.assertIsNone(error)
        self.assertTrue(result['already_satisfied'])
        self.assertEqual(requests, [])
        self.assertEqual(controller.commands, [])
        self.assertTrue((folder / 'after.png').exists())

    def test_cross_action_object_pair_rejected_even_when_both_are_in_schema_enums(self):
        with self.assertRaises(ValueError):
            demo.validate_response(response('{"action":"OPEN","object":"Apple"}'),
                                   {'OPEN': ['Cabinet'], 'PICKUP': ['Apple']})

    def test_wrong_object_success_does_not_complete_goal(self):
        controller = Controller()
        controller.last_event.metadata['objects'].append(
            {'objectId': 'cabinet', 'objectType': 'Cabinet', 'visible': True,
             'openable': True, 'isOpen': False, 'distance': 1.0})
        result, requests, controller, folder, error = self.run_loop(
            [response('{"action":"OPEN","object":"Cabinet"}')], retries=0, controller=controller)
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(result['task_success'])
        self.assertEqual(result['attempts'][0]['failure_stage'], 'goal')


if __name__ == '__main__':
    unittest.main()
