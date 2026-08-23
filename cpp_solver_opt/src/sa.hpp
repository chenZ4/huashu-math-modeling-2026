#ifndef SA_HPP
#define SA_HPP

#include <cmath>
#include <cstdlib>
#include <list>
#include <tuple>
#include <vector>

#include "floor_plan.hpp"

enum class Mode { Q1, Q2 };

template<typename ID, typename LEN>
class SA {
public:
  SA(FLOOR_PLAN<ID, LEN>& fp, ID Nblcks, int W, int H, float R, float P,
     float alpha_base, float beta, float true_alpha, Mode mode = Mode::Q2,
     ostream* log = nullptr, float t2_div = 0.f)
    : _fp(fp), _best_sol(fp.get_tree()), _Nblcks(Nblcks), _N(Nblcks),
      _W(W), _H(H), _alpha_base(alpha_base), _R(R), _true_alpha(true_alpha),
      _alpha(alpha_base), _beta(beta), _N_feas(0), _mode(mode), _log(log),
      _t2_div(t2_div) {
    _fp.init();
    vector<int3> costs(_N + 1);
    costs[0] = _fp.cost();
    _avg_r = float(get<2>(costs[0])) / get<1>(costs[0]);
    _avg_hpwl = get<0>(costs[0]) / 2.;
    _avg_area = get<1>(costs[0]) * get<2>(costs[0]);
    _avg_true = _true_alpha * _avg_area + (1 - _true_alpha) * _avg_hpwl;
    const float pen0 = q1_pen(get<1>(costs[0]), get<2>(costs[0]));
    _avg_pen = pen0;
    for (ID i = 1; i <= _N; ++i) {
      _fp.perturb();
      _fp.init();
      costs[i] = _fp.cost();
      const float area = get<1>(costs[i]) * get<2>(costs[i]);
      const float hpwl = get<0>(costs[i]) / 2.;
      _avg_hpwl += hpwl;
      _avg_area += area;
      _avg_true += _true_alpha * area + (1 - _true_alpha) * hpwl;
      const float r = float(get<2>(costs[i])) / get<1>(costs[i]);
      _avg_r += (r - R) * (r - R);
      _avg_pen += q1_pen(get<1>(costs[i]), get<2>(costs[i]));
    }
    _fp.restore(_best_sol);
    _avg_hpwl = _avg_hpwl * 1.1 / (_N + 1);
    _avg_area = _avg_area * 1.1 / (_N + 1);
    _avg_r = _avg_r * 1.1 / (_N + 1);
    _avg_true = _avg_true * 1.1 / (_N + 1);
    _avg_pen = _avg_pen * 1.1 / (_N + 1);
    if (_avg_pen <= 0) _avg_pen = 1e-3f;
    float avg_cost = 0;
    for (ID i = 1; i <= _N; ++i) {
      if (_mode == Mode::Q1) avg_cost += abs(q1_cost(costs[i]) - q1_cost(costs[i - 1]));
      else avg_cost += abs(norm_cost(costs[i]) - norm_cost(costs[i - 1]));
    }
    _init_T = -avg_cost / _N / logf(P);
  };
  void run(const int k, int rnd, const float c, bool early_feas = false) {
    _recs.resize(_N, false);
    _N_feas = 0;
    _beta = 0.0;
    int reset_th = 2 * _Nblcks, stop_th = 4 * _Nblcks, reset_cnt = 0;
    _fp.init();
    int iter = 1, tot_feas = 0;
    bool done = false;
    float _T = _init_T, prv_cost = norm_cost(_fp.cost(true, true));
    _best_cost = prv_cost;
    dbg_push(_best_cost);
    int rej_num = 0, cnt = 1;
    typename FLOOR_PLAN<ID, LEN>::TREE last_sol = _fp.get_tree();
    while (!done && (_T > temp_th || float(rej_num) <= rej_ratio * cnt || !tot_feas)) {
      if (tot_feas) _beta += 0.01;
      float avg_delta_cost = 0;
      rej_num = 0, cnt = 1;
      for (; cnt <= rnd; ++cnt) {
        _fp.perturb();
        _fp.init();
        int3 costs = _fp.cost(true, true);
        float cost = norm_cost(costs);
        float delta_cost = (cost - prv_cost);
        avg_delta_cost += abs(delta_cost);

        if (*_recs.begin()) --_N_feas;
        _recs.pop_front();
        if (feas(costs)) {
          ++_N_feas;
          _recs.push_back(true);
          ++tot_feas;
          if (early_feas) { done = true; break; }
        } else _recs.push_back(false);
        _alpha = _alpha_base + (1 - _alpha_base) * float(_N_feas) / float(_N);

        if (delta_cost <= 0 || randf() < expf(-delta_cost / _T) || tot_feas == 1) {
          prv_cost = cost;
          last_sol = _fp.get_tree();
          if (feas(costs)) {
            if (cost < _best_cost || tot_feas == 1) {
              _best_sol = _fp.get_tree();
              _best_cost = cost;
              dbg_push(_best_cost);
            }
          }
        } else {
          _fp.restore(last_sol);
          ++rej_num;
        }
      }
      if (done) break;
      ++iter;
      if (iter <= k) _T = _init_T * avg_delta_cost / cnt / iter / c;
      else _T = _init_T * avg_delta_cost / cnt / iter;
      _fp.init();
      dbg_log("run", iter, _T, _alpha, tot_feas ? 1 : 0);
      if (_log) {
        _snap_iters.push_back(iter);
        _snap_trees.push_back(_best_sol);
      }
      if (reset_cnt > _Nblcks / 16 + 1) break;
      if (!tot_feas) {
        if (iter > reset_th) {
          _T = _init_T;
          iter = 1;
          reset_th += 1;
          stop_th += 1;
          rnd += 1;
          ++reset_cnt;
        }
      } else if (iter > stop_th) break;
    }
    _fp.restore(_best_sol);
    _last_feasible = (tot_feas > 0);
    dbg_snapshots();
  }
  pair<float, typename FLOOR_PLAN<ID, LEN>::TREE>
  run2(const int k, int rnd, const float c) {
    float _init_T2 = _init_T / ((_t2_div > 0.f) ? _t2_div
                                 : ((_mode == Mode::Q1) ? 20.f : 50.f));
    int reset_th = 2 * _Nblcks, stop_th = 9 * _Nblcks, reset_cnt = 0;
    int iter = 1, tot_feas = 0, rej_num = 0, cnt = 1;
    _fp.init();
    tot_feas = feas(_fp.cost()) ? 1 : 0;
    float _T = _init_T2;
    float prv_cost = (_mode == Mode::Q1) ? q1_cost(_fp.cost()) : true_cost(_fp.cost(), _avg_true);
    _best_cost = prv_cost;
#ifdef TREE_DEBUG
    _dbg_hist.push_back(-1.0f);
#endif
    dbg_push(_best_cost);
    typename FLOOR_PLAN<ID, LEN>::TREE last_sol = _best_sol;
    while (_T > temp_th || float(rej_num) <= rej_ratio * cnt || !tot_feas) {
      float avg_delta_cost = 0;
      rej_num = 0, cnt = 1;
      for (; cnt <= rnd; ++cnt) {
        _fp.perturb();
        _fp.init();
        int3 costs = _fp.cost();
        float cost = (_mode == Mode::Q1) ? q1_cost(costs) : true_cost(costs, _avg_true);
        float delta_cost = (cost - prv_cost);
        avg_delta_cost += abs(delta_cost);

        if (delta_cost <= 0 || randf() < expf(-delta_cost / _T)) {
          prv_cost = cost;
          last_sol = _fp.get_tree();
          if (feas(costs)) {
            ++tot_feas;
            if (cost < _best_cost) {
              _best_sol = _fp.get_tree();
              _best_cost = cost;
              dbg_push(_best_cost);
            }
          }
        } else {
          _fp.restore(last_sol);
          ++rej_num;
        }
      }
      ++iter;
      if (iter <= k) _T = _init_T2 * avg_delta_cost / cnt / iter / c;
      else _T = _init_T2 * avg_delta_cost / cnt / iter;
      _fp.init();
      dbg_log("run2", iter, _T, _alpha, tot_feas ? 1 : 0);
      if (_log) {
        _snap_iters.push_back(iter);
        _snap_trees.push_back(_best_sol);
      }
      if (reset_cnt > _Nblcks / 7 + 1) break;
      if (!tot_feas) {
        if (iter > reset_th) {
          _T = _init_T2;
          iter = 1;
          ++reset_th, ++stop_th, ++rnd, ++reset_cnt;
        }
      } else if (iter > stop_th) break;
    }
    _fp.restore(_best_sol);
    _fp.init();
    dbg_snapshots();
    int3 costs = _fp.cost();
    _best_cost = (_mode == Mode::Q1) ? q1_cost(costs) : true_cost(costs);
    if (_mode == Mode::Q1) dbg_push(q1_cost(costs));
    else dbg_push(true_cost(costs, _avg_true));
    return {_best_cost, _best_sol};
  }
#ifdef TREE_DEBUG
  const vector<float>& dbg_hist() const { return _dbg_hist; }
  float dbg_best_cost() const { return _best_cost; }
  float dbg_q1_cost_of(const int3& c) const { return q1_cost(c); }
  float dbg_q1_avg_area() const { return _avg_area; }
  float dbg_q1_avg_pen() const { return _avg_pen; }
#endif
  bool last_feasible() const { return _last_feasible; }
private:
  void dbg_snapshots() {
    if (!_log) return;
    const size_t n = _snap_trees.size();
    if (n == 0) return;

    for (int k = 1; k <= 9; ++k) {
      const size_t idx = (k * n) / 10;
      _fp.restore(_snap_trees[idx]);
      _fp.init();
      LEN maxx = 0, maxy = 0;
      for (ID i = 1; i <= _Nblcks; ++i) {
        maxx = max(maxx, LEN(_fp.blk(i)._x + _fp.blk(i)._w));
        maxy = max(maxy, LEN(_fp.blk(i)._y + _fp.blk(i)._h));
      }
      *_log << "snap " << k << " " << _snap_iters[idx] << " " << int(maxx)
            << " " << int(maxy) << "\n";
      for (ID i = 1; i <= _Nblcks; ++i) {
        const auto& b = _fp.blk(i);
        *_log << b._name << " " << int(b._x) << " " << int(b._y) << " "
              << int(b._x + b._w) << " " << int(b._y + b._h) << "\n";
      }
    }
    _fp.restore(_best_sol);
    _fp.init();  // 修复: snapshots 后显式重放置, 与无 log 路径状态逐位对齐
  }
  void dbg_log(const char* phase, int iter, float T, float alpha, int feas_flag) {
    if (_log) {
      *_log << phase << " " << iter << " " << T << " " << _best_cost << " "
            << alpha << " " << feas_flag << "\n";
    }
  }
  float q1_pen(int W, int H) const {
    const float r = float(max(W, H)) / float(min(W, H));
    return r + 1.0f / r - 2.0f;
  }
  float q1_cost(const int3& cost) const {
    const float area = float(get<1>(cost)) * float(get<2>(cost));
    const float pen = q1_pen(get<1>(cost), get<2>(cost));
    return _true_alpha * area / _avg_area + (1 - _true_alpha) * pen / _avg_pen;
  }
  void dbg_push(float v) {
#ifdef TREE_DEBUG
    _dbg_hist.push_back(v);
#else
    (void)v;
#endif
  }
  float norm_cost(const int3& cost) const {
    const float r = float(get<2>(cost)) / get<1>(cost);
    const float area_term = _alpha * get<1>(cost) * get<2>(cost) / _avg_area;
    const float hpwl_term = (_avg_hpwl > 0) ? _beta * get<0>(cost) / _avg_hpwl / 2. : 0.f;
    const float r_term = (_avg_r > 0)
        ? (1 - _alpha - _beta) * (r - _R) * (r - _R) / _avg_r : 0.f;
    return area_term + hpwl_term + r_term;
  }
  float true_cost(const int3& cost, const float den = 1) const {
    return (_true_alpha * get<1>(cost) * get<2>(cost)
            + (1 - _true_alpha) * get<0>(cost) / 2.) / den;
  }
  bool feas(const int3& cost) {
    if (_mode == Mode::Q1) return true;
    return (get<1>(cost) <= _W && get<2>(cost) <= _H);
  }
  float randf() const { return float(rand()) / float(RAND_MAX); }
  FLOOR_PLAN<ID, LEN>& _fp;
  typename FLOOR_PLAN<ID, LEN>::TREE _best_sol;
  float _best_cost;
  const ID _Nblcks, _N;
  const int _W, _H;
  const float _alpha_base, _R, _true_alpha;
  float _alpha, _beta, _init_T, _avg_hpwl, _avg_area, _avg_r, _avg_true, _avg_pen;
  ID _N_feas;
  list<bool> _recs;
  Mode _mode;
  ostream* _log;
  float _t2_div;
  bool _last_feasible = false;
  vector<int> _snap_iters;
  vector<typename FLOOR_PLAN<ID, LEN>::TREE> _snap_trees;
#ifdef TREE_DEBUG
  vector<float> _dbg_hist;
#endif
  static constexpr float temp_th = 0.001f, rej_ratio = 0.99f;
};

template<typename ID, typename LEN>
void solve(ifstream& fnets, ifstream& fblcks, ifstream& fpl,
           const string& rpt, int Nnets, int Nblcks, int Ntrmns,
           float alpha, float dead_ratio, Mode mode = Mode::Q2,
           ostream* log = nullptr, bool feas_only = false,
           float t2_div = 0.f,
           const vector<string>* init_order = nullptr) {
  FLOOR_PLAN<ID, LEN> fp(fnets, fblcks, fpl, rpt, Nnets, Nblcks, Ntrmns,
                         alpha, dead_ratio, mode == Mode::Q1);
  if (init_order && !fp.set_init_order(*init_order)) {
    cerr << "solve: invalid --init-order (count mismatch / unknown / duplicate block)\n";
    exit(1);
  }
  float P = 0.9f, alpha_base = 0.5f, beta = 0.1f;
  const float R = fp.R();
  int k = max(2, Nblcks / 11), rnd = 2 * Nblcks + 20;
  float c = max(100 - int(Nblcks), 10);
  SA<ID, LEN> sa(fp, Nblcks, fp.W(), fp.H(), R, P, alpha_base, beta, alpha,
                 mode, log, t2_div);
  if (feas_only) {
    sa.run(k, rnd, c, true);
    fp.init();
    int3 costs = fp.cost();
    ofstream outs(rpt);
    outs << (sa.last_feasible() ? 1 : 0) << '\n';
    outs << get<1>(costs) << " " << get<2>(costs) << '\n';
    outs << get<0>(costs) / 2. << '\n';
    return;
  }
  typename FLOOR_PLAN<ID, LEN>::TREE trees[2];
  float costs[2];
  if (mode == Mode::Q1) {
    for (int i = 0; i < 2; ++i) {
      tie(costs[i], trees[i]) = sa.run2(k, rnd, c);
    }
  } else {
    for (int i = 0; i < 2; ++i) {
      sa.run(k, rnd, c);
      tie(costs[i], trees[i]) = sa.run2(k, rnd, c);
    }
  }
  fp.restore(costs[0] < costs[1] ? trees[0] : trees[1]);
  fp.init();
  ofstream outs(rpt);
  fp.output(outs);
}

#endif
