#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <sys/wait.h>
#include <tuple>
#include <unistd.h>
#include <vector>

using namespace std;

#include "floor_plan.hpp"
#include "test_oracle.hpp"
#include "sa.hpp"

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
  vector<short> P = {1, 0, 1, 2, 3, 4}, L = {0, 2, 3, 4, 5, 0}, R = {0, 0, 0, 0, 0, 0};
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
  vector<short> P = {1, 0, 1, 2}, L = {0, 2, 3, 0}, R = {0, 0, 0, 0};
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
    vector<short> P = {1, 0, 1, 2, 3}, L = {0, 2, 3, 4, 0}, R = {0, 0, 0, 0, 0};
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
    CHECK_EQ(fp.tree().dbg_l(2), 4, "op2: 2 keeps own child 4");
    CHECK_EQ(fp.tree().dbg_l(3), 5, "op2: 3 keeps own child 5");
    CHECK_EQ(fp.tree().dbg_p(4), 2, "op2: 4.p == 2");
    CHECK_EQ(fp.tree().dbg_p(5), 3, "op2: 5.p == 3");
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
  struct Case { const char* pre; int nb, nt, nn; int w, h; };
  Case cases[] = {
    {"n100", 100, 334, 885, 43, 33},
    {"n200", 200, 564, 1585, 36, 16},
    {"n300", 300, 569, 1893, 27, 15},
  };
  for (auto& c : cases) {
    string pre = c.pre;
    ifstream fblcks("../data/raw/" + pre + ".blocks");
    ifstream fnets("../data/raw/" + pre + ".nets");
    ifstream fpl("../data/raw/" + pre + ".pl");
    if (!fblcks || !fnets || !fpl) {
      ++g_fail;
      cerr << "  [FAIL] missing ../data/raw/" << pre << ".* (run from cpp_solver/)\n";
      return;
    }
    FP fp(fnets, fblcks, fpl, "", c.nn, c.nb, c.nt, 0.5f, 0.15f);
    CHECK_EQ(fp.Nblcks(), c.nb, pre + " block count");
    CHECK_EQ(fp.Ntrmns(), c.nt, pre + " terminal count");
    CHECK_EQ(fp.blk(1)._w, c.w, pre + " b0 width");
    CHECK_EQ(fp.blk(1)._h, c.h, pre + " b0 height");
    CHECK_EQ(fp.blk(c.nb + 1)._x, 0, pre + " p1 x");
    CHECK_EQ(fp.blk(c.nb + 1)._y, 0, pre + " p1 y");
    long long total = 0;
    for (int i = 1; i <= c.nb; ++i) total += (long long)fp.blk(i)._w * fp.blk(i)._h;
    int expected_w = (int)ceil(sqrt((double)total * 1.15));
    CHECK_EQ(fp.W(), expected_w, pre + " W = ceil(sqrt(total_area*1.15))");
    CHECK_EQ(fp.H(), fp.W(), pre + " square outline");
    fp.init();
    expect_valid(fp, pre + " initial random tree");
    string err;
    CHECK(scan_overlap(fp, c.nb, err), pre + " no overlap: " + err);
  }
}

static void test_o1_definition_verify() {
  srand(11);
  for (int trial = 0; trial < 3; ++trial) {
    const int N = 5 + trial * 15;
    vector<tuple<int, int, string>> specs;
    for (int i = 1; i <= N; ++i)
      specs.emplace_back(1 + rand() % 40, 1 + rand() % 40, "B" + to_string(i));
    FP fp = make_fp(specs, 10000, 10000);
    for (int iter = 0; iter < 300; ++iter) { fp.perturb(); fp.init(); }
    string err;
    CHECK(verify_layout_definition(fp, N, err), "O1 def verify N=" + to_string(N) + ": " + err);
  }
}

static void test_o2_differential_random() {
  srand(2026);
  for (int trial = 0; trial < 5; ++trial) {
    const int N = 3 + trial * 8;
    vector<tuple<int, int, string>> specs;
    for (int i = 1; i <= N; ++i)
      specs.emplace_back(1 + rand() % 40, 1 + rand() % 40, "B" + to_string(i));
    FP fp = make_fp(specs, 10000, 10000);
    for (int iter = 0; iter < 2000; ++iter) {
      fp.perturb();
      fp.init();
      vector<tuple<int, int, string>> cur;
      for (int i = 1; i <= N; ++i)
        cur.emplace_back(fp.blk(i)._w, fp.blk(i)._h, "B" + to_string(i));
      vector<tuple<int, int, int, int>> ref;
      string err;
      ref_decode(fp.tree(), cur, N, ref, err);
      if (!err.empty()) { ++g_fail; cerr << "  [FAIL] O2 ref err " << err << "\n"; return; }
      for (int i = 1; i <= N; ++i) {
        const FP::BLOCK& b = fp.blk(i);
        if (b._x != get<0>(ref[i - 1]) || b._y != get<1>(ref[i - 1]) ||
            b._w != get<2>(ref[i - 1]) || b._h != get<3>(ref[i - 1])) {
          ++g_fail;
          cerr << "  [FAIL] O2 differential N=" << N << " iter=" << iter
               << " block " << i << " got (" << b._x << "," << b._y << ","
               << b._w << "," << b._h << ") ref (" << get<0>(ref[i - 1]) << ","
               << get<1>(ref[i - 1]) << "," << get<2>(ref[i - 1]) << ","
               << get<3>(ref[i - 1]) << ")\n";
          return;
        }
      }
      if (iter % 400 == 0) ++g_pass;
    }
    ++g_pass;
    cerr << "  [PASS] O2 differential N=" << N << " 2000 trees exact\n";
  }
}

static void test_o2_differential_real() {
  for (auto& pre : {"n100", "n200"}) {
    string p = pre;
    ifstream fblcks("../data/raw/" + p + ".blocks");
    ifstream fnets("../data/raw/" + p + ".nets");
    ifstream fpl("../data/raw/" + p + ".pl");
    if (!fblcks || !fnets || !fpl) { ++g_fail; cerr << "  [FAIL] O2 missing real data\n"; return; }
    int Nnets = read_labeled_int(fnets);
    int Nblcks = read_labeled_int(fblcks);
    int Ntrmns = read_labeled_int(fblcks);
    fnets.seekg(0);
    fblcks.seekg(0);
    FP fp(fnets, fblcks, fpl, "", Nnets, Nblcks, Ntrmns, 0.5f, 0.15f);
    for (int iter = 0; iter < 300; ++iter) {
      fp.perturb();
      fp.init();
      vector<tuple<int, int, string>> cur;
      for (int i = 1; i <= Nblcks; ++i)
        cur.emplace_back(fp.blk(i)._w, fp.blk(i)._h, fp.blk(i)._name);
      vector<tuple<int, int, int, int>> ref;
      string err;
      ref_decode(fp.tree(), cur, Nblcks, ref, err);
      if (!err.empty()) { ++g_fail; cerr << "  [FAIL] O2 real ref err " << err << "\n"; return; }
      for (int i = 1; i <= Nblcks; ++i) {
        const FP::BLOCK& b = fp.blk(i);
        if (b._x != get<0>(ref[i - 1]) || b._y != get<1>(ref[i - 1]) ||
            b._w != get<2>(ref[i - 1]) || b._h != get<3>(ref[i - 1])) {
          ++g_fail;
          cerr << "  [FAIL] O2 real " << p << " iter=" << iter << " block "
               << b._name << " mismatch\n";
          return;
        }
      }
    }
    ++g_pass;
    cerr << "  [PASS] O2 differential " << p << " 300 trees exact\n";
  }
}

static void test_o3_hpwl_handcrafted() {
  ofstream f1("/tmp/o3.blocks");
  f1 << "NumHardBlocks : 2\nNumTerminals : 1\n"
     << "b1 block 4 (0, 0) (0, 5) (10, 5) (10, 0)\n"
     << "b2 block 4 (0, 0) (0, 8) (10, 8) (10, 0)\n"
     << "p1 terminal\n";
  f1.close();
  ofstream f2("/tmp/o3.nets");
  f2 << "NumNets : 2\nNumPins : 5\n"
     << "NetDegree : 2\nb1\nb2\n"
     << "NetDegree : 3\np1\nb1\nb2\n";
  f2.close();
  ofstream f3("/tmp/o3.pl");
  f3 << "p1 0 0\n";
  f3.close();
  ifstream fblcks("/tmp/o3.blocks");
  ifstream fnets("/tmp/o3.nets");
  ifstream fpl("/tmp/o3.pl");
  FP fp(fnets, fblcks, fpl, "", 2, 2, 1, 0.5f, 0.15f);
  vector<short> P = {1, 0, 1}, L = {0, 2, 0}, R = {0, 0, 0};
  TR t(2, P, L, R);
  fp.restore(t);
  fp.init();
  CHECK_EQ(fp.blk(1)._x, 0, "O3 b1.x");
  CHECK_EQ(fp.blk(1)._y, 0, "O3 b1.y");
  CHECK_EQ(fp.blk(2)._x, 10, "O3 b2.x");
  CHECK_EQ(fp.blk(2)._y, 0, "O3 b2.y");
  CHECK_EQ(oracle_hpwl(fp), 61LL, "O3 handcrafted hpwl=61 (20+3 + 30+8)");
  CHECK_EQ((long long)get<0>(fp.cost()), 61LL, "O3 cost() hpwl matches oracle");
  CHECK_EQ((long long)get<1>(fp.cost()), 20, "O3 bbox w=20");
  CHECK_EQ((long long)get<2>(fp.cost()), 8, "O3 bbox h=8");
}

static void write_random_instance(const string& pre, int N, int Nterms, int Nnets,
                                  vector<tuple<int, int, string>>& specs,
                                  vector<tuple<int, int, string>>& terms) {
  specs.clear();
  terms.clear();
  ofstream fb("/tmp/" + pre + ".blocks");
  fb << "NumHardBlocks : " << N << "\nNumTerminals : " << Nterms << "\n";
  for (int i = 1; i <= N; ++i) {
    int w = 1 + rand() % 30, h = 1 + rand() % 30;
    specs.emplace_back(w, h, "b" + to_string(i));
    fb << "b" << i << " block 4 (0, 0) (0, " << h << ") (" << w << ", " << h
       << ") (" << w << ", 0)\n";
  }
  for (int t = 1; t <= Nterms; ++t) {
    terms.emplace_back(0, 0, "p" + to_string(t));
    fb << "p" << t << " terminal\n";
  }
  fb.close();
  ofstream fn("/tmp/" + pre + ".nets");
  fn << "NumNets : " << Nnets << "\nNumPins : 0\n";
  for (int n = 0; n < Nnets; ++n) {
    int deg = 2 + rand() % 4;
    fn << "NetDegree : " << deg << "\n";
    for (int d = 0; d < deg; ++d) {
      bool term = (Nterms > 0) && (rand() % 3 == 0);
      if (term) fn << "p" << 1 + rand() % Nterms << "\n";
      else fn << "b" << 1 + rand() % N << "\n";
    }
  }
  fn.close();
  ofstream fp("/tmp/" + pre + ".pl");
  for (int t = 1; t <= Nterms; ++t) {
    int x = rand() % 500, y = rand() % 500;
    get<0>(terms[t - 1]) = x;
    get<1>(terms[t - 1]) = y;
    fp << "p" << t << " " << x << " " << y << "\n";
  }
  fp.close();
}

static void test_o3_hpwl_random() {
  srand(313);
  for (int trial = 0; trial < 3; ++trial) {
    const int N = 8 + trial * 12, NT = 4, NN = 40;
    vector<tuple<int, int, string>> specs, terms;
    write_random_instance("o3r", N, NT, NN, specs, terms);
    ifstream fblcks("/tmp/o3r.blocks");
    ifstream fnets("/tmp/o3r.nets");
    ifstream fpl("/tmp/o3r.pl");
    FP fp(fnets, fblcks, fpl, "", NN, N, NT, 0.5f, 0.15f);
    long long lb = 0;
    for (auto& s : specs) lb += (long long)get<0>(s) * get<1>(s);
    for (int iter = 0; iter < 500; ++iter) {
      fp.perturb();
      fp.init();
      if (oracle_hpwl(fp) != (long long)get<0>(fp.cost())) {
        ++g_fail;
        cerr << "  [FAIL] O3 random hpwl mismatch N=" << N << " iter=" << iter
             << " oracle=" << oracle_hpwl(fp) << " cost=" << get<0>(fp.cost()) << "\n";
        return;
      }
      if (iter % 100 == 0) {
        long long area = (long long)get<1>(fp.cost()) * get<2>(fp.cost());
        CHECK(area >= lb, "O3 area >= sum of block areas");
        string err;
        CHECK(verify_layout_definition(fp, N, err), "O3 def valid: " + err);
        ++g_pass;
      }
    }
    ++g_pass;
    cerr << "  [PASS] O3 random hpwl oracle N=" << N << " 500 trees\n";
  }
}

static void test_o3_hpwl_real() {
  ifstream fblcks("../data/raw/n100.blocks");
  ifstream fnets("../data/raw/n100.nets");
  ifstream fpl("../data/raw/n100.pl");
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  FP fp(fnets, fblcks, fpl, "", Nnets, Nblcks, Ntrmns, 0.5f, 0.15f);
  for (int iter = 0; iter < 300; ++iter) {
    fp.perturb();
    fp.init();
    if (oracle_hpwl(fp) != (long long)get<0>(fp.cost())) {
      ++g_fail;
      cerr << "  [FAIL] O3 real hpwl mismatch iter=" << iter << "\n";
      return;
    }
  }
  ++g_pass;
  cerr << "  [PASS] O3 real n100 hpwl oracle 300 trees\n";
}

static void test_o4_operator_semantics() {
  const int N = 5;
  vector<short> P = {1, 0, 1, 1, 2, 3}, L = {0, 2, 4, 5, 0, 0}, R = {0, 3, 0, 0, 0, 0};
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(2 + i, 2 + i, "B" + to_string(i));

  {
    TR t(N, P, L, R);
    vector<int> s3, s5;
    collect_subtree(t, 3, s3);
    collect_subtree(t, 5, s5);
    t.swap_two_nodes(3, 5);
    vector<int> s3b, s5b;
    collect_subtree(t, 3, s3b);
    collect_subtree(t, 5, s5b);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "O4 swap(3,5) valid (adjacent parent-child path)");
    CHECK_EQ(t.dbg_p(5), 1, "O4 5 took 3's slot (1,R)");
    CHECK_EQ(t.dbg_r(1), 5, "O4 1.r == 5");
    CHECK_EQ(t.dbg_p(3), 5, "O4 3 re-hung under 5");
    CHECK_EQ(t.dbg_l(5), 3, "O4 5.l == 3");
    vector<int> u1 = s3, u2 = s5;
    u1.insert(u1.end(), s5.begin(), s5.end());
    vector<int> v1 = s3b, v2 = s5b;
    v1.insert(v1.end(), s5b.begin(), s5b.end());
    sort(u1.begin(), u1.end());
    sort(v1.begin(), v1.end());
    u1.erase(unique(u1.begin(), u1.end()), u1.end());
    v1.erase(unique(v1.begin(), v1.end()), v1.end());
    CHECK(u1 == v1, "O4 swap(3,5): node-set union preserved");
  }
  {
    TR t(N, P, L, R);
    vector<int> s2, s5;
    collect_subtree(t, 2, s2);
    collect_subtree(t, 5, s5);
    t.swap_two_nodes(2, 5);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "O4 swap(2,5) valid (non-adjacent slot exchange)");
    CHECK_EQ(t.dbg_p(5), 1, "O4 5 took 2's slot (1,L)");
    CHECK_EQ(t.dbg_l(1), 5, "O4 1.l == 5");
    CHECK_EQ(t.dbg_p(2), 3, "O4 2 took 5's slot (3,L)");
    CHECK_EQ(t.dbg_l(3), 2, "O4 3.l == 2");
    vector<int> s2b, s5b;
    collect_subtree(t, 2, s2b);
    collect_subtree(t, 5, s5b);
    vector<int> u1 = s2, v1 = s2b;
    u1.insert(u1.end(), s5.begin(), s5.end());
    v1.insert(v1.end(), s5b.begin(), s5b.end());
    sort(u1.begin(), u1.end());
    sort(v1.begin(), v1.end());
    u1.erase(unique(u1.begin(), u1.end()), u1.end());
    v1.erase(unique(v1.begin(), v1.end()), v1.end());
    CHECK(u1 == v1, "O4 swap(2,5): node-set union preserved");
    CHECK_EQ(s2b.size() + s5b.size(), s2.size() + s5.size(), "O4 swap(2,5): no subtree members lost");
  }
  {
    TR t(N, P, L, R);
    vector<int> s2;
    collect_subtree(t, 2, s2);
    t.del_from_tree(2);
    t.ins_to_tree(3, 2, true);
    FP fp = make_fp(specs, 10000, 10000);
    fp.restore(t);
    fp.init();
    expect_valid(fp, "O4 del+ins valid");
    CHECK_EQ(t.dbg_p(2), 3, "O4 2.p == 3");
    CHECK_EQ(t.dbg_l(3), 2, "O4 3.l == 2");
    CHECK_EQ(t.dbg_l(2), 5, "O4 2 took 3's old left child 5");
    CHECK_EQ(t.dbg_p(5), 2, "O4 5.p == 2");
    CHECK_EQ(t.dbg_l(1), 4, "O4 2's old child 4 promoted to 1.l");
    CHECK_EQ(t.dbg_p(4), 1, "O4 4.p == 1");
    CHECK_EQ(s2.size(), (size_t)2, "O4 old subtree(2) had 2 members");
  }
}

static void test_o5_sa_reproducible_and_monotone() {
  srand(1234);
  const int N = 20;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(1 + rand() % 30, 1 + rand() % 30, "B" + to_string(i));
  const int k = 2, rnd = 2 * N + 20;
  const float c = 100 - N;
  srand(1234);
  FP fp1 = make_fp(specs, 1000, 1000);
  SA<short, int> sa1(fp1, N, fp1.W(), fp1.H(), fp1.R(), 0.9f, 0.5f, 0.1f, 0.5f);
  sa1.run(k, rnd, c);
  auto res1 = sa1.run2(k, rnd, c);
  srand(1234);
  FP fp2 = make_fp(specs, 1000, 1000);
  SA<short, int> sa2(fp2, N, fp2.W(), fp2.H(), fp2.R(), 0.9f, 0.5f, 0.1f, 0.5f);
  sa2.run(k, rnd, c);
  auto res2 = sa2.run2(k, rnd, c);
  CHECK(res1.first == res2.first, "O5 reproducible final cost");
  const TR& t1 = res1.second;
  const TR& t2 = res2.second;
  bool same = t1.dbg_root() == t2.dbg_root();
  for (int i = 1; i <= N && same; ++i)
    same = t1.dbg_p(i) == t2.dbg_p(i) && t1.dbg_l(i) == t2.dbg_l(i) &&
           t1.dbg_r(i) == t2.dbg_r(i) && t1.rot(i) == t2.rot(i);
  CHECK(same, "O5 reproducible best tree");
  bool mono = true;
  const auto& h1 = sa1.dbg_hist();
  int seg_jumps = 0;
  bool in_run2 = false;
  for (size_t i = 1; i < h1.size(); ++i) {
    if (h1[i] == -1.0f) { in_run2 = true; seg_jumps = 0; continue; }
    if (h1[i - 1] == -1.0f) continue;
    if (h1[i] > h1[i - 1]) ++seg_jumps;
    if (seg_jumps > (in_run2 ? 0 : 1)) mono = false;
  }
  CHECK(mono, "O5 best-cost history non-increasing per phase (run: <=1 forced first-feasible jump, run2: strict)");
  fp2.restore(res2.second);
  fp2.init();
  string err;
  CHECK(verify_layout_definition(fp2, N, err), "O5 final solution legal: " + err);
}

static void test_o5_vs_bruteforce() {
  srand(555);
  for (int trial = 0; trial < 5; ++trial) {
    const int N = 4;
    vector<pair<int, int>> wh;
    for (int i = 1; i <= N; ++i) wh.emplace_back(1 + rand() % 8, 1 + rand() % 8);
    long long opt = brute_area_opt(N, wh);
    vector<tuple<int, int, string>> specs;
    for (int i = 1; i <= N; ++i)
      specs.emplace_back(wh[i - 1].first, wh[i - 1].second, "B" + to_string(i));
    FP fp = make_fp(specs, 10000, 10000);
    SA<short, int> sa(fp, N, 10000, 10000, 1.0f, 0.9f, 0.5f, 0.1f, 0.5f);
    const int k = 2, rnd = 2 * N + 20;
    sa.run(k, rnd, 96);
    auto res = sa.run2(k, rnd, 96);
    fp.restore(res.second);
    fp.init();
    long long area = (long long)get<1>(fp.cost()) * get<2>(fp.cost());
    long long lb = 0;
    for (auto& p : wh) lb += (long long)p.first * p.second;
    CHECK(area >= lb, "O5 brute: SA area >= block area sum");
    CHECK(area <= opt + opt / 4, "O5 brute: SA within 25% of exhaustive optimum");
    string err;
    CHECK(verify_layout_definition(fp, N, err), "O5 brute: legal: " + err);
  }
}

static void test_o5_end_to_end_n100() {
  srand(20260808);
  ifstream fblcks("../data/raw/n100.blocks");
  ifstream fnets("../data/raw/n100.nets");
  ifstream fpl("../data/raw/n100.pl");
  if (!fblcks || !fnets || !fpl) { ++g_fail; cerr << "  [FAIL] O5 e2e missing data\n"; return; }
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  solve<short, int>(fnets, fblcks, fpl, "/tmp/o5_e2e.rpt", Nnets, Nblcks, Ntrmns,
                    0.5f, 0.15f);
  ifstream in("/tmp/o5_e2e.rpt");
  string text((istreambuf_iterator<char>(in)), istreambuf_iterator<char>());
  long long area, hpwl;
  int W, H;
  vector<tuple<string, int, int, int, int>> blocks;
  CHECK(parse_rpt(text, area, W, H, hpwl, blocks), "O5 e2e rpt parses");
  CHECK_EQ(blocks.size(), (size_t)100, "O5 e2e 100 blocks in rpt");
  map<string, pair<int, int>> dims;
  long long total = 0;
  {
    ifstream fb2("../data/raw/n100.blocks");
    string line;
    while (getline(fb2, line)) {
      if (line.find("block 4") == string::npos) continue;
      for (char& c : line) if (c == '(' || c == ')' || c == ',') c = ' ';
      istringstream iss(line);
      string name, type;
      int nc;
      iss >> name >> type >> nc;
      int mnx = 1 << 28, mny = 1 << 28, mxx = 0, mxy = 0;
      for (int i = 0; i < nc; ++i) {
        int x, y; iss >> x >> y;
        mnx = min(mnx, x); mxx = max(mxx, x);
        mny = min(mny, y); mxy = max(mxy, y);
      }
      dims[name] = {mxx - mnx, mxy - mny};
      total += (long long)(mxx - mnx) * (mxy - mny);
    }
  }
  int outline = (int)ceil(sqrt((double)total * 1.15));
  int maxx = 0, maxy = 0;
  bool size_ok = true, overlap = false;
  for (auto& b : blocks) {
    int w = get<3>(b) - get<1>(b), h = get<4>(b) - get<2>(b);
    auto it = dims.find(get<0>(b));
    if (it == dims.end() ||
        min(w, h) != min(it->second.first, it->second.second) ||
        max(w, h) != max(it->second.first, it->second.second))
      size_ok = false;
    maxx = max(maxx, get<3>(b));
    maxy = max(maxy, get<4>(b));
  }
  for (size_t i = 0; i < blocks.size() && !overlap; ++i)
    for (size_t j = i + 1; j < blocks.size() && !overlap; ++j) {
      const auto& a = blocks[i];
      const auto& b = blocks[j];
      if (get<1>(a) < get<3>(b) && get<1>(b) < get<3>(a) &&
          get<2>(a) < get<4>(b) && get<2>(b) < get<4>(a))
        overlap = true;
    }
  CHECK(size_ok, "O5 e2e all block dimensions preserved");
  CHECK(!overlap, "O5 e2e no overlap in rpt");
  CHECK_EQ(maxx, W, "O5 e2e bbox w matches rpt header");
  CHECK_EQ(maxy, H, "O5 e2e bbox h matches rpt header");
  CHECK_EQ(area, (long long)W * H, "O5 e2e area == W*H");
  CHECK(maxx <= outline && maxy <= outline, "O5 e2e within outline");
}

static void test_o6_node_packing_limits() {
  TR t(5);
  t.dbg_set_l(1, 1023);
  t.dbg_set_r(1, 1023);
  t.dbg_set_p(1, 1023);
  CHECK_EQ(t.dbg_l(1), 1023, "O6: 10-bit l max round-trip");
  CHECK_EQ(t.dbg_r(1), 1023, "O6: 10-bit r max round-trip");
  CHECK_EQ(t.dbg_p(1), 1023, "O6: 10-bit p max round-trip");
  t.set_rot(1);
  CHECK(t.rot(1), "O6: rot set");
  t.set_rot(1);
  CHECK(!t.rot(1), "O6: rot clear");
  srand(1);
  TR big(1023);
  string err;
  CHECK(big.validate_tree(err), "O6: 1023-node tree valid: " + err);
}

static void test_o6_rpt_format() {
  srand(7);
  vector<tuple<int, int, string>> specs = {{10, 5, "B1"}, {10, 8, "B2"}, {30, 2, "B3"}};
  vector<short> P = {1, 0, 1, 1}, L = {0, 2, 0, 0}, R = {0, 3, 0, 0};
  TR t(3, P, L, R);
  FP fp = make_fp(specs, 1000, 1000);
  fp.restore(t);
  fp.init();
  ostringstream ss;
  fp.output(ss);
  long long area, hpwl;
  int W, H;
  vector<tuple<string, int, int, int, int>> blocks;
  CHECK(parse_rpt(ss.str(), area, W, H, hpwl, blocks), "O6 rpt parses");
  CHECK_EQ(blocks.size(), (size_t)3, "O6 rpt block count");
  CHECK_EQ(W, 30, "O6 rpt W = 30");
  CHECK_EQ(H, 10, "O6 rpt H = 10");
  CHECK_EQ(area, 300LL, "O6 rpt area = 300");
  CHECK_EQ(get<1>(blocks[0]), 0, "O6 B1.x1");
  CHECK_EQ(get<3>(blocks[0]) - get<1>(blocks[0]), 10, "O6 B1 w preserved");
  CHECK_EQ(get<4>(blocks[0]) - get<2>(blocks[0]), 5, "O6 B1 h preserved");
  CHECK_EQ(get<2>(blocks[2]), 8, "O6 B3.y == 8");
}

static void test_d1_n1_and_empty_rotable() {
  srand(5);
  FP fp = make_fp({{10, 5, "B1"}}, 100, 100);
  for (int i = 0; i < 500; ++i) { fp.perturb(); fp.init(); }
  CHECK(true, "D1: N=1 perturb 500x no hang (rand()%0 guards)");
  string err;
  CHECK(verify_layout_definition(fp, 1, err), "D1: N=1 layout legal");
  ofstream fb("/tmp/d1.blocks");
  fb << "NumHardBlocks : 3\nNumTerminals : 0\n";
  fb << "b1 block 4 (0,0) (0,50) (300,50) (300,0)\n";
  fb << "b2 block 4 (0,0) (0,60) (280,60) (280,0)\n";
  fb << "b3 block 4 (0,0) (0,40) (260,40) (260,0)\n";
  fb.close();
  ofstream fn("/tmp/d1.nets");
  fn << "NumNets : 0\nNumPins : 0\n";
  fn.close();
  ofstream fpl("/tmp/d1.pl");
  fpl.close();
  ifstream fb2("/tmp/d1.blocks");
  ifstream fn2("/tmp/d1.nets");
  ifstream fpl2("/tmp/d1.pl");
  FP fp2(fn2, fb2, fpl2, "", 0, 3, 0, 0.5f, 0.15f);
  for (int i = 0; i < 2000; ++i) { fp2.perturb(); fp2.init(); }
  CHECK(true, "D1: empty _rotable perturb 2000x no crash");
  fp2.dbg_rotate();
  fp2.dbg_rotate();
  CHECK(true, "D1: dbg_rotate on empty _rotable safe (guard)");
}

static void test_d1_big_tree_stress_1023() {
  srand(77);
  const int N = 1023;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i)
    specs.emplace_back(1 + rand() % 20, 1 + rand() % 20, "B" + to_string(i));
  FP fp = make_fp(specs, 50000, 50000);
  string err;
  for (int iter = 0; iter < 20000; ++iter) {
    fp.perturb();
    fp.init();
    if (!fp.tree().validate_tree(err)) {
      ++g_fail;
      cerr << "  [FAIL] D1 1023-stress iter=" << iter << ": " << err << "\n";
      return;
    }
    if (iter % 500 == 0) {
      if (!scan_overlap(fp, N, err)) {
        ++g_fail;
        cerr << "  [FAIL] D1 1023-stress iter=" << iter << " overlap: " << err << "\n";
        return;
      }
    }
  }
  ++g_pass;
  cerr << "  [PASS] D1: 1023-node 20k perturb stress clean\n";
}

static void test_d1_deep_chain_recursion() {
  vector<short> P(1030, 0), L(1030, 0), R(1030, 0);
  for (int i = 1; i <= 1023; ++i) { P[i] = i - 1; L[i - 1] = i; }
  P[0] = 1;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= 1023; ++i) specs.emplace_back(1 + i % 5, 1 + (i * 3) % 5, "B" + to_string(i));
  TR t(1023, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  string err;
  CHECK(fp.tree().validate_tree(err), "D1: 1023-chain tree valid: " + err);
  CHECK(verify_layout_definition(fp, 1023, err), "D1: 1023-chain decode legal: " + err);
}

static bool reachable_excluding(const TR& t, int N, int victim, string& err) {
  const short root = t.dbg_root();
  if (root < 1 || root > N || root == victim) { err = "root invalid"; return false; }
  vector<char> seen(N + 1, 0);
  vector<int> stk(1, root);
  seen[root] = 1;
  int cnt = 0;
  while (!stk.empty()) {
    int u = stk.back();
    stk.pop_back();
    ++cnt;
    for (int c : {t.dbg_l(u), t.dbg_r(u)}) {
      if (c == 0) continue;
      if (c == victim) { err = "victim still linked as child"; return false; }
      if (seen[c]) { err = "cycle"; return false; }
      if (c > N || c < 1) { err = "oob child"; return false; }
      seen[c] = 1;
      stk.push_back(c);
    }
  }
  for (int i = 1; i <= N; ++i)
    if (i != victim && !seen[i]) { err = "unreachable node " + to_string(i); return false; }
  if (cnt != N - 1) { err = "count mismatch"; return false; }
  return true;
}

static void test_d2_delete_all_two_child_nodes() {
  const int N = 15;
  vector<short> P(N + 1, 0), L(N + 1, 0), R(N + 1, 0);
  P[0] = 1;
  for (int i = 1; i <= N; ++i) {
    P[i] = i / 2;
    if (2 * i <= N) L[i] = 2 * i;
    if (2 * i + 1 <= N) R[i] = 2 * i + 1;
  }
  P[1] = 0;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(2 + i, 3 + i, "B" + to_string(i));
  for (int victim = 1; victim <= 7; ++victim) {
    srand(100 + victim);
    TR t(N, P, L, R);
    t.del_from_tree(victim);
    string err;
    if (!reachable_excluding(t, N, victim, err)) {
      ++g_fail;
      cerr << "  [FAIL] D2 del two-child node " << victim << ": " << err << "\n";
      return;
    }
    if (t.dbg_p(victim) != 0 || t.dbg_l(victim) || t.dbg_r(victim)) {
      ++g_fail;
      cerr << "  [FAIL] D2 victim " << victim << " not fully detached\n";
      return;
    }
    short p = (victim == 1) ? 2 : short(victim / 2);
    t.ins_to_tree(p, victim, true);
    if (!t.validate_tree(err)) {
      ++g_fail;
      cerr << "  [FAIL] D2 re-insert " << victim << ": " << err << "\n";
      return;
    }
  }
  ++g_pass;
  cerr << "  [PASS] D2: delete+reinsert every two-child node in complete tree\n";
}

static void test_d2_root_leaf_delete() {
  vector<tuple<int, int, string>> specs = {{3, 4, "B1"}, {5, 6, "B2"}};
  {
    vector<short> P = {1, 0, 1}, L = {0, 2, 0}, R = {0, 0, 0};
    TR t(2, P, L, R);
    t.del_from_tree(2);
    string err;
    CHECK(reachable_excluding(t, 2, 2, err), "D2: del leaf child: " + err);
    CHECK_EQ(t.dbg_root(), 1, "D2: root unchanged");
    t.del_from_tree(1);
    CHECK_EQ(t.dbg_root(), 1, "D2: root leaf delete leaves root slot intact");
    CHECK_EQ(t.dbg_l(1), 0, "D2: deleted root has no left child");
    CHECK_EQ(t.dbg_r(1), 0, "D2: deleted root has no right child");
    CHECK_EQ(t.dbg_p(1), 0, "D2: deleted root p==0");
  }
  {
    vector<short> P = {1, 0, 1, 2}, L = {0, 2, 3, 0}, R = {0, 0, 0, 0};
    TR t(3, P, L, R);
    t.del_from_tree(1);
    string err;
    CHECK(reachable_excluding(t, 3, 1, err), "D2: del root with one child: " + err);
    CHECK_EQ(t.dbg_root(), 2, "D2: child promoted to root");
    CHECK_EQ(t.dbg_p(2), 0, "D2: new root p==0");
  }
}

static void test_d2_op_closure() {
  srand(202);
  const int N = 40;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(1 + rand() % 25, 1 + rand() % 25, "B" + to_string(i));
  FP fp = make_fp(specs, 10000, 10000);
  string err;
  for (int iter = 0; iter < 20000; ++iter) {
    switch (iter % 3) {
      case 0: fp.dbg_rotate(); break;
      case 1: fp.dbg_del_ins(); break;
      default: fp.dbg_swap(); break;
    }
    fp.init();
    if (!fp.tree().validate_tree(err)) {
      ++g_fail;
      cerr << "  [FAIL] D2 op-closure iter=" << iter << ": " << err << "\n";
      return;
    }
    if (iter % 500 == 0) {
      if (!scan_overlap(fp, N, err)) {
        ++g_fail;
        cerr << "  [FAIL] D2 op-closure iter=" << iter << " overlap: " << err << "\n";
        return;
      }
    }
  }
  ++g_pass;
  cerr << "  [PASS] D2: op closure, 20k direct mixed ops (rotate/del-ins/swap)\n";
}

static long long catalan(int n) {
  long long c = 1;
  for (int i = 0; i < n; ++i) c = c * 2 * (2 * i + 1) / (i + 2);
  return c;
}

static void test_d3_exhaustive_shapes() {
  for (int N : {6, 7, 8}) {
    auto shapes = gen_shapes(0, N - 1);
    CHECK_EQ((long long)shapes.size(), catalan(N), "D3: shape count == Catalan(" + to_string(N) + ")");
    srand(1000 + N);
    int checked = 0;
    for (auto& s : shapes) {
      for (int rep = 0; rep < 4; ++rep) {
        vector<short> perm(N);
        iota(perm.begin(), perm.end(), 1);
        shuffle(perm.begin(), perm.end(), mt19937((unsigned)rand()));
        vector<short> P(N + 1, 0), L(N + 1, 0), R(N + 1, 0);
        for (int sid = 0; sid < N; ++sid) {
          int bid = perm[sid];
          if (s.P[sid] != -1) P[bid] = perm[s.P[sid]];
          if (s.L[sid] != -1) L[bid] = perm[s.L[sid]];
          if (s.R[sid] != -1) R[bid] = perm[s.R[sid]];
        }
        vector<tuple<int, int, string>> specs;
        for (int i = 1; i <= N; ++i) {
          int w = 1 + rand() % 20, h = 1 + rand() % 20;
          specs.emplace_back(w, h, "B" + to_string(i));
        }
        for (int sid = 0; sid < N; ++sid) {
          if (rand() % 2) {
            int bid = perm[sid];
            swap(get<0>(specs[bid - 1]), get<1>(specs[bid - 1]));
          }
        }
        TR t(N, P, L, R);
        FP fp = make_fp(specs, 10000, 10000);
        fp.restore(t);
        fp.init();
        vector<tuple<int, int, string>> cur;
        for (int i = 1; i <= N; ++i)
          cur.emplace_back(fp.blk(i)._w, fp.blk(i)._h, "B" + to_string(i));
        vector<tuple<int, int, int, int>> ref;
        string err;
        ref_decode(t, cur, N, ref, err);
        for (int i = 1; i <= N; ++i) {
          const FP::BLOCK& b = fp.blk(i);
          if (b._x != get<0>(ref[i - 1]) || b._y != get<1>(ref[i - 1]) ||
              b._w != get<2>(ref[i - 1]) || b._h != get<3>(ref[i - 1])) {
            ++g_fail;
            cerr << "  [FAIL] D3 exhaustive N=" << N << " shape#" << checked
                 << " rep=" << rep << " block " << i << " mismatch\n";
            return;
          }
        }
        ++checked;
      }
    }
    ++g_pass;
    cerr << "  [PASS] D3: exhaustive all " << shapes.size() << " shapes of N=" << N
         << " (" << checked << " decodes) exact vs ref decoder\n";
  }
}

static void test_d3_crusher_mini() {
  vector<tuple<int, int, string>> specs = {{1, 1, "B0"}, {1, 1, "B1"}, {1, 100, "B2"},
                                           {1, 1, "B3"}, {1, 1, "B4"}, {5, 1, "S"}};
  vector<short> P = {1, 0, 1, 2, 3, 4, 1};
  vector<short> L = {0, 2, 3, 4, 5, 0, 0};
  vector<short> R = {0, 6, 0, 0, 0, 0, 0};
  TR t(6, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  CHECK_EQ(fp.blk(6)._y, 100, "D3 mini: SUPER.y == 100 (pushed by tall B2 in chain)");
  string err;
  CHECK(scan_overlap(fp, 6, err), "D3 mini: zero overlap: " + err);
  vector<tuple<int, int, string>> cur;
  for (int i = 1; i <= 6; ++i) cur.emplace_back(fp.blk(i)._w, fp.blk(i)._h, "B" + to_string(i));
  vector<tuple<int, int, int, int>> ref;
  ref_decode(t, cur, 6, ref, err);
  bool exact = true;
  for (int i = 1; i <= 6 && exact; ++i)
    exact = fp.blk(i)._x == get<0>(ref[i - 1]) && fp.blk(i)._y == get<1>(ref[i - 1]);
  CHECK(exact, "D3 mini: differential exact");
}

static void test_d3_crusher_500() {
  const int NT = 500, N = NT + 1;
  vector<tuple<int, int, string>> specs;
  srand(31);
  for (int i = 1; i <= NT; ++i) specs.emplace_back(1, 1 + rand() % 10, "T" + to_string(i));
  specs.emplace_back(500, 2, "SUPER");
  vector<short> P(N + 1, 0), L(N + 1, 0), R(N + 1, 0);
  P[0] = 1;
  for (int i = 2; i <= NT; ++i) { P[i] = i - 1; L[i - 1] = i; }
  P[N] = 1;
  R[1] = N;
  TR t(N, P, L, R);
  FP fp = make_fp(specs, 10000, 10000);
  fp.restore(t);
  fp.init();
  vector<tuple<int, int, string>> cur;
  for (int i = 1; i <= N; ++i) cur.emplace_back(fp.blk(i)._w, fp.blk(i)._h, "B" + to_string(i));
  vector<tuple<int, int, int, int>> ref;
  string err;
  ref_decode(t, cur, N, ref, err);
  bool exact = true;
  for (int i = 1; i <= N && exact; ++i)
    exact = fp.blk(i)._x == get<0>(ref[i - 1]) && fp.blk(i)._y == get<1>(ref[i - 1]);
  CHECK(exact, "D3: crusher differential exact (500 tins + 1 super)");
  CHECK(scan_overlap(fp, N, err), "D3: crusher zero overlap");
  CHECK_EQ(fp.tree().dbg_cy().size(), (size_t)1, "D3: crusher contour merged to one segment");
  CHECK_EQ(fp.tree().dbg_cy()[0], (short)N, "D3: crusher contour holds SUPER only");
  int maxtop = 0;
  for (int i = 1; i <= NT; ++i) maxtop = max(maxtop, (int)fp.blk(i)._y + fp.blk(i)._h);
  CHECK_EQ(fp.blk(N)._y, maxtop, "D3: SUPER.y == max of all 500 tin tops");
  CHECK_EQ(get<2>(fp.cost(true, true)), maxtop + 2, "D3: bbox height == maxtop + 2");
}

static void test_d4_sa_numerics() {
  srand(42);
  const int N = 30;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i) specs.emplace_back(1 + rand() % 25, 1 + rand() % 25, "B" + to_string(i));
  FP fp = make_fp(specs, 1000, 1000);
  SA<short, int> sa(fp, N, fp.W(), fp.H(), fp.R(), 0.9f, 0.5f, 0.1f, 0.5f);
  sa.run(1, 2 * N + 20, 1000.0f);
  sa.run2(1, 2 * N + 20, 1000.0f);
  bool finite = true;
  for (auto v : sa.dbg_hist())
    if (v != v || v > 1e30f || v < -1e30f) finite = false;
  CHECK(finite, "D4: no NaN/Inf in best-cost history under extreme cooling");
  string err;
  CHECK(verify_layout_definition(fp, N, err), "D4: final layout legal: " + err);
}

static void test_d4_hpwl_center_rotation() {
  ifstream fblcks("/tmp/o3.blocks");
  ifstream fnets("/tmp/o3.nets");
  ifstream fpl("/tmp/o3.pl");
  if (!fblcks || !fnets || !fpl) { ++g_fail; cerr << "  [FAIL] D4 missing o3 files\n"; return; }
  FP fp(fnets, fblcks, fpl, "", 2, 2, 1, 0.5f, 0.15f);
  vector<short> P = {1, 0, 1}, L = {0, 2, 0}, R = {0, 0, 0};
  TR t(2, P, L, R);
  fp.restore(t);
  fp.init();
  CHECK_EQ(oracle_hpwl(fp), 61LL, "D4: baseline hpwl 61");
  TR t2 = fp.tree();
  t2.set_rot(1);
  fp.restore(t2);
  fp.init();
  CHECK_EQ(fp.blk(1)._w, 5, "D4: b1 rotated w=5");
  CHECK_EQ(fp.blk(1)._h, 10, "D4: b1 rotated h=10");
  CHECK_EQ(fp.blk(2)._x, 5, "D4: b2 follows parent width 5 -> x=5");
  CHECK_EQ(oracle_hpwl(fp), 47LL, "D4: rotated center mapping hpwl 47 (17+30)");
  CHECK_EQ((long long)get<0>(fp.cost()), 47LL, "D4: cost() matches oracle after rotation");
}

static void test_f1_infeasible_outline_terminates() {
  srand(901);
  const int N = 8;
  vector<tuple<int, int, string>> specs;
  long long total = 0;
  for (int i = 1; i <= N; ++i) {
    int w = 1 + rand() % 10, h = 1 + rand() % 10;
    specs.emplace_back(w, h, "B" + to_string(i));
    total += (long long)w * h;
  }
  int tiny = (int)ceil(sqrt((double)total / 2.0));
  FP fp = make_fp(specs, tiny, tiny);
  SA<short, int> sa(fp, N, fp.W(), fp.H(), fp.R(), 0.9f, 0.5f, 0.1f, 0.5f);
  sa.run(2, 2 * N + 20, 100 - N);
  CHECK(true, "T1: run() terminates on infeasible outline (reset bound)");
  auto res = sa.run2(2, 2 * N + 20, 100 - N);
  bool finite = true;
  for (auto v : sa.dbg_hist())
    if (v != v) finite = false;
  CHECK(finite, "T1: cost history finite through infeasible run");
  fp.restore(res.second);
  fp.init();
  string err;
  CHECK(fp.tree().validate_tree(err), "T1: tree intact after infeasible run: " + err);
}

static void test_f2_labeled_int_formats() {
  istringstream a("NumNets : 885");
  CHECK_EQ(read_labeled_int(a), 885, "T2: 'X : n' format");
  istringstream b("NumNets: 885");
  CHECK_EQ(read_labeled_int(b), 885, "T2: 'X: n' format");
  istringstream c("NumNets 885");
  CHECK_EQ(read_labeled_int(c), 885, "T2: 'X n' format (no colon)");
  istringstream d("");
  CHECK_EQ(read_labeled_int(d), -1, "T2: empty stream returns -1");
  istringstream e("NumNets");
  CHECK_EQ(read_labeled_int(e), -1, "T2: truncated stream returns -1");
  istringstream f("garbage !!");
  CHECK_EQ(read_labeled_int(f), -1, "T2: non-numeric returns -1");
}

static void test_f3_degenerate_block_rejected() {
  ofstream fb("/tmp/t3.blocks");
  fb << "NumHardBlocks : 1\nNumTerminals : 0\n"
     << "b1 block 4 (0,0) (0,5) (0,5) (0,0)\n";
  fb.close();
  ofstream fn("/tmp/t3.nets");
  fn << "NumNets : 0\nNumPins : 0\n";
  fn.close();
  ofstream fpl("/tmp/t3.pl");
  fpl.close();
  pid_t pid = fork();
  if (pid == 0) {
    ifstream fb2("/tmp/t3.blocks");
    ifstream fn2("/tmp/t3.nets");
    ifstream fpl2("/tmp/t3.pl");
    FP fp(fn2, fb2, fpl2, "", 0, 1, 0, 0.5f, 0.15f);
    _exit(0);
  }
  int status = 0;
  waitpid(pid, &status, 0);
  bool rejected = WIFEXITED(status) && WEXITSTATUS(status) == 1;
  CHECK(rejected, "T3: degenerate zero-width block rejected with exit(1)");
}

static void test_f4_n2_operators() {
  srand(606);
  vector<tuple<int, int, string>> specs = {{3, 7, "B1"}, {5, 4, "B2"}};
  FP fp = make_fp(specs, 100, 100);
  string err;
  for (int iter = 0; iter < 200; ++iter) {
    if (iter % 2) fp.dbg_del_ins();
    else fp.dbg_swap();
    fp.init();
    if (!fp.tree().validate_tree(err)) {
      ++g_fail;
      cerr << "  [FAIL] T4 N=2 iter=" << iter << ": " << err << "\n";
      return;
    }
    vector<tuple<int, int, string>> cur;
    for (int i = 1; i <= 2; ++i)
      cur.emplace_back(fp.blk(i)._w, fp.blk(i)._h, "B" + to_string(i));
    vector<tuple<int, int, int, int>> ref;
    ref_decode(fp.tree(), cur, 2, ref, err);
    if (fp.blk(1)._x != get<0>(ref[0]) || fp.blk(1)._y != get<1>(ref[0]) ||
        fp.blk(2)._x != get<0>(ref[1]) || fp.blk(2)._y != get<1>(ref[1])) {
      ++g_fail;
      cerr << "  [FAIL] T4 N=2 differential iter=" << iter << "\n";
      return;
    }
  }
  ++g_pass;
  cerr << "  [PASS] T4: N=2 200 mixed ops, topology + differential clean\n";
}

static void test_q1_cost_oracle() {
  srand(777);
  const int N = 12;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i)
    specs.emplace_back(1 + rand() % 20, 1 + rand() % 20, "B" + to_string(i));
  FP fp = make_fp(specs, 10000, 10000);
  const float lambda = 0.7f;
  SA<short, int> sa(fp, N, fp.W(), fp.H(), fp.R(), 0.9f, 0.5f, 0.1f, lambda, Mode::Q1);
  CHECK(sa.dbg_q1_avg_area() > 0, "Q1: avg area normalizer positive");
  CHECK(sa.dbg_q1_avg_pen() > 0, "Q1: avg aspect-penalty normalizer positive");
  fp.init();
  int3 c = fp.cost();
  const float area = float(get<1>(c)) * float(get<2>(c));
  const float r = float(max(get<1>(c), get<2>(c))) / float(min(get<1>(c), get<2>(c)));
  const float pen = r + 1.0f / r - 2.0f;
  const float expect = lambda * area / sa.dbg_q1_avg_area() + (1 - lambda) * pen / sa.dbg_q1_avg_pen();
  const float got = sa.dbg_q1_cost_of(c);
  CHECK(fabs(expect - got) < 1e-3f * max(1.0f, fabs(expect)),
        "Q1 cost oracle: q1_cost == independent formula");
  const int3 c2 = make_tuple(0, 100, 100);
  CHECK_EQ(sa.dbg_q1_cost_of(c2), lambda * 10000.0f / sa.dbg_q1_avg_area(), "Q1: square bbox pen == 0");
}

static void test_q1_end_to_end_and_log() {
  srand(888);
  const int N = 4;
  vector<pair<int, int>> wh;
  for (int i = 1; i <= N; ++i) wh.emplace_back(1 + rand() % 8, 1 + rand() % 8);
  long long opt = brute_area_opt(N, wh);
  double fopt;
  long long aopt;
  double aspopt;
  tie(fopt, aopt, aspopt) = brute_q1_opt(N, wh, 0.5f);
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i)
    specs.emplace_back(wh[i - 1].first, wh[i - 1].second, "B" + to_string(i));
  FP fp = make_fp(specs, 10000, 10000);
  ostringstream log;
  SA<short, int> sa(fp, N, 10000, 10000, 1.0f, 0.9f, 0.5f, 0.1f, 0.5f, Mode::Q1, &log);
  const int k = 4, rnd = 3 * N + 40;
  auto res = sa.run2(k, rnd, 96.0f);
  auto res2 = sa.run2(k, rnd, 96.0f);
  if (res2.first < res.first) res = res2;
  fp.restore(res.second);
  fp.init();
  long long area = (long long)get<1>(fp.cost()) * get<2>(fp.cost());
  long long lb = 0;
  for (auto& p : wh) lb += (long long)p.first * p.second;
  CHECK(area >= lb, "Q1: area >= sum of block areas");
  CHECK(area <= opt + opt / 2, "Q1: area <= 1.5x pure-area optimum");
  int W = get<1>(fp.cost()), H = get<2>(fp.cost());
  const double r = double(max(W, H)) / double(min(W, H));
  double f_sa = 0.5 * double(area) + 0.5 * (r + 1.0 / r - 2.0);
  CHECK(f_sa <= fopt * 1.5, "Q1: weighted cost within 1.5x weighted brute optimum");
  CHECK(r <= 1.5, "Q1: aspect ratio <= 1.5");
  string err;
  CHECK(verify_layout_definition(fp, N, err), "Q1: final layout legal: " + err);
  const auto& h = sa.dbg_hist();
  bool finite = true, mono = true;
  for (size_t i = 1; i < h.size(); ++i) {
    if (h[i] == -1.0f || h[i - 1] == -1.0f) continue;
    if (h[i] != h[i]) finite = false;
    if (h[i] > h[i - 1]) mono = false;
  }
  CHECK(finite, "Q1: hist finite (no NaN under no-net path)");
  CHECK(mono, "Q1: hist monotone non-increasing (Q1 mode)");
  istringstream ls(log.str());
  string ph;
  int iter, feas_f;
  float T, best, alpha;
  int lines = 0;
  while (ls >> ph >> iter >> T >> best >> alpha >> feas_f) {
    ++lines;
    if (ph != "run2" || feas_f != 1) {
      ++g_fail;
      cerr << "  [FAIL] Q1 log field: phase=" << ph << " feas=" << feas_f << "\n";
      return;
    }
  }
  CHECK(lines >= 1, "Q1: log has >= 1 temperature layer");
}

static void test_q1_snapshots() {
  srand(999);
  const int N = 8;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i)
    specs.emplace_back(1 + rand() % 10, 1 + rand() % 10, "B" + to_string(i));
  FP fp = make_fp(specs, 1000, 1000);
  ostringstream log;
  SA<short, int> sa(fp, N, 1000, 1000, 1.0f, 0.9f, 0.5f, 0.1f, 0.5f, Mode::Q1, &log);
  sa.run2(2, 2 * N + 20, 90.0f);
  istringstream ls(log.str());
  string tok;
  int snaps = 0, snap_blocks = 0;
  int cur_blocks = 0;
  bool in_snap = false;
  int total_blocks_lines = 0;
  string name;
  int x1, y1, x2, y2;
  while (ls >> tok) {
    if (tok == "snap") {
      int k, iter, W, H;
      ls >> k >> iter >> W >> H;
      ++snaps;
      CHECK(k >= 1 && k <= 9, "Q1 snap k in 1..9");
      CHECK(W > 0 && H > 0, "Q1 snap bbox positive");
      in_snap = true;
      cur_blocks = 0;
      continue;
    }
    if (in_snap) {
      if (tok == "run2") { in_snap = false; continue; }
      ls >> x1 >> y1 >> x2 >> y2;
      ++cur_blocks;
      ++total_blocks_lines;
      if (cur_blocks > N) { ++g_fail; cerr << "  [FAIL] snap block count overflow\n"; return; }
      CHECK(x2 > x1 && y2 > y1, "Q1 snap block positive extent");
    }
  }
  CHECK_EQ(snaps, 9, "Q1: exactly 9 snapshots in log");
  CHECK_EQ(total_blocks_lines, 9 * N, "Q1: 9 snapshots x N blocks");
  string err;
  CHECK(fp.tree().validate_tree(err), "Q1: tree intact after snapshots: " + err);
}

static void test_q2_run_snapshots() {
  srand(4321);
  const int N = 10;
  vector<tuple<int, int, string>> specs;
  for (int i = 1; i <= N; ++i)
    specs.emplace_back(1 + rand() % 15, 1 + rand() % 15, "B" + to_string(i));
  FP fp = make_fp(specs, 1000, 1000);
  ostringstream log;
  SA<short, int> sa(fp, N, 1000, 1000, 1.0f, 0.9f, 0.5f, 0.1f, 0.5f, Mode::Q2, &log);
  sa.run(2, 2 * N + 20, 90.0f);
  CHECK(sa.last_feasible(), "T1: Q2 run found feasible solution");
  istringstream ls(log.str());
  string tok;
  int snaps = 0, blocks_in_snap = 0;
  bool in_snap = false;
  int last_k = 0;
  while (ls >> tok) {
    if (tok == "snap") {
      int k, iter, W, H;
      ls >> k >> iter >> W >> H;
      ++snaps;
      CHECK(k >= 1 && k <= 9, "T1: run snap k in 1..9");
      last_k = k;
      in_snap = true;
      continue;
    }
    if (in_snap) {
      if (tok == "run2" || tok == "run") { in_snap = false; continue; }
      int x1, y1, x2, y2;
      ls >> x1 >> y1 >> x2 >> y2;
      ++blocks_in_snap;
      CHECK(x2 > x1 && y2 > y1, "T1: run snap block positive");
    }
  }
  CHECK_EQ(snaps, 9, "T1: run() emits 9 snapshots");
  CHECK_EQ(last_k, 9, "T1: last snap k == 9");
  CHECK_EQ(blocks_in_snap, 9 * N, "T1: 9 snapshots x N blocks");
}

static void test_q2_feas_only() {
  srand(5555);
  const int N = 12;
  vector<tuple<int, int, string>> specs;
  long long total = 0;
  for (int i = 1; i <= N; ++i) {
    int w = 1 + rand() % 12, h = 1 + rand() % 12;
    specs.emplace_back(w, h, "B" + to_string(i));
    total += (long long)w * h;
  }
  {
    FP fp = make_fp(specs, 1000, 1000);
    SA<short, int> sa(fp, N, 1000, 1000, 1.0f, 0.9f, 0.5f, 0.1f, 0.5f, Mode::Q2);
    sa.run(2, 2 * N + 20, 90.0f);
    CHECK(sa.last_feasible(), "T2: feasible instance -> last_feasible true");
  }
  {
    int tiny = (int)ceil(sqrt((double)total / 2.0));
    FP fp = make_fp(specs, tiny, tiny);
    SA<short, int> sa(fp, N, tiny, tiny, 1.0f, 0.9f, 0.5f, 0.1f, 0.5f, Mode::Q2);
    sa.run(2, 2 * N + 20, 90.0f);
    CHECK(!sa.last_feasible(), "T2: infeasible instance -> last_feasible false");
    string err;
    CHECK(fp.tree().validate_tree(err), "T2: tree intact after infeasible run: " + err);
  }
}

static void test_q2_end_to_end_hpwl() {
  ifstream fblcks("../data/raw/n100.blocks");
  ifstream fnets("../data/raw/n100.nets");
  ifstream fpl("../data/raw/n100.pl");
  if (!fblcks || !fnets || !fpl) { ++g_fail; cerr << "  [FAIL] T3 missing data\n"; return; }
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  FP fp(fnets, fblcks, fpl, "", Nnets, Nblcks, Ntrmns, 0.5f, 0.15f);
  SA<short, int> sa(fp, Nblcks, fp.W(), fp.H(), fp.R(), 0.9f, 0.5f, 0.1f, 0.5f, Mode::Q2);
  const int k = max(2, Nblcks / 11), rnd = 2 * Nblcks + 20;
  const float c = max(100 - int(Nblcks), 10);
  sa.run(k, rnd, c);
  auto res = sa.run2(k, rnd, c);
  fp.restore(res.second);
  fp.init();
  CHECK_EQ(oracle_hpwl(fp), (long long)get<0>(fp.cost()), "T3: Q2 SA result hpwl == oracle");
  string err;
  CHECK(verify_layout_definition(fp, Nblcks, err), "T3: Q2 SA result legal: " + err);
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
  cerr << "== O1: decode definition verify ==\n";
  test_o1_definition_verify();
  cerr << "== O2: differential decode oracle ==\n";
  test_o2_differential_random();
  test_o2_differential_real();
  cerr << "== O3: cost oracle (independent hpwl/area) ==\n";
  test_o3_hpwl_handcrafted();
  test_o3_hpwl_random();
  test_o3_hpwl_real();
  cerr << "== O4: operator semantics (position swap / subtree follow) ==\n";
  test_o4_operator_semantics();
  cerr << "== O5: SA engine ==\n";
  test_o5_sa_reproducible_and_monotone();
  test_o5_vs_bruteforce();
  test_o5_end_to_end_n100();
  cerr << "== O6: boundaries & rpt format ==\n";
  test_o6_node_packing_limits();
  test_o6_rpt_format();
  cerr << "== D1: memory safety & UB ==\n";
  test_d1_n1_and_empty_rotable();
  test_d1_big_tree_stress_1023();
  test_d1_deep_chain_recursion();
  cerr << "== D2: topology extremes ==\n";
  test_d2_delete_all_two_child_nodes();
  test_d2_root_leaf_delete();
  test_d2_op_closure();
  cerr << "== D3: skyline crusher & exhaustive shapes ==\n";
  test_d3_exhaustive_shapes();
  test_d3_crusher_mini();
  test_d3_crusher_500();
  cerr << "== D4: SA numerics ==\n";
  test_d4_sa_numerics();
  test_d4_hpwl_center_rotation();
  cerr << "== F: regression fixes ==\n";
  test_f1_infeasible_outline_terminates();
  test_f2_labeled_int_formats();
  test_f3_degenerate_block_rejected();
  test_f4_n2_operators();
  cerr << "== Q1: free-outline mode ==\n";
  test_q1_cost_oracle();
  test_q1_end_to_end_and_log();
  test_q1_snapshots();
  cerr << "== Q2: fixed-outline mode ==\n";
  test_q2_run_snapshots();
  test_q2_feas_only();
  test_q2_end_to_end_hpwl();
  cerr << "--------------------------------\n";
  cerr << "PASS: " << g_pass << "  FAIL: " << g_fail << "\n";
  return g_fail ? 1 : 0;
}
