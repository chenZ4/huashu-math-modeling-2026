#ifndef TEST_ORACLE_HPP
#define TEST_ORACLE_HPP

#include <algorithm>
#include <climits>
#include <functional>
#include <numeric>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

#include "floor_plan.hpp"

typedef FLOOR_PLAN<short, int> FP;
typedef FP::TREE TR;

struct RefDecoder {
  struct Seg { int x0, x1, top; };
  vector<Seg> sky;
  int place(int x, int w, int h) {
    int y = 0;
    for (auto& s : sky)
      if (s.x0 < x + w && s.x1 > x) y = max(y, s.top);
    vector<Seg> out;
    int nx0 = x, nx1 = x + w;
    bool inserted = false;
    for (auto& s : sky) {
      if (s.x1 <= nx0) { out.push_back(s); continue; }
      if (s.x0 >= nx1) {
        if (!inserted) { out.push_back({nx0, nx1, y + h}); inserted = true; }
        out.push_back(s);
        continue;
      }
      if (s.x0 < nx0) out.push_back({s.x0, nx0, s.top});
      if (s.x1 > nx1) out.push_back({nx1, s.x1, s.top});
    }
    if (!inserted) out.push_back({nx0, nx1, y + h});
    sky.swap(out);
    return y;
  }
};

bool ref_decode(const TR& t, const vector<tuple<int, int, string>>& specs, int N,
                vector<tuple<int, int, int, int>>& out, string& err) {
  vector<pair<int, int>> dims(N + 1);
  for (int i = 1; i <= N; ++i) dims[i] = {get<0>(specs[i - 1]), get<1>(specs[i - 1])};
  RefDecoder rd;
  vector<int> xs(N + 1, 0), ys(N + 1, 0);
  function<void(int)> dfs = [&](int id) {
    int w = dims[id].first, h = dims[id].second;
    if (id == t.dbg_root()) {
      xs[id] = 0;
    } else {
      int p = t.dbg_p(id);
      if (p < 1 || p > N) { err = "parent oob at " + to_string(id); return; }
      if (t.dbg_l(p) == id) xs[id] = xs[p] + dims[p].first;
      else if (t.dbg_r(p) == id) xs[id] = xs[p];
      else { err = "node " + to_string(id) + " not child of its parent"; return; }
    }
    ys[id] = rd.place(xs[id], w, h);
    if (t.dbg_l(id)) dfs(t.dbg_l(id));
    if (t.dbg_r(id)) dfs(t.dbg_r(id));
  };
  dfs(t.dbg_root());
  for (int i = 1; i <= N; ++i)
    out.emplace_back(xs[i], ys[i], dims[i].first, dims[i].second);
  return true;
}

bool verify_layout_definition(const FP& fp, int N, string& err) {
  const TR& t = fp.tree();
  for (int i = 1; i <= N; ++i) {
    const FP::BLOCK& b = fp.blk(i);
    if (b._x < 0 || b._y < 0 || b._w <= 0 || b._h <= 0) {
      err = "block " + to_string(i) + " non-positive extent";
      return false;
    }
    if (i == t.dbg_root()) {
      if (b._x != 0 || b._y != 0) { err = "root not at origin"; return false; }
      continue;
    }
    int p = t.dbg_p(i);
    if (p < 1 || p > N) { err = "parent oob at " + to_string(i); return false; }
    bool isl = t.dbg_l(p) == i, isr = t.dbg_r(p) == i;
    if (!isl && !isr) {
      err = to_string(i) + " is not a child of its parent " + to_string(p);
      return false;
    }
    int xexp = isl ? fp.blk(p)._x + fp.blk(p)._w : fp.blk(p)._x;
    if (b._x != xexp) { err = "x mismatch at " + to_string(i); return false; }
  }
  for (int i = 1; i <= N; ++i)
    for (int j = i + 1; j <= N; ++j) {
      const FP::BLOCK& a = fp.blk(i);
      const FP::BLOCK& b = fp.blk(j);
      if (a._x < b._x + b._w && b._x < a._x + a._w &&
          a._y < b._y + b._h && b._y < a._y + a._h) {
        err = "overlap " + to_string(i) + " vs " + to_string(j);
        return false;
      }
    }
  return true;
}

long long oracle_hpwl(const FP& fp) {
  long long total = 0;
  for (int n = 0; n < fp.Nnets(); ++n) {
    const auto& net = fp.dbg_net(n);
    long long mnx = LLONG_MAX, mny = LLONG_MAX, mxx = 0, mxy = 0;
    for (auto id : net._blcks) {
      const FP::BLOCK& b = fp.blk(id);
      long long px = (id <= fp.Nblcks()) ? 2LL * b._x + b._w : 2LL * b._x;
      long long py = (id <= fp.Nblcks()) ? 2LL * b._y + b._h : 2LL * b._y;
      mnx = min(mnx, px); mxx = max(mxx, px);
      mny = min(mny, py); mxy = max(mxy, py);
    }
    total += (mxx - mnx) + (mxy - mny);
  }
  return total;
}

void collect_subtree(const TR& t, int root, vector<int>& out) {
  out.push_back(root);
  if (t.dbg_l(root)) collect_subtree(t, t.dbg_l(root), out);
  if (t.dbg_r(root)) collect_subtree(t, t.dbg_r(root), out);
}
bool same_set(const vector<int>& a, const vector<int>& b) {
  if (a.size() != b.size()) return false;
  vector<int> x = a, y = b;
  sort(x.begin(), x.end());
  sort(y.begin(), y.end());
  return x == y;
}

struct BShape { int root; vector<int> P, L, R; };
vector<BShape> gen_shapes(int lo, int hi) {
  vector<BShape> res;
  int n = hi - lo + 1;
  if (n <= 0) { res.push_back({-1, {}, {}, {}}); return res; }
  for (int a = 0; a < n; ++a) {
    auto ls = gen_shapes(lo + 1, lo + a);
    auto rs = gen_shapes(lo + a + 1, hi);
    for (auto& l : ls)
      for (auto& r : rs) {
        BShape s;
        s.root = 0;
        s.P.assign(n, -1);
        s.L.assign(n, -1);
        s.R.assign(n, -1);
        if (a > 0) {
          s.L[0] = 1;
          const int base = 1;
          for (int k = 0; k < a; ++k) {
            s.P[base + k] = (l.P[k] == -1) ? -1 : base + l.P[k];
            s.L[base + k] = (l.L[k] == -1) ? -1 : base + l.L[k];
            s.R[base + k] = (l.R[k] == -1) ? -1 : base + l.R[k];
          }
          s.P[1] = 0;
        }
        if (n - 1 - a > 0) {
          s.R[0] = a + 1;
          const int base = 1 + a;
          for (int k = 0; k < n - 1 - a; ++k) {
            s.P[base + k] = (r.P[k] == -1) ? -1 : base + r.P[k];
            s.L[base + k] = (r.L[k] == -1) ? -1 : base + r.L[k];
            s.R[base + k] = (r.R[k] == -1) ? -1 : base + r.R[k];
          }
          s.P[base] = 0;
        }
        res.push_back(s);
      }
  }
  return res;
}

long long brute_area_opt(int N, const vector<pair<int, int>>& wh) {
  auto shapes = gen_shapes(0, N - 1);
  vector<int> perm(N);
  iota(perm.begin(), perm.end(), 1);
  long long best = LLONG_MAX;
  do {
    for (int mask = 0; mask < (1 << N); ++mask) {
      for (auto& s : shapes) {
        RefDecoder rd;
        vector<int> xs(N, 0), ys(N, 0), pw(N, 0), ph(N, 0);
        function<void(int)> dfs = [&](int sid) {
          int bid = perm[sid];
          int w = wh[bid - 1].first, h = wh[bid - 1].second;
          if (mask & (1 << sid)) swap(w, h);
          int x = 0;
          if (sid != s.root) {
            int p = s.P[sid];
            if (s.L[p] == sid) x = xs[p] + pw[p];
            else x = xs[p];
          }
          ys[sid] = rd.place(x, w, h);
          xs[sid] = x;
          pw[sid] = w;
          ph[sid] = h;
          if (s.L[sid] != -1) dfs(s.L[sid]);
          if (s.R[sid] != -1) dfs(s.R[sid]);
        };
        dfs(s.root);
        long long maxx = 0, maxy = 0;
        for (int i = 0; i < N; ++i) {
          maxx = max(maxx, (long long)xs[i] + pw[i]);
          maxy = max(maxy, (long long)ys[i] + ph[i]);
        }
        best = min(best, maxx * maxy);
      }
    }
  } while (next_permutation(perm.begin(), perm.end()));
  return best;
}

tuple<double, long long, double> brute_q1_opt(int N, const vector<pair<int, int>>& wh,
                                              float lambda) {
  auto shapes = gen_shapes(0, N - 1);
  vector<int> perm(N);
  iota(perm.begin(), perm.end(), 1);
  double best_f = 1e300;
  long long best_area = LLONG_MAX;
  double best_asp = 0;
  do {
    for (int mask = 0; mask < (1 << N); ++mask) {
      for (auto& s : shapes) {
        RefDecoder rd;
        vector<int> xs(N, 0), ys(N, 0), pw(N, 0), ph(N, 0);
        function<void(int)> dfs = [&](int sid) {
          int bid = perm[sid];
          int w = wh[bid - 1].first, h = wh[bid - 1].second;
          if (mask & (1 << sid)) swap(w, h);
          int x = 0;
          if (sid != s.root) {
            int p = s.P[sid];
            if (s.L[p] == sid) x = xs[p] + pw[p];
            else x = xs[p];
          }
          ys[sid] = rd.place(x, w, h);
          xs[sid] = x;
          pw[sid] = w;
          ph[sid] = h;
          if (s.L[sid] != -1) dfs(s.L[sid]);
          if (s.R[sid] != -1) dfs(s.R[sid]);
        };
        dfs(s.root);
        long long maxx = 0, maxy = 0;
        for (int i = 0; i < N; ++i) {
          maxx = max(maxx, (long long)xs[i] + pw[i]);
          maxy = max(maxy, (long long)ys[i] + ph[i]);
        }
        const long long area = maxx * maxy;
        const double r = double(max(maxx, maxy)) / double(min(maxx, maxy));
        const double pen = r + 1.0 / r - 2.0;
        const double f = lambda * double(area) + (1.0 - lambda) * pen;
        if (f < best_f - 1e-9) {
          best_f = f;
          best_area = area;
          best_asp = r;
        }
      }
    }
  } while (next_permutation(perm.begin(), perm.end()));
  return {best_f, best_area, best_asp};
}

bool parse_rpt(const string& text, long long& area, int& W, int& H, long long& hpwl,
               vector<tuple<string, int, int, int, int>>& blocks) {
  istringstream iss(text);
  float cost, hpwl_f, t;
  if (!(iss >> cost)) return false;
  if (!(iss >> hpwl_f)) return false;
  hpwl = (long long)hpwl_f;
  if (!(iss >> area)) return false;
  if (!(iss >> W >> H)) return false;
  if (!(iss >> t)) return false;
  string name;
  int x1, y1, x2, y2;
  while (iss >> name >> x1 >> y1 >> x2 >> y2)
    blocks.emplace_back(name, x1, y1, x2, y2);
  return true;
}

#endif
