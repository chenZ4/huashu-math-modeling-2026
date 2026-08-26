#ifndef SEQ_PAIR_HPP
#define SEQ_PAIR_HPP
// Sequence Pair 编码基线（Murata et al., 1995）。
// 与 FLOOR_PLAN 同接口（init/perturb/cost/get_tree/restore/blk/R/W/H），
// 供 sa.hpp 泛型 SA 驱动，用于编码消融对比实验。
// 打包：按 P 序单遍最长路径，O(n²)；关系：P、Q 同序→左，P 正 Q 反→下。
// 解析/代价/output 格式与 FLOOR_PLAN 逐位同构（int3 = (2*HPWL, W, H)），
// 独立实现以便冻结 B* 路径零改动；合法性由 verify.py + 金标准双重复核。
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

#include "floor_plan.hpp"

using namespace std;

template<typename ID, typename LEN>
class SEQ_PAIR {
public:
  struct BLOCK;
  struct NET;
  class TREE;
  SEQ_PAIR(ifstream& fnets, ifstream& fblcks, ifstream& fpl,
           const string& out_rpt, int Nnets, int Nblcks, int Ntrmns,
           float alpha, float dead_ratio, bool free_outline = false)
    : _alpha(alpha), _rot_prob(0.3f), _disp_prob(0.5f),
      _W(0), _H(0), _Nblcks(Nblcks), _Ntrmns(Ntrmns), _Nnets(Nnets),
      _out_rpt(out_rpt), _tree(Nblcks), _has_init(false), _t0(clock()) {
    read_blocks(fblcks, Nblcks, Ntrmns);
    long long total = 0;
    for (ID i = 1; i <= Nblcks; ++i)
      total += (long long)_blcks[i]._w * _blcks[i]._h;
    double side = sqrt((double)total * (1.0 + dead_ratio));
    _W = (int)ceil(side);
    _H = _W;
    read_terminals(fpl);
    read_nets(fnets);
    if (free_outline) {
      for (ID i = 1; i <= Nblcks; ++i) _rotable.push_back(i);
      return;
    }
    int cnt = 0;
    for (ID i = 1; i <= Nblcks; ++i) {
      int min_wh = min(_W, _H);
      if (max(_blcks[i]._w, _blcks[i]._h) > min_wh) {
        ++cnt;
        if (_blcks[i]._w > _W || _blcks[i]._h > _H) {
          _blcks[i]._rot = true;
          swap(_blcks[i]._w, _blcks[i]._h);
          _tree.rot[i] = 1;
        }
      } else _rotable.push_back(i);
    }
    _rot_prob *= (1 - float(cnt) / Nblcks);
  }
  // --init-order：P=Q=给定序列（首次 init() 前调用；校验失败返回 false）
  bool set_init_order(const vector<string>& names) {
    if ((ID)names.size() != _Nblcks) return false;
    vector<ID> ids;
    ids.reserve(names.size());
    for (const string& n : names) {
      auto it = _blcks_id.find(n);
      if (it == _blcks_id.end()) return false;
      ids.push_back(it->second);
    }
    sort(ids.begin(), ids.end());
    for (ID i = 1; i <= _Nblcks; ++i)
      if (ids[i - 1] != i) return false;
    TREE t(_Nblcks);
    // 保留 P/Q[0] 哨兵位（值 0），只覆写 [1..N]
    for (ID k = 0; k < _Nblcks; ++k) t.P[k + 1] = ids[k];
    t.Q = t.P;
    _tree = t;
    return true;
  }
  void init() {
    if (_has_init) return;
    pack();
    _has_init = true;
  }
  int3 cost(bool get_area = true, bool get_hpwl = true) const {
    LEN MAX_X = 0, MAX_Y = 0;
    if (get_area) {
      for (ID i = 1; i <= _Nblcks; ++i) {
        MAX_X = max(MAX_X, LEN(_blcks[i]._x + _blcks[i]._w));
        MAX_Y = max(MAX_Y, LEN(_blcks[i]._y + _blcks[i]._h));
      }
      if (!get_hpwl) return make_tuple(1, MAX_X, MAX_Y);
    }
    int hpwl = 0;
    for (auto& net : _nets) {
      LEN min_x = (LEN)2 * net._mnx, min_y = (LEN)2 * net._mny;
      LEN max_x = (LEN)2 * net._mxx, max_y = (LEN)2 * net._mxy;
      if (min_x > 0)
        for (auto& id : net._ids) {
          if (id <= _Nblcks)
            min_x = min(min_x, LEN(2 * _blcks[id]._x + _blcks[id]._w));
          else break;
        }
      if (min_y > 0)
        for (auto& id : net._ids) {
          if (id <= _Nblcks)
            min_y = min(min_y, LEN(2 * _blcks[id]._y + _blcks[id]._h));
          else break;
        }
      for (auto& id : net._ids) if (id <= _Nblcks) {
        const LEN& x = LEN(2 * _blcks[id]._x + _blcks[id]._w);
        const LEN& y = LEN(2 * _blcks[id]._y + _blcks[id]._h);
        max_x = max(max_x, x);
        max_y = max(max_y, y);
      }
      hpwl += (max_x - min_x + max_y - min_y);
    }
    return make_tuple(hpwl, MAX_X, MAX_Y);
  }
  void output(ostream& out) const {
    int width, height, hpwl; tie(hpwl, width, height) = cost();
    out << setprecision(13) << _alpha * width * height + (1 - _alpha) * hpwl / 2. << '\n';
    out << hpwl / 2. << '\n';
    out << width * height << '\n';
    out << width << " " << height << '\n';
    out << double(clock() - _t0) / CLOCKS_PER_SEC << '\n';
    for (ID i = 1; i <= _Nblcks; ++i) {
      out << _blcks[i]._name << " " << int(_blcks[i]._x) << " "
          << int(_blcks[i]._y) << " " << int(_blcks[i]._x + _blcks[i]._w) << " "
          << int(_blcks[i]._y + _blcks[i]._h) << '\n';
    }
  }
  void perturb() {
    float p1 = randf(), p2 = randf();
    if (p1 < _rot_prob) rotate_one();
    else if (p2 < _disp_prob) displace();
    else swap_q();
    _has_init = false;
  }
  void restore(const TREE& t) {
    _tree = t;
    for (ID i = 1; i <= _Nblcks; ++i) if (_blcks[i]._rot ^ (bool)_tree.rot[i]) {
      swap(_blcks[i]._w, _blcks[i]._h);
      _blcks[i]._rot = _tree.rot[i];
    }
    _has_init = false;
  }
  float R() const { return float(_H) / _W; }
  int W() const { return _W; }
  int H() const { return _H; }
  int Nblcks() const { return _Nblcks; }
  int Ntrmns() const { return _Ntrmns; }
  int Nnets() const { return _Nnets; }
  const BLOCK& blk(ID i) const { return _blcks[i]; }
  TREE get_tree() { return _tree; }
  class TREE {
  public:
    TREE() {};
    explicit TREE(ID Nblcks)
      : P(Nblcks + 1), Q(Nblcks + 1), rot(Nblcks + 1, 0) {
      iota(P.begin() + 1, P.end(), ID(1));
      shuffle(P.begin() + 1, P.end(), mt19937((unsigned)rand()));
      iota(Q.begin() + 1, Q.end(), ID(1));
      shuffle(Q.begin() + 1, Q.end(), mt19937((unsigned)rand()));
    }
    vector<ID> P, Q;   // 正/负序列，位置 0 弃用
    vector<uchar> rot; // 每块旋转位（下标即块 ID）
    void rotate(ID id) { rot[id] ^= 1; }
    void swap_two_nodes(ID i, ID j) {
      ID pi = 0, pj = 0;
      for (ID k = 1; k < ID(P.size()); ++k) {
        if (P[k] == i) pi = k;
        if (P[k] == j) pj = k;
      }
      swap(P[pi], P[pj]);
    }
  };
private:
  void pack() {
    for (ID k = 1; k <= _Nblcks; ++k) _posq[_tree.Q[k]] = k;
    for (ID a = 1; a <= _Nblcks; ++a) {
      const ID i = _tree.P[a];
      LEN x = 0, y = 0;
      for (ID b = 1; b < a; ++b) {
        const ID j = _tree.P[b];
        if (_posq[j] < _posq[i]) x = max(x, LEN(_blcks[j]._x + _blcks[j]._w));
        else y = max(y, LEN(_blcks[j]._y + _blcks[j]._h));
      }
      _blcks[i]._x = x;
      _blcks[i]._y = y;
    }
  }
  void rotate_one() {
    if (_rotable.empty()) return;
    ID id = _rotable[(rand() % _rotable.size())];
    _blcks[id]._rot = !_blcks[id]._rot;
    swap(_blcks[id]._w, _blcks[id]._h);
    _tree.rot[id] ^= 1;
  }
  void displace() {
    if (_Nblcks < 2) return;
    ID id = (rand() % _Nblcks) + 1;
    ID at = 0;
    while (_tree.P[at] != id) ++at;
    _tree.P.erase(_tree.P.begin() + at);
    ID pos = (rand() % _Nblcks) + 1; // 插入位∈[1,N]，避开 P[0] 哨兵
    _tree.P.insert(_tree.P.begin() + pos, id);
  }
  void swap_q() {
    if (_Nblcks < 2) return;
    ID p1 = rand() % _Nblcks;
    ID p2 = (p1 + ((rand() % (_Nblcks - 1)) + 1)) % _Nblcks;
    swap(_tree.Q[p1 + 1], _tree.Q[p2 + 1]);
  }
  void read_blocks(ifstream& fblcks, int Nblcks, int Ntrmns) {
    read_labeled_int(fblcks);
    read_labeled_int(fblcks);
    _blcks.resize(1, {0, 0, 0, "NULL"});
    vector<tuple<string, LEN, LEN>> blocks;
    vector<string> terms;
    string line;
    while (getline(fblcks, line)) {
      if (line.empty()) continue;
      for (char& c : line)
        if (c == '(' || c == ')' || c == ',') c = ' ';
      istringstream iss(line);
      string name, type;
      if (!(iss >> name >> type)) continue;
      if (type == "terminal") {
        terms.push_back(name);
      } else {
        int nc; iss >> nc;
        LEN minx = 1 << 28, miny = 1 << 28, maxx = 0, maxy = 0;
        for (int k = 0; k < nc; ++k) {
          LEN x, y; iss >> x >> y;
          minx = min(minx, x); maxx = max(maxx, x);
          miny = min(miny, y); maxy = max(maxy, y);
        }
        if (maxx <= minx || maxy <= miny) {
          cerr << "degenerate block " << name << " with zero extent\n";
          exit(1);
        }
        blocks.emplace_back(name, maxx - minx, maxy - miny);
      }
    }
    if (int(blocks.size()) != Nblcks || int(terms.size()) != Ntrmns) {
      cerr << "block/terminal count mismatch: blocks=" << blocks.size()
           << " expect=" << Nblcks << " terms=" << terms.size()
           << " expect=" << Ntrmns << '\n';
      exit(1);
    }
    for (auto& b : blocks) {
      ID id = ID(_blcks.size());
      _blcks.emplace_back(id, get<1>(b), get<2>(b), get<0>(b));
      _blcks_id[get<0>(b)] = id;
    }
    for (auto& t : terms) {
      ID id = ID(_blcks.size());
      _blcks.emplace_back(id, 0, 0, t);
      _blcks_id[t] = id;
    }
    _posq.resize(Nblcks + 1);
  }
  void read_terminals(ifstream& fpl) {
    map<string, pair<int, int>> pos;
    string name; int x, y;
    while (fpl >> name >> x >> y) pos[name] = make_pair(x, y);
    for (ID i = _Nblcks + 1; i <= _Nblcks + _Ntrmns; ++i) {
      auto it = pos.find(_blcks[i]._name);
      if (it == pos.end()) {
        cerr << "terminal " << _blcks[i]._name << " missing in .pl\n";
        exit(1);
      }
      _blcks[i]._x = it->second.first;
      _blcks[i]._y = it->second.second;
    }
  }
  void read_nets(ifstream& fnets) {
    read_labeled_int(fnets);
    read_labeled_int(fnets);
    _nets.reserve(_Nnets);
    for (int i = 1; i <= _Nnets; ++i) {
      int deg = read_labeled_int(fnets);
      _nets.emplace_back(i);
      auto& net = _nets.back();
      net._ids.reserve(deg);
      for (int j = 0; j < deg; ++j) {
        string name; fnets >> name;
        auto it = _blcks_id.find(name);
        if (it == _blcks_id.end()) {
          cerr << "unknown pin " << name << " in net " << i << '\n';
          exit(1);
        }
        ID bid = it->second;
        net._ids.push_back(bid);
        if (bid > _Nblcks) net.update(_blcks[bid]._x, _blcks[bid]._y);
      }
      sort(net._ids.begin(), net._ids.end());
    }
  }
  float randf() const { return float(rand()) / float(RAND_MAX); }
public:
  struct BLOCK {
    BLOCK(ID id, LEN w, LEN h, const string& name, LEN x = 0, LEN y = 0,
          bool rot = false)
      : _id(id), _w(w), _h(h), _x(x), _y(y), _name(name), _rot(rot) {};
    ID _id;
    LEN _w, _h, _x, _y;
    string _name;
    bool _rot;
  };
  struct NET {
    NET(ID id) : _id(id), _mxx(0), _mxy(0),
                 _mnx(1 << (sizeof(LEN) * 8 - 3)), _mny(1 << (sizeof(LEN) * 8 - 3)) {};
    void update(LEN x, LEN y) {
      _mxx = max(_mxx, x);
      _mxy = max(_mxy, y);
      _mnx = min(_mnx, x);
      _mny = min(_mny, y);
    }
    ID _id;
    LEN _mxx, _mxy, _mnx, _mny;
    vector<ID> _ids;
  };
private:
  float _alpha, _rot_prob, _disp_prob;
  int _W, _H, _Nblcks, _Ntrmns, _Nnets;
  string _out_rpt;
  vector<BLOCK> _blcks;
  vector<NET> _nets;
  TREE _tree;
  vector<ID> _posq;
  map<string, ID> _blcks_id;
  bool _has_init;
  vector<ID> _rotable;
  clock_t _t0;
};

#endif
