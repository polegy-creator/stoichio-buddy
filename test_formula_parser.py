import unittest

from stoichio.chemistry.formula_parser import molar_mass, parse_formula


class FormulaParserTests(unittest.TestCase):
    def test_decimal_formula(self):
        self.assertEqual(parse_formula("Fe1.98Ti0.02O3"), {"Fe": 1.98, "Ti": 0.02, "O": 3.0})

    def test_parentheses_formula(self):
        self.assertEqual(parse_formula("Ba(NO3)2"), {"Ba": 1.0, "N": 2.0, "O": 6.0})

    def test_nested_group_formula(self):
        self.assertEqual(parse_formula("Al2(SO4)3"), {"Al": 2.0, "S": 3.0, "O": 12.0})

    def test_middle_dot_hydrate_formula(self):
        self.assertEqual(parse_formula("CuSO4·5H2O"), {"Cu": 1.0, "S": 1.0, "O": 9.0, "H": 10.0})

    def test_asterisk_hydrate_formula(self):
        self.assertEqual(parse_formula("CuSO4*5H2O"), {"Cu": 1.0, "S": 1.0, "O": 9.0, "H": 10.0})

    def test_group_molar_mass(self):
        composition = parse_formula("Ca(OH)2")
        expected = 40.078 + 2 * (15.999 + 1.008)
        self.assertAlmostEqual(molar_mass(composition), expected, places=6)

    def test_fe2o3_molar_mass_from_atomic_masses(self):
        self.assertAlmostEqual(molar_mass(parse_formula("Fe2O3")), 159.687, places=6)

    def test_invalid_trailing_hydrate_separator_rejected(self):
        with self.assertRaises(ValueError):
            parse_formula("CuSO4·")


if __name__ == "__main__":
    unittest.main()
