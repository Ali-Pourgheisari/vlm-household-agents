"""Scripted diagnostic of TV power and remote presence, separate from VLM runs."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ai2thor.controller import Controller
from PIL import Image
from household_agents.artifacts import save


def describe(obj):
    keys = ('objectId', 'objectType', 'position', 'visible', 'distance', 'toggleable',
            'isToggled', 'breakable', 'isBroken', 'pickupable', 'isPickedUp', 'parentReceptacles')
    return {key: obj.get(key) for key in keys}


def main():
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('tv_feasibility_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    result = {'scene': 'FloorPlan201', 'scope': 'Scripted feasibility check; no VLM inference',
              'feasible_without_remote': False, 'setup': [], 'attempts': []}
    controller = None
    print(f'Artifacts: {output}', flush=True)
    try:
        controller = Controller(scene='FloorPlan201', width=640, height=480, gridSize=.25,
                                snapToGrid=False, visibilityDistance=1.5)
        objects = controller.last_event.metadata['objects']
        tv = next(obj for obj in objects if obj['objectType'] == 'Television')
        result['initial_tv'] = describe(tv)
        result['remotes'] = [describe(obj) for obj in objects if obj['objectType'] == 'RemoteControl']
        result['remote_supports'] = [describe(obj) for obj in objects
                                     if any(obj['objectId'] in (remote['parentReceptacles'] or [])
                                            for remote in result['remotes'])]
        result['initial_inventory'] = controller.last_event.metadata['inventoryObjects']
        Image.fromarray(controller.last_event.frame).save(output/'initial_room.png')
        event = controller.step(action='GetReachablePositions')
        if not event.metadata['lastActionSuccess']:
            raise RuntimeError(event.metadata['errorMessage'])
        target = tv['axisAlignedBoundingBox']['center']
        positions = sorted(event.metadata['actionReturn'], key=lambda p:
                           (p['x']-target['x'])**2 + (p['z']-target['z'])**2)
        for position in positions:
            distance = math.hypot(position['x']-target['x'], position['z']-target['z'])
            if not .65 <= distance <= 1.4:
                continue
            yaw = math.degrees(math.atan2(target['x']-position['x'], target['z']-position['z'])) % 360
            horizon = max(-30, min(60, math.degrees(math.atan2(position['y']+.675-target['y'], distance))))
            event = controller.step(action='TeleportFull', position=position,
                                    rotation={'x':0,'y':yaw,'z':0}, horizon=horizon, standing=True)
            result['setup'].append({'position':position, 'yaw':yaw, 'horizon':horizon,
                                    'success':event.metadata['lastActionSuccess']})
            if not event.metadata['lastActionSuccess']:
                continue
            obj = next(obj for obj in event.metadata['objects'] if obj['objectId']==tv['objectId'])
            if not obj['visible']:
                continue
            if obj['isToggled']:
                event=controller.step(action='ToggleObjectOff',objectId=obj['objectId'],forceAction=False)
                result['setup'].append({'action':'ToggleObjectOff','success':event.metadata['lastActionSuccess']})
                if not event.metadata['lastActionSuccess']:
                    continue
            obj=next(obj for obj in controller.last_event.metadata['objects'] if obj['objectId']==tv['objectId'])
            result['before_tv']=describe(obj)
            result['inventory_before_toggle']=controller.last_event.metadata['inventoryObjects']
            Image.fromarray(controller.last_event.frame).save(output/'before.png')
            command={'action':'ToggleObjectOn','objectId':tv['objectId'],'forceAction':False}
            event=controller.step(**command)
            obj=next(obj for obj in event.metadata['objects'] if obj['objectId']==tv['objectId'])
            attempt={'command':command,'success':event.metadata['lastActionSuccess'],
                     'error':event.metadata['errorMessage'],'after_tv':describe(obj),
                     'inventory':event.metadata['inventoryObjects']}
            result['attempts'].append(attempt)
            Image.fromarray(event.frame).save(output/'after.png')
            if attempt['success'] and obj['isToggled'] and not result['inventory_before_toggle']:
                result['feasible_without_remote']=True
                break
        if not result['feasible_without_remote']:
            raise RuntimeError('No tested near-TV pose yielded successful power-on with empty inventory')
    except Exception as exc:
        result['error']=str(exc)
        raise
    finally:
        save(output/'result.json',result)
        print(json.dumps(result,indent=2),flush=True)
        if controller is not None:
            controller.stop()


if __name__=='__main__':
    main()
