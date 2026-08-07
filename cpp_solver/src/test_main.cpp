#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

using namespace std;

#include "floor_plan.hpp"

typedef FLOOR_PLAN<short, int> FP;
typedef FP::TREE TR;

static int g_pass = 0, g_fail = 0;

#define CHECK(cond, msg) do { \
  if (cond) { ++g_pass; } \
  else { ++g_fail; cerr << "  [FAIL] " << msg << " (line " << __LINE__ << ")\n"; } \
} while (0)

#define CHECK_EQ(a, b, msg) do { \
  long long va = (a), vb = (b); \
  if (va == vb) { ++g_pass; } \
  else { ++g_fail; cerr << "  [FAIL] " << msg << ": got " << va << " expect " << vb \
                        << " (line " << __LINE__ << ")\n"; } \
} while (0)

static FP make_fp(const vector<tuple<int, int, string>>& blks, int W, int H) {
  return FP(blks, {}, W, H, 0.5f);
}

static bool scan_overlap(const FP& fp, int N, string& err) {
  for (int i = 1; i <= N; ++i)
    for (int j = i + 1; j <= N; ++j) {
      const FP::BLOCK& a = fp.blk(i);
      const FP::BLOCK& b = fp.blk(j);
      if (a._x < b._x + b._w && b._x < a._x + a._w &&
          a._y < b._y + b._h && b._y < a._y + a._h) {
        err = a._name + " vs " + b._name;
        return false;
      }
    }
  return true;
}

static void expect_valid(const FP& fp, const string& tag) {
  string err;
  if (fp.tree().validate_tree(err)) ++g_pass;
  else { ++g_fail; cerr << "  [FAIL] " << tag << ": " << err << " (line " << __LINE__ << ")\n"; }
}

static void expect_invalid(TR& t, const string& tag) {
  string err;
  if (!t.validate_tree(err)) ++g_pass;
  else { ++g_fail; cerr << "  [FAIL] " << tag << ": corruption NOT detected (line " << __LINE__ << ")\n"; }
}

static void test_m1_valid_random_tree() {
  for (int N : {1, 2, 7, 50}) {
    vector<tuple<int, int, string>> specs;
    for (int i = 1; i <= N; ++i)
      specs.emplace_back(1 + i % 37, 1 + (i * 7) % 53, "B" + to_string(i));
    FP fp = make_fp(specs, 10000, 10000);
    fp.init();
    expect_valid(fp, "random tree N=" + to_string(N));
    string err;
    if (scan_overlap(fp, N, err)) ++g_pass;
    else { ++g_fail; cerr << "  [FAIL] random tree N=" << N << " overlap: " << err << "\n"; }
  }
}

static void test_m1_negative_corruptions() {
  const int N = 5;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(3 + i, 2 + i, "B" + to_string(i));
  FP fp = make_fp(specs, 10000, 10000);
  vector<short> P = {1, 0, 1, 2, 3, 4}, L = {0, 2, 0, 0, 0, 0}, R = {0, 0, 0, 0, 0, 0};
  TR base(N, P, L, R);
  {
    FP fp0 = make_fp(specs, 10000, 10000);
    fp0.restore(base);
    fp0.init();
    expect_valid(fp0, "chain baseline");
  }

  TR t = base; t.dbg_set_l(5, 2); expect_invalid(t, "cycle: 5.l=ancestor2");
  t = base; t.dbg_set_p(3, 3);    expect_invalid(t, "self parent: 3.p=3");
  t = base; t.dbg_set_p(2, 0);    expect_invalid(t, "fake root: 2.p=0");
  t = base; t.dbg_set_l(1, 99);   expect_invalid(t, "oob left child");
  t = base; t.dbg_set_r(1, 99);   expect_invalid(t, "oob right child");
  t = base; t.dbg_set_l(3, 4); t.dbg_set_r(3, 4); expect_invalid(t, "duplicate child l==r");
  t = base; t.dbg_set_root(7);    expect_invalid(t, "oob root");
  t = base; t.dbg_set_p(5, 0);    expect_invalid(t, "orphan claim root: 5.p=0");
  t = base; t.dbg_set_l(4, 5); t.dbg_set_l(5, 4); expect_invalid(t, "two-node cycle 4<->5");
}

static void test_m1_fuzz() {
  srand(20260807);
  for (int trial = 0; trial < 3; ++trial) {
    const int N = 5 + trial * 15;
    vector<tuple<int, int, string>> specs;
    for (int i = 1; i <= N; ++i)
      specs.emplace_back(1 + rand() % 30, 1 + rand() % 30, "B" + to_string(i));
    FP fp = make_fp(specs, 10000, 10000);
    string err;
    for (int iter = 0; iter < 20000; ++iter) {
      fp.perturb();
      fp.init();
      if (!fp.tree().validate_tree(err)) {
        ++g_fail;
        cerr << "  [FAIL] fuzz N=" << N << " iter=" << iter << ": " << err << "\n";
        return;
      }
      if (iter % 100 == 0) {
        if (!scan_overlap(fp, N, err)) {
          ++g_fail;
          cerr << "  [FAIL] fuzz N=" << N << " iter=" << iter << " overlap: " << err << "\n";
          return;
        }
        vector<tuple<short, short, short, short>> snap;
        for (int i = 1; i <= N; ++i) {
          const FP::BLOCK& b = fp.blk(i);
          snap.emplace_back(b._x, b._y, b._w, b._h);
        }
        fp.dbg_reset_init();
        fp.init();
        for (int i = 1; i <= N; ++i) {
          const FP::BLOCK& b = fp.blk(i);
          if (b._x != get<0>(snap[i - 1]) || b._y != get<1>(snap[i - 1]) ||
              b._w != get<2>(snap[i - 1]) || b._h != get<3>(snap[i - 1])) {
            ++g_fail;
            cerr << "  [FAIL] fuzz N=" << N << " iter=" << iter
                 << " full re-decode mismatch at block " << i << "\n";
            return;
          }
        }
        ++g_pass;
      }
    }
    ++g_pass;
    cerr << "  [PASS] fuzz N=" << N << " 20000 perturbs, all topology/overlap/decode checks clean\n";
  }
}

static void test_m2_op3_subtree_preservation() {
  const int N = 4;
  vector<short> P = {1, 0, 1, 1, 2}, L = {0, 2, 0, 0, 0}, R = {0, 3, 0, 0, 0};
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(2 + i, 2 + i, "B" + to_string(i));
  TR t(N, P, L, R);
  t.del_from_tree(4);
  t.ins_to_tree(1, 4, true);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  expect_valid(fp, "op3: insert into occupied left slot");
  CHECK_EQ(fp.tree().dbg_p(4), 1, "op3: 4.p == 1");
  CHECK_EQ(fp.tree().dbg_p(2), 4, "op3: old left child 2 re-hung under 4");
  CHECK_EQ(fp.tree().dbg_l(1), 4, "op3: 1.l == 4");
  CHECK_EQ(fp.tree().dbg_r(1), 3, "op3: right subtree intact");
}

static void test_m2_op3_into_former_descendant() {
  const int N = 3;
  vector<short> P = {1, 0, 1, 2}, L = {0, 2, 0, 0}, R = {0, 0, 0, 0};
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(2 + i, 2 + i, "B" + to_string(i));
  TR t(N, P, L, R);
  t.del_from_tree(1);
  t.ins_to_tree(3, 1, true);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  expect_valid(fp, "op3: root re-inserted under former descendant");
  CHECK_EQ(fp.tree().dbg_p(2), 0, "op3: 2 becomes root");
  CHECK_EQ(fp.tree().dbg_l(3), 1, "op3: 3.l == 1");
  CHECK_EQ(fp.tree().dbg_l(2), 3, "op3: 2.l == 3");
  CHECK_EQ(fp.tree().dbg_p(1), 3, "op3: 1.p == 3");
}

static void test_m2_op3_child_carry() {
  const int N = 5;
  vector<short> P = {1, 0, 1, 1, 2, 3}, L = {0, 2, 4, 5, 0, 0}, R = {0, 3, 0, 0, 0, 0};
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(2 + i, 2 + i, "B" + to_string(i));
  TR t(N, P, L, R);
  t.del_from_tree(2);
  t.ins_to_tree(3, 2, true);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  expect_valid(fp, "op3: node with child moved, child must not be lost");
  CHECK_EQ(fp.tree().dbg_l(1), 4, "op3: 2's child 4 promoted to 1.l");
  CHECK_EQ(fp.tree().dbg_p(4), 1, "op3: 4.p == 1");
  CHECK_EQ(fp.tree().dbg_l(3), 2, "op3: 3.l == 2");
  CHECK_EQ(fp.tree().dbg_p(2), 3, "op3: 2.p == 3");
  CHECK_EQ(fp.tree().dbg_l(2), 5, "op3: 3's old child 5 handed to 2");
  CHECK_EQ(fp.tree().dbg_p(5), 2, "op3: 5.p == 2");
}

static void test_m2_op2_swaps() {
  {
    vector<short> P = {1, 0, 1}, L = {0, 2, 0}, R = {0, 0, 0};
    vector<tuple<int, int, string>> specs = {{2, 3, "B1"}, {4, 5, "B2"}};
    TR t(2, P, L, R);
    t.swap_two_nodes(1, 2);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "op2: adjacent parent-child swap");
    CHECK_EQ(fp.tree().dbg_p(2), 0, "op2: new root 2");
    CHECK_EQ(fp.tree().dbg_l(2), 1, "op2: 2.l == 1");
    CHECK_EQ(fp.tree().dbg_p(1), 2, "op2: 1.p == 2");
  }
  {
    vector<short> P = {1, 0, 1, 1}, L = {0, 2, 0, 0}, R = {0, 3, 0, 0};
    vector<tuple<int, int, string>> specs = {{2, 3, "B1"}, {4, 5, "B2"}, {6, 7, "B3"}};
    TR t(3, P, L, R);
    t.swap_two_nodes(2, 3);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "op2: sibling swap (same parent)");
    CHECK_EQ(fp.tree().dbg_l(1), 3, "op2: 1.l == 3");
    CHECK_EQ(fp.tree().dbg_r(1), 2, "op2: 1.r == 2");
  }
  {
    vector<short> P = {1, 0, 1, 2, 3}, L = {0, 2, 0, 0, 0}, R = {0, 0, 0, 0, 0};
    vector<tuple<int, int, string>> specs = {{2, 3, "B1"}, {4, 5, "B2"}, {6, 7, "B3"}, {8, 9, "B4"}};
    TR t(4, P, L, R);
    t.swap_two_nodes(1, 4);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "op2: root vs deep descendant swap");
    CHECK_EQ(fp.tree().dbg_p(4), 0, "op2: 4 is root after swap");
    CHECK_EQ(fp.tree().dbg_l(4), 2, "op2: 4 takes 1's old subtree");
    CHECK_EQ(fp.tree().dbg_p(1), 3, "op2: 1 re-hung under 3");
  }
  {
    vector<short> P = {1, 0, 1, 1, 2, 3}, L = {0, 2, 4, 5, 0, 0}, R = {0, 3, 0, 0, 0, 0};
    vector<tuple<int, int, string>> specs = {{2, 3, "B1"}, {4, 5, "B2"}, {6, 7, "B3"}, {8, 9, "B4"}, {10, 11, "B5"}};
    TR t(5, P, L, R);
    t.swap_two_nodes(2, 3);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "op2: sibling swap with subtrees");
    CHECK_EQ(fp.tree().dbg_l(1), 3, "op2: 1.l == 3");
    CHECK_EQ(fp.tree().dbg_r(1), 2, "op2: 1.r == 2");
    CHECK_EQ(fp.tree().dbg_l(3), 4, "op2: 4 follows 2");
    CHECK_EQ(fp.tree().dbg_l(2), 5, "op2: 5 follows 3");
    CHECK_EQ(fp.tree().dbg_p(4), 3, "op2: 4.p == 3");
    CHECK_EQ(fp.tree().dbg_p(5), 2, "op2: 5.p == 2");
  }
}

static void test_m2_op1_rotate_sync() {
  const int N = 3;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(3 * i, 2 * i, "B" + to_string(i));
  FP fp = make_fp(specs, 10000, 10000);
  TR t = fp.tree();
  t.set_rot(2);
  fp.restore(t);
  CHECK_EQ(fp.blk(2)._w, 4, "op1: w/h swapped after restore");
  CHECK_EQ(fp.blk(2)._h, 6, "op1: w/h swapped after restore");
}

static void test_m3_skyline_user_scenario() {
  vector<tuple<int, int, string>> specs = {{10, 5, "M1"}, {10, 8, "M2"}, {30, 2, "M3"}};
  vector<short> P = {1, 0, 1, 1}, L = {0, 2, 0, 0}, R = {0, 3, 0, 0};
  TR t(3, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  expect_valid(fp, "skyline user scenario");
  CHECK_EQ(fp.blk(2)._x, 10, "M2.x == 10");
  CHECK_EQ(fp.blk(2)._y, 0, "M2.y == 0");
  CHECK_EQ(fp.blk(3)._x, 0, "M3.x == 0");
  CHECK_EQ(fp.blk(3)._y, 8, "M3.y == 8 (pushed by M2, not M1)");
  CHECK_EQ(get<1>(fp.cost(true, true)), 30, "bbox width 30");
  CHECK_EQ(get<2>(fp.cost(true, true)), 10, "bbox height 10");
  string err;
  CHECK(scan_overlap(fp, 3, err), "skyline no overlap");
  CHECK_EQ(fp.tree().dbg_cy().size(), (size_t)1, "contour merged to one segment");
  CHECK_EQ(fp.tree().dbg_cy()[0], 3, "contour holds M3 only");
}

static void test_m3_touching_boundary() {
  vector<tuple<int, int, string>> specs = {{10, 5, "M1"}, {10, 8, "M2"}};
  vector<short> P = {1, 0, 1}, L = {0, 2, 0}, R = {0, 0, 0};
  TR t(2, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  CHECK_EQ(fp.blk(2)._x, 10, "touching: M2.x == 10");
  CHECK_EQ(fp.blk(2)._y, 0, "touching: M2.y == 0 (edge-adjacent must not stack)");
}

static void test_m3_stacking() {
  vector<tuple<int, int, string>> specs = {{10, 5, "M1"}, {10, 8, "M2"}, {2, 1, "M4"}};
  vector<short> P = {1, 0, 1, 2}, L = {0, 2, 0, 0}, R = {0, 0, 3, 0};
  TR t(3, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  CHECK_EQ(fp.blk(3)._x, 10, "stacking: M4.x == 10");
  CHECK_EQ(fp.blk(3)._y, 8, "stacking: M4.y == 8 (on M2)");
}

static void test_m3_right_child_over_multi_segment_left_subtree() {
  vector<tuple<int, int, string>> specs = {{10, 5, "M1"}, {10, 8, "M2"}, {2, 1, "M4"}, {6, 1, "M5"}};
  vector<short> P = {1, 0, 1, 2, 1}, L = {0, 2, 0, 0, 0}, R = {0, 4, 3, 0, 0};
  TR t(4, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  expect_valid(fp, "right child over multi-segment left subtree");
  string err;
  CHECK(scan_overlap(fp, 4, err), "M5 must not overlap M1: " + err);
  CHECK_EQ(fp.blk(3)._x, 10, "M4.x == 10");
  CHECK_EQ(fp.blk(3)._y, 8, "M4.y == 8");
  CHECK_EQ(fp.blk(4)._x, 0, "M5.x == 0");
  CHECK_EQ(fp.blk(4)._y, 5, "M5.y == 5 (must sit on M1)");
}

static void test_m3_wide_right_child_over_left_subtree() {
  vector<tuple<int, int, string>> specs = {{10, 5, "P"}, {4, 4, "A"}, {4, 3, "B"}, {30, 2, "R"}};
  vector<short> P = {1, 0, 1, 2, 1}, L = {0, 2, 3, 0, 0}, R = {0, 4, 0, 0, 0};
  TR t(4, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  expect_valid(fp, "wide right child over left subtree");
  string err;
  CHECK(scan_overlap(fp, 4, err), "R must not overlap P: " + err);
  CHECK_EQ(fp.blk(4)._x, 0, "R.x == 0");
  CHECK_EQ(fp.blk(4)._y, 5, "R.y == 5 (on P, tallest of P/A/B)");
}

static void test_m4_redecode_idempotence() {
  srand(42);
  const int N = 30;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(1 + rand() % 25, 1 + rand() % 25, "B" + to_string(i));
  FP fp = make_fp(specs, 10000, 10000);
  for (int cyc = 0; cyc < 3; ++cyc) {
    for (int i = 0; i < 500; ++i) { fp.perturb(); fp.init(); }
    fp.init();
    vector<tuple<short, short>> snap;
    for (int i = 1; i <= N; ++i) snap.emplace_back(fp.blk(i)._x, fp.blk(i)._y);
    fp.dbg_reset_init();
    fp.init();
    bool same = true;
    for (int i = 1; i <= N; ++i)
      if (fp.blk(i)._x != get<0>(snap[i - 1]) || fp.blk(i)._y != get<1>(snap[i - 1])) same = false;
    CHECK(same, "re-decode idempotence cycle " + to_string(cyc));
  }
}

static void test_parser_real_data() {
  ifstream fblcks("../data/raw/n100.blocks");
  ifstream fnets("../data/raw/n100.nets");
  ifstream fpl("../data/raw/n100.pl");
  if (!fblcks || !fnets || !fpl) {
    ++g_fail;
    cerr << "  [FAIL] missing ../data/raw/n100.* (run from cpp_solver/)\n";
    return;
  }
  FP fp(fnets, fblcks, fpl, "", 885, 100, 334, 0.5f, 0.15f);
  CHECK_EQ(fp.Nblcks(), 100, "n100 blocks count");
  CHECK_EQ(fp.Ntrmns(), 334, "n100 terminal count");
  CHECK(fp.blk(1)._name == "b0", "b0 is id 1");
  CHECK_EQ(fp.blk(1)._w, 43, "b0 width from corners");
  CHECK_EQ(fp.blk(1)._h, 33, "b0 height from corners");
  CHECK_EQ(fp.blk(2)._w, 65, "b1 width");
  CHECK_EQ(fp.blk(2)._h, 37, "b1 height");
  CHECK_EQ(fp.blk(101)._x, 0, "terminal p1 x from .pl");
  CHECK_EQ(fp.blk(101)._y, 0, "terminal p1 y from .pl");
  CHECK_EQ(fp.blk(102)._x, 4, "terminal p2 x from .pl");
  CHECK_EQ(fp.blk(102)._y, 0, "terminal p2 y from .pl");
  long long total = 0;
  for (int i = 1; i <= 100; ++i) total += (long long)fp.blk(i)._w * fp.blk(i)._h;
  int expected_w = (int)ceil(sqrt((double)total * 1.15));
  CHECK_EQ(fp.W(), expected_w, "W = ceil(sqrt(total_area * 1.15))");
  CHECK_EQ(fp.H(), fp.W(), "square outline");
  fp.init();
  expect_valid(fp, "n100 initial random tree");
  string err;
  CHECK(scan_overlap(fp, 100, err), "n100 no overlap: " + err);
}

int main() {
  cerr << "== M1: topology invariant ==\n";
  test_m1_valid_random_tree();
  test_m1_negative_corruptions();
  test_m1_fuzz();
  cerr << "== M2: operator corner cases ==\n";
  test_m2_op3_subtree_preservation();
  test_m2_op3_into_former_descendant();
  test_m2_op3_child_carry();
  test_m2_op2_swaps();
  test_m2_op1_rotate_sync();
  cerr << "== M3: skyline contour ==\n";
  test_m3_skyline_user_scenario();
  test_m3_touching_boundary();
  test_m3_stacking();
  test_m3_right_child_over_multi_segment_left_subtree();
  test_m3_wide_right_child_over_left_subtree();
  cerr << "== M4: full alignment ==\n";
  test_m4_redecode_idempotence();
  cerr << "== parser: real data ==\n";
  test_parser_real_data();
  cerr << "--------------------------------\n";
  cerr << "PASS: " << g_pass << "  FAIL: " << g_fail << "\n";
  return g_fail ? 1 : 0;
}
