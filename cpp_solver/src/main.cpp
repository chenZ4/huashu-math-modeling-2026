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
            "[dead_ratio] [--log <file>]\n";
    return 1;
  }
  Mode mode = (string(argv[1]) == "q1") ? Mode::Q1 : Mode::Q2;
  float alpha = stof(argv[2]);
  float dead_ratio = 0.15f;
  ostream* log = nullptr;
  ofstream logfile;
  for (int i = 7; i < argc; ++i) {
    if (string(argv[i]) == "--log" && i + 1 < argc) {
      logfile.open(argv[i + 1]);
      log = &logfile;
      ++i;
    } else {
      dead_ratio = stof(argv[i]);
    }
  }
  srand((unsigned)time(NULL));
  ifstream fblcks(argv[3]);
  ifstream fnets(argv[4]);
  ifstream fpl(argv[5]);
  int Nnets = read_labeled_int(fnets);
  int Nblcks = read_labeled_int(fblcks);
  int Ntrmns = read_labeled_int(fblcks);
  fnets.seekg(0);
  fblcks.seekg(0);
  if (Nblcks + Ntrmns + 2 < SHRT_MAX)
    solve<short, int>(fnets, fblcks, fpl, argv[6], Nnets, Nblcks, Ntrmns,
                      alpha, dead_ratio, mode, log);
  else
    solve<int, int>(fnets, fblcks, fpl, argv[6], Nnets, Nblcks, Ntrmns,
                    alpha, dead_ratio, mode, log);
  return 0;
}
