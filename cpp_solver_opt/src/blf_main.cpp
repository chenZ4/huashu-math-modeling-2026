// BLF-greedy 基线：Bottom-Left-Fill 贪心（无搜索）。
// 面积降序（同积按名序），单元分辨率 skyline 数组上取最低可行带，
// 双朝向在快照上分别评估后择优落写；完全确定性，无随机数。
// 复用 FLOOR_PLAN 解析与轮廓推导；网表自解析按同一引脚模型输出 .rpt
// （金标准 HPWL 由外部 wrapper 独立复核）。
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <string>
#include <vector>

using namespace std;

#include "floor_plan.hpp"

int main(int argc, char** argv) {
  ios_base::sync_with_stdio(false);
  if (argc < 7) {
    cerr << "usage: blf <mode:q1|q2> <alpha> <blocks> <nets> <pl> <rpt> "
            "[dead_ratio]\n";
    return 1;
  }
  float alpha = stof(argv[2]);
  float dead_ratio = 0.15f;
  if (argc > 7) dead_ratio = stof(argv[7]);
  ifstream fblcks(argv[3]);
  ifstream fnets(argv[4]);
  ifstream fpl(argv[5]);
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  clock_t t0 = clock();
  FLOOR_PLAN<short, int> fp(fnets, fblcks, fpl, "", Nnets, Nblcks, Ntrmns,
                            alpha, dead_ratio, true);
  const int SIDE = fp.W();
  vector<int> bw(Nblcks + 1), bh(Nblcks + 1);
  vector<string> name(Nblcks + 1);
  vector<int> order(Nblcks);
  for (int i = 1; i <= Nblcks; ++i) {
    bw[i] = fp.blk(i)._w;
    bh[i] = fp.blk(i)._h;
    name[i] = fp.blk(i)._name;
    order[i - 1] = i;
  }
  sort(order.begin(), order.end(), [&](int a, int b) {
    long long aa = (long long)bw[a] * bh[a], ab = (long long)bw[b] * bh[b];
    if (aa != ab) return aa > ab;
    return name[a] < name[b];
  });
  const int CAP = SIDE;
  vector<int> H(CAP + 1, 0);
  vector<int> px(Nblcks + 1, 0), py(Nblcks + 1, 0);
  vector<int> pw(Nblcks + 1, 0), ph(Nblcks + 1, 0);
  bool overflow = false;
  auto scan_best = [&](const vector<int>& hs, int w,
                       int& bx, int& by) -> bool {
    if (w > CAP) return false;
    bx = -1;
    by = 0;
    for (int x = 0; x + w <= CAP; ++x) {
      int y = 0;
      for (int k = x; k < x + w; ++k)
        if (hs[k] > y) y = hs[k];
      if (bx < 0 || y < by) { bx = x; by = y; }
      if (by == 0) break; // 已达最低带，最左优先
    }
    return bx >= 0;
  };
  for (int idx : order) {
    vector<int> snap = H;
    int ax, ay, bxx = -1, byy = 0;
    bool has_a = scan_best(snap, bw[idx], ax, ay);
    bool has_b = (bw[idx] != bh[idx]) && scan_best(snap, bh[idx], bxx, byy);
    int cx, cy, cw, ch;
    if (has_a && (!has_b || ay < byy || (ay == byy && ax <= bxx))) {
      cx = ax; cy = ay; cw = bw[idx]; ch = bh[idx];
    } else if (has_b) {
      cx = bxx; cy = byy; cw = bh[idx]; ch = bw[idx];
    } else {
      cerr << "BLF: cannot place " << name[idx] << "\n";
      return 2;
    }
    px[idx] = cx;
    py[idx] = cy;
    pw[idx] = cw;
    ph[idx] = ch;
    for (int k = cx; k < cx + cw; ++k) H[k] = cy + ch;
    if (cx + cw > SIDE || cy + ch > SIDE) overflow = true;
  }
  long long Wb = 0, Hb = 0;
  for (int i = 1; i <= Nblcks; ++i) {
    Wb = max(Wb, (long long)(px[i] + pw[i]));
    Hb = max(Hb, (long long)(py[i] + ph[i]));
  }
  map<string, pair<long long, long long>> term;
  {
    ifstream f2(argv[5]);
    string nm; long long x, y;
    while (f2 >> nm >> x >> y) term[nm] = {2 * x, 2 * y};
  }
  map<string, int> id_of;
  for (int i = 1; i <= Nblcks; ++i) id_of[name[i]] = i;
  long long hpwl2 = 0;
  {
    ifstream f2(argv[4]);
    string s;
    while (getline(f2, s)) {
      if (s.rfind("NetDegree", 0) != 0) continue;
      int deg = stoi(s.substr(s.find(':') + 1));
      long long mnx = 1LL << 60, mny = 1LL << 60, mxx = 0, mxy = 0;
      for (int k = 0; k < deg; ++k) {
        string p; f2 >> p;
        long long qx, qy;
        auto it = id_of.find(p);
        if (it != id_of.end()) {
          int i = it->second;
          qx = 2LL * px[i] + pw[i];
          qy = 2LL * py[i] + ph[i];
        } else {
          qx = term[p].first;
          qy = term[p].second;
        }
        mnx = min(mnx, qx); mny = min(mny, qy);
        mxx = max(mxx, qx); mxy = max(mxy, qy);
      }
      hpwl2 += (mxx - mnx) + (mxy - mny);
    }
  }
  ofstream out(argv[6]);
  out << setprecision(13)
      << alpha * (double)Wb * Hb + (1 - alpha) * hpwl2 / 2. << '\n';
  out << hpwl2 / 2. << '\n';
  out << Wb * Hb << '\n';
  out << Wb << " " << Hb << '\n';
  out << double(clock() - t0) / CLOCKS_PER_SEC << '\n';
  for (int i = 1; i <= Nblcks; ++i) {
    out << name[i] << " " << px[i] << " " << py[i] << " "
        << px[i] + pw[i] << " " << py[i] + ph[i] << '\n';
  }
  return overflow ? 3 : 0;
}
