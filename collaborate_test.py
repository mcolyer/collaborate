import collaborate
import unittest

class InclusionTests(unittest.TestCase):
    def setUp(self):
        pass
    
    def testInclusion_ii_before(self):
        op_first = collaborate.InsertOperation('0', 1)
        op_second = collaborate.InsertOperation('0', 20)
        op_return = op_first.include(op_second)
        assert(op_return.equals(op_first))
    
    def testInclusion_ii_after(self):
        op_first = collaborate.InsertOperation('0', 1)
        op_second = collaborate.InsertOperation('0', 20)
        op_return = op_second.include(op_first)
        assert(op_return.s == op_second.s and op_return.p == op_second.p +
                op_first.l)
    
    def testInclusion_id_before(self):
        op_first = collaborate.InsertOperation('0', 1)
        op_second = collaborate.DeleteOperation(5, 20)
        op_return = op_first.include(op_second)
        assert(op_return.equals(op_first))
    
    def testInclusion_id_equal(self):
        op_equal_a = collaborate.InsertOperation('0', 1)
        op_equal_b = collaborate.DeleteOperation(5, 1)
        op_return = op_equal_a.include(op_equal_b)
        assert(op_return.equals(op_equal_a))
    
    def testInclusion_id_after_non_overlap(self):
        op_equal_a = collaborate.InsertOperation('0', 10)
        op_equal_b = collaborate.DeleteOperation(5, 1)
        op_return = op_equal_a.include(op_equal_b)
        assert(op_return.s == op_equal_a.s and op_return.p == (op_equal_a.p - op_equal_b.l))
    
    def testInclusion_id_after_overlap(self):
        op_equal_a = collaborate.InsertOperation('0', 3)
        op_equal_b = collaborate.DeleteOperation(5, 1)
        op_return = op_equal_a.include(op_equal_b)
        assert(op_return.s == op_equal_a.s and op_return.p == op_equal_b.p)
    
    def testInclusion_di_after(self):
        op_first = collaborate.DeleteOperation(5, 3)
        op_second = collaborate.InsertOperation("1", 10)
        op_return = op_first.include(op_second)
        assert(op_return.equals(op_first))
    
    def testInclusion_di_after_equal(self):
        op_first = collaborate.DeleteOperation(5, 3)
        op_second = collaborate.InsertOperation("12", 8)
        op_return = op_first.include(op_second)
        assert(op_return.equals(op_first))
    
    def testInclusion_di_inside(self):
        op_inside = collaborate.DeleteOperation(5, 2)
        op_first = collaborate.InsertOperation("1234", 1)
        op_return = op_inside.include(op_first)
        assert(op_return.l == op_inside.l and op_return.p == op_inside.p +
                op_first.l)
    
    def testInclusion_di_inside_equal(self):
        op_inside = collaborate.DeleteOperation(2, 1)
        op_first = collaborate.InsertOperation("1234", 1)
        op_return = op_inside.include(op_first)
        assert(op_return.l == op_inside.l and op_return.p == op_inside.p +
                op_first.l)
    
    def testInclusion_di_split(self):
        op_orig = collaborate.DeleteOperation(10, 1)
        op_insert = collaborate.InsertOperation("1234", 2)
        op_return = op_orig.include(op_insert)
        assert(op_return.is_split() and (op_return.l == (op_insert.p -
            op_orig.p) and op_return.p == op_orig.p) and
            (op_return.sl == op_orig.l - (op_insert.p - op_orig.p)
            and op_return.sp == (op_insert.p + op_insert.l)))
    
    def testInclusion_dd_first(self):
        op_first = collaborate.DeleteOperation(2, 2)
        op_second = collaborate.DeleteOperation(4, 5)
        op_return = op_first.include(op_second)
        assert(op_return.equals(op_first))
    
    def testInclusion_dd_first_equal(self):
        op_first = collaborate.DeleteOperation(2, 2)
        op_second = collaborate.DeleteOperation(4, 4)
        op_return = op_first.include(op_second)
        assert(op_return.equals(op_first))
    
    def testInclusion_dd_after(self):
        op_a = collaborate.DeleteOperation(5, 5)
        op_b = collaborate.DeleteOperation(2, 2)
        op_return = op_a.include(op_b)
        assert(op_return.l == op_a.l and op_return.p == (op_a.p -
            op_b.l))
    
    def testInclusion_dd_after_equals(self):
        op_a = collaborate.DeleteOperation(4, 5)
        op_b = collaborate.DeleteOperation(2, 2)
        op_return = op_a.include(op_b)
        assert(op_return.l == op_a.l and op_return.p == (op_a.p -
            op_b.l))
    
    def testInclusion_dd_overlap_enclosed(self):
        op_first = collaborate.DeleteOperation(2, 2)
        op_second = collaborate.DeleteOperation(4, 1)
        op_return = op_first.include(op_second)
        assert(op_return.l == 0 and op_return.p == op_first.p)
    
    def testInclusion_dd_overlap_first(self):
        op_first = collaborate.DeleteOperation(6, 2)
        op_second = collaborate.DeleteOperation(4, 1)
        op_return = op_first.include(op_second)
        assert(op_return.l == (op_first.p + op_first.l - (op_second.p +
            op_second.l)) and op_return.p == op_second.p)
    
    def testInclusion_dd_overlap_second(self):
        op_first = collaborate.DeleteOperation(3, 1)
        op_second = collaborate.DeleteOperation(4, 2)
        op_return = op_first.include(op_second)
        assert(op_return.l == (op_second.p - op_first.p) and op_return.p == op_first.p)

    def testInclusion_dd_overlap_second_equals(self):
        op_first = collaborate.DeleteOperation(2, 1)
        op_second = collaborate.DeleteOperation(1, 2)
        op_return = op_first.include(op_second)
        assert(op_return.l == (op_second.p - op_first.p) and op_return.p == op_first.p)

    def testInclusion_dd_overlap_encloses(self):
        op_first = collaborate.DeleteOperation(10, 1)
        op_second = collaborate.DeleteOperation(4, 2)
        op_return = op_first.include(op_second)
        assert(op_return.l == (op_first.l - op_second.l) and op_return.p == op_first.p)
    
class ExclusionTests(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    
    #if P(O_a) <= P(O_b) O_a' := O_a
    def testExclusion_ii_completely_before(self):
        op_a = collaborate.InsertOperation("a", 1)
        op_b = collaborate.InsertOperation("b", 5)
        op_return = op_a.exclude(op_b)
        assert(op_return == op_a)
    
    #else P(O_a) >= (P(O_b) + L(O_b)) O_a' := [S(O_a), P(O_a)-L(O_b)]
    def testExclusion_ii_completely_after(self):
        op_a = collaborate.InsertOperation("a", 5)
        op_b = collaborate.InsertOperation("b", 1)
        op_return = op_a.exclude(op_b)
        assert(op_return.p == (op_a.p - op_b.l) and op_return.s == op_a.s)

    #else
    def testExclusion_ii_inside(self):
        op_a = collaborate.InsertOperation("a", 2)
        op_b = collaborate.InsertOperation("bad", 1)
        op_return = op_a.exclude(op_b)
        assert(op_return.p == (op_a.p - op_b.p) and op_return.s == op_a.s)
    
    def testExclusion_id_recover(self):
        pass

    #if P(O_a) <= P(O_b) O_a' := O_a
    def testExclusion_id_completely_before(self):
        op_a = collaborate.InsertOperation("a", 1)
        op_b = collaborate.DeleteOperation(2, 2)
        op_return = op_a.exclude(op_b)
        assert(op_return == op_a)

    #else
    def testExclusion_id_anywhere_after(self):
        op_a = collaborate.InsertOperation("a", 5)
        op_b = collaborate.DeleteOperation(2, 2)
        op_return = op_a.exclude(op_b)
        assert(op_return.s == op_a.s and op_return.p == (op_a.p + op_b.l))

    #if P(O_b) >= (P(O_a) + L(O_a)) O_a' := O_a
    def testExclusion_di_completely_before(self):
        op_a = collaborate.DeleteOperation(2, 2)
        op_b = collaborate.InsertOperation("a", 5)
        op_return = op_a.exclude(op_b)
        assert(op_return == op_a)

    #if P(O_a) >= (P(O_b)+L(O_b)) O_a' := [L(O_a), P(O_a)-L(O_b)]
    def testExclusion_di_completely_after(self):
        op_a = collaborate.DeleteOperation(2, 6)
        op_b = collaborate.InsertOperation("a", 1)
        op_return = op_a.exclude(op_b)
        assert(op_return.l == op_a.l and op_return.p == (op_a.p - op_b.l))

    #else
    #if P(O_b) <= P(O_a) and (P(O_a) + L(O_a)) <= (P(O_b)+L(O_b))
    def testExclusion_di_completely_inside(self):
        op_a = collaborate.DeleteOperation(2, 2)
        op_b = collaborate.InsertOperation("dogs", 1)
        op_return = op_a.exclude(op_b)
        assert(op_return.l == op_a.l and op_return.p == (op_a.p - op_b.p))
 
    #if P(O_b) <= P(O_a) and (P(O_a) + L(O_a)) > (P(O_b)+L(O_b))
    def testExclusion_di_overlaps_end(self):
        op_a = collaborate.DeleteOperation(6, 2)
        op_b = collaborate.InsertOperation("dogs", 1)
        op_return = op_a.exclude(op_b)
        assert((op_return.l == (op_b.p + op_b.l - op_a.p) and op_return.p == (op_a.p - op_b.p)) and (op_return.sl == ((op_a.p + op_a.l) - (op_b.p + op_b.l)) and op_return.sp == op_b.p))

    #if P(O_a) < P(O_b) and (P(O_b) + L(O_b)) <= (P(O_a)+L(O_a))
    def testExclusion_di_encloses(self):
        op_a = collaborate.DeleteOperation(8, 1)
        op_b = collaborate.InsertOperation("dogs", 2)
        op_return = op_a.exclude(op_b)
        assert((op_return.l == op_b.l and op_return.p == 0) and (op_return.sl == (op_a.l - op_b.l) and op_return.sp == op_a.p))

    #else
    def testExclusion_di_overlaps_start(self):
        op_a = collaborate.DeleteOperation(2, 1)
        op_b = collaborate.InsertOperation("dogsandcats", 2)
        op_return = op_a.exclude(op_b)
        assert((op_return.l == (op_a.p + op_a.l - op_b.p) and op_return.p == 0) and (op_return.sl == (op_b.p - op_a.p) and op_return.sp == op_a.p))

    #if Check_LI(O_a, O_b)
    def testExclusion_dd_check_li(self):
        pass

    #else if P(O_b) >= (P(O_a)+L(O_a)) O_a' := O_a
    def testExclusion_dd_completely_before(self):
        op_a = collaborate.DeleteOperation(1, 1)
        op_b = collaborate.DeleteOperation(10, 3)
        op_return = op_a.exclude(op_b)
        assert(op_return == op_a)
 
    #else if P(O_b) <= P(O_a) O_a' := [L(O_a), P(O_a)+L(O_b)]
    def testExclusion_dd_overlaps(self):
        op_a = collaborate.DeleteOperation(2, 4)
        op_b = collaborate.DeleteOperation(10, 3)
        op_return = op_a.exclude(op_b)
        assert(op_return.l == op_a.l and op_return.p == (op_a.p + op_b.l))

    #else
    def testExclusion_dd_encloses(self):
        op_a = collaborate.DeleteOperation(10, 1)
        op_b = collaborate.DeleteOperation(5, 2)
        op_return = op_a.exclude(op_b)
        assert((op_return.l == (op_b.p - op_a.p) and op_return.p == op_a.p) and (op_return.sl == (op_a.l - (op_b.p - op_a.p)) and op_return.sp == (op_b.l + op_b.p)))

if __name__ == '__main__':
    unittest.main()
