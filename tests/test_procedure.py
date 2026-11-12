"""Verify sequence continuity, checkpoint states, and failure stopping."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_interaction import Controller, response
from household_agents.model import OllamaModel
from household_agents.procedure import run_procedure
from household_agents.tasks import ObjectTask


class ProcedureTests(unittest.TestCase):
    def run_sequence(self, replies, retries=0):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        controller = Controller()
        requests = []
        answers = iter(replies)
        def request(body, attempt_folder):
            requests.append(body)
            return next(answers)
        tasks = [ObjectTask(action, 'Fridge', 'fridge-id') for action in ('OPEN', 'CLOSE')]
        result = {}
        with patch('household_agents.model.make_prompt', side_effect=lambda task, choices, feedback: task):
            try:
                run_procedure(controller, tasks, OllamaModel(request=request), folder, retries, result)
                error = None
            except Exception as exc:
                error = exc
        return result, requests, controller, folder, error

    def test_open_then_close_same_instance_with_three_checkpoint_states(self):
        result, requests, controller, folder, error = self.run_sequence([
            response(), response('{"action":"CLOSE","object":"Fridge"}')])
        self.assertIsNone(error)
        self.assertTrue(result['procedure_success'])
        self.assertEqual([cmd['action'] for cmd in controller.commands], ['OpenObject', 'CloseObject'])
        self.assertEqual({cmd['objectId'] for cmd in controller.commands}, {'fridge-id'})
        self.assertEqual(len(requests), 2)
        self.assertIn('CLOSE', requests[1]['format']['properties']['action']['enum'])
        self.assertEqual([result['checkpoints'][i]['objects'][0]['isOpen'] for i in (0, 1, -1)],
                         [False, True, False])
        self.assertEqual(result['steps'][1]['before'][0]['isOpen'], True)
        for image in ('before.png', 'middle.png', 'after.png'):
            self.assertTrue((folder / image).exists())
        self.assertTrue(json.loads((folder / 'result.json').read_text())['procedure_success'])

    def test_failed_first_step_stops_before_close(self):
        result, requests, controller, folder, error = self.run_sequence([response('{}')])
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(result['procedure_success'])
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual(controller.commands, [])
        self.assertFalse((folder / 'middle.png').exists())
        self.assertTrue((folder / 'after.png').exists())

    def test_failed_second_step_preserves_open_middle_and_failed_final_state(self):
        result, requests, controller, folder, error = self.run_sequence([response(), response('{}')])
        self.assertIsInstance(error, RuntimeError)
        self.assertFalse(result['procedure_success'])
        self.assertEqual(len(result['steps']), 2)
        self.assertEqual(len(controller.commands), 1)
        self.assertTrue(result['checkpoints'][-1]['objects'][0]['isOpen'])
        self.assertTrue((folder / 'middle.png').exists())
