import unittest
from workbench.domain import *

class DomainBoundaryTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(subtract([8,17],[[7,18]]),[])
        self.assertEqual(subtract([8,17],[[17,19]]),[[8,17]])
        self.assertEqual(subtract([8,17],[[10,12],[12,14]]),[[8,10],[14,17]])
        self.assertIsNone(intersect([8,9],[9,10]))
        self.assertEqual(zone_overlap(['A'],['B']),[])
