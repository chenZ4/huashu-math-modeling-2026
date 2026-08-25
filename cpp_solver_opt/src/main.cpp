#include <climits>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <string>

using namespace std;

#include "sa.hpp"

int main(int argc, char** argv) {
  ios_base::sync_with_stdio(false);
  if (argc < 7) {
    cerr << "usage: main <mode:q1|q2> <alpha> <blocks> <nets> <pl> <rpt> "
            "[dead_ratio] [--log <file>] [--feas-only] [--seed <n>]\n";
    return 1;
  }
  Mode mode = (string(argv[1]) == "q1") ? Mode::Q1 : Mode::Q2;
  float alpha = stof(argv[2]);
  float dead_ratio = 0.15f;
  bool feas_only = false;
  float t2_div = 0.f;
  unsigned seed = (unsigned)time(NULL);
  ostream* log = nullptr;
  ofstream logfile;
  vector<string> init_order;
  bool has_init_order = false;
  bool descent = false;
  for (int i = 7; i < argc; ++i) {
    if (string(argv[i]) == "--log" && i + 1 < argc) {
      logfile.open(argv[i + 1]);
      log = &logfile;
      ++i;
    } else if (string(argv[i]) == "--feas-only") {
      feas_only = true;
    } else if (string(argv[i]) == "--descent") {
      descent = true;
    } else if (string(argv[i]) == "--seed" && i + 1 < argc) {
      seed = (unsigned)stoul(argv[i + 1]);
      ++i;
    } else if (string(argv[i]) == "--t2-div" && i + 1 < argc) {
      t2_div = stof(argv[i + 1]);
      ++i;
    } else if (string(argv[i]) == "--init-order" && i + 1 < argc) {
      ifstream ofile(argv[i + 1]);
      if (!ofile) {
        cerr << "cannot open --init-order file: " << argv[i + 1] << '\n';
        return 1;
      }
      string tok;
      while (ofile >> tok) init_order.push_back(tok);
      has_init_order = true;
      ++i;
    } else {
      dead_ratio = stof(argv[i]);
    }
  }
  srand(seed);
  ifstream fblcks(argv[3]);
  ifstream fnets(argv[4]);
  ifstream fpl(argv[5]);
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  const vector<string>* init_ptr = has_init_order ? &init_order : nullptr;
  if (Nblcks + Ntrmns + 2 < SHRT_MAX)
    solve<FLOOR_PLAN, short, int>(fnets, fblcks, fpl, argv[6], Nnets, Nblcks,
                                  Ntrmns, alpha, dead_ratio, mode, log,
                                  feas_only, t2_div, init_ptr, descent);
  else
    solve<FLOOR_PLAN, int, int>(fnets, fblcks, fpl, argv[6], Nnets, Nblcks,
                                Ntrmns, alpha, dead_ratio, mode, log,
                                feas_only, t2_div, init_ptr, descent);
  return 0;
}
