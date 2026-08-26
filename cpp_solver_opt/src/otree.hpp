#ifndef OTREE_HPP
#define OTREE_HPP
// O-tree 编码基线（Guo & Chu, TCAD 2001）。
// 与 FLOOR_PLAN / SEQ_PAIR 同接口（init/perturb/cost/get_tree/restore/blk/R/W/H），
// 供 sa.hpp 泛型 SA 驱动，用于编码消融对比实验。
// 打包：DFS 预序遍历 + skyline 放置，O(n²)；编码：parent 数组（多叉树）。
// 解析/代价/output 格式与 SEQ_PAIR 逐位同构（int3 = (2*HPWL, W, H)），
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
class OTREE {
public:
  struct BLOCK;
  struct NET;
  class TREE;
  OTREE(ifstream& fnets, ifstream& fblcks, ifstream& fpl,
        const string& out_rpt, int Nnets, int Nblcks, int Ntrmns,
        float alpha, float dead_ratio, bool free_outline = false)
    : _alpha(alpha), _rot_prob(0.3f), _del_and_ins_prob(0.5f),
      _W(0), _H(0), _Nblcks(Nblcks), _Ntrmns(Ntrmns), _Nnets(Nnets),
      _out_rpt(out_rpt), _tree(Nblcks), _has_init(false), _t0(clock()) {
    read_blocks(fblcks, Nblcks, Ntrmns);
    long long total = 0;
    for (ID i = 1; i <= Nblcks; ++i)
      total += (long long)_blks[i]._w * _blks[i]._h;
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
      if (max(_blks[i]._w, _blks[i]._h) > min_wh) {
        ++cnt;
        if (_blks[i]._w > _W || _blks[i]._h > _H) {
          _blks[i]._rot = true;
          swap(_blks[i]._w, _blks[i]._h);
          _tree.rot[i] = 1;
        }
      } else _rotable.push_back(i);
    }
    _rot_prob *= (1 - float(cnt) / Nblcks);
  }
  bool set_init_order(const vector<string>& names) {
    if ((ID)names.size() != _Nblcks) return false;
    vector<ID> ids;
    ids.reserve(names.size());
    for (const string& n : names) {
      auto it = _blks_id.find(n);
      if (it == _blks_id.end()) return false;
      ids.push_back(it->second);
    }
    sort(ids.begin(), ids.end());
    for (ID i = 1; i <= _Nblcks; ++i)
      if (ids[i - 1] != i) return false;
    TREE t(_Nblcks);
    // 初始链式树：parent[i] = i-1（每个块是前一个块的子节点）
    for (ID k = 0; k < _Nblcks; ++k)
      t.parent[ids[k]] = (k == 0) ? 0 : ids[k - 1];
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
        MAX_X = max(MAX_X, LEN(_blks[i]._x + _blks[i]._w));
        MAX_Y = max(MAX_Y, LEN(_blks[i]._y + _blks[i]._h));
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
            min_x = min(min_x, LEN(2 * _blks[id]._x + _blks[id]._w));
          else break;
        }
      if (min_y > 0)
        for (auto& id : net._ids) {
          if (id <= _Nblcks)
            min_y = min(min_y, LEN(2 * _blks[id]._y + _blks[id]._h));
          else break;
        }
      for (auto& id : net._ids) if (id <= _Nblcks) {
        const LEN& x = LEN(2 * _blks[id]._x + _blks[id]._w);
        const LEN& y = LEN(2 * _blks[id]._y + _blks[id]._h);
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
      out << _blks[i]._name << " " << int(_blks[i]._x) << " "
          << int(_blks[i]._y) << " " << int(_blks[i]._x + _blks[i]._w) << " "
          << int(_blks[i]._y + _blks[i]._h) << '\n';
    }
  }
  void perturb() {
    float p1 = randf(), p2 = randf();
    if (p1 < _rot_prob) rotate_one();
    else if (p2 < _del_and_ins_prob) del_and_ins();
    else swap_two();
    _has_init = false;
  }
  void restore(const TREE& t) {
    _tree = t;
    for (ID i = 1; i <= _Nblcks; ++i) if (_blks[i]._rot ^ (bool)_tree.rot[i]) {
      swap(_blks[i]._w, _blks[i]._h);
      _blks[i]._rot = _tree.rot[i];
    }
    _has_init = false;
  }
  float R() const { return float(_H) / _W; }
  int W() const { return _W; }
  int H() const { return _H; }
  int Nblcks() const { return _Nblcks; }
  int Ntrmns() const { return _Ntrmns; }
  int Nnets() const { return _Nnets; }
  const BLOCK& blk(ID i) const { return _blks[i]; }
  TREE get_tree() { return _tree; }
  class TREE {
  public:
    TREE() {};
    explicit TREE(ID Nblcks)
      : parent(Nblcks + 1, 0), rot(Nblcks + 1, 0) {
      // 随机树：每个块的父节点从 [0..i-1] 中随机选取
      for (ID i = 1; i <= Nblcks; ++i)
        parent[i] = rand() % i;
    }
    vector<ID> parent;  // parent[i] = 父节点（0 = 根/虚拟节点）
    vector<uchar> rot;  // 每块旋转位（下标即块 ID）
    void rotate(ID id) { rot[id] ^= 1; }
    void swap_two_nodes(ID i, ID j) {
      // 交换两个块的父节点；若产生环则撤销
      swap(parent[i], parent[j]);
      if (has_cycle(i) || has_cycle(j))
        swap(parent[i], parent[j]);
    }
  private:
    bool has_cycle(ID start) const {
      vector<uchar> vis(parent.size(), 0);
      ID cur = start;
      while (cur != 0) {
        if (vis[cur]) return true;
        vis[cur] = 1;
        cur = parent[cur];
      }
      return false;
    }
  };
private:
  void pack() {
    vector<vector<ID>> ch(_Nblcks + 1);
    for (ID i = 1; i <= _Nblcks; ++i)
      ch[_tree.parent[i]].push_back(i);
    for (auto& v : ch) sort(v.begin(), v.end());
    // skyline 向量扩展到能容纳所有块宽度之和（安全上界）
    LEN max_extent = _W;
    for (ID i = 1; i <= _Nblcks; ++i)
      max_extent += _blks[i]._w;
    vector<LEN> skyline(max_extent + 1, 0);
    for (ID child : ch[0])
      dfs_pack(child, ch, skyline);
  }
  void dfs_pack(ID id, const vector<vector<ID>>& ch,
                vector<LEN>& skyline) {
    ID pid = _tree.parent[id];
    LEN x = 0;
    if (pid != 0) {
      const auto& siblings = ch[pid];
      bool found_self = false;
      for (ID sib : siblings) {
        if (sib == id) { found_self = true; break; }
        x = max(x, LEN(_blks[sib]._x + _blks[sib]._w));
      }
      if (!found_self || x == 0)
        x = LEN(_blks[pid]._x + _blks[pid]._w);
    }
    // skyline 查找最大高度（完整宽度，含超出轮廓部分）
    LEN y = 0;
    LEN x_end = x + _blks[id]._w;
    for (LEN k = x; k < x_end; ++k)
      y = max(y, skyline[k]);
    _blks[id]._x = x;
    _blks[id]._y = y;
    // 完整更新 skyline
    for (LEN k = x; k < x_end; ++k)
      skyline[k] = y + _blks[id]._h;
    for (ID child : ch[id])
      dfs_pack(child, ch, skyline);
  }
  void rotate_one() {
    if (_rotable.empty()) return;
    ID id = _rotable[(rand() % _rotable.size())];
    _blks[id]._rot = !_blks[id]._rot;
    swap(_blks[id]._w, _blks[id]._h);
    _tree.rot[id] ^= 1;
  }
  void del_and_ins() {
    if (_Nblcks < 2) return;
    ID id = (rand() % _Nblcks) + 1;
    ID new_parent = rand() % _Nblcks; // [0, N-1]
    if (new_parent >= id) new_parent = (new_parent + 1) % (_Nblcks + 1);
    // 尝试新父节点，若产生环则不操作
    ID old_parent = _tree.parent[id];
    _tree.parent[id] = new_parent;
    if (_tree_has_cycle(id)) _tree.parent[id] = old_parent;
  }
  void swap_two() {
    if (_Nblcks < 2) return;
    ID p1 = (rand() % _Nblcks) + 1;
    ID p2 = p1;
    while (p2 == p1) p2 = (rand() % _Nblcks) + 1;
    _tree.swap_two_nodes(p1, p2);
  }
  bool _tree_has_cycle(ID start) const {
    vector<uchar> vis(_Nblcks + 1, 0);
    ID cur = start;
    while (cur != 0) {
      if (vis[cur]) return true;
      vis[cur] = 1;
      cur = _tree.parent[cur];
    }
    return false;
  }
  void read_blocks(ifstream& fblcks, int Nblcks, int Ntrmns) {
    read_labeled_int(fblcks);
    read_labeled_int(fblcks);
    _blks.resize(1, {0, 0, 0, "NULL"});
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
      ID id = ID(_blks.size());
      _blks.emplace_back(id, get<1>(b), get<2>(b), get<0>(b));
      _blks_id[get<0>(b)] = id;
    }
    for (auto& t : terms) {
      ID id = ID(_blks.size());
      _blks.emplace_back(id, 0, 0, t);
      _blks_id[t] = id;
    }
  }
  void read_terminals(ifstream& fpl) {
    map<string, pair<int, int>> pos;
    string name; int x, y;
    while (fpl >> name >> x >> y) pos[name] = make_pair(x, y);
    for (ID i = _Nblcks + 1; i <= _Nblcks + _Ntrmns; ++i) {
      auto it = pos.find(_blks[i]._name);
      if (it == pos.end()) {
        cerr << "terminal " << _blks[i]._name << " missing in .pl\n";
        exit(1);
      }
      _blks[i]._x = it->second.first;
      _blks[i]._y = it->second.second;
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
        auto it = _blks_id.find(name);
        if (it == _blks_id.end()) {
          cerr << "unknown pin " << name << " in net " << i << '\n';
          exit(1);
        }
        ID bid = it->second;
        net._ids.push_back(bid);
        if (bid > _Nblcks) net.update(_blks[bid]._x, _blks[bid]._y);
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
  float _alpha, _rot_prob, _del_and_ins_prob;
  int _W, _H, _Nblcks, _Ntrmns, _Nnets;
  string _out_rpt;
  vector<BLOCK> _blks;
  vector<NET> _nets;
  TREE _tree;
  map<string, ID> _blks_id;
  bool _has_init;
  vector<ID> _rotable;
  clock_t _t0;
};

#endif
