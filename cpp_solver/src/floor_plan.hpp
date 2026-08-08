#ifndef FLOOR_PLAN_HPP
#define FLOOR_PLAN_HPP

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

using namespace std;

typedef unsigned char uchar;
typedef unsigned short ushort;
typedef unsigned int uint;
typedef tuple<int, int, int> int3;

int read_labeled_int(istream& fs) {
  string tok;
  if (!(fs >> tok)) return -1;
  if (!tok.empty() && tok.back() == ':') {
    int n;
    if (!(fs >> n)) return -1;
    return n;
  }
  string tok2;
  if (!(fs >> tok2)) return -1;
  if (tok2 == ":") {
    int n;
    if (!(fs >> n)) return -1;
    return n;
  }
  try {
    return stoi(tok2);
  } catch (...) {
    return -1;
  }
}

template<typename ID, typename LEN>
class FLOOR_PLAN {
public:
  struct BLOCK;
  struct NET;
  struct NODE;
  class TREE;
  FLOOR_PLAN(ifstream& fnets, ifstream& fblcks, ifstream& fpl,
             const string& out_rpt, int Nnets, int Nblcks, int Ntrmns,
             float alpha, float dead_ratio, bool free_outline = false)
    : _alpha(alpha), _rot_prob(0.3f), _del_and_ins_prob(0.5f),
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
          _tree.set_rot(i);
        }
      } else _rotable.push_back(i);
    }
    _rot_prob *= (1 - float(cnt) / Nblcks);
  }
#ifdef TREE_DEBUG
  FLOOR_PLAN(const vector<tuple<int, int, string>>& blk_specs,
             const vector<tuple<int, int, string>>& term_specs,
             int W, int H, float alpha)
    : _alpha(alpha), _rot_prob(0.3f), _del_and_ins_prob(0.5f),
      _W(W), _H(H), _Nblcks(int(blk_specs.size())),
      _Ntrmns(int(term_specs.size())), _Nnets(0), _out_rpt(""),
      _tree(int(blk_specs.size())), _has_init(false), _t0(clock()) {
    _blcks.resize(1, {0, 0, 0, "NULL"});
    for (auto& spec : blk_specs) {
      ID id = ID(_blcks.size());
      _blcks.emplace_back(id, get<0>(spec), get<1>(spec), get<2>(spec));
      _blcks_id[get<2>(spec)] = id;
    }
    for (auto& spec : term_specs) {
      ID id = ID(_blcks.size());
      _blcks.emplace_back(id, 0, 0, get<2>(spec), get<0>(spec), get<1>(spec));
      _blcks_id[get<2>(spec)] = id;
    }
    for (ID i = 1; i <= _Nblcks; ++i) _rotable.push_back(i);
  }
#endif
  void init() {
    if (_has_init) return;
    _tree.init(_blcks);
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
        for (auto& id : net._blcks) {
          if (id <= _Nblcks)
            min_x = min(min_x, LEN(2 * _blcks[id]._x + _blcks[id]._w));
          else break;
        }
      if (min_y > 0)
        for (auto& id : net._blcks) {
          if (id <= _Nblcks)
            min_y = min(min_y, LEN(2 * _blcks[id]._y + _blcks[id]._h));
          else break;
        }
      for (auto& id : net._blcks) if (id <= _Nblcks) {
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
    if (p1 < _rot_prob) rotate();
    else if (p2 < _del_and_ins_prob) del_and_ins();
    else swap_two_nodes();
    _has_init = false;
  }
  void restore(const TREE& tree) {
    _tree = tree;
    for (ID i = 1; i <= _Nblcks; ++i) if (_blcks[i]._rot ^ _tree.rot(i)) {
      swap(_blcks[i]._w, _blcks[i]._h);
      _blcks[i]._rot = _tree.rot(i);
    }
    _has_init = false;
  }
  float R() const { return float(_H) / _W; }
  int W() const { return _W; }
  int H() const { return _H; }
  int Nblcks() const { return _Nblcks; }
  int Ntrmns() const { return _Ntrmns; }
  int Nnets() const { return _Nnets; }
  TREE get_tree() { return _tree; }
#ifdef TREE_DEBUG
  const TREE& tree() const { return _tree; }
  const BLOCK& blk(ID i) const { return _blcks[i]; }
  const NET& dbg_net(int idx) const { return _nets[idx]; }
  void dbg_reset_init() { _has_init = false; }
  void dbg_rotate() { rotate(); _has_init = false; }
  void dbg_del_ins() { del_and_ins(); _has_init = false; }
  void dbg_swap() { swap_two_nodes(); _has_init = false; }
#endif
private:
  void read_blocks(ifstream& fblcks, int Nblcks, int Ntrmns) {
    read_labeled_int(fblcks);
    read_labeled_int(fblcks);
    if (Nblcks + Ntrmns + 2 >= (1 << 10)) {
      cerr << "too many nodes for 10-bit packing: " << Nblcks + Ntrmns << '\n';
      exit(1);
    }
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
      net._blcks.reserve(deg);
      for (int j = 0; j < deg; ++j) {
        string name; fnets >> name;
        auto it = _blcks_id.find(name);
        if (it == _blcks_id.end()) {
          cerr << "unknown pin " << name << " in net " << i << '\n';
          exit(1);
        }
        ID bid = it->second;
        net._blcks.push_back(bid);
        if (bid > _Nblcks) net.update(_blcks[bid]._x, _blcks[bid]._y);
      }
      net.do_sort();
    }
  }
  void rotate() {
    if (_rotable.empty()) return;
    ID id = _rotable[(rand() % _rotable.size())];
    _blcks[id]._rot = !_blcks[id]._rot;
    swap(_blcks[id]._w, _blcks[id]._h);
    _tree.rotate(id);
  }
  void del_and_ins() {
    if (_Nblcks < 2) return;
    ID id = (rand() % _Nblcks) + 1;
    _tree.del_from_tree(id);
    ID p = (rand() % _Nblcks) + 1;
    bool left = randb();
    while (id == p) p = (rand() % _Nblcks) + 1;
    _tree.ins_to_tree(p, id, left);
  }
  void swap_two_nodes() {
    if (_Nblcks < 2) return;
    ID id1 = rand() % _Nblcks;
    ID id2 = (id1 + ((rand() % (_Nblcks - 1)) + 1)) % _Nblcks;
    _tree.swap_two_nodes(id1 + 1, id2 + 1);
  }
  float randf() const { return float(rand()) / float(RAND_MAX); }
  bool randb() const { return rand() % 2; }
  float _alpha, _rot_prob, _del_and_ins_prob;
  int _W, _H, _Nblcks, _Ntrmns, _Nnets;
  string _out_rpt;
  vector<BLOCK> _blcks;
  vector<NET> _nets;
  TREE _tree;
  map<string, ID> _blcks_id;
  bool _has_init;
  vector<ID> _rotable;
  vector<bool> _bads;
  clock_t _t0;
};
template<typename ID, typename LEN> class FLOOR_PLAN<ID, LEN>::TREE {
public:
  TREE() {};
  TREE(ID Nblcks) {
    vector<ID> _tree(Nblcks + 1);
    iota(_tree.begin() + 1, _tree.end(), 1);
    shuffle(_tree.begin() + 1, _tree.end(), mt19937((unsigned)rand()));
    _nodes.resize(Nblcks + 1);
    for (ID i = 1; i <= Nblcks; ++i) {
      ID& id = _tree[i];
      _nodes[id].s_p(_tree[i / 2]);
      if (i * 2 <= Nblcks) _nodes[id].s_l(_tree[i * 2]);
      if (i * 2 + 1 <= Nblcks) _nodes[id].s_r(_tree[i * 2 + 1]);
    }
    _nodes[0].s_p(_tree[1]);
  }
#ifdef TREE_DEBUG
  TREE(ID Nblcks, const vector<ID>& P, const vector<ID>& L, const vector<ID>& R) {
    _nodes.resize(Nblcks + 1);
    _nodes[0].s_p(P[0]);
    for (ID i = 1; i <= Nblcks; ++i) {
      _nodes[i].s_p(P[i]);
      _nodes[i].s_l(L[i]);
      _nodes[i].s_r(R[i]);
    }
  }
#endif
  void init(vector<BLOCK>& blcks) {
    const ID& root_id = _nodes[0]._p();
    blcks[root_id]._x = blcks[root_id]._y = 0;
    list<ID> cy(1, root_id);
    auto cur = cy.begin();
    dfs(root_id, cy, cur, blcks);
#ifdef TREE_DEBUG
    _dbg_cy.assign(cy.begin(), cy.end());
#endif
  }
  void rotate(ID id) {
    _nodes[id].s_rot();
  }
  void swap_two_nodes(ID id1, ID id2) {
    if (_nodes[id1]._p() == id2) swap_near(id2, id1);
    else if (_nodes[id2]._p() == id1) swap_near(id1, id2);
    else swap_not_near(id1, id2);
  }
  void del_from_tree(ID id) {
    if (_nodes[id]._l() && _nodes[id]._r()) {
      while (_nodes[id]._l() && _nodes[id]._r()) {
        ID p = id;
        id = (randb() ? _nodes[id]._l() : _nodes[id]._r());
        swap_near(p, id);
        id = p;
      }
      del_from_tree(id);
    } else if (_nodes[id]._l()) {
      if (id == _nodes[0]._p()) {
        _nodes[0].s_p(_nodes[id]._l());
        _nodes[_nodes[id]._l()].s_p(0);
      }
      else {
        _nodes[_nodes[id]._l()].s_p(_nodes[id]._p());
        if (id == _nodes[_nodes[id]._p()]._l())
          _nodes[_nodes[id]._p()].s_l(_nodes[id]._l());
        else if (id == _nodes[_nodes[id]._p()]._r())
          _nodes[_nodes[id]._p()].s_r(_nodes[id]._l());
      }
    } else if (_nodes[id]._r()) {
      if (id == _nodes[0]._p()) {
        _nodes[0].s_p(_nodes[id]._r());
        _nodes[_nodes[id]._r()].s_p(0);
      }
      else {
        _nodes[_nodes[id]._r()].s_p(_nodes[id]._p());
        if (id == _nodes[_nodes[id]._p()]._l())
          _nodes[_nodes[id]._p()].s_l(_nodes[id]._r());
        else if (id == _nodes[_nodes[id]._p()]._r())
          _nodes[_nodes[id]._p()].s_r(_nodes[id]._r());
      }
    } else {
      if (id == _nodes[_nodes[id]._p()]._l())
        _nodes[_nodes[id]._p()].s_l(0);
      else if (id == _nodes[_nodes[id]._p()]._r())
        _nodes[_nodes[id]._p()].s_r(0);
    }
    _nodes[id].s_p(0);
  }
  void ins_to_tree(ID p, ID id, bool left) {
    if (left) {
      _nodes[id].s_l(_nodes[p]._l());
      _nodes[id].s_r(0);
      if (_nodes[p]._l()) _nodes[_nodes[p]._l()].s_p(id);
      _nodes[p].s_l(id);
      _nodes[id].s_p(p);
    } else {
      _nodes[id].s_r(_nodes[p]._r());
      _nodes[id].s_l(0);
      if (_nodes[p]._r()) _nodes[_nodes[p]._r()].s_p(id);
      _nodes[p].s_r(id);
      _nodes[id].s_p(p);
    }
  }
  bool rot(ID id) const { return _nodes[id]._rot(); }
  void set_rot(ID id) { _nodes[id].s_rot(); }
#ifdef TREE_DEBUG
  bool validate_tree(string& err) const {
    err.clear();
    const ID N = ID(_nodes.size()) - 1;
    if (N == 0) { err = "empty tree"; return false; }
    const ID root = _nodes[0]._p();
    if (root < 1 || root > N) { err = "root oob: " + to_string(int(root)); return false; }
    vector<uchar> color(N + 1, 0);
    vector<ID> stk(1, root);
    color[root] = 1;
    ID visited = 0;
    while (!stk.empty()) {
      const ID u = stk.back();
      stk.pop_back();
      if (color[u] != 1) {
        err = "revisit/cycle at node " + to_string(int(u));
        return false;
      }
      color[u] = 2;
      ++visited;
      const ID l = _nodes[u]._l(), r = _nodes[u]._r(), p = _nodes[u]._p();
      if (l > N || r > N || p > N) {
        err = "oob children at node " + to_string(int(u))
           + " p=" + to_string(int(p)) + " l=" + to_string(int(l))
           + " r=" + to_string(int(r));
        return false;
      }
      if (p != 0 && _nodes[p]._l() != u && _nodes[p]._r() != u) {
        err = "parent-child mismatch at node " + to_string(int(u))
           + " (p=" + to_string(int(p)) + ")";
        return false;
      }
      if (l != 0) {
        if (l == r) { err = "duplicate child l==r at node " + to_string(int(u)); return false; }
        if (color[l] != 0) { err = "cycle via left child at node " + to_string(int(u)); return false; }
        if (_nodes[l]._p() != u) { err = "left child parent mismatch at node " + to_string(int(u)); return false; }
        color[l] = 1; stk.push_back(l);
      }
      if (r != 0) {
        if (color[r] != 0) { err = "cycle via right child at node " + to_string(int(u)); return false; }
        if (_nodes[r]._p() != u) { err = "right child parent mismatch at node " + to_string(int(u)); return false; }
        color[r] = 1; stk.push_back(r);
      }
    }
    for (ID i = 1; i <= N; ++i)
      if (color[i] != 2) {
        err = "orphan/unreachable node " + to_string(int(i))
           + " (p=" + to_string(int(_nodes[i]._p()))
           + " l=" + to_string(int(_nodes[i]._l()))
           + " r=" + to_string(int(_nodes[i]._r())) + ")";
        return false;
      }
    if (visited != N) { err = "visited count mismatch"; return false; }
    return true;
  }
  void dbg_set_p(ID u, ID v) { _nodes[u].s_p(v); }
  void dbg_set_l(ID u, ID v) { _nodes[u].s_l(v); }
  void dbg_set_r(ID u, ID v) { _nodes[u].s_r(v); }
  void dbg_set_root(ID r) { _nodes[0].s_p(r); }
  ID dbg_p(ID u) const { return _nodes[u]._p(); }
  ID dbg_l(ID u) const { return _nodes[u]._l(); }
  ID dbg_r(ID u) const { return _nodes[u]._r(); }
  ID dbg_root() const { return _nodes[0]._p(); }
  const vector<ID>& dbg_cy() const { return _dbg_cy; }
#endif
private:
  bool randb() const { return rand() % 2; }
  void dfs(ID id, list<ID>& cy, typename list<ID>::iterator& cur,
           vector<BLOCK>& blcks) {
    if (_nodes[id]._l()) {
      const ID& lc = _nodes[id]._l();
      blcks[lc]._x = blcks[id]._x + blcks[id]._w;
      blcks[lc]._y = find_max_y(cy, ++cur, blcks, blcks[lc]);
      dfs(_nodes[id]._l(), cy, cur, blcks);
      --cur;
    }
    if (_nodes[id]._r()) {
      const ID& rc = _nodes[id]._r();
      blcks[rc]._x = blcks[id]._x;
      blcks[rc]._y = find_max_y(cy, cur, blcks, blcks[rc]);
      dfs(_nodes[id]._r(), cy, cur, blcks);
    }
  }
  LEN find_max_y(list<ID>& l, typename list<ID>::iterator& cur,
                 vector<BLOCK>& blcks, BLOCK& blck) {
    LEN y = 0;
    auto it = cur, rit = cur;
    while (it != l.end() && blcks[*it]._x < blck._x + blck._w) {
      if (blcks[*it]._y + blcks[*it]._h > y) y = blcks[*it]._y + blcks[*it]._h;
      if (blcks[*rit]._x + blcks[*rit]._w <= blck._x + blck._w) ++rit;
      ++it;
    }
    cur = l.erase(cur, rit);
    cur = l.insert(cur, blck._id);
    return y;
  }
  void swap_not_near(ID id1, ID id2) {
    if (_nodes[id1]._p() == _nodes[id2]._p()) {
      ID tmp = _nodes[_nodes[id1]._p()]._l();
      _nodes[_nodes[id1]._p()].s_l(_nodes[_nodes[id1]._p()]._r());
      _nodes[_nodes[id1]._p()].s_r(tmp);
      ID tmpl = _nodes[id1]._l();
      _nodes[id1].s_l(_nodes[id2]._l());
      _nodes[id2].s_l(tmpl);
      ID tmpr = _nodes[id1]._r();
      _nodes[id1].s_r(_nodes[id2]._r());
      _nodes[id2].s_r(tmpr);
    } else {
      if (id1 == _nodes[0]._p()) _nodes[0].s_p(id2);
      else if (id2 == _nodes[0]._p()) _nodes[0].s_p(id1);
      if (_nodes[_nodes[id1]._p()]._l() == id1)
        _nodes[_nodes[id1]._p()].s_l(id2);
      else if (_nodes[_nodes[id1]._p()]._r() == id1)
        _nodes[_nodes[id1]._p()].s_r(id2);
      if (_nodes[_nodes[id2]._p()]._l() == id2)
        _nodes[_nodes[id2]._p()].s_l(id1);
      else if (_nodes[_nodes[id2]._p()]._r() == id2)
        _nodes[_nodes[id2]._p()].s_r(id1);
    }
    if (_nodes[id1]._l()) _nodes[_nodes[id1]._l()].s_p(id2);
    if (_nodes[id2]._l()) _nodes[_nodes[id2]._l()].s_p(id1);
    if (_nodes[id1]._r()) _nodes[_nodes[id1]._r()].s_p(id2);
    if (_nodes[id2]._r()) _nodes[_nodes[id2]._r()].s_p(id1);
    ID tmpp = _nodes[id1]._p();
    _nodes[id1].s_p(_nodes[id2]._p());
    _nodes[id2].s_p(tmpp);
    ID tmpl = _nodes[id1]._l();
    _nodes[id1].s_l(_nodes[id2]._l());
    _nodes[id2].s_l(tmpl);
    ID tmpr = _nodes[id1]._r();
    _nodes[id1].s_r(_nodes[id2]._r());
    _nodes[id2].s_r(tmpr);
  }
  void swap_near(ID p, ID id) {
    if (p == _nodes[0]._p()) _nodes[0].s_p(id);
    else if (p == _nodes[_nodes[p]._p()]._l())
      _nodes[_nodes[p]._p()].s_l(id);
    else if (p == _nodes[_nodes[p]._p()]._r())
      _nodes[_nodes[p]._p()].s_r(id);
    if (_nodes[p]._l() == id) {
      _nodes[p].s_l(_nodes[id]._l());
      if (_nodes[id]._l()) _nodes[_nodes[id]._l()].s_p(p);
      _nodes[id].s_l(p);
      if (_nodes[id]._r()) _nodes[_nodes[id]._r()].s_p(p);
      if (_nodes[p]._r()) _nodes[_nodes[p]._r()].s_p(id);
      ID tmp = _nodes[id]._r();
      _nodes[id].s_r(_nodes[p]._r());
      _nodes[p].s_r(tmp);
    } else if (_nodes[p]._r() == id) {
      _nodes[p].s_r(_nodes[id]._r());
      if (_nodes[id]._r()) _nodes[_nodes[id]._r()].s_p(p);
      _nodes[id].s_r(p);
      if (_nodes[id]._l()) _nodes[_nodes[id]._l()].s_p(p);
      if (_nodes[p]._l()) _nodes[_nodes[p]._l()].s_p(id);
      ID tmp = _nodes[id]._l();
      _nodes[id].s_l(_nodes[p]._l());
      _nodes[p].s_l(tmp);
    }
    _nodes[id].s_p(_nodes[p]._p());
    _nodes[p].s_p(id);
  }
  vector<NODE> _nodes;
#ifdef TREE_DEBUG
  vector<ID> _dbg_cy;
#endif
};
template<typename ID, typename LEN> struct FLOOR_PLAN<ID, LEN>::BLOCK {
  BLOCK(ID id, LEN w, LEN h, const string& name, LEN x = 0, LEN y = 0,
        bool rot = false)
    : _id(id), _w(w), _h(h), _x(x), _y(y), _name(name), _rot(rot) {};
  ID _id;
  LEN _w, _h, _x, _y;
  string _name;
  bool _rot;
};
template<typename ID, typename LEN> struct FLOOR_PLAN<ID, LEN>::NET {
  NET(ID id) : _id(id), _mxx(0), _mxy(0),
               _mnx(1 << (sizeof(LEN) * 8 - 3)), _mny(1 << (sizeof(LEN) * 8 - 3)) {};
  void update(LEN x, LEN y) {
    _mxx = max(_mxx, x);
    _mxy = max(_mxy, y);
    _mnx = min(_mnx, x);
    _mny = min(_mny, y);
  }
  void do_sort() { sort(_blcks.begin(), _blcks.end()); }
  ID _id;
  LEN _mxx, _mxy, _mnx, _mny;
  vector<ID> _blcks;
};
constexpr uint msk_l = ((1 << 10) - 1) << 1;
constexpr uint msk_r = ((1 << 10) - 1) << 11;
constexpr uint msk_p = ((1 << 10) - 1) << 21;
constexpr uint rmsk_l = ~msk_l;
constexpr uint rmsk_r = ~msk_r;
constexpr uint rmsk_p = ~msk_p;
template<typename ID, typename LEN> struct FLOOR_PLAN<ID, LEN>::NODE {
  NODE() : x(0) {};
  ID _l() const { return (x >> 01) & ((1 << 10) - 1); }
  ID _r() const { return (x >> 11) & ((1 << 10) - 1); }
  ID _p() const { return (x >> 21) & ((1 << 10) - 1); }
  bool _rot() const { return x & 1; }
  void s_l(const uint& i) { x = ((x & rmsk_l) | ((i << 01) & msk_l)); }
  void s_r(const uint& i) { x = ((x & rmsk_r) | ((i << 11) & msk_r)); }
  void s_p(const uint& i) { x = ((x & rmsk_p) | ((i << 21) & msk_p)); }
  void s_rot() { x ^= 1; }
  int x;
};

#endif
