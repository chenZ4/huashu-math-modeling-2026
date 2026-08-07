#include <climits>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

using namespace std;

#include "floor_plan.hpp"

template<typename ID, typename LEN>
class SA {
public:
  SA(FLOOR_PLAN<ID, LEN>& fp, ID Nblcks, int W, int H, float R, float P,
     float alpha_base, float beta, float true_alpha)
    : _fp(fp), _Nblcks(Nblcks), _N(Nblcks), _R(R), _best_sol(fp.get_tree()),
      _alpha_base(alpha_base), _alpha(alpha_base), _N_feas(0),
      _beta(beta), _W(W), _H(H), _true_alpha(true_alpha) {
    _fp.init();
    vector<int3> costs(_N + 1);
    costs[0] = _fp.cost();
    _avg_r = float(get<2>(costs[0])) / get<1>(costs[0]);
    _avg_hpwl = get<0>(costs[0]) / 2.;
    _avg_area = get<1>(costs[0]) * get<2>(costs[0]);
    _avg_true = _true_alpha * _avg_area + (1 - _true_alpha) * _avg_hpwl;
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
    }
    _fp.restore(_best_sol);
    _avg_hpwl = _avg_hpwl * 1.1 / (_N + 1);
    _avg_area = _avg_area * 1.1 / (_N + 1);
    _avg_r = _avg_r * 1.1 / (_N + 1);
    _avg_true = _avg_true * 1.1 / (_N + 1);
    float avg_cost = 0;
    for (ID i = 1; i <= _N; ++i)
      avg_cost += abs(norm_cost(costs[i]) - norm_cost(costs[i - 1]));
    _init_T = -avg_cost / _N / logf(P);
  };
  void run(const int k, int rnd, const float c) {
    _recs.resize(_N, false);
    _N_feas = 0;
    _beta = 0.0;
    int reset_th = 2 * _Nblcks, stop_th = 4 * _Nblcks;
    _fp.init();
    int iter = 1, tot_feas = 0;
    float _T = _init_T, prv_cost = norm_cost(_fp.cost(true, true));
    _best_cost = prv_cost;
    int rej_num = 0, cnt = 1;
    typename FLOOR_PLAN<ID, LEN>::TREE last_sol = _fp.get_tree();
    while (_T > temp_th || float(rej_num) <= rej_ratio * cnt || !tot_feas) {
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
        } else _recs.push_back(false);
        _alpha = _alpha_base + (1 - _alpha_base) * _N_feas / _N;

        if (delta_cost <= 0 || randf() < expf(-delta_cost / _T) || tot_feas == 1) {
          prv_cost = cost;
          last_sol = _fp.get_tree();
          if (feas(costs)) {
            if (cost < _best_cost || tot_feas == 1) {
              _best_sol = _fp.get_tree();
              _best_cost = cost;
            }
          }
        } else {
          _fp.restore(last_sol);
          ++rej_num;
        }
      }
      ++iter;
      if (iter <= k) _T = _init_T * avg_delta_cost / cnt / iter / c;
      else _T = _init_T * avg_delta_cost / cnt / iter;
      _fp.init();
      if (!tot_feas) {
        if (iter > reset_th) {
          _T = _init_T;
          iter = 1;
          reset_th += 1;
          stop_th += 1;
          rnd += 1;
        }
      } else if (iter > stop_th) break;
    }
    _fp.restore(_best_sol);
  }
  pair<float, typename FLOOR_PLAN<ID, LEN>::TREE>
  run2(const int k, int rnd, const float c) {
    float _init_T2 = _init_T / 50;
    int reset_th = 2 * _Nblcks, stop_th = 9 * _Nblcks, reset_cnt = 0;
    int iter = 1, tot_feas = 0, rej_num = 0, cnt = 1;
    _fp.init();
    float _T = _init_T2, prv_cost = true_cost(_fp.cost(), _avg_true);
    _best_cost = prv_cost;
    typename FLOOR_PLAN<ID, LEN>::TREE last_sol = _best_sol;
    while (_T > temp_th || float(rej_num) <= rej_ratio * cnt || !tot_feas) {
      float avg_delta_cost = 0;
      rej_num = 0, cnt = 1;
      for (; cnt <= rnd; ++cnt) {
        _fp.perturb();
        _fp.init();
        int3 costs = _fp.cost();
        float cost = true_cost(costs, _avg_true);
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
    int3 costs = _fp.cost();
    _best_cost = true_cost(costs);
    return {_best_cost, _best_sol};
  }
private:
  float norm_cost(const int3& cost) const {
    const float r = float(get<2>(cost)) / get<1>(cost);
    return (_alpha * get<1>(cost) * get<2>(cost) / _avg_area
         + _beta * get<0>(cost) / _avg_hpwl / 2.
         + (1 - _alpha - _beta) * (r - _R) * (r - _R) / _avg_r);
  }
  float true_cost(const int3& cost, const float den = 1) const {
    return (_true_alpha * get<1>(cost) * get<2>(cost)
            + (1 - _true_alpha) * get<0>(cost) / 2.) / den;
  }
  bool feas(const int3& cost) {
    return (get<1>(cost) <= _W && get<2>(cost) <= _H);
  }
  float randf() const { return float(rand()) / RAND_MAX; }
  FLOOR_PLAN<ID, LEN>& _fp;
  typename FLOOR_PLAN<ID, LEN>::TREE _best_sol;
  float _best_cost;
  const ID _Nblcks, _N;
  const int _W, _H;
  const float _alpha_base, _R, _true_alpha;
  float _alpha, _beta, _init_T, _avg_hpwl, _avg_area, _avg_r, _avg_true;
  ID _N_feas;
  list<bool> _recs;
  static constexpr float temp_th = 0.001f, rej_ratio = 0.99f;
};

template<typename ID, typename LEN>
void solve(ifstream& fnets, ifstream& fblcks, ifstream& fpl,
           const string& rpt, int Nnets, int Nblcks, int Ntrmns,
           float alpha, float dead_ratio) {
  FLOOR_PLAN<ID, LEN> fp(fnets, fblcks, fpl, rpt, Nnets, Nblcks, Ntrmns,
                         alpha, dead_ratio);
  float P = 0.9f, alpha_base = 0.5f, beta = 0.1f;
  const float R = fp.R();
  int k = max(2, Nblcks / 11), rnd = 2 * Nblcks + 20;
  float c = max(100 - int(Nblcks), 10);
  SA<ID, LEN> sa(fp, Nblcks, fp.W(), fp.H(), R, P, alpha_base, beta, alpha);
  typename FLOOR_PLAN<ID, LEN>::TREE trees[2];
  float costs[2];
  for (int i = 0; i < 2; ++i) {
    sa.run(k, rnd, c);
    tie(costs[i], trees[i]) = sa.run2(k, rnd, c);
  }
  fp.restore(costs[0] < costs[1] ? trees[0] : trees[1]);
  fp.init();
  ofstream outs(rpt);
  fp.output(outs);
}

int main(int argc, char** argv) {
  ios_base::sync_with_stdio(false);
  if (argc < 6) {
    cerr << "usage: main <alpha> <blocks> <nets> <pl> <rpt> [dead_ratio]\n";
    return 1;
  }
  srand((unsigned)time(NULL));
  float alpha = stof(argv[1]);
  float dead_ratio = (argc > 6) ? stof(argv[6]) : 0.15f;
  ifstream fblcks(argv[2]);
  ifstream fnets(argv[3]);
  ifstream fpl(argv[4]);
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  if (Nblcks + Ntrmns + 2 < SHRT_MAX)
    solve<short, int>(fnets, fblcks, fpl, argv[5], Nnets, Nblcks, Ntrmns,
                      alpha, dead_ratio);
  else
    solve<int, int>(fnets, fblcks, fpl, argv[5], Nnets, Nblcks, Ntrmns,
                    alpha, dead_ratio);
  return 0;
}
