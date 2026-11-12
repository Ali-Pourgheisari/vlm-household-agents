"""Verify a TV fixture requiring N forward moves; no model inference."""
import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from ai2thor.controller import Controller
from PIL import Image
from household_agents.artifacts import save, state
from household_agents.navigation import NAVIGATION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=int, choices=range(1, 11), default=1)
    args = parser.parse_args()
    output = PROJECT / 'results' / datetime.now(timezone.utc).strftime('tv_step_calibration_%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True)
    result = {'scene': 'FloorPlan201', 'scope': 'Scripted fixture verification, not VLM success',
              'required_forward_steps': args.steps, 'verified': False, 'candidates': []}
    controller = None
    print(f'Calibration artifacts: {output}', flush=True)
    try:
        controller = Controller(scene='FloorPlan201', width=640, height=480, gridSize=.25,
                                snapToGrid=False, rotateStepDegrees=45, visibilityDistance=1.5)
        tv = next(o for o in controller.last_event.metadata['objects'] if o['objectType']=='Television')
        target = tv['position']
        def current_tv():
            return next(o for o in controller.last_event.metadata['objects'] if o['objectId']==tv['objectId'])
        event = controller.step(action='GetReachablePositions')
        if not event.metadata['lastActionSuccess']:
            raise RuntimeError(event.metadata['errorMessage'])
        # Search free positions around the previously verified approach corridor.
        # This heuristic is calibration-only and is never sent to the model.
        extra = (args.steps - 1) * .25
        nominal = {'x': -3.0-extra*math.sin(math.radians(20.22196536864363)),
                   'z': 4.5-extra*math.cos(math.radians(20.22196536864363))}
        points = []
        for position in event.metadata['actionReturn']:
            distance = math.sqrt(sum((position[k]-target[k])**2 for k in ('x','y','z')))
            if 1.5+extra < distance < 2.25+extra:
                rank=sum((position[k]-nominal[k])**2 for k in ('x','z'))
                points.append((rank, position))
        for _, position in sorted(points, key=lambda pair:pair[0]):
            yaw=math.degrees(math.atan2(target['x']-position['x'],target['z']-position['z']))%360
            command={'action':'TeleportFull','position':position,'rotation':{'x':0,'y':yaw,'z':0},
                     'horizon':32.288995612310536,'standing':True}
            event=controller.step(**command)
            candidate={'setup_command':command,'setup_success':event.metadata['lastActionSuccess'], 'moves': []}
            result['candidates'].append(candidate)
            if not event.metadata['lastActionSuccess']:
                continue
            candidate['before_tv']=state(current_tv())
            if current_tv()['visible'] or current_tv()['isToggled']:
                continue
            Image.fromarray(event.frame).save(output/'candidate_before.png')
            # Verify power-on is rejected at every earlier interaction boundary.
            eligible = False
            for count in range(args.steps + 1):
                event=controller.step(action='ToggleObjectOn',objectId=tv['objectId'],forceAction=False)
                check={'after_forward_steps': count, 'tv': state(current_tv()),
                       'toggle_success': event.metadata['lastActionSuccess'],
                       'toggle_error': event.metadata['errorMessage']}
                candidate.setdefault('power_checks', []).append(check)
                if event.metadata['lastActionSuccess'] or current_tv()['isToggled']:
                    if count == args.steps and current_tv()['isToggled']:
                        eligible = True
                        break
                    controller.step(action='ToggleObjectOff',objectId=tv['objectId'],forceAction=False)
                    break
                if count == args.steps:
                    break
                event=controller.step(**NAVIGATION['MOVE_AHEAD'])
                candidate['moves'].append({'step':count+1,'success':event.metadata['lastActionSuccess'],
                                           'error':event.metadata['errorMessage'], 'tv':state(current_tv())})
                Image.fromarray(event.frame).save(output/f'candidate_move_{count+1:02d}.png')
                if not event.metadata['lastActionSuccess']:
                    break
            if eligible:
                result.update(verified=True, fixture=candidate, object_id=tv['objectId'],
                              movement_command=NAVIGATION['MOVE_AHEAD'])
                (output/'before.png').write_bytes((output/'candidate_before.png').read_bytes())
                for count in range(1,args.steps+1):
                    (output/f'after_move_{count:02d}.png').write_bytes((output/f'candidate_move_{count:02d}.png').read_bytes())
                (output/'middle.png').write_bytes((output/f'candidate_move_{args.steps:02d}.png').read_bytes())
                Image.fromarray(event.frame).save(output/'after.png')
                print(f'Verified {args.steps}-step fixture:',command,flush=True)
                print('Power-on outcomes:',[c['toggle_success'] for c in candidate['power_checks']],flush=True)
                break
        if not result['verified']:
            raise RuntimeError(f'No pose verified power-on only after {args.steps} forward moves')
    except Exception as exc:
        result['error']=str(exc)
        raise
    finally:
        save(output/'result.json',result)
        if controller is not None:
            controller.stop()


if __name__=='__main__':
    main()
