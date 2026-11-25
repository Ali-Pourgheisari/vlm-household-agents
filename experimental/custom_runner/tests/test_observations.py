"""Separate rendered-object evidence from range-limited simulator interaction."""
import json
from pathlib import Path
import tempfile
import unittest

from test_episode import TVController, tv_task
from test_interaction import response
from household_agents.episode import goal_prompt, run_episode
from household_agents.model import OllamaModel
from household_agents.observations import camera_observations


class ObservationTests(unittest.TestCase):
    def event(self):
        controller = TVController()
        controller.last_event.instance_detections2D = {'tv-id': (10, 10, 110, 80)}
        controller.last_event.metadata['objects'][0].update(position={'x':999,'y':999,'z':999}, distance=99)
        return controller.last_event

    def test_rendered_out_of_range_tv_is_reported_without_enabling_toggle(self):
        event = self.event()
        choices = {'MOVE_AHEAD': ['None']}
        obs, evidence = camera_observations(event, tv_task(), choices)
        self.assertTrue(obs['goal_object_in_view'])
        tv = obs['goal_observations'][0]
        self.assertEqual(tv['object'], 'Television')
        self.assertEqual(tv['interaction_status'], 'not_currently_interactable')
        self.assertFalse(tv['isToggled'])
        self.assertEqual(tv['eligible_actions'], [])
        text=json.dumps(obs)
        for forbidden in ('999','objectId','bbox','position','distance','tv-id'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(evidence['rendered_instances'][0]['objectId'], 'tv-id')
        self.assertEqual(choices, {'MOVE_AHEAD':['None']})

    def test_offscreen_target_metadata_is_not_reported_as_camera_observation(self):
        event=self.event()
        event.instance_detections2D={}
        obs,_=camera_observations(event,tv_task(),{})
        self.assertFalse(obs['goal_object_in_view'])
        self.assertEqual(obs['goal_observations'], [])
        self.assertEqual(obs['objects_in_view'], [])

    def test_missing_renderer_is_an_error_instead_of_silent_oracle_fallback(self):
        event=TVController().last_event
        with self.assertRaises(ValueError):
            camera_observations(event,tv_task(),{})

    def test_eligible_power_control_is_reported_when_rendered_and_in_range(self):
        event=self.event()
        event.metadata['objects'][0]['visible']=True
        obs,_=camera_observations(event,tv_task(),{'TOGGLE_ON':['Television']})
        tv=obs['goal_observations'][0]
        self.assertEqual(tv['interaction_status'],'currently_interactable')
        self.assertEqual(tv['eligible_actions'],['TOGGLE_ON'])

    def test_eligibility_belongs_to_each_instance_and_its_current_state(self):
        event = self.event()
        for name, visible, powered in [('near-off', True, False),
                                       ('far-off', False, False),
                                       ('near-on', True, True)]:
            event.metadata['objects'].append({
                'objectId': name, 'objectType': 'Television', 'visible': visible,
                'toggleable': True, 'isToggled': powered,
            })
            event.instance_detections2D[name] = (10, 10, 110, 80)
        obs, evidence = camera_observations(event, tv_task(), {'TOGGLE_ON': ['Television']})
        by_id = {item['objectId']: observed['eligible_actions']
                 for item, observed in zip(evidence['rendered_instances'], obs['objects_in_view'])}
        self.assertEqual(by_id['near-off'], ['TOGGLE_ON'])
        self.assertEqual(by_id['far-off'], [])
        self.assertEqual(by_id['near-on'], [])
        self.assertEqual(by_id['tv-id'], [])

    def test_scene_feedback_reaches_model_while_action_schema_remains_range_limited(self):
        controller=TVController()
        controller.last_event.instance_detections2D={'tv-id':(10,10,100,100)}
        replies=iter([response('{"action":"MOVE_AHEAD","object":"None"}'),
                      response('{"action":"TOGGLE_ON","object":"Television"}')])
        requests=[]
        def request(body,folder):
            requests.append(body)
            return next(replies)
        with tempfile.TemporaryDirectory() as directory:
            result=run_episode(controller,tv_task(),OllamaModel(request=request,prompt_builder=goal_prompt),
                               Path(directory),max_steps=2,scene_observations=True)
            self.assertTrue(result['goal_success'])
            self.assertNotIn('TOGGLE_ON', requests[0]['format']['properties']['action']['enum'])
            text=requests[0]['messages'][0]['content']
            self.assertIn('Television',text)
            self.assertIn('not_currently_interactable',text)
            self.assertNotIn('tv-id',text)
            self.assertNotIn('bbox',text)
            self.assertTrue((Path(directory)/'decision_01/scene_observations.json').exists())
            self.assertIn('TOGGLE_ON',requests[1]['format']['properties']['action']['enum'])
