"""State-aware loop detection and bounded recovery without route substitution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_episode import TVController, tv_task
from test_interaction import response
from household_agents.episode import goal_prompt, run_episode
from household_agents.model import OllamaModel
from household_agents.repetition import RepetitionMonitor, state_signature


def choice(action, obj='Laptop'):
    return response(json.dumps({'action': action, 'object': obj}))


CYCLE = [choice('TOGGLE_ON'), choice('TOGGLE_OFF')] * 2


class LaptopController(TVController):
    def __init__(self):
        super().__init__()
        self.last_event.metadata['agent'] = {
            'position': {'x': 0., 'y': 0., 'z': 0.},
            'rotation': {'x': 0., 'y': 0., 'z': 0.}, 'cameraHorizon': 0., 'isStanding': True}
        self.last_event.metadata['objects'].append(
            {'objectId': 'Laptop|+00.00|+00.00|+00.00', 'objectType': 'Laptop',
             'toggleable': True, 'isToggled': False, 'visible': True, 'distance': 1.})

    def step(self, **command):
        self.commands.append(command)
        event = copy.deepcopy(self.last_event)
        if command['action'] in ('ToggleObjectOn', 'ToggleObjectOff'):
            obj = next(obj for obj in event.metadata['objects'] if obj['objectId'] == command['objectId'])
            obj['isToggled'] = command['action'] == 'ToggleObjectOn'
        elif command['action'] == 'RotateLeft':
            event.metadata['agent']['rotation']['y'] -= 45
        elif command['action'] == 'MoveAhead':
            event.metadata['agent']['position']['z'] += .25
            event.metadata['objects'][0]['visible'] = True
        event.metadata.update(lastActionSuccess=True, errorMessage='')
        self.last_event = event
        return event


class RepetitionTests(unittest.TestCase):
    def run_loop(self, replies, **options):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        controller = LaptopController()
        answers = iter(replies)
        requests = []
        def request(body, directory):
            requests.append(body)
            return next(answers)
        result = run_episode(controller, tv_task(), OllamaModel(request=request, prompt_builder=goal_prompt),
                             folder, max_steps=len(replies), **options)
        return result, controller, requests, folder

    def test_laptop_cycle_warns_then_stops_without_executing_repeated_choices(self):
        r, c, requests, folder = self.run_loop(CYCLE + [choice('TOGGLE_ON')] * 2)
        self.assertEqual(r['stop_reason'], 'repetition_limit')
        self.assertEqual(len(c.commands), 4)
        self.assertEqual(len(r['decisions']), 6)
        self.assertEqual(len(r['repetition_events']), 1)
        self.assertEqual(r['repetition_events'][0]['detected_at_decision'], 4)
        self.assertFalse(r['decisions'][4]['action_executed'])
        self.assertFalse(r['decisions'][5]['action_executed'])
        self.assertIn('REPETITION FEEDBACK', requests[4]['messages'][0]['content'])
        self.assertIn('was not executed', requests[5]['messages'][0]['content'])
        feedback=json.loads((folder/'decision_05/feedback.json').read_text())
        self.assertFalse(feedback['goal_status']['complete'])
        self.assertNotIn('+00.00', requests[5]['messages'][0]['content'])

    def test_model_can_select_different_action_and_recover(self):
        r, c, requests, folder = self.run_loop(CYCLE + [choice('ROTATE_LEFT', 'None'),
                                             choice('MOVE_AHEAD', 'None'), choice('TOGGLE_ON', 'Television')])
        self.assertTrue(r['goal_success'])
        self.assertEqual(r['stop_reason'], 'goal_reached')
        self.assertEqual(r['repetition_events'][0]['recovered_at_decision'], 5)
        self.assertEqual([cmd['action'] for cmd in c.commands][-3:],
                         ['RotateLeft', 'MoveAhead', 'ToggleObjectOn'])

    def test_goal_status_and_actual_object_state_are_returned_after_successful_wrong_action(self):
        r, c, requests, folder = self.run_loop([choice('TOGGLE_ON'), choice('ROTATE_LEFT', 'None')])
        text=requests[1]['messages'][0]['content']
        self.assertIn('remains incomplete', text)
        self.assertIn('Laptop', text)
        self.assertIn('"isToggled": true', text)
        self.assertFalse(r['goal_success'])
        self.assertNotIn('distance', text)
        self.assertNotIn('objectId', text)

    def test_baseline_keeps_old_history_without_goal_or_repetition_feedback(self):
        r, c, requests, folder = self.run_loop(CYCLE + [choice('TOGGLE_ON'), choice('TOGGLE_OFF')],
                                             enhanced_feedback=False)
        self.assertEqual(len(c.commands), 6)
        self.assertEqual(r['stop_reason'], 'decision_limit')
        self.assertEqual(r['repetition_events'], [])
        self.assertNotIn('Current goal status', requests[1]['messages'][0]['content'])
        self.assertNotIn('REPETITION FEEDBACK', requests[4]['messages'][0]['content'])

    def test_zero_repetition_retries_stops_as_soon_as_cycle_detected(self):
        r, c, requests, folder = self.run_loop(CYCLE, max_repetition_retries=0)
        self.assertEqual(r['stop_reason'], 'repetition_limit')
        self.assertEqual(len(c.commands), 4)

    def test_repeated_forward_motion_with_changing_pose_is_not_a_cycle(self):
        c=LaptopController()
        monitor=RepetitionMonitor(state_signature(c.last_event.metadata))
        for _ in range(12):
            event=c.step(action='MoveAhead')
            self.assertIsNone(monitor.observe(('MOVE_AHEAD','None',None), state_signature(event.metadata)))

    def test_missing_pose_disables_state_based_detection(self):
        monitor=RepetitionMonitor(None)
        self.assertIsNone(monitor.observe(('MOVE_AHEAD','None',None),None))
        self.assertIsNone(monitor.observe(('MOVE_AHEAD','None',None),None))

    def test_tiny_pose_noise_and_signed_zero_do_not_hide_cycle(self):
        c = LaptopController()
        a = state_signature(c.last_event.metadata)
        c.last_event.metadata['agent']['position']['x'] = -0.000001
        c.last_event.metadata['agent']['cameraHorizon'] = -0.0
        self.assertEqual(a, state_signature(c.last_event.metadata))

    def test_goal_completion_is_not_flagged_as_repetition(self):
        r,c,requests,folder=self.run_loop([choice('MOVE_AHEAD','None'),choice('TOGGLE_ON','Television')])
        self.assertTrue(r['goal_success'])
        self.assertEqual(r['repetition_events'], [])
