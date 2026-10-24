import unittest
from unittest.mock import patch
try:
    from desktop_pet.smooth_motion import (BASE, SIZE, FPS, SmoothPlayer, ease,
        prepare, compute_pair, tween, np)
except ModuleNotFoundError as error:
    # This legacy renderer is optional and excluded from the Live2D build.
    # Do not swallow broken imports other than its known optional dependencies.
    if error.name not in {'cv2', 'numpy', 'PIL'}:
        raise
    raise unittest.SkipTest(f'Optional legacy motion dependency {error.name} absent; see requirements-motion.txt') from error


class SmoothMotionTests(unittest.TestCase):
    def test_target_fps(self):
        self.assertEqual(FPS,60)

    @unittest.skipUnless((BASE / 'assets/characters/silver-dragon/animations/atlas-v1.png').is_file(),
                         'Optional legacy atlas absent; see RESOURCES.md')
    def test_tween_endpoints_and_transparency(self):
        poses=prepare(BASE/'assets/characters/silver-dragon/animations/atlas-v1.png')
        a,b=poses[0],poses[5]
        pair=compute_pair(a,b)
        np.testing.assert_array_equal(tween(a,b,pair,0),a)
        np.testing.assert_array_equal(tween(a,b,pair,1),b)
        middle=tween(a,b,pair,.5)
        self.assertEqual(middle.shape,(SIZE,SIZE,4))
        self.assertTrue(np.isfinite(middle).all())
        self.assertTrue((middle>=0).all() and (middle<=1).all())
        self.assertEqual(float(middle[0,0,3]),0)

    def player(self):
        player=SmoothPlayer.__new__(SmoothPlayer)
        player.clips={'idle':list(range(round(4.5*FPS))), 'click':list(range(round(1.7*FPS))), 'success':list(range(round(1.8*FPS)))}
        player.state='idle'; player.started=0; player.paused_at=None
        player.pending=None; player.speed=1
        return player

    @patch('desktop_pet.smooth_motion.time.monotonic')
    def test_pause_resume_and_queue(self,clock):
        p=self.player()
        clock.return_value=0; p.play('click')
        clock.return_value=.5; before=p.image(); p.pause(True)
        clock.return_value=10; self.assertEqual(p.image(),before)
        p.pause(False); self.assertEqual(p.image(),before)
        p.play('success'); self.assertEqual(p.state,'click')
        clock.return_value=12; p.image(); self.assertEqual(p.state,'success')
        clock.return_value=14; p.image(); self.assertEqual(p.state,'idle')
        self.assertFalse(p.play('missing'))

    def test_easing_has_soft_start_and_end(self):
        self.assertEqual(ease(0),0); self.assertEqual(ease(1),1)
        self.assertLess(ease(.01),.001)
        self.assertGreater(ease(.99),.999)

if __name__=='__main__': unittest.main()
